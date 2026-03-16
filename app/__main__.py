from __future__ import annotations

import argparse
import heapq
import math
import random
import socket
import struct
import time
from dataclasses import dataclass
from typing import List, Optional, Tuple


PAYLOAD_FORMAT = "!Iq3f4ffq"
PAYLOAD_SIZE = struct.calcsize(PAYLOAD_FORMAT)


@dataclass(slots=True)
class HapticPacket:
	"""Fixed 52-byte payload model for HapticNet."""

	sequence: int
	timestamp_ns: int
	pos_x: float
	pos_y: float
	pos_z: float
	rot_w: float
	rot_x: float
	rot_y: float
	rot_z: float
	force: float
	texture_id: int

	def to_bytes(self) -> bytes:
		return struct.pack(
			PAYLOAD_FORMAT,
			self.sequence,
			self.timestamp_ns,
			self.pos_x,
			self.pos_y,
			self.pos_z,
			self.rot_w,
			self.rot_x,
			self.rot_y,
			self.rot_z,
			self.force,
			self.texture_id,
		)

	@classmethod
	def from_bytes(cls, payload: bytes) -> "HapticPacket":
		if len(payload) != PAYLOAD_SIZE:
			raise ValueError(f"Invalid payload size: expected {PAYLOAD_SIZE}, got {len(payload)}")

		values = struct.unpack(PAYLOAD_FORMAT, payload)
		return cls(*values)


class JitterBuffer:
	"""Small reordering buffer for out-of-order UDP packets."""

	def __init__(self, capacity: int = 3):
		self.capacity = capacity
		self._heap: List[Tuple[int, HapticPacket]] = []

	def push(self, packet: HapticPacket, expected_seq: int) -> bool:
		if packet.sequence < expected_seq:
			return False

		heapq.heappush(self._heap, (packet.sequence, packet))
		while len(self._heap) > self.capacity:
			heapq.heappop(self._heap)
		return True

	def pop_expected(self, expected_seq: int) -> Optional[HapticPacket]:
		if not self._heap:
			return None

		seq, packet = self._heap[0]
		if seq == expected_seq:
			heapq.heappop(self._heap)
			return packet
		return None


class DeadReckoner:
	"""Linear extrapolation for packet loss compensation."""

	def __init__(self):
		self._last_packet: Optional[HapticPacket] = None
		self._velocity = (0.0, 0.0, 0.0)

	def update(self, packet: HapticPacket) -> None:
		if self._last_packet is not None:
			dt = (packet.timestamp_ns - self._last_packet.timestamp_ns) / 1_000_000_000.0
			if dt > 0:
				self._velocity = (
					(packet.pos_x - self._last_packet.pos_x) / dt,
					(packet.pos_y - self._last_packet.pos_y) / dt,
					(packet.pos_z - self._last_packet.pos_z) / dt,
				)

		self._last_packet = packet

	def estimate(self, sequence: int, timestamp_ns: int) -> Optional[HapticPacket]:
		if self._last_packet is None:
			return None

		dt = (timestamp_ns - self._last_packet.timestamp_ns) / 1_000_000_000.0
		next_x = self._last_packet.pos_x + self._velocity[0] * dt
		next_y = self._last_packet.pos_y + self._velocity[1] * dt
		next_z = self._last_packet.pos_z + self._velocity[2] * dt

		return HapticPacket(
			sequence=sequence,
			timestamp_ns=timestamp_ns,
			pos_x=next_x,
			pos_y=next_y,
			pos_z=next_z,
			rot_w=self._last_packet.rot_w,
			rot_x=self._last_packet.rot_x,
			rot_y=self._last_packet.rot_y,
			rot_z=self._last_packet.rot_z,
			force=self._last_packet.force,
			texture_id=self._last_packet.texture_id,
		)


class HapticSimulator:
	"""Generates deterministic high-frequency motion data for testing."""

	def __init__(self):
		self._sequence = 0
		self._start = time.perf_counter()

	def next_packet(self) -> HapticPacket:
		t = time.perf_counter() - self._start
		self._sequence += 1

		return HapticPacket(
			sequence=self._sequence,
			timestamp_ns=time.time_ns(),
			pos_x=math.sin(t),
			pos_y=math.cos(t),
			pos_z=math.sin(t * 0.5),
			rot_w=1.0,
			rot_x=0.0,
			rot_y=0.0,
			rot_z=0.0,
			force=0.25 + random.random() * 0.5,
			texture_id=1,
		)


def run_simulation(sample_count: int) -> None:
	simulator = HapticSimulator()
	for _ in range(sample_count):
		packet = simulator.next_packet()
		payload = packet.to_bytes()
		unpacked = HapticPacket.from_bytes(payload)
		print(
			f"seq={unpacked.sequence:04d} "
			f"pos=({unpacked.pos_x:+.3f},{unpacked.pos_y:+.3f},{unpacked.pos_z:+.3f}) "
			f"force={unpacked.force:.2f} bytes={len(payload)}"
		)
		time.sleep(0.01)


def run_sender(host: str, port: int, rate_hz: int) -> None:
	simulator = HapticSimulator()
	interval = 1.0 / rate_hz

	with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
		print(f"Sender started -> {host}:{port} at {rate_hz} Hz (payload={PAYLOAD_SIZE} bytes)")
		while True:
			packet = simulator.next_packet()
			sock.sendto(packet.to_bytes(), (host, port))
			time.sleep(interval)


def run_receiver(bind_host: str, port: int, buffer_size: int) -> None:
	jitter_buffer = JitterBuffer(capacity=buffer_size)
	reckoner = DeadReckoner()
	expected_seq = 1

	with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
		sock.bind((bind_host, port))
		sock.settimeout(0.02)
		print(f"Receiver started on {bind_host}:{port} (jitter buffer={buffer_size})")

		while True:
			try:
				payload, _ = sock.recvfrom(1024)
				packet = HapticPacket.from_bytes(payload)
				jitter_buffer.push(packet, expected_seq=expected_seq)
			except socket.timeout:
				pass
			except ValueError:
				continue

			in_order = jitter_buffer.pop_expected(expected_seq)
			if in_order is not None:
				reckoner.update(in_order)
				print(f"rx seq={in_order.sequence:04d} pos=({in_order.pos_x:+.3f},{in_order.pos_y:+.3f},{in_order.pos_z:+.3f})")
				expected_seq += 1
				continue

			estimated = reckoner.estimate(sequence=expected_seq, timestamp_ns=time.time_ns())
			if estimated is not None:
				print(
					f"dr seq={estimated.sequence:04d} "
					f"pos=({estimated.pos_x:+.3f},{estimated.pos_y:+.3f},{estimated.pos_z:+.3f})"
				)
				expected_seq += 1


def build_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(description="HapticNet project skeleton")
	subparsers = parser.add_subparsers(dest="mode", required=True)

	simulate_parser = subparsers.add_parser("simulate", help="Run local payload simulation")
	simulate_parser.add_argument("--samples", type=int, default=10)

	send_parser = subparsers.add_parser("send", help="Run UDP packet sender")
	send_parser.add_argument("--host", default="127.0.0.1")
	send_parser.add_argument("--port", type=int, default=9000)
	send_parser.add_argument("--rate", type=int, default=100)

	receive_parser = subparsers.add_parser("receive", help="Run UDP receiver with jitter buffer")
	receive_parser.add_argument("--bind", default="0.0.0.0")
	receive_parser.add_argument("--port", type=int, default=9000)
	receive_parser.add_argument("--buffer", type=int, default=3)

	return parser


def main() -> None:
	parser = build_parser()
	args = parser.parse_args()

	if args.mode == "simulate":
		run_simulation(sample_count=args.samples)
	elif args.mode == "send":
		run_sender(host=args.host, port=args.port, rate_hz=args.rate)
	elif args.mode == "receive":
		run_receiver(bind_host=args.bind, port=args.port, buffer_size=args.buffer)


if __name__ == "__main__":
	main()

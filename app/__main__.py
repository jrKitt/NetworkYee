from __future__ import annotations

import argparse
import heapq
import math
import random
import socket
import struct
import threading
import time
from dataclasses import dataclass
from typing import List, Optional, Tuple


PAYLOAD_FORMAT = "!Iq3f4ffq"
PAYLOAD_SIZE = struct.calcsize(PAYLOAD_FORMAT)
DISCOVERY_REQUEST = b"NETWORKYEE_HAPTIC_DISCOVER_V1"
DISCOVERY_RESPONSE_PREFIX = "NETWORKYEE_HAPTIC_HERE "


def get_local_ip() -> str:
	"""Return the primary LAN/hotspot IP (not loopback)."""
	with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
		try:
			s.connect(("8.8.8.8", 80))
			return s.getsockname()[0]
		except OSError:
			return "127.0.0.1"


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


@dataclass(slots=True)
class ReceiverStats:
	"""Tracks QoS-like network quality metrics for the receiver."""

	rx_packets: int = 0
	estimated_packets: int = 0
	out_of_order_packets: int = 0
	dropped_packets: int = 0
	latency_sum_ms: float = 0.0
	latency_samples: int = 0
	latency_min_ms: float = float("inf")
	latency_max_ms: float = 0.0
	last_print_at: float = 0.0

	def add_latency(self, latency_ms: float) -> None:
		self.latency_sum_ms += latency_ms
		self.latency_samples += 1
		self.latency_min_ms = min(self.latency_min_ms, latency_ms)
		self.latency_max_ms = max(self.latency_max_ms, latency_ms)

	def report(self, expected_seq: int) -> None:
		now = time.perf_counter()
		if self.last_print_at == 0.0:
			self.last_print_at = now
			return

		elapsed = now - self.last_print_at
		if elapsed < 1.0:
			return

		total_expected = max(1, expected_seq - 1)
		loss_rate = (self.dropped_packets / total_expected) * 100.0
		estimate_rate = (self.estimated_packets / total_expected) * 100.0
		rx_rate = self.rx_packets / elapsed
		if self.latency_samples > 0:
			lat_avg = self.latency_sum_ms / self.latency_samples
			lat_min = self.latency_min_ms
			lat_max = self.latency_max_ms
			latency_text = f"lat(avg/min/max)={lat_avg:.2f}/{lat_min:.2f}/{lat_max:.2f} ms"
		else:
			latency_text = "lat(avg/min/max)=n/a"
		print(
			"stats "
			f"rx={self.rx_packets} est={self.estimated_packets} ooo={self.out_of_order_packets} "
			f"drop={self.dropped_packets} loss={loss_rate:.2f}% dr={estimate_rate:.2f}% "
			f"rx_rate={rx_rate:.1f} pkt/s {latency_text}"
		)
		self.rx_packets = 0
		self.estimated_packets = 0
		self.out_of_order_packets = 0
		self.latency_sum_ms = 0.0
		self.latency_samples = 0
		self.latency_min_ms = float("inf")
		self.latency_max_ms = 0.0
		self.last_print_at = now


def calculate_latency_ms(packet_timestamp_ns: int, now_ns: Optional[int] = None) -> Optional[float]:
	"""Calculate one-way latency from sender timestamp to local receive time."""
	if now_ns is None:
		now_ns = time.time_ns()
	if packet_timestamp_ns <= 0:
		return None
	latency_ms = (now_ns - packet_timestamp_ns) / 1_000_000.0
	if latency_ms < 0:
		return None
	return latency_ms


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
		print(f"Sender started")
		print(f"  Local IP  : {get_local_ip()}")
		print(f"  Target    : {host}:{port}")
		print(f"  Rate      : {rate_hz} Hz | Payload: {PAYLOAD_SIZE} bytes")
		while True:
			packet = simulator.next_packet()
			sock.sendto(packet.to_bytes(), (host, port))
			time.sleep(interval)


def discover_receiver(
	discovery_port: int = 9001,
	timeout: float = 3.0,
	broadcast_ip: str = "255.255.255.255",
) -> str:
	with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
		sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
		sock.settimeout(timeout)
		sock.sendto(DISCOVERY_REQUEST, (broadcast_ip, discovery_port))
		try:
			payload, addr = sock.recvfrom(1024)
		except TimeoutError as exc:
			raise RuntimeError(
				"No haptic discovery response. Ensure server is running and UDP discovery port is open."
			) from exc

	message = payload.decode("utf-8", errors="strict")
	if not message.startswith(DISCOVERY_RESPONSE_PREFIX):
		raise RuntimeError(f"Invalid discovery response: {message!r}")
	try:
		discovered_port = int(message[len(DISCOVERY_RESPONSE_PREFIX) :])
	except ValueError as exc:
		raise RuntimeError(f"Invalid discovered port in response: {message!r}") from exc

	return f"{addr[0]}:{discovered_port}"


def _discovery_server(port: int, discovery_port: int, stop_event: threading.Event) -> None:
	with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
		sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		sock.bind(("0.0.0.0", discovery_port))
		sock.settimeout(0.5)
		print(f"Discovery listener started on 0.0.0.0:{discovery_port} -> haptic port {port}")
		while not stop_event.is_set():
			try:
				payload, addr = sock.recvfrom(1024)
			except socket.timeout:
				continue
			except OSError:
				break

			if payload != DISCOVERY_REQUEST:
				continue

			response = f"{DISCOVERY_RESPONSE_PREFIX}{port}".encode("utf-8")
			sock.sendto(response, addr)


def run_receiver(
	bind_host: str,
	port: int,
	buffer_size: int,
	enable_discovery: bool = True,
	discovery_port: int = 9001,
) -> None:
	jitter_buffer = JitterBuffer(capacity=buffer_size)
	reckoner = DeadReckoner()
	stats = ReceiverStats()
	expected_seq = 1
	stop_event = threading.Event()
	discovery_thread: Optional[threading.Thread] = None
	if enable_discovery:
		discovery_thread = threading.Thread(
			target=_discovery_server,
			args=(port, discovery_port, stop_event),
			daemon=True,
		)
		discovery_thread.start()

	try:
		with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
			sock.bind((bind_host, port))
			sock.settimeout(0.02)
			local_ip = get_local_ip()
			print(f"Receiver started")
			print(f"  Bind      : {bind_host}:{port}")
			print(f"  Hotspot IP: {local_ip}  <-- ใช้ค่านี้เป็น --host บนเครื่อง client")
			print(f"  Jitter buf: {buffer_size} packets")
			print(f"  Command   : python -m app client --host {local_ip} --port {port}")
			print("  Latency   : one-way (requires clock sync for cross-machine accuracy)")
			if enable_discovery:
				print(f"  Discovery : UDP 0.0.0.0:{discovery_port}")
				print(f"  Auto cmd  : python -m app client --discover")

			while True:
				try:
					payload, _ = sock.recvfrom(1024)
					packet = HapticPacket.from_bytes(payload)
					if packet.sequence > expected_seq:
						stats.out_of_order_packets += 1
					jitter_buffer.push(packet, expected_seq=expected_seq)
				except socket.timeout:
					pass
				except ValueError:
					continue

				in_order = jitter_buffer.pop_expected(expected_seq)
				if in_order is not None:
					reckoner.update(in_order)
					stats.rx_packets += 1
					latency_ms = calculate_latency_ms(in_order.timestamp_ns)
					if latency_ms is not None:
						stats.add_latency(latency_ms)
						latency_text = f"lat={latency_ms:.2f}ms"
					else:
						latency_text = "lat=n/a"
					print(
						f"rx seq={in_order.sequence:04d} "
						f"pos=({in_order.pos_x:+.3f},{in_order.pos_y:+.3f},{in_order.pos_z:+.3f}) "
						f"{latency_text}"
					)
					expected_seq += 1
					stats.report(expected_seq)
					continue

				estimated = reckoner.estimate(sequence=expected_seq, timestamp_ns=time.time_ns())
				if estimated is not None:
					stats.estimated_packets += 1
					stats.dropped_packets += 1
					print(
						f"dr seq={estimated.sequence:04d} "
						f"pos=({estimated.pos_x:+.3f},{estimated.pos_y:+.3f},{estimated.pos_z:+.3f})"
					)
					expected_seq += 1
					stats.report(expected_seq)
	finally:
		stop_event.set()
		if discovery_thread is not None:
			discovery_thread.join(timeout=1.0)


def run_client(
	host: str,
	port: int,
	rate_hz: int,
	discover: bool = False,
	discovery_port: int = 9001,
	broadcast_ip: str = "255.255.255.255",
	timeout: float = 3.0,
) -> None:
	resolved_host = host
	resolved_port = port
	if discover:
		target = discover_receiver(
			discovery_port=discovery_port,
			timeout=timeout,
			broadcast_ip=broadcast_ip,
		)
		resolved_host, resolved_port_str = target.rsplit(":", 1)
		resolved_port = int(resolved_port_str)
		print(f"Discovered haptic server at {target}")

	run_sender(host=resolved_host, port=resolved_port, rate_hz=rate_hz)


def build_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(description="HapticNet high-frequency transport")
	subparsers = parser.add_subparsers(dest="mode", required=True)

	simulate_parser = subparsers.add_parser("simulate", help="Run local payload simulation")
	simulate_parser.add_argument("--samples", type=int, default=10)

	server_parser = subparsers.add_parser("server", aliases=["receive"], help="Run haptic receiver server")
	server_parser.add_argument("--bind", default="0.0.0.0")
	server_parser.add_argument("--port", type=int, default=9000)
	server_parser.add_argument("--buffer", type=int, default=3)
	server_parser.add_argument("--discovery-port", type=int, default=9001)
	server_parser.add_argument("--disable-discovery", action="store_true")

	client_parser = subparsers.add_parser("client", aliases=["send"], help="Run haptic sender client")
	client_parser.add_argument("--host", default="127.0.0.1")
	client_parser.add_argument("--port", type=int, default=9000)
	client_parser.add_argument("--rate", type=int, default=100)
	client_parser.add_argument("--discover", action="store_true")
	client_parser.add_argument("--discovery-port", type=int, default=9001)
	client_parser.add_argument("--broadcast-ip", default="255.255.255.255")
	client_parser.add_argument("--timeout", type=float, default=3.0)

	discover_parser = subparsers.add_parser("discover", help="Discover haptic server over UDP broadcast")
	discover_parser.add_argument("--discovery-port", type=int, default=9001)
	discover_parser.add_argument("--timeout", type=float, default=3.0)
	discover_parser.add_argument("--broadcast-ip", default="255.255.255.255")

	return parser


def main() -> None:
	parser = build_parser()
	args = parser.parse_args()

	if args.mode == "simulate":
		run_simulation(sample_count=args.samples)
	elif args.mode in {"client", "send"}:
		run_client(
			host=args.host,
			port=args.port,
			rate_hz=args.rate,
			discover=args.discover,
			discovery_port=args.discovery_port,
			broadcast_ip=args.broadcast_ip,
			timeout=args.timeout,
		)
	elif args.mode in {"server", "receive"}:
		run_receiver(
			bind_host=args.bind,
			port=args.port,
			buffer_size=args.buffer,
			enable_discovery=not args.disable_discovery,
			discovery_port=args.discovery_port,
		)
	elif args.mode == "discover":
		target = discover_receiver(
			discovery_port=args.discovery_port,
			timeout=args.timeout,
			broadcast_ip=args.broadcast_ip,
		)
		print(f"Discovered haptic server at {target}")


if __name__ == "__main__":
	main()

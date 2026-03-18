from typing import Dict, Optional
import time

from .models import HapticPacket
from .config import SEQUENCE_OFFSET, TEXTURE_ID_OFFSET

def _read_sequence(payload: bytes) -> int:
    return int.from_bytes(payload[SEQUENCE_OFFSET:SEQUENCE_OFFSET + 4], byteorder='big')


class PacketBuffer:
    def __init__(self, capacity: int = 100):
        self.capacity = capacity
        self._entries: Dict[int, bytes] = {}
        self._min_seq: Optional[int] = None

    def add(self, sequence: int, payload: bytes) -> bool:
        self._entries[sequence] = payload
        if self._min_seq is None or sequence < self._min_seq:
            self._min_seq = sequence
        if len(self._entries) > self.capacity:
            drop_seq = self._min_seq
            if drop_seq is None:
                drop_seq = min(self._entries)
            self._entries.pop(drop_seq, None)
            self._min_seq = min(self._entries) if self._entries else None
        return True

    def pop_expected(self, expected_seq: int) -> Optional[bytes]:
        payload = self._entries.pop(expected_seq, None)
        if payload is None:
            return None
        if self._min_seq == expected_seq:
            self._min_seq = min(self._entries) if self._entries else None
        return payload

    def peek_sequence(self) -> Optional[int]:
        if not self._entries:
            return None
        if self._min_seq is None or self._min_seq not in self._entries:
            self._min_seq = min(self._entries)
        return self._min_seq

class DeadReckoner:
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

def calculate_latency_ms(packet_timestamp_ns: int, now_ns: Optional[int] = None) -> float:
    if now_ns is None:
        now_ns = time.time_ns()
    if packet_timestamp_ns <= 0:
        return 0.0
    latency_ms = (now_ns - packet_timestamp_ns) / 1_000_000.0
    return max(0.0, latency_ms)

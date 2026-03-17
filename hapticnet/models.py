from dataclasses import dataclass
import time

from .config import PAYLOAD_STRUCT, PAYLOAD_SIZE

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
        return PAYLOAD_STRUCT.pack(
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
        values = PAYLOAD_STRUCT.unpack(payload)
        return cls(*values)

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
        if self.rx_packets == 0 and self.latency_samples == 0:
            self.last_print_at = now
            return

        rx_rate = self.rx_packets / elapsed
        lat_avg = self.latency_sum_ms / self.latency_samples
        lat_min = self.latency_min_ms
        lat_max = self.latency_max_ms
        latency_text = f"lat(avg/min/max)={lat_avg:.2f}/{lat_min:.2f}/{lat_max:.2f} ms"
        print(f"hapticnet stats rx={self.rx_packets} rx_rate={rx_rate:.1f} pkt/s {latency_text}")
        self.rx_packets = 0
        self.estimated_packets = 0
        self.out_of_order_packets = 0
        self.latency_sum_ms = 0.0
        self.latency_samples = 0
        self.latency_min_ms = float("inf")
        self.latency_max_ms = 0.0
        self.last_print_at = now

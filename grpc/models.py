from dataclasses import dataclass
import time

@dataclass(slots=True)
class StreamStats:
    received_packets: int = 0
    latency_sum_ms: float = 0.0
    latency_samples: int = 0
    latency_min_ms: float = float("inf")
    latency_max_ms: float = 0.0
    window_packets: int = 0
    window_latency_sum_ms: float = 0.0
    window_latency_samples: int = 0
    window_latency_min_ms: float = float("inf")
    window_latency_max_ms: float = 0.0
    last_report_at: float = 0.0

    def add_latency(self, latency_ms: float) -> None:
        self.latency_sum_ms += latency_ms
        self.latency_samples += 1
        self.latency_min_ms = min(self.latency_min_ms, latency_ms)
        self.latency_max_ms = max(self.latency_max_ms, latency_ms)
        self.window_latency_sum_ms += latency_ms
        self.window_latency_samples += 1
        self.window_latency_min_ms = min(self.window_latency_min_ms, latency_ms)
        self.window_latency_max_ms = max(self.window_latency_max_ms, latency_ms)

    def report_if_due(self) -> None:
        now = time.perf_counter()
        if self.last_report_at == 0.0:
            self.last_report_at = now
            return

        elapsed = now - self.last_report_at
        if elapsed < 1.0:
            return

        rx_rate = self.window_packets / elapsed
        if self.window_latency_samples > 0:
            lat_avg = self.window_latency_sum_ms / self.window_latency_samples
            lat_min = self.window_latency_min_ms
            lat_max = self.window_latency_max_ms
            lat_text = f"lat(avg/min/max)={lat_avg:.2f}/{lat_min:.2f}/{lat_max:.2f} ms"
        else:
            lat_text = "lat(avg/min/max)=n/a"

        print(f"grpc stats rx={self.window_packets} rx_rate={rx_rate:.1f} pkt/s {lat_text}")
        self.window_packets = 0
        self.window_latency_sum_ms = 0.0
        self.window_latency_samples = 0
        self.window_latency_min_ms = float("inf")
        self.window_latency_max_ms = 0.0
        self.last_report_at = now

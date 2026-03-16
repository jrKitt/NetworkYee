from __future__ import annotations

import argparse
import socket
import sys
import threading
import time
from concurrent import futures
from dataclasses import dataclass
from pathlib import Path

import grpc

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

import helloworld_pb2
import helloworld_pb2_grpc

DISCOVERY_REQUEST = b"NETWORKYEE_GRPC_DISCOVER_V1"


class Greeter(helloworld_pb2_grpc.GreeterServicer):
    def SayHello(self, request, context):
        started_at = time.perf_counter()
        reply = helloworld_pb2.HelloReply(message=f"Hello, {request.name}!")
        latency_ms = (time.perf_counter() - started_at) * 1000.0
        print(f"SayHello peer={context.peer()} name={request.name!r} latency_ms={latency_ms:.3f}")
        return reply


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


class HapticBridge(helloworld_pb2_grpc.HapticBridgeServicer):
    def StreamHaptics(self, request_iterator, context):
        stats = StreamStats()
        started = time.perf_counter()
        for frame in request_iterator:
            stats.received_packets += 1
            stats.window_packets += 1
            now_ns = time.time_ns()
            latency_ms = (now_ns - frame.timestamp_ns) / 1_000_000.0
            if latency_ms >= 0:
                stats.add_latency(latency_ms)
                lat_text = f"lat={latency_ms:.2f}ms"
            else:
                lat_text = "lat=n/a"

            print(
                f"grpc rx seq={frame.sequence:04d} "
                f"pos=({frame.pos_x:+.3f},{frame.pos_y:+.3f},{frame.pos_z:+.3f}) {lat_text}"
            )
            stats.report_if_due()

        duration_s = time.perf_counter() - started
        if stats.latency_samples > 0:
            avg_latency_ms = stats.latency_sum_ms / stats.latency_samples
            min_latency_ms = stats.latency_min_ms
            max_latency_ms = stats.latency_max_ms
        else:
            avg_latency_ms = 0.0
            min_latency_ms = 0.0
            max_latency_ms = 0.0

        print(
            "grpc stream summary "
            f"packets={stats.received_packets} "
            f"lat(avg/min/max)={avg_latency_ms:.2f}/{min_latency_ms:.2f}/{max_latency_ms:.2f} ms "
            f"duration={duration_s:.2f}s"
        )
        return helloworld_pb2.StreamSummary(
            received_packets=stats.received_packets,
            avg_latency_ms=avg_latency_ms,
            min_latency_ms=min_latency_ms,
            max_latency_ms=max_latency_ms,
            duration_s=duration_s,
        )


def _discovery_server(grpc_port: int, discovery_port: int, stop_event: threading.Event) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("0.0.0.0", discovery_port))
        sock.settimeout(0.5)
        print(f"Discovery listener started on 0.0.0.0:{discovery_port} -> grpc port {grpc_port}")
        while not stop_event.is_set():
            try:
                payload, addr = sock.recvfrom(1024)
            except socket.timeout:
                continue
            except OSError:
                break

            if payload != DISCOVERY_REQUEST:
                continue

            response = f"NETWORKYEE_GRPC_HERE {grpc_port}".encode("utf-8")
            sock.sendto(response, addr)


def serve(
    host: str = "0.0.0.0",
    port: int = 50051,
    enable_discovery: bool = True,
    discovery_port: int = 50052,
) -> None:
    stop_event = threading.Event()
    discovery_thread: threading.Thread | None = None
    if enable_discovery:
        discovery_thread = threading.Thread(
            target=_discovery_server,
            args=(port, discovery_port, stop_event),
            daemon=True,
        )
        discovery_thread.start()

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    helloworld_pb2_grpc.add_GreeterServicer_to_server(Greeter(), server)
    helloworld_pb2_grpc.add_HapticBridgeServicer_to_server(HapticBridge(), server)
    server.add_insecure_port(f"{host}:{port}")
    server.start()
    print(f"grpc server started on {host}:{port}")
    try:
        server.wait_for_termination()
    finally:
        stop_event.set()
        if discovery_thread is not None:
            discovery_thread.join(timeout=1.0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run gRPC Greeter server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=50051)
    parser.add_argument("--discovery-port", type=int, default=50052)
    parser.add_argument("--disable-discovery", action="store_true")
    args = parser.parse_args()
    serve(
        host=args.host,
        port=args.port,
        enable_discovery=not args.disable_discovery,
        discovery_port=args.discovery_port,
    )

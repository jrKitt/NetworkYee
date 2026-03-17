from __future__ import annotations

import sys
import threading
import time
from concurrent import futures
from pathlib import Path

import grpc

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

import helloworld_pb2
import helloworld_pb2_grpc
from .models import StreamStats
from .discovery import _discovery_server

class Greeter(helloworld_pb2_grpc.GreeterServicer):
    def SayHello(self, request, context):
        started_at = time.perf_counter()
        reply = helloworld_pb2.HelloReply(message=f"Hello, {request.name}!")
        latency_ms = (time.perf_counter() - started_at) * 1000.0
        print(f"SayHello peer={context.peer()} name={request.name!r} latency_ms={latency_ms:.3f}")
        return reply

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


def run_server(
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

from __future__ import annotations

import argparse
import socket
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

DISCOVERY_REQUEST = b"NETWORKYEE_GRPC_DISCOVER_V1"


class Greeter(helloworld_pb2_grpc.GreeterServicer):
    def SayHello(self, request, context):
        started_at = time.perf_counter()
        reply = helloworld_pb2.HelloReply(message=f"Hello, {request.name}!")
        latency_ms = (time.perf_counter() - started_at) * 1000.0
        print(f"SayHello peer={context.peer()} name={request.name!r} latency_ms={latency_ms:.3f}")
        return reply


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
    server.add_insecure_port(f"{host}:{port}")
    server.start()
    print(f"gRPC server started on {host}:{port}")
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

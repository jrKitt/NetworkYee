from __future__ import annotations

import argparse
import sys
import time
from concurrent import futures
from pathlib import Path

import grpc

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

import helloworld_pb2
import helloworld_pb2_grpc


class Greeter(helloworld_pb2_grpc.GreeterServicer):
    def SayHello(self, request, context):
        started_at = time.perf_counter()
        reply = helloworld_pb2.HelloReply(message=f"Hello, {request.name}!")
        latency_ms = (time.perf_counter() - started_at) * 1000.0
        print(f"SayHello peer={context.peer()} name={request.name!r} latency_ms={latency_ms:.3f}")
        return reply


def serve(host: str = "0.0.0.0", port: int = 50051) -> None:
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    helloworld_pb2_grpc.add_GreeterServicer_to_server(Greeter(), server)
    server.add_insecure_port(f"{host}:{port}")
    server.start()
    print(f"gRPC server started on {host}:{port}")
    server.wait_for_termination()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run gRPC Greeter server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=50051)
    args = parser.parse_args()
    serve(host=args.host, port=args.port)

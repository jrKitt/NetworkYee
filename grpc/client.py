from __future__ import annotations

import argparse
import sys
from pathlib import Path

import grpc

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

import helloworld_pb2
import helloworld_pb2_grpc


def run(name: str = "World", host: str = "127.0.0.1", port: int = 50051, timeout: float = 5.0) -> None:
    target = f"{host}:{port}"
    with grpc.insecure_channel(target) as channel:
        grpc.channel_ready_future(channel).result(timeout=timeout)
        stub = helloworld_pb2_grpc.GreeterStub(channel)
        response = stub.SayHello(helloworld_pb2.HelloRequest(name=name), timeout=timeout)
        print(f"Greeter client received: {response.message}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run gRPC Greeter client")
    parser.add_argument("--name", default="World")
    parser.add_argument("--host", default="127.0.0.1", help="Server IP/hostname (use remote machine IP for cross-machine)")
    parser.add_argument("--port", type=int, default=50051)
    parser.add_argument("--timeout", type=float, default=5.0)
    args = parser.parse_args()
    run(name=args.name, host=args.host, port=args.port, timeout=args.timeout)

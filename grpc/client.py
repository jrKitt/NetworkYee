from __future__ import annotations

import argparse
import socket
import sys
from pathlib import Path

import grpc

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

import helloworld_pb2
import helloworld_pb2_grpc

DISCOVERY_REQUEST = b"NETWORKYEE_GRPC_DISCOVER_V1"


def discover_server(
    discovery_port: int = 50052,
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
                "No discovery response received. Ensure server is running with discovery enabled and UDP port is open."
            ) from exc

    message = payload.decode("utf-8", errors="strict")
    prefix = "NETWORKYEE_GRPC_HERE "
    if not message.startswith(prefix):
        raise RuntimeError(f"Invalid discovery response: {message!r}")
    try:
        discovered_port = int(message[len(prefix) :])
    except ValueError as exc:
        raise RuntimeError(f"Invalid discovered port in response: {message!r}") from exc
    return f"{addr[0]}:{discovered_port}"


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
    parser.add_argument("--discover", action="store_true", help="Auto-discover server IP via UDP broadcast")
    parser.add_argument("--discovery-port", type=int, default=50052)
    parser.add_argument("--broadcast-ip", default="255.255.255.255")
    args = parser.parse_args()
    if args.discover:
        target = discover_server(
            discovery_port=args.discovery_port,
            timeout=args.timeout,
            broadcast_ip=args.broadcast_ip,
        )
        host, port_str = target.rsplit(":", 1)
        print(f"Discovered gRPC server at {target}")
        run(name=args.name, host=host, port=int(port_str), timeout=args.timeout)
    else:
        run(name=args.name, host=args.host, port=args.port, timeout=args.timeout)

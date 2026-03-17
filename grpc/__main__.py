from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from .client import run_client
from .server import run_server
from .discovery import discover_server


BASE_DIR = Path(__file__).resolve().parent

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run HapticNet gRPC utilities")
    subparsers = parser.add_subparsers(dest="command", required=True)

    server_parser = subparsers.add_parser("server", help="Run gRPC server")
    server_parser.add_argument("--host", default="0.0.0.0")
    server_parser.add_argument("--port", type=int, default=50051)
    server_parser.add_argument("--discovery-port", type=int, default=50052)
    server_parser.add_argument("--disable-discovery", action="store_true")

    client_parser = subparsers.add_parser("client", help="Run gRPC client")
    client_parser.add_argument("--host", default="127.0.0.1")
    client_parser.add_argument("--port", type=int, default=50051)
    client_parser.add_argument("--timeout", type=float, default=0.0)
    client_parser.add_argument("--rate", type=int, default=100)
    client_parser.add_argument("--samples", type=int, default=1000)
    client_parser.add_argument("--discover", action="store_true")
    client_parser.add_argument("--discovery-port", type=int, default=50052)
    client_parser.add_argument("--broadcast-ip", default="255.255.255.255")

    discover_parser = subparsers.add_parser("discover", help="Discover gRPC server over UDP broadcast")
    discover_parser.add_argument("--discovery-port", type=int, default=50052)
    discover_parser.add_argument("--timeout", type=float, default=3.0)
    discover_parser.add_argument("--broadcast-ip", default="255.255.255.255")

    subparsers.add_parser("gen-proto", help="Generate protobuf Python files")
    return parser

def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "server":
        run_server(
            host=args.host,
            port=args.port,
            enable_discovery=not args.disable_discovery,
            discovery_port=args.discovery_port,
        )
    elif args.command == "client":
        run_client(
            host=args.host,
            port=args.port,
            timeout=args.timeout,
            rate_hz=args.rate,
            samples=args.samples,
            discover=args.discover,
            discovery_port=args.discovery_port,
            broadcast_ip=args.broadcast_ip,
        )
    elif args.command == "discover":
        target = discover_server(
            discovery_port=args.discovery_port,
            timeout=args.timeout,
            broadcast_ip=args.broadcast_ip,
        )
        print(f"Discovered grpc server at {target}")
    elif args.command == "gen-proto":
        command = ["bash", str(BASE_DIR / "gen_proto.sh")]
        exit_code = subprocess.run(command, check=False).returncode
        raise SystemExit(exit_code)
    else:
        parser.error(f"Unknown command: {args.command}")

if __name__ == "__main__":
    main()

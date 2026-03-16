from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent


def _run_script(script_name: str, args: list[str]) -> int:
    command = [sys.executable, str(BASE_DIR / script_name), *args]
    completed = subprocess.run(command, check=False)
    return completed.returncode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run gRPC utilities")
    subparsers = parser.add_subparsers(dest="command", required=True)

    server_parser = subparsers.add_parser("server", help="Run gRPC server")
    server_parser.add_argument("--host", default="0.0.0.0")
    server_parser.add_argument("--port", type=int, default=50051)

    client_parser = subparsers.add_parser("client", help="Run gRPC client")
    client_parser.add_argument("--host", default="127.0.0.1")
    client_parser.add_argument("--port", type=int, default=50051)
    client_parser.add_argument("--name", default="World")
    client_parser.add_argument("--timeout", type=float, default=5.0)

    subparsers.add_parser("gen-proto", help="Generate protobuf Python files")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "server":
        exit_code = _run_script("server.py", ["--host", args.host, "--port", str(args.port)])
    elif args.command == "client":
        exit_code = _run_script(
            "client.py",
            ["--host", args.host, "--port", str(args.port), "--name", args.name, "--timeout", str(args.timeout)],
        )
    elif args.command == "gen-proto":
        command = ["bash", str(BASE_DIR / "gen_proto.sh")]
        exit_code = subprocess.run(command, check=False).returncode
    else:
        parser.error(f"Unknown command: {args.command}")
        return

    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()

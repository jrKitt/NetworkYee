from __future__ import annotations

import argparse
import math
import random
import socket
import sys
import time
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


def _frame_stream(rate_hz: int, samples: int) -> object:
    interval = 1.0 / rate_hz
    sequence = 0
    started = time.perf_counter()

    while samples <= 0 or sequence < samples:
        t = time.perf_counter() - started
        sequence += 1
        yield helloworld_pb2.HapticFrame(
            sequence=sequence,
            timestamp_ns=time.time_ns(),
            pos_x=math.sin(t),
            pos_y=math.cos(t),
            pos_z=math.sin(t * 0.5),
            rot_w=1.0,
            rot_x=0.0,
            rot_y=0.0,
            rot_z=0.0,
            force=0.25 + random.random() * 0.5,
            texture_id=1,
        )
        time.sleep(interval)


def _resolve_timeout(timeout: float, rate_hz: int, samples: int) -> float | None:
    if timeout > 0:
        return timeout
    if samples <= 0:
        return None
    estimated_duration = samples / max(rate_hz, 1)
    return max(10.0, estimated_duration + 5.0)


def run(host: str = "127.0.0.1", port: int = 50051, timeout: float = 0.0, rate_hz: int = 100, samples: int = 1000) -> None:
    target = f"{host}:{port}"
    rpc_timeout = _resolve_timeout(timeout=timeout, rate_hz=rate_hz, samples=samples)
    connect_timeout = 10.0 if rpc_timeout is None else min(10.0, rpc_timeout)
    with grpc.insecure_channel(target) as channel:
        grpc.channel_ready_future(channel).result(timeout=connect_timeout)
        stub = helloworld_pb2_grpc.HapticBridgeStub(channel)
        print(f"grpc client sending to {target} rate={rate_hz}Hz samples={samples}")
        response = stub.StreamHaptics(_frame_stream(rate_hz=rate_hz, samples=samples), timeout=rpc_timeout)
        print(
            "grpc stream summary "
            f"packets={response.received_packets} "
            f"lat(avg/min/max)={response.avg_latency_ms:.2f}/{response.min_latency_ms:.2f}/{response.max_latency_ms:.2f} ms "
            f"duration={response.duration_s:.2f}s"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run HapticNet gRPC client")
    parser.add_argument("--host", default="127.0.0.1", help="Server IP/hostname (use remote machine IP for cross-machine)")
    parser.add_argument("--port", type=int, default=50051)
    parser.add_argument("--timeout", type=float, default=0.0, help="RPC timeout in seconds (<=0 means auto)")
    parser.add_argument("--rate", type=int, default=100)
    parser.add_argument("--samples", type=int, default=1000, help="Number of frames to send (<=0 means infinite)")
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
        print(f"Discovered grpc server at {target}")
        run(host=host, port=int(port_str), timeout=args.timeout, rate_hz=args.rate, samples=args.samples)
    else:
        run(host=args.host, port=args.port, timeout=args.timeout, rate_hz=args.rate, samples=args.samples)

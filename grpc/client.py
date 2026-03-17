from __future__ import annotations

import math
import random
import time
from pathlib import Path
import sys

import grpc

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

import helloworld_pb2
import helloworld_pb2_grpc
from .discovery import discover_server


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


def run_client(host: str = "127.0.0.1", port: int = 50051, timeout: float = 0.0, rate_hz: int = 100, samples: int = 1000, discover: bool = False, discovery_port: int = 50052, broadcast_ip: str = "255.255.255.255") -> None:
    if discover:
        target = discover_server(discovery_port=discovery_port, broadcast_ip=broadcast_ip)
        print(f"Discovered grpc server at {target}")
    else:
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

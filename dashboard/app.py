"""
dashboard.app
~~~~~~~~~~~~~
FastAPI application exposing REST endpoints and a WebSocket hub.
All packet events from both HapticNet and gRPC adapters are pushed
through the single /ws WebSocket channel.
"""
from __future__ import annotations

import asyncio
import socket
import threading
import time
from pathlib import Path
from typing import Any, Literal, Optional, Set

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .haptic_adapter import HapticAdapter
from .grpc_adapter import GrpcAdapter
from . import grpc_adapter as dashboard_grpc_adapter

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="NetworkYee Dashboard")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Shared asyncio event queue filled by adapter threads
_event_queue: asyncio.Queue = asyncio.Queue(maxsize=2000)
_ws_clients: Set[WebSocket] = set()
_loop: Optional[asyncio.AbstractEventLoop] = None

haptic_adapter: Optional[HapticAdapter] = None
grpc_adapter: Optional[GrpcAdapter] = None

# Client-side runner state
_haptic_client_thread: Optional[threading.Thread] = None
_haptic_client_stop: Optional[threading.Event] = None
_grpc_client_thread: Optional[threading.Thread] = None
_grpc_client_stop: Optional[threading.Event] = None

# Web simulator sender state
_sim_lock = threading.Lock()
_sim_haptic_seq = 0
_sim_grpc_seq = 0
_sim_grpc_target: Optional[str] = None
_sim_grpc_channel: Any = None
_sim_grpc_stub: Any = None


# ---------------------------------------------------------------------------
# Startup / Shutdown
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def startup() -> None:
    global _loop, haptic_adapter, grpc_adapter
    _loop = asyncio.get_running_loop()

    haptic_adapter = HapticAdapter(
        bind_host="0.0.0.0",
        port=9000,
        buffer_size=3,
        discovery_port=9001,
        event_queue=_event_queue,
        loop=_loop,
    )
    grpc_adapter = GrpcAdapter(
        host="0.0.0.0",
        port=50051,
        discovery_port=50052,
        event_queue=_event_queue,
        loop=_loop,
    )
    haptic_adapter.start()
    grpc_adapter.start()

    # Background task: broadcast events from queue to all WS clients
    asyncio.create_task(_broadcast_loop())


@app.on_event("shutdown")
async def shutdown() -> None:
    global _sim_grpc_channel, _sim_grpc_stub, _sim_grpc_target
    if haptic_adapter:
        haptic_adapter.stop()
    if grpc_adapter:
        grpc_adapter.stop()
    if _sim_grpc_channel is not None:
        _sim_grpc_channel.close()
        _sim_grpc_channel = None
        _sim_grpc_stub = None
        _sim_grpc_target = None


# ---------------------------------------------------------------------------
# WebSocket hub
# ---------------------------------------------------------------------------

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    _ws_clients.add(ws)
    try:
        while True:
            await ws.receive_text()  # keep-alive / ignore client messages
    except WebSocketDisconnect:
        _ws_clients.discard(ws)


async def _broadcast_loop() -> None:
    global _ws_clients
    while True:
        event: dict = await _event_queue.get()
        dead = set()
        for client in list(_ws_clients):
            try:
                await client.send_json(event)
            except Exception:
                dead.add(client)
        _ws_clients -= dead


# ---------------------------------------------------------------------------
# Static UI
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    html = (STATIC_DIR / "index.html").read_text()
    return HTMLResponse(content=html)


@app.get("/simulate", response_class=HTMLResponse)
async def simulate_page() -> HTMLResponse:
    html = (STATIC_DIR / "simulate.html").read_text()
    return HTMLResponse(content=html)


# ---------------------------------------------------------------------------
# REST – status
# ---------------------------------------------------------------------------

@app.get("/api/status")
async def get_status() -> dict:
    return {
        "hapticnet": {
            "server_running": haptic_adapter.is_running if haptic_adapter else False,
            "client_running": _haptic_client_thread is not None and _haptic_client_thread.is_alive(),
            "packet_loss_rate": haptic_adapter._packet_loss_rate if haptic_adapter else 0.0,
        },
        "grpc": {
            "server_running": grpc_adapter.is_running if grpc_adapter else False,
            "client_running": _grpc_client_thread is not None and _grpc_client_thread.is_alive(),
            "packet_loss_rate": grpc_adapter._loss_ref[0] if grpc_adapter else 0.0,
        },
    }


# ---------------------------------------------------------------------------
# REST – HapticNet client control
# ---------------------------------------------------------------------------

class ClientConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 9000
    rate_hz: int = 100
    samples: int = 1000


@app.post("/api/hapticnet/start-client")
async def hapticnet_start_client(cfg: ClientConfig) -> dict:
    global _haptic_client_thread, _haptic_client_stop
    if _haptic_client_thread and _haptic_client_thread.is_alive():
        return {"status": "already_running"}

    from hapticnet.control import run_client as _hnet_run_client

    _haptic_client_stop = threading.Event()
    stop = _haptic_client_stop

    def _run():
        try:
            _hnet_run_client(
                host=cfg.host,
                port=cfg.port,
                rate_hz=cfg.rate_hz,
                samples=cfg.samples,
                stop_event=stop,
            )
        except Exception as exc:
            print(f"[hapticnet client] {exc}")
        finally:
            if _loop:
                _loop.call_soon_threadsafe(
                    _event_queue.put_nowait,
                    {"type": "client_done", "protocol": "hapticnet"},
                )

    _haptic_client_thread = threading.Thread(target=_run, daemon=True)
    _haptic_client_thread.start()
    return {"status": "started"}


@app.post("/api/hapticnet/stop-client")
async def hapticnet_stop_client() -> dict:
    if _haptic_client_stop:
        _haptic_client_stop.set()
    return {"status": "stopping"}


# ---------------------------------------------------------------------------
# REST – gRPC client control
# ---------------------------------------------------------------------------

class GrpcClientConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 50051
    rate_hz: int = 100
    samples: int = 1000


@app.post("/api/grpc/start-client")
async def grpc_start_client(cfg: GrpcClientConfig) -> dict:
    global _grpc_client_thread, _grpc_client_stop
    if _grpc_client_thread and _grpc_client_thread.is_alive():
        return {"status": "already_running"}

    import sys as _sys
    import importlib.util as _ilu
    from pathlib import Path as _Path
    _pkg_name = "_localgrpc.client"
    if _pkg_name not in _sys.modules:
        _local_grpc_dir = _Path(__file__).parent.parent / "grpc"
        _spec = _ilu.spec_from_file_location(_pkg_name, str(_local_grpc_dir / "client.py"))
        _mod = _ilu.module_from_spec(_spec)
        _mod.__package__ = "_localgrpc"
        _sys.modules[_pkg_name] = _mod
        _spec.loader.exec_module(_mod)
    _grpc_run_client = _sys.modules[_pkg_name].run_client

    _grpc_client_stop = threading.Event()

    def _run():
        try:
            _grpc_run_client(
                host=cfg.host,
                port=cfg.port,
                rate_hz=cfg.rate_hz,
                samples=cfg.samples,
            )
        except Exception as exc:
            print(f"[grpc client] {exc}")
        finally:
            if _loop:
                _loop.call_soon_threadsafe(
                    _event_queue.put_nowait,
                    {"type": "client_done", "protocol": "grpc"},
                )

    _grpc_client_thread = threading.Thread(target=_run, daemon=True)
    _grpc_client_thread.start()
    return {"status": "started"}


@app.post("/api/grpc/stop-client")
async def grpc_stop_client() -> dict:
    if _grpc_client_stop:
        _grpc_client_stop.set()
    return {"status": "stopping"}


# ---------------------------------------------------------------------------
# REST – Packet loss control
# ---------------------------------------------------------------------------

class LossConfig(BaseModel):
    rate: float  # 0.0 – 1.0


@app.post("/api/hapticnet/packet-loss")
async def hapticnet_set_loss(cfg: LossConfig) -> dict:
    if haptic_adapter:
        haptic_adapter.set_packet_loss_rate(cfg.rate)
    return {"status": "ok", "rate": cfg.rate}


@app.post("/api/grpc/packet-loss")
async def grpc_set_loss(cfg: LossConfig) -> dict:
    if grpc_adapter:
        grpc_adapter.set_packet_loss_rate(cfg.rate)
    return {"status": "ok", "rate": cfg.rate}


# ---------------------------------------------------------------------------
# REST – Web simulator sender
# ---------------------------------------------------------------------------

class SimulateConfig(BaseModel):
    target: Literal["hapticnet", "grpc", "both"] = "both"
    payload_mode: Literal["position", "position_force", "full"] = "position_force"
    haptic_host: str = "127.0.0.1"
    haptic_port: int = 9000
    grpc_host: str = "127.0.0.1"
    grpc_port: int = 50051
    pos_x: float = 0.0
    pos_y: float = 0.0
    pos_z: float = 0.0
    force: float = 0.3
    texture_id: int = 1


def _sim_payload(mode: str, cfg: SimulateConfig) -> dict[str, float | int]:
    if mode == "position":
        return {
            "pos_x": cfg.pos_x,
            "pos_y": cfg.pos_y,
            "pos_z": cfg.pos_z,
            "rot_w": 1.0,
            "rot_x": 0.0,
            "rot_y": 0.0,
            "rot_z": 0.0,
            "force": 0.0,
            "texture_id": 0,
        }
    if mode == "position_force":
        return {
            "pos_x": cfg.pos_x,
            "pos_y": cfg.pos_y,
            "pos_z": cfg.pos_z,
            "rot_w": 1.0,
            "rot_x": 0.0,
            "rot_y": 0.0,
            "rot_z": 0.0,
            "force": cfg.force,
            "texture_id": 1,
        }
    return {
        "pos_x": cfg.pos_x,
        "pos_y": cfg.pos_y,
        "pos_z": cfg.pos_z,
        "rot_w": 1.0,
        "rot_x": 0.0,
        "rot_y": cfg.pos_x * 0.2,
        "rot_z": cfg.pos_y * 0.2,
        "force": cfg.force,
        "texture_id": cfg.texture_id,
    }


def _next_seq(target: str) -> int:
    global _sim_haptic_seq, _sim_grpc_seq
    with _sim_lock:
        if target == "hapticnet":
            _sim_haptic_seq += 1
            return _sim_haptic_seq
        _sim_grpc_seq += 1
        return _sim_grpc_seq


def _send_haptic_frame(cfg: SimulateConfig, payload: dict[str, float | int]) -> int:
    from hapticnet.models import HapticPacket

    seq = _next_seq("hapticnet")
    packet = HapticPacket(
        sequence=seq,
        timestamp_ns=time.time_ns(),
        pos_x=float(payload["pos_x"]),
        pos_y=float(payload["pos_y"]),
        pos_z=float(payload["pos_z"]),
        rot_w=float(payload["rot_w"]),
        rot_x=float(payload["rot_x"]),
        rot_y=float(payload["rot_y"]),
        rot_z=float(payload["rot_z"]),
        force=float(payload["force"]),
        texture_id=int(payload["texture_id"]),
    )
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.sendto(packet.to_bytes(), (cfg.haptic_host, cfg.haptic_port))
    return seq


def _grpc_stub(host: str, port: int) -> Any:
    global _sim_grpc_target, _sim_grpc_channel, _sim_grpc_stub
    target = f"{host}:{port}"
    with _sim_lock:
        if _sim_grpc_stub is not None and _sim_grpc_target == target:
            return _sim_grpc_stub
        if _sim_grpc_channel is not None:
            _sim_grpc_channel.close()
        _sim_grpc_channel = dashboard_grpc_adapter.grpc.insecure_channel(target)
        dashboard_grpc_adapter.grpc.channel_ready_future(_sim_grpc_channel).result(timeout=2.0)
        _sim_grpc_stub = dashboard_grpc_adapter.helloworld_pb2_grpc.HapticBridgeStub(_sim_grpc_channel)
        _sim_grpc_target = target
        return _sim_grpc_stub


def _send_grpc_frame(cfg: SimulateConfig, payload: dict[str, float | int]) -> int:
    seq = _next_seq("grpc")
    frame = dashboard_grpc_adapter.helloworld_pb2.HapticFrame(
        sequence=seq,
        timestamp_ns=time.time_ns(),
        pos_x=float(payload["pos_x"]),
        pos_y=float(payload["pos_y"]),
        pos_z=float(payload["pos_z"]),
        rot_w=float(payload["rot_w"]),
        rot_x=float(payload["rot_x"]),
        rot_y=float(payload["rot_y"]),
        rot_z=float(payload["rot_z"]),
        force=float(payload["force"]),
        texture_id=int(payload["texture_id"]),
    )
    stub = _grpc_stub(cfg.grpc_host, cfg.grpc_port)
    stub.StreamHaptics(iter([frame]), timeout=2.0)
    return seq


@app.post("/api/simulate/send")
async def simulate_send(cfg: SimulateConfig) -> dict:
    payload = _sim_payload(cfg.payload_mode, cfg)
    sent: list[dict[str, int]] = []

    if cfg.target in ("hapticnet", "both"):
        seq = await asyncio.to_thread(_send_haptic_frame, cfg, payload)
        sent.append({"protocol": "hapticnet", "seq": seq})
    if cfg.target in ("grpc", "both"):
        seq = await asyncio.to_thread(_send_grpc_frame, cfg, payload)
        sent.append({"protocol": "grpc", "seq": seq})

    return {"status": "ok", "sent": sent}


# ---------------------------------------------------------------------------
# Entry point when run as module: python3 -m dashboard
# ---------------------------------------------------------------------------

def serve(host: str = "0.0.0.0", port: int = 8080) -> None:
    uvicorn.run(app, host=host, port=port, log_level="info")

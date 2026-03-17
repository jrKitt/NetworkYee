"""
dashboard.app
~~~~~~~~~~~~~
FastAPI application exposing REST endpoints and a WebSocket hub.
All packet events from both HapticNet and gRPC adapters are pushed
through the single /ws WebSocket channel.
"""
from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from typing import Any, Optional, Set

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .haptic_adapter import HapticAdapter
from .grpc_adapter import GrpcAdapter

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
    if haptic_adapter:
        haptic_adapter.stop()
    if grpc_adapter:
        grpc_adapter.stop()


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
# Entry point when run as module: python3 -m dashboard
# ---------------------------------------------------------------------------

def serve(host: str = "0.0.0.0", port: int = 8080) -> None:
    uvicorn.run(app, host=host, port=port, log_level="info")

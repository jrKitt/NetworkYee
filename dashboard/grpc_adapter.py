import asyncio
import importlib
import importlib.util as _ilu
import random
import site
import sys
import threading
import time
from concurrent import futures
from pathlib import Path
from typing import Any, Optional

# ── Resolve grpcio <-> local grpc/ namespace conflict ───────────────────────
#
# Local grpc/ shadows installed grpcio when project root is on sys.path.
# Solution: find grpcio in site-packages by absolute path and inject it into
# sys.modules['grpc'] BEFORE the local grpc/ package is ever touched.
#
def _load_real_grpcio():
    """Find grpcio in site-packages and load it, bypassing sys.modules lookup."""
    for sp in site.getsitepackages():
        grpcio_init = Path(sp) / "grpc" / "__init__.py"
        if not grpcio_init.exists():
            continue
        grpcio_dir = grpcio_init.parent
        # Only accept the real grpcio (has __version__)
        # Load using a temporary module name to avoid sys.modules['grpc'] conflict
        spec = _ilu.spec_from_file_location(
            "__grpcio_real__", str(grpcio_init),
            submodule_search_locations=[str(grpcio_dir)],
        )
        if spec is None:
            continue
        mod = _ilu.module_from_spec(spec)
        mod.__path__ = [str(grpcio_dir)]
        mod.__package__ = "__grpcio_real__"
        # Temporarily register grpcio submodules under their real names so that
        # grpcio's __init__.py (which does `from grpc import _foo`) can import them.
        # We accomplish this by briefly swapping sys.modules['grpc'] ourselves.
        _old_grpc = sys.modules.get("grpc")
        sys.modules["grpc"] = mod
        sys.modules["__grpcio_real__"] = mod
        try:
            spec.loader.exec_module(mod)
            # Success — keep grpc = real grpcio in sys.modules
            return mod
        except Exception:
            # Roll back on failure
            if _old_grpc is not None:
                sys.modules["grpc"] = _old_grpc
            else:
                sys.modules.pop("grpc", None)
    return None

grpc = _load_real_grpcio()
if grpc is None:
    raise ImportError("Could not load grpcio from site-packages. Is it installed?")
# Alias in sys.modules so all future `import grpc` statements get grpcio
sys.modules["grpc"] = grpc

# ── Load local grpc/ submodules under the alias '_localgrpc' ────────────────
_LOCAL_GRPC_DIR = Path(__file__).resolve().parent.parent / "grpc"


def _ensure_local_grpc_loaded() -> None:
    pkg_name = "_localgrpc"
    if pkg_name in sys.modules:
        return
    init_path = _LOCAL_GRPC_DIR / "__init__.py"
    spec = _ilu.spec_from_file_location(
        pkg_name, str(init_path),
        submodule_search_locations=[str(_LOCAL_GRPC_DIR)]
    )
    pkg = _ilu.module_from_spec(spec)
    pkg.__path__ = [str(_LOCAL_GRPC_DIR)]
    pkg.__package__ = pkg_name
    sys.modules[pkg_name] = pkg
    spec.loader.exec_module(pkg)
    for sub in ("config", "models", "discovery"):
        sub_spec = _ilu.spec_from_file_location(
            f"{pkg_name}.{sub}", str(_LOCAL_GRPC_DIR / f"{sub}.py")
        )
        sub_mod = _ilu.module_from_spec(sub_spec)
        sub_mod.__package__ = pkg_name
        sys.modules[f"{pkg_name}.{sub}"] = sub_mod
        sub_spec.loader.exec_module(sub_mod)


_ensure_local_grpc_loaded()
StreamStats = sys.modules["_localgrpc.models"].StreamStats
_discovery_server = sys.modules["_localgrpc.discovery"]._discovery_server

# ── Proto stubs ─────────────────────────────────────────────────────────────
if str(_LOCAL_GRPC_DIR) not in sys.path:
    sys.path.insert(0, str(_LOCAL_GRPC_DIR))

helloworld_pb2 = importlib.import_module("helloworld_pb2")
helloworld_pb2_grpc = importlib.import_module("helloworld_pb2_grpc")



class _HapticBridgeServicer(helloworld_pb2_grpc.HapticBridgeServicer):
    """gRPC HapticBridge that emits events to an asyncio queue."""

    def __init__(
        self,
        loss_ref: list,  # mutable list[float] so we can change from outside
        event_queue: Optional[asyncio.Queue],
        loop: Optional[asyncio.AbstractEventLoop],
    ) -> None:
        self._loss = loss_ref
        self._event_queue = event_queue
        self._loop = loop

    def _emit(self, data: dict) -> None:
        if self._event_queue is None or self._loop is None:
            return
        event: dict[str, Any] = {"type": "grpc_rx", **data}
        self._loop.call_soon_threadsafe(self._event_queue.put_nowait, event)

    def StreamHaptics(self, request_iterator, context):
        stats = StreamStats()
        started = time.perf_counter()

        for frame in request_iterator:
            # Artificial packet loss injection
            if self._loss[0] > 0.0 and random.random() < self._loss[0]:
                continue  # drop packet for symmetric DR comparison

            stats.received_packets += 1
            stats.window_packets += 1
            now_ns = time.time_ns()
            latency_ms = max(0.0, (now_ns - frame.timestamp_ns) / 1_000_000.0)
            stats.add_latency(latency_ms)

            print(
                f"grpc rx seq={frame.sequence:04d} "
                f"pos=({frame.pos_x:+.3f},{frame.pos_y:+.3f},{frame.pos_z:+.3f}) "
                f"lat={latency_ms:.2f}ms"
            )

            self._emit({
                "seq": frame.sequence,
                "pos": [round(frame.pos_x, 4), round(frame.pos_y, 4), round(frame.pos_z, 4)],
                "force": round(frame.force, 4),
                "latency_ms": round(latency_ms, 3),
                "source": "real",
            })
            stats.report_if_due()

        duration_s = time.perf_counter() - started
        if stats.latency_samples > 0:
            avg_ms = stats.latency_sum_ms / stats.latency_samples
            min_ms = stats.latency_min_ms
            max_ms = stats.latency_max_ms
        else:
            avg_ms = min_ms = max_ms = 0.0

        print(
            "grpc stream summary "
            f"packets={stats.received_packets} "
            f"lat(avg/min/max)={avg_ms:.2f}/{min_ms:.2f}/{max_ms:.2f} ms "
            f"duration={duration_s:.2f}s"
        )
        return helloworld_pb2.StreamSummary(
            received_packets=stats.received_packets,
            avg_latency_ms=avg_ms,
            min_latency_ms=min_ms,
            max_latency_ms=max_ms,
            duration_s=duration_s,
        )


class GrpcAdapter:
    """Wraps the gRPC server in a daemon thread."""

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 50051,
        discovery_port: int = 50052,
        event_queue: Optional[asyncio.Queue] = None,
        loop: Optional[asyncio.AbstractEventLoop] = None,
    ) -> None:
        self.host = host
        self.port = port
        self.discovery_port = discovery_port
        self._event_queue = event_queue
        self._loop = loop
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._loss_ref: list = [0.0]

    # ------------------------------------------------------------------

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=3.0)
            self._thread = None

    def set_packet_loss_rate(self, rate: float) -> None:
        self._loss_ref[0] = max(0.0, min(1.0, rate))

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # ------------------------------------------------------------------

    def _run(self) -> None:
        discovery_thread: Optional[threading.Thread] = None
        try:
            discovery_thread = threading.Thread(
                target=_discovery_server,
                args=(self.port, self.discovery_port, self._stop_event),
                daemon=True,
            )
            discovery_thread.start()

            servicer = _HapticBridgeServicer(
                loss_ref=self._loss_ref,
                event_queue=self._event_queue,
                loop=self._loop,
            )
            server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
            helloworld_pb2_grpc.add_HapticBridgeServicer_to_server(servicer, server)
            server.add_insecure_port(f"{self.host}:{self.port}")
            server.start()
            print(f"grpc server started on {self.host}:{self.port}")

            # Poll stop_event since gRPC server doesn't natively support it
            while not self._stop_event.is_set():
                time.sleep(0.25)
            server.stop(grace=1.0)
        except Exception as exc:
            print(f"[GrpcAdapter] server error: {exc}")
        finally:
            self._stop_event.set()
            if discovery_thread:
                discovery_thread.join(timeout=1.0)

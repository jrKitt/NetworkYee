"""
dashboard.haptic_adapter
~~~~~~~~~~~~~~~~~~~~~~~~~
Runs the HapticNet UDP receiver in a background thread and forwards
packet events to an asyncio Queue consumed by the WebSocket hub.
"""
from __future__ import annotations

import asyncio
import threading
from typing import Any, Optional

from hapticnet.control import run_receiver


class HapticAdapter:
    """Wraps hapticnet run_receiver in a daemon thread."""

    def __init__(
        self,
        bind_host: str = "0.0.0.0",
        port: int = 9000,
        buffer_size: int = 3,
        discovery_port: int = 9001,
        event_queue: Optional[asyncio.Queue] = None,
        loop: Optional[asyncio.AbstractEventLoop] = None,
    ) -> None:
        self.bind_host = bind_host
        self.port = port
        self.buffer_size = buffer_size
        self.discovery_port = discovery_port
        self._event_queue = event_queue
        self._loop = loop
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._packet_loss_rate: float = 0.0

    # ------------------------------------------------------------------
    # Public API
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
        self._packet_loss_rate = max(0.0, min(1.0, rate))
        # propagate to live receiver if running
        setter = getattr(run_receiver, "_set_loss", None)
        if callable(setter):
            setter(self._packet_loss_rate)

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _on_packet(self, data: dict) -> None:
        if self._event_queue is None or self._loop is None:
            return
        event: dict[str, Any] = {"type": "hapticnet_rx", **data}
        # Thread-safe push into asyncio event loop
        self._loop.call_soon_threadsafe(self._event_queue.put_nowait, event)

    def _run(self) -> None:
        try:
            run_receiver(
                bind_host=self.bind_host,
                port=self.port,
                buffer_size=self.buffer_size,
                enable_discovery=True,
                discovery_port=self.discovery_port,
                stop_event=self._stop_event,
                packet_loss_rate=self._packet_loss_rate,
                on_packet=self._on_packet,
            )
        except Exception as exc:
            print(f"[HapticAdapter] server error: {exc}")

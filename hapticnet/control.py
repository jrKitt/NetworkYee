"""
hapticnet.control
~~~~~~~~~~~~~~~~~
Core runner functions for the HapticNet UDP transport.
Imported by both the CLI (__main__.py) and the dashboard backend.
"""
from __future__ import annotations

import random
import socket
import threading
import time
from typing import Callable, Optional

from .config import (
    DISCOVERY_REQUEST,
    DISCOVERY_RESPONSE_PREFIX,
    PAYLOAD_SIZE,
    SUMMARY_RESPONSE_PREFIX,
)
from .logic import DeadReckoner, PacketBuffer as JitterBuffer, _read_sequence, calculate_latency_ms
from .models import HapticPacket, ReceiverStats
from .simulator import HapticSimulator


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------

def run_simulation(sample_count: int) -> None:
    """Run a local encode/decode simulation and print results."""
    simulator = HapticSimulator()
    for _ in range(sample_count):
        packet = simulator.next_packet()
        payload = packet.to_bytes()
        unpacked = HapticPacket.from_bytes(payload)
        print(
            f"seq={unpacked.sequence:04d} "
            f"pos=({unpacked.pos_x:+.3f},{unpacked.pos_y:+.3f},{unpacked.pos_z:+.3f}) "
            f"force={unpacked.force:.2f} bytes={len(payload)}"
        )
        time.sleep(0.01)


# ---------------------------------------------------------------------------
# Discovery helpers
# ---------------------------------------------------------------------------

def discover_receiver(
    discovery_port: int = 9001,
    timeout: float = 5.0,
    broadcast_ip: str = "255.255.255.255",
) -> str:
    """Broadcast and return 'host:port' of the first responding server."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(timeout)
        sock.sendto(DISCOVERY_REQUEST, (broadcast_ip, discovery_port))
        try:
            payload, addr = sock.recvfrom(1024)
        except TimeoutError as exc:
            raise RuntimeError(
                "No haptic discovery response. Ensure server is running and UDP discovery port is open."
            ) from exc

    message = payload.decode("utf-8", errors="strict")
    if not message.startswith(DISCOVERY_RESPONSE_PREFIX):
        raise RuntimeError(f"Invalid discovery response: {message!r}")
    try:
        discovered_port = int(message[len(DISCOVERY_RESPONSE_PREFIX):])
    except ValueError as exc:
        raise RuntimeError(f"Invalid discovered port in response: {message!r}") from exc

    return f"{addr[0]}:{discovered_port}"


def _discovery_server(port: int, discovery_port: int, stop_event: threading.Event) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("0.0.0.0", discovery_port))
        sock.settimeout(0.5)
        print(f"Discovery listener started on 0.0.0.0:{discovery_port} -> haptic port {port}")
        while not stop_event.is_set():
            try:
                payload, addr = sock.recvfrom(1024)
            except socket.timeout:
                continue
            except OSError:
                break
            if payload != DISCOVERY_REQUEST:
                continue
            response = f"{DISCOVERY_RESPONSE_PREFIX}{port}".encode("utf-8")
            sock.sendto(response, addr)


# ---------------------------------------------------------------------------
# Sender / Client
# ---------------------------------------------------------------------------

def run_sender(
    host: str,
    port: int,
    rate_hz: int,
    samples: int = 1000,
    stop_event: Optional[threading.Event] = None,
) -> None:
    """Send haptic packets to *host:port* at *rate_hz* Hz."""
    simulator = HapticSimulator()
    interval = 1.0 / rate_hz
    sent_packets = 0
    started_at = time.perf_counter()

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        print(f"hapticnet client sending to {host}:{port} rate={rate_hz}Hz samples={samples}")
        next_deadline = time.perf_counter()
        while (samples <= 0 or sent_packets < samples):
            if stop_event is not None and stop_event.is_set():
                break
            packet = simulator.next_packet()
            sock.sendto(packet.to_bytes(), (host, port))
            sent_packets += 1
            next_deadline += interval
            sleep_for = next_deadline - time.perf_counter()
            if sleep_for > 0:
                time.sleep(sleep_for)

        if samples > 0 and (stop_event is None or not stop_event.is_set()):
            end_marker = HapticPacket(
                sequence=0,
                timestamp_ns=time.time_ns(),
                pos_x=0.0, pos_y=0.0, pos_z=0.0,
                rot_w=0.0, rot_x=0.0, rot_y=0.0, rot_z=0.0,
                force=0.0, texture_id=-1,
            )
            for _ in range(3):
                sock.sendto(end_marker.to_bytes(), (host, port))
                time.sleep(0.002)
            sock.settimeout(2.0)
            try:
                payload, _ = sock.recvfrom(1024)
                message = payload.decode("utf-8", errors="strict")
                prefix = SUMMARY_RESPONSE_PREFIX
                if message.startswith(prefix):
                    packets_s, avg_s, min_s, max_s, duration_s = message[len(prefix):].split()
                    print(
                        "hapticnet stream summary "
                        f"packets={packets_s} "
                        f"lat(avg/min/max)={float(avg_s):.2f}/{float(min_s):.2f}/{float(max_s):.2f} ms "
                        f"duration={float(duration_s):.2f}s"
                    )
                    return
            except (TimeoutError, ValueError):
                pass

    duration_s = time.perf_counter() - started_at
    print(
        "hapticnet stream summary "
        f"packets={sent_packets} "
        "lat(avg/min/max)=0.00/0.00/0.00 ms "
        f"duration={duration_s:.2f}s"
    )


def run_client(
    host: str,
    port: int,
    rate_hz: int,
    samples: int = 1000,
    discover: bool = False,
    discovery_port: int = 9001,
    broadcast_ip: str = "255.255.255.255",
    timeout: float = 5.0,
    stop_event: Optional[threading.Event] = None,
) -> None:
    resolved_host = host
    resolved_port = port
    if discover:
        target = discover_receiver(
            discovery_port=discovery_port,
            timeout=timeout,
            broadcast_ip=broadcast_ip,
        )
        resolved_host, resolved_port_str = target.rsplit(":", 1)
        resolved_port = int(resolved_port_str)
        print(f"Discovered hapticnet server at {target}")

    run_sender(
        host=resolved_host,
        port=resolved_port,
        rate_hz=rate_hz,
        samples=samples,
        stop_event=stop_event,
    )


# ---------------------------------------------------------------------------
# Receiver / Server
# ---------------------------------------------------------------------------

def run_receiver(
    bind_host: str,
    port: int,
    buffer_size: int,
    enable_discovery: bool = True,
    discovery_port: int = 9001,
    stop_event: Optional[threading.Event] = None,
    packet_loss_rate: float = 0.0,
    on_packet: Optional[Callable[[dict], None]] = None,
) -> None:
    """
    Receive haptic packets and process them through the jitter buffer +
    dead-reckoning pipeline.

    Parameters
    ----------
    packet_loss_rate : float
        Probability [0.0, 1.0] that an incoming packet is artificially
        dropped to simulate network packet loss for DR testing.
    on_packet : callable, optional
        Called on every consumed or estimated packet with a dict:
            {"seq": int, "pos": [x,y,z], "latency_ms": float,
             "source": "real"|"dead_reckoned"}
    """
    jitter_buffer = JitterBuffer(capacity=buffer_size)
    reckoner = DeadReckoner()
    stats = ReceiverStats()

    stream_packets = 0
    stream_latency_sum_ms = 0.0
    stream_latency_samples = 0
    stream_latency_min_ms = float("inf")
    stream_latency_max_ms = 0.0
    stream_started_at = 0.0
    expected_seq = 1
    initialized_expected_seq = False
    missing_since = 0.0
    missing_wait_s = 0.03
    last_rx_at = 0.0
    dr_max_gap_s = 0.02
    last_dr_at = 0.0
    dr_emit_interval_s = 0.02
    rx_log_every = 10

    _stop = stop_event if stop_event is not None else threading.Event()

    discovery_thread: Optional[threading.Thread] = None
    if enable_discovery:
        discovery_thread = threading.Thread(
            target=_discovery_server,
            args=(port, discovery_port, _stop),
            daemon=True,
        )
        discovery_thread.start()

    # Mutable reference so the loss rate can be changed from another thread
    _loss = [max(0.0, min(1.0, packet_loss_rate))]

    def _set_loss(rate: float) -> None:
        _loss[0] = max(0.0, min(1.0, rate))

    # Attach setter as attribute so callers can hot-swap the loss rate
    run_receiver._set_loss = _set_loss  # type: ignore[attr-defined]

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.bind((bind_host, port))
            sock.settimeout(0.02)
            print(f"hapticnet server started on {bind_host}:{port} jitter_buffer={buffer_size}")

            while not _stop.is_set():
                try:
                    payload, sender_addr = sock.recvfrom(1024)
                    if len(payload) != PAYLOAD_SIZE:
                        continue

                    # ---- artificial packet loss injection ----
                    if _loss[0] > 0.0 and random.random() < _loss[0]:
                        continue  # drop for DR testing

                    seq = int.from_bytes(payload[0:4], "big", signed=False)
                    last_rx_at = time.perf_counter()

                    # end-of-stream marker
                    if seq == 0:
                        packet = HapticPacket.from_bytes(payload)
                        if packet.texture_id == -1:
                            if stream_packets == 0:
                                continue
                            duration_s = (
                                max(0.0, time.perf_counter() - stream_started_at)
                                if stream_started_at > 0
                                else 0.0
                            )
                            if stream_latency_samples > 0:
                                avg_latency_ms = stream_latency_sum_ms / stream_latency_samples
                                min_latency_ms = stream_latency_min_ms
                                max_latency_ms = stream_latency_max_ms
                            else:
                                avg_latency_ms = min_latency_ms = max_latency_ms = 0.0
                            print(
                                "hapticnet stream summary "
                                f"packets={stream_packets} "
                                f"lat(avg/min/max)={avg_latency_ms:.2f}/{min_latency_ms:.2f}/{max_latency_ms:.2f} ms"
                            )
                            summary = (
                                f"{SUMMARY_RESPONSE_PREFIX}"
                                f"{stream_packets} {avg_latency_ms:.6f} {min_latency_ms:.6f} {max_latency_ms:.6f} {duration_s:.6f}"
                            ).encode("utf-8")
                            sock.sendto(summary, sender_addr)
                            # reset state
                            stream_packets = 0
                            stream_latency_sum_ms = 0.0
                            stream_latency_samples = 0
                            stream_latency_min_ms = float("inf")
                            stream_latency_max_ms = 0.0
                            stream_started_at = 0.0
                            jitter_buffer = JitterBuffer(capacity=buffer_size)
                            reckoner = DeadReckoner()
                            expected_seq = 1
                            initialized_expected_seq = False
                            missing_since = 0.0
                            last_rx_at = 0.0
                            continue

                    if stream_started_at == 0.0:
                        stream_started_at = time.perf_counter()
                    if not initialized_expected_seq:
                        expected_seq = seq
                        initialized_expected_seq = True
                    if seq > expected_seq:
                        stats.out_of_order_packets += 1
                    jitter_buffer.add(seq, payload)

                except socket.timeout:
                    pass
                except ValueError:
                    continue

                in_order_payload = jitter_buffer.pop_expected(expected_seq)
                if in_order_payload is not None:
                    in_order = HapticPacket.from_bytes(in_order_payload)
                    reckoner.update(in_order)
                    stats.rx_packets += 1
                    stream_packets += 1
                    latency_ms = calculate_latency_ms(in_order.timestamp_ns)
                    stats.add_latency(latency_ms)
                    stream_latency_sum_ms += latency_ms
                    stream_latency_samples += 1
                    stream_latency_min_ms = min(stream_latency_min_ms, latency_ms)
                    stream_latency_max_ms = max(stream_latency_max_ms, latency_ms)
                    if in_order.sequence == 1 or (in_order.sequence % rx_log_every) == 0:
                        print(
                            f"hapticnet rx seq={in_order.sequence:04d} "
                            f"pos=({in_order.pos_x:+.3f},{in_order.pos_y:+.3f},{in_order.pos_z:+.3f}) "
                            f"lat={latency_ms:.2f}ms"
                        )
                    if on_packet is not None:
                        on_packet({
                            "seq": in_order.sequence,
                            "pos": [round(in_order.pos_x, 4), round(in_order.pos_y, 4), round(in_order.pos_z, 4)],
                            "force": round(in_order.force, 4),
                            "latency_ms": round(latency_ms, 3),
                            "source": "real",
                        })
                    expected_seq += 1
                    missing_since = 0.0
                    stats.report(expected_seq)
                    continue

                head_seq = jitter_buffer.peek_sequence()
                now = time.perf_counter()
                if head_seq is not None and head_seq > expected_seq:
                    if missing_since == 0.0:
                        missing_since = now
                    if (now - missing_since) < missing_wait_s:
                        stats.report(expected_seq)
                        continue
                else:
                    missing_since = 0.0

                if (time.perf_counter() - last_rx_at) > dr_max_gap_s:
                    stats.report(expected_seq)
                    continue

                estimated = reckoner.estimate(sequence=expected_seq, timestamp_ns=time.time_ns())
                if estimated is not None:
                    if (now - last_dr_at) < dr_emit_interval_s:
                        continue
                    last_dr_at = now
                    stats.estimated_packets += 1
                    stats.dropped_packets += 1
                    print(
                        f"hapticnet dr seq={estimated.sequence:04d} "
                        f"pos=({estimated.pos_x:+.3f},{estimated.pos_y:+.3f},{estimated.pos_z:+.3f})"
                    )
                    if on_packet is not None:
                        on_packet({
                            "seq": estimated.sequence,
                            "pos": [round(estimated.pos_x, 4), round(estimated.pos_y, 4), round(estimated.pos_z, 4)],
                            "force": round(estimated.force, 4),
                            "latency_ms": 0.0,
                            "source": "dead_reckoned",
                        })
                    expected_seq += 1
                    missing_since = 0.0
                    stats.report(expected_seq)
    finally:
        _stop.set()
        if discovery_thread is not None:
            discovery_thread.join(timeout=1.0)

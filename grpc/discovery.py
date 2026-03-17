import socket
import threading
from .config import DISCOVERY_REQUEST, DISCOVERY_RESPONSE_PREFIX

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
    if not message.startswith(DISCOVERY_RESPONSE_PREFIX):
        raise RuntimeError(f"Invalid discovery response: {message!r}")
    try:
        discovered_port = int(message[len(DISCOVERY_RESPONSE_PREFIX) :])
    except ValueError as exc:
        raise RuntimeError(f"Invalid discovered port in response: {message!r}") from exc
    return f"{addr[0]}:{discovered_port}"

def _discovery_server(grpc_port: int, discovery_port: int, stop_event: threading.Event) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("0.0.0.0", discovery_port))
        sock.settimeout(0.5)
        print(f"Discovery listener started on 0.0.0.0:{discovery_port} -> grpc port {grpc_port}")
        while not stop_event.is_set():
            try:
                payload, addr = sock.recvfrom(1024)
            except socket.timeout:
                continue
            except OSError:
                break

            if payload != DISCOVERY_REQUEST:
                continue

            response = f"{DISCOVERY_RESPONSE_PREFIX}{grpc_port}".encode("utf-8")
            sock.sendto(response, addr)

import math
import random
import time

from .models import HapticPacket

class HapticSimulator:
    """Generates deterministic high-frequency motion data for testing."""
    def __init__(self):
        self._sequence = 0
        self._start = time.perf_counter()

    def next_packet(self) -> HapticPacket:
        t = time.perf_counter() - self._start
        self._sequence += 1

        return HapticPacket(
            sequence=self._sequence,
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

def run_simulation(sample_count: int) -> None:
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

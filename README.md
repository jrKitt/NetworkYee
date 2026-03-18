# HAPTIC NETWORK

## app

```bash
# help
python3 -m hapticnet -h

# simulate packet
python3 -m hapticnet simulate --samples 10

# server
python3 -m hapticnet server --bind 0.0.0.0 --port 9000 --buffer 3

# client (local)
python3 -m hapticnet client --host 127.0.0.1 --port 9000 --rate 100 --samples 1000

# client (cross-machine)
python3 -m hapticnet client --host <SERVER_LAN_IP> --port 9000 --rate 100 --samples 1000

# client (auto-discovery)
python3 -m hapticnet client --discover --rate 100 --samples 1000
```

- Data: UDP `9000`
- Discovery: UDP `9001`

## grpc

```bash
# help
python3 -m grpc -h

# generate proto
python3 -m grpc gen-proto

# server
python3 -m grpc server --host 0.0.0.0 --port 50051

# client (local)
python3 -m grpc client --host 127.0.0.1 --port 50051 --rate 100 --samples 1000

# client (cross-machine)
python3 -m grpc client --host <SERVER_LAN_IP> --port 50051 --rate 100 --samples 1000

# client (auto-discovery)
python3 -m grpc client --discover --rate 100 --samples 1000
```

- Data: TCP `50051`
- Discovery: UDP `50052`

## dashboard (web simulate client)

```bash
# start dashboard backend + hapticnet server + grpc server (all in one)
python3 -m dashboard
```

Open `http://127.0.0.1:8080` for dashboard,
then open `http://127.0.0.1:8080/simulate` for **Web Sim Client (Mouse Drag)**:
- drag on the pad to stream position data
- choose `hapticnet`, `grpc`, or `both`
- choose payload mode: `position`, `position + force`, `full`

### One-liner: run separate client/server together (quick test)

```bash
python3 -m hapticnet server --bind 0.0.0.0 --port 9000 --buffer 3 & \
python3 -m grpc server --host 0.0.0.0 --port 50051 & \
sleep 1 && \
python3 -m hapticnet client --host 127.0.0.1 --port 9000 --rate 100 --samples 300 & \
python3 -m grpc client --host 127.0.0.1 --port 50051 --rate 100 --samples 300
```


# HapticNet Architecture Specification v3.0

**Architectural Review Document - Undergraduate Term Project**

## Document Control

| Version | Date         | Author              | Role      | Changes                                                  |
| ------- | ------------ | ------------------- | --------- | -------------------------------------------------------- |
| v3.0    | [28/02/2569] | Kittichai Raksawong | Architect | Upgraded to Custom Binary Payload & Dead Reckoning logic |

## Team Roles

| Role Name      | Assigned To       | Primary Responsibilities                                                     |
| -------------- | ----------------- | ---------------------------------------------------------------------------- |
| **Architect**  | Kittichai (Honda) | System design, Byte-level payload structure, Algorithm selection             |
| **Engineer**   | Aekkarin (Nai)    | UDP Socket implementation, Byte Serialization/Deserialization, Jitter Buffer |
| **Specialist** | Sorawit (Boat)    | High-frequency Data Simulator, Dead Reckoning mathematical modeling          |
| **DevOps**     | Phatsaporn (Waan) | Local network setup, Environment configuration, Version control              |
| **Tester/QA**  | Piyada (Yo)       | Packet loss injection, Stress testing, Jitter & Latency metric tracking      |

## Part 1: Executive Summary

### 1.1 Project Vision

The HapticNet project aims to engineer a highly efficient, low-latency network protocol for transmitting physical interaction data (Haptics) over a Local Area Network. By moving away from text-based payloads like JSON and utilizing raw Byte Array Serialization over UDP, the system minimizes network overhead. Furthermore, the project introduces packet loss compensation algorithms to maintain real-time fluidity.

### 1.2 Educational Objectives

- Implement deep networking concepts (UDP Sockets, Byte-level Data Serialization).
- Manage network anomalies by building a custom Application-level Jitter Buffer.
- Apply mathematical models (Linear Extrapolation/Dead Reckoning) to solve real-world packet loss issues.
- Understand the trade-offs between processing overhead and network payload size.

### 1.3 Scope and Constraints

| Aspect       | In Scope                                                               | Out of Scope                                |
| ------------ | ---------------------------------------------------------------------- | ------------------------------------------- |
| Architecture | UDP Client-Server topology via LAN, Jitter Buffer queueing             | TCP fallbacks, Global cloud deployment      |
| Payload      | Custom 52-Byte Haptic Data Structure (Seq, Timestamp, Pos, Rot, Force) | Text-based formats (JSON/XML)               |
| Reliability  | Dead Reckoning algorithm for packet loss compensation                  | Complex AI/Neural Network prediction models |

## Part 2: Architectural Review

### 2.1 Architecture Overview

| HapticNet Protocol Stack | Function                                              |
| ------------------------ | ----------------------------------------------------- |
| Application Layer        | Data Simulator & Dead Reckoning Extrapolation         |
| Presentation Layer       | Custom Byte Array Serialization (Bitwise operations)  |
| Transport Layer          | Standard UDP with custom Jitter Buffer implementation |
| Network Layer            | Local IPv4 Routing                                    |

### 2.2 Layer-by-Layer Architecture Review

#### 2.2.1 Presentation Layer - Custom Binary Payload

**Design Review Status: Approved**

- **Concept:** Data is packed into a strict 52-byte array to maximize throughput.
  - `Sequence (Int, 4 bytes)`
  - `Timestamp (Long, 8 bytes)`
  - `Position X/Y/Z (Float x3, 12 bytes)`
  - `Rotation W/X/Y/Z (Float x4, 16 bytes)`
  - `Force (Float, 4 bytes)` + `TextureID (Long, 8 bytes)`

#### 2.2.2 Transport & Application Layer - UDP + Jitter Buffer

**Design Review Status: Approved**

- **Concept:** UDP guarantees speed but not order. The receiver will implement a small Jitter Buffer (e.g., holding 3 packets) to reorder sequences. Packets arriving too late are dropped to prevent lag buildup.

#### 2.2.3 Application Layer - Dead Reckoning (Packet Loss Compensation)

**Design Review Status: Approved**

- **Concept:** When a packet is dropped, the system will not freeze. Instead, it will estimate the missing coordinates using Linear Extrapolation based on the velocity of previous packets.
- **Formula:** $P_{t} = P_{t-1} + (\vec{v} \cdot \Delta t)$

## Part 3: Architecture Decisions Log

- **Decision 1: Custom Binary over JSON.** (Approved) JSON introduces unnecessary string parsing overhead. A byte array forces strict typing and optimizes bandwidth.
- **Decision 2: Math over AI.** (Approved) Using a straightforward mathematical equation for Dead Reckoning provides predictable, low-latency compensation compared to training a high-overhead machine learning model.

## Part 4: Sign-off

- **Architect (Kittichai):** \***\*\_\_\_\_\*\***
- **Engineer (Aekkarin):** \***\*\_\_\_\_\*\***
- **Specialist (Sorawit):** \***\*\_\_\_\_\*\***
- **DevOps (Phatsaporn):** \***\*\_\_\_\_\*\***
- **Tester (Piyada):** \***\*\_\_\_\_\*\***
# NetworkYee Code Internals: Packet Flow, Translation, and Loss Handling

This document explains how the code works internally, with emphasis on:

- How packets are created, serialized, transmitted, received, and translated between producers/consumers.
- How packet loss is simulated and handled.
- How the dashboard unifies UDP (HapticNet) and gRPC streams for device-to-device testing.

## 1) High-Level Runtime Architecture

NetworkYee contains three runnable stacks:

- `hapticnet/`: custom UDP binary protocol.
- `grpc/`: gRPC streaming protocol.
- `dashboard/`: FastAPI server + WebSocket UI hub to control and compare both.

Typical run modes:

1. Protocol-only mode
   - Run `hapticnet` server/client directly.
   - Run `grpc` server/client directly.
2. Unified dashboard mode
   - Run `python3 -m dashboard`.
   - Dashboard starts both protocol servers through adapters.
   - Browser clients subscribe to one WebSocket feed (`/ws`) for all events.

## 2) Packet Model and Binary Translation (HapticNet)

Core files:

- `hapticnet/config.py`
- `hapticnet/models.py`
- `hapticnet/control.py`
- (legacy/parallel implementation also exists in `hapticnet/__main__.py`)

### 2.1 Fixed payload format

HapticNet uses a fixed binary layout (`PAYLOAD_FORMAT = "!Iq3f4ffq"`) defined in `hapticnet/config.py`.

Fields encoded in strict order:

1. sequence (4-byte int)
2. timestamp_ns (8-byte int)
3. pos_x, pos_y, pos_z (3 floats)
4. rot_w, rot_x, rot_y, rot_z (4 floats)
5. force (float)
6. texture_id (8-byte int)

Why this matters:

- Constant payload size means very predictable parsing cost.
- No JSON parsing overhead.
- Network byte order is explicit (big-endian), so sender and receiver interpret data identically.

### 2.2 Encode/decode boundary

`hapticnet.models.HapticPacket` is the translation boundary:

- `to_bytes()` translates structured values -> network payload bytes.
- `from_bytes()` translates bytes -> structured packet object.

This is the core "between device" translation for UDP peers: each device only needs to agree on this binary contract.

### 2.3 Byte offsets and decode strategy

From `hapticnet/config.py` and `hapticnet/logic.py`, the receiver uses two important offsets:

- `SEQUENCE_OFFSET = 0`
- `TEXTURE_ID_OFFSET = PAYLOAD_SIZE - 8`

Practical layout map (byte indices):

- `0..3` -> `sequence`
- `4..11` -> `timestamp_ns`
- `12..23` -> `pos_x, pos_y, pos_z`
- `24..39` -> `rot_w, rot_x, rot_y, rot_z`
- `40..43` -> `force`
- `44..51` -> `texture_id`

Decode is intentionally two-phase in the UDP receiver for performance:

1. **Fast path**: read only sequence (`_read_sequence`) to decide ordering and jitter-buffer behavior.
2. **Full decode path**: call `HapticPacket.from_bytes(...)` only when packet is actually consumed (or when checking special markers).

This reduces unnecessary unpack overhead when packets are buffered, dropped, or skipped.

### 2.4 Encode/decode reliability checks

`HapticPacket.from_bytes(...)` rejects malformed payloads by checking exact byte size (`PAYLOAD_SIZE`).

Reliability implications:

- Wrong-size UDP payloads are ignored early.
- Corrupted or incompatible packet formats fail fast before entering motion logic.
- Stream end marker is safely recognized by semantic values (`sequence == 0` and `texture_id == -1`) after decode.

### 2.5 Cross-device translation path (browser/device/protocol)

In dashboard mode, translation occurs in both directions:

1. Browser sends JSON to `POST /api/simulate/send`.
2. `dashboard/app.py` maps this JSON into canonical motion fields (`_sim_payload`).
3. Depending on target protocol:
   - HapticNet: instantiate `HapticPacket` -> `to_bytes()` -> UDP send.
   - gRPC: instantiate `HapticFrame` protobuf -> gRPC stream call.
4. On receive side, adapters normalize packets back to common event dict shape and push to WebSocket.

So the dashboard is not only a visual UI; it is also an active protocol translator between web payloads and network-native packet formats.

## 3) gRPC Frame Translation

Core files:

- `grpc/helloworld.proto`
- `grpc/client.py`
- `grpc/server.py`
- `grpc/models.py`

The gRPC path translates motion/force data through protobuf messages (`HapticFrame`) instead of manual struct packing.

Flow:

1. `grpc/client.py` generates frames in `_frame_stream(...)`.
2. Frames are streamed to `HapticBridge.StreamHaptics`.
3. `grpc/server.py` reads each frame and computes latency from `timestamp_ns`.

Compared with HapticNet:

- Translation is schema-driven by protobuf (generated code), not manual `struct`.
- Transport is TCP-based through gRPC runtime.
- Easier interoperability, at higher protocol overhead than raw UDP bytes.

## 4) End-to-End Packet Path (Sender -> Receiver)

## 4.1 HapticNet sender path

In `hapticnet/control.py`:

1. `HapticSimulator` generates synthetic motion packets.
2. `run_sender(...)` sends each packet over UDP at configured rate.
3. Optional stream-end marker is sent (`sequence=0`, `texture_id=-1`) so receiver can return stream summary.

### 4.2 HapticNet receiver path

In `run_receiver(...)`:

1. UDP datagram arrives.
2. Fast sequence extraction (`_read_sequence`) avoids full decode until needed.
3. Packet enters jitter buffer (`PacketBuffer` in `hapticnet/logic.py`).
4. Receiver attempts in-order consume by `expected_seq`.
5. On consume, it decodes packet, updates dead reckoner, computes one-way latency, and emits stats/event callbacks.

### 4.3 gRPC stream receiver path

In `grpc/server.py` (or dashboard `GrpcAdapter` servicer):

1. `StreamHaptics` iterates incoming `HapticFrame` stream.
2. Per frame: count packet, compute latency, aggregate min/max/avg metrics.
3. Emit periodic and final summary stats.

## 5) Translation Between Devices (Dashboard Bridge)

Core file: `dashboard/app.py`

The dashboard acts as a protocol bridge/control plane between different clients/devices:

- Browser sends control/simulation requests over HTTP.
- Dashboard converts browser payload to either:
  - UDP `HapticPacket` bytes (`_send_haptic_frame`), or
  - protobuf `HapticFrame` (`_send_grpc_frame`).
- Adapters (`dashboard/haptic_adapter.py`, `dashboard/grpc_adapter.py`) receive packets and push normalized event dictionaries into one async queue.
- `/ws` broadcasts these normalized events to all web clients.

This gives one UI view for both protocols even though underlying transports are very different.

## 6) Packet Loss Handling Strategy

NetworkYee handles packet loss in two layers:

- A) Loss simulation/injection for testing.
- B) Recovery/continuity logic for UDP stream quality.

### 6.1 Loss injection (test/chaos mode)

HapticNet (`hapticnet/control.py`):

- `packet_loss_rate` controls random dropping of received packets.
- If random threshold is hit, packet is skipped intentionally.
- Dashboard can update this at runtime through `HapticAdapter.set_packet_loss_rate(...)` and REST endpoint `/api/hapticnet/packet-loss`.

gRPC (`dashboard/grpc_adapter.py`):

- Adapter servicer also applies random drop using `_loss_ref[0]` for symmetric comparison testing.
- Controlled via `/api/grpc/packet-loss`.

### 6.2 Reordering and late-packet policy (UDP)

The UDP path has no delivery ordering guarantee, so receiver adds application-level control:

1. Small jitter buffer stores by sequence.
2. Receiver consumes only `expected_seq`.
3. If head sequence is ahead of expected, it waits briefly (`reorder_wait_s`) to allow missing packet arrival.
4. If still missing, behavior depends on dead-reckoning mode:
   - Dead reckoning off: skip missing gap and advance expected sequence to prevent lag accumulation.
   - Dead reckoning on: estimate missing packet(s) to keep motion continuity.

This policy prioritizes real-time smoothness over strict completeness.

### 6.3 Dead reckoning (UDP continuity)

Implemented in `hapticnet/logic.py` (`DeadReckoner`):

1. On every real packet, update velocity from position delta and time delta.
2. When packet(s) missing, estimate next position via linear extrapolation:

   `P_t = P_(t-1) + v * dt`

3. Keep orientation/force/texture based on last known packet.
4. Emit estimated packet as source `dead_reckoned`.

Guardrails in receiver:

- Max no-RX gap before DR stops (`dr_max_gap_s`) to avoid unbounded prediction drift.
- DR emit interval (`dr_emit_interval_s`) to cap synthetic output frequency.

### 6.3.1 Dead reckoning algorithm internals

`DeadReckoner` keeps:

- last real packet: `self._last_packet`
- estimated velocity vector: `self._velocity = (vx, vy, vz)`

On each **real** packet update:

1. Compute time delta:

   `dt = (t_now - t_prev) / 1e9`

2. If `dt > 0`, compute per-axis velocity:

   `vx = (x_now - x_prev) / dt`

   `vy = (y_now - y_prev) / dt`

   `vz = (z_now - z_prev) / dt`

3. Store current packet as new anchor.

On **missing** sequence estimation:

1. Compute prediction horizon from last anchor timestamp:

   `dt_pred = (t_est - t_anchor) / 1e9`

2. Extrapolate position:

   `x_est = x_anchor + vx * dt_pred`

   `y_est = y_anchor + vy * dt_pred`

   `z_est = z_anchor + vz * dt_pred`

3. Build synthetic packet with:
   - new `sequence` = expected missing sequence
   - new `timestamp_ns` = estimation time
   - orientation/force/texture copied from anchor packet

This keeps spatial motion smooth during short drop bursts while preserving non-positional fields from the latest trusted sample.

### 6.3.2 When dead reckoning is allowed to emit

In `run_receiver(...)`, DR emission is gated by state checks:

1. Receiver first waits for reorder window (`reorder_wait_s`) when head sequence is ahead.
2. If gap persists and DR mode is enabled, estimate one missing packet.
3. Throttle synthetic output by `dr_emit_interval_s`.
4. Stop DR if no real packets have arrived for too long (`dr_max_gap_s`).

This avoids uncontrolled free-running prediction and limits drift when the sender disappears.

### 6.3.3 Behavior when dead reckoning is disabled

If DR is disabled and a gap remains after reorder wait:

- Receiver counts dropped packets.
- `expected_seq` jumps forward to available head sequence.

Trade-off:

- Better real-time responsiveness and lower lag buildup.
- Visible motion discontinuity at loss points.

### 6.3.4 Accuracy limits and error characteristics

Because the estimator is linear and velocity-based:

- Works best for short gaps and near-linear motion.
- Error grows with longer outages or abrupt acceleration/turn changes.
- Guardrails (`dr_max_gap_s`, wait windows) are essential to keep error bounded in practice.

### 6.4 End-of-stream summary and reliability metrics

For finite runs, sender transmits an end marker and receiver returns summary including:

- received packet count
- average/min/max one-way latency
- duration

Stats classes (`ReceiverStats`, `StreamStats`) also track window-based rates and latency spread for live monitoring.

## 7) Discovery and Cross-Device Translation on LAN

Both protocol stacks support UDP broadcast discovery:

- HapticNet discovery: default UDP 9001.
- gRPC discovery: default UDP 50052.

Mechanism:

1. Client sends discovery request broadcast.
2. Server discovery listener replies with service port.
3. Client forms target `host:port` and starts stream.

This removes hard-coded IP dependency and makes device-to-device testing easier in shared LAN.

## 8) Practical Behavior Under Loss and Jitter

When loss/jitter increases:

- HapticNet with jitter buffer + DR attempts to preserve motion continuity at the cost of occasional estimated data.
- gRPC path (in dashboard comparison mode) may also intentionally drop for experiment parity, but does not implement the same application-level DR compensation logic.

So the project demonstrates two philosophies:

- Minimal-overhead custom transport with explicit real-time compensation logic.
- Framework-managed transport with stronger developer ergonomics.

## 9) Important Internal Notes

- There is duplicated/parallel logic in `hapticnet/__main__.py` and `hapticnet/control.py`; current modular path is centered around `control.py` and adapter usage in dashboard.
- `dashboard/grpc_adapter.py` contains explicit handling for local package name collision (`grpc/` folder vs installed `grpcio`) to ensure real `grpcio` is loaded for runtime.

## 10) Quick File Map (for reviewers)

- UDP payload contract and constants: `hapticnet/config.py`
- UDP packet model and stats model: `hapticnet/models.py`
- UDP sender/receiver/discovery/pipeline: `hapticnet/control.py`
- Reorder + dead reckoning primitives: `hapticnet/logic.py`
- gRPC client/server/stream stats: `grpc/client.py`, `grpc/server.py`, `grpc/models.py`
- gRPC discovery: `grpc/discovery.py`
- Dashboard API + simulation bridge: `dashboard/app.py`
- Dashboard protocol adapters: `dashboard/haptic_adapter.py`, `dashboard/grpc_adapter.py`

# HapticNet Implementation Plan v3.0

**4-Week Sprint Planning - Undergraduate Term Project**

## Document Control

| Version | Date         | Author               | Role   | Changes                                             |
| ------- | ------------ | -------------------- | ------ | --------------------------------------------------- |
| v3.0    | [28/02/2569] | Phatsaporn Musanthia | DevOps | Revised sprints for Binary Payload & Dead Reckoning |

## Part 1: Implementation Analysis

### 1.1 Complexity Assessment

| Component                    | Complexity (1-5) | Risk Level | Lead Owner           |
| ---------------------------- | ---------------- | ---------- | -------------------- |
| Custom Byte Serialization    | 4                | Medium     | Engineer (Aekkarin)  |
| UDP Socket + Jitter Buffer   | 4                | Medium     | Engineer (Aekkarin)  |
| Dead Reckoning Algorithm     | 4                | High       | Specialist (Sorawit) |
| Packet Loss Stress Testing   | 3                | Low        | Tester/QA (Piyada)   |
| Local Networking & Git Setup | 2                | Low        | DevOps (Phatsaporn)  |

### 1.2 Technical Debt Assessment

- **Bitwise Errors:** Incorrect byte shifting during serialization will corrupt the entire payload. Mitigation: Create strict unit tests for the encode/decode functions before attaching them to sockets.
- **Buffer Bloat:** A Jitter Buffer that is too large will artificially increase latency. Mitigation: Keep the buffer size minimal (e.g., <= 5 packets).

## Part 2: 4-Week Sprint Planning

### Week 1: Foundation Sprint (Data Structures & Sockets)

**Theme:** Binary Packing and Connection

- **DevOps (Phatsaporn):** Establish Git repository. Configure network environments for cross-machine testing.
- **Architect (Kittichai):** Finalize the exact byte offsets for the 52-byte Haptic payload.
- **Engineer (Aekkarin):** Write the Serialization/Deserialization classes using Bitwise operations or `ByteBuffer` in Java/Kotlin.
- **Specialist (Sorawit):** Develop the Data Simulator to generate random but continuous spatial data (simulating a moving hand).

### Week 2: Implementation Sprint (Transport & Queuing)

**Theme:** UDP and Jitter Management

- **Engineer (Aekkarin):** Implement UDP Client and Server. Build the Jitter Buffer logic on the Server side to sort incoming packets by Sequence ID and drop delayed packets.
- **Specialist (Sorawit):** Hook the Data Simulator into the UDP Client to stream data at 60Hz.
- **Architect (Kittichai):** Review network thread management to ensure the receiving socket does not block the main application thread.

### Week 3: Integration Sprint (Compensation & Chaos)

**Theme:** Dead Reckoning and Stress Testing

- **Specialist (Sorawit):** Implement the Dead Reckoning logic ($P_{t} = P_{t-1} + (\vec{v} \cdot \Delta t)$). If the Jitter Buffer is empty (packet loss), trigger the algorithm to generate the missing coordinate.
- **Tester (Piyada):** Develop a "Chaos Tool" to intentionally drop packets at specific rates (e.g., 5%, 15%, 30%) and observe if the Dead Reckoning can smoothly cover the gaps.

### Week 4: Delivery Sprint (Validation & Demo)

**Theme:** Metrics and Presentation

- **Tester (Piyada):** Compile final metrics (Bandwidth saved using Binary vs JSON, Latency measurements, Error rates before and after Dead Reckoning).
- **All:** Code freeze and repository cleanup.
- **Architect & Engineer:** Finalize architectural diagrams and code snippets for the slide deck.
- **DevOps:** Ensure the live demo environment is stable for the final presentation.

## Part 3: Sprint Review & Standup Protocol

- **Weekly Sync:** 30-minute code review every week focusing on algorithm efficiency and memory leaks.
- **Testing Gate:** Code cannot be merged into `main` until the Serialization unit tests pass 100%.

## Part 4: Success Criteria Sign-off

- [ ] System successfully packs and unpacks the 52-byte custom binary payload without data corruption.
- [ ] Jitter Buffer correctly reorders out-of-sequence packets and drops late arrivals.
- [ ] Dead Reckoning algorithm successfully estimates coordinates during simulated 15% packet loss.
- [ ] Project demonstrates a clear understanding of low-level networking and data structure optimization.

**(Signatures required from all 5 members prior to Sprint 1 commencement)**

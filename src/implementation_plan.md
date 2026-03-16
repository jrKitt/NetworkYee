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

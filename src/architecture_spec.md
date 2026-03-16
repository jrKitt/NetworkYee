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

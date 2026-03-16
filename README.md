# Getting Started

## 1) ดูคำสั่งทั้งหมด

```bash
python3 -m app -h
python3 -m grpc -h
```

## 2) Haptic Transport (app)

### 2.1 ทดสอบ payload ในเครื่องเดียว

```bash
python3 -m app simulate --samples 10
```

### 2.2 รันแบบ Local (เครื่องเดียว)

Terminal A (Server):

```bash
python3 -m app server --bind 0.0.0.0 --port 9000 --buffer 3
```

Terminal B (Client):

```bash
python3 -m app client --host 127.0.0.1 --port 9000 --rate 100
```

### 2.3 รันข้ามเครื่องใน LAN/Hotspot

Machine A (Server):

```bash
python3 -m app server --bind 0.0.0.0 --port 9000 --buffer 3
```

Machine B (Client):

```bash
python3 -m app client --host <SERVER_LAN_IP> --port 9000 --rate 100
```

### 2.4 Auto-discovery

Machine A (Server):

```bash
python3 -m app server --bind 0.0.0.0 --port 9000
```

Machine B (Client):

```bash
python3 -m app discover
python3 -m app client --discover --rate 100
```

### 2.5 Output ที่เพิ่มเข้ามา

- Receiver แสดง one-way latency ต่อแพ็กเก็ต: `lat=...ms`
- Receiver แสดงสรุปทุก ~1 วินาที: `lat(avg/min/max)=... ms`

หมายเหตุ:
- ค่า one-way latency จะแม่นเมื่อ clock ของสองเครื่องใกล้เคียงกัน
- ถ้า clock ต่างกันมาก อาจเห็น `lat=n/a`

### 2.6 Backward-compatible aliases

```bash
python3 -m app receive --bind 0.0.0.0 --port 9000 --buffer 3
python3 -m app send --host 127.0.0.1 --port 9000 --rate 100
```

## 3) gRPC Utilities (grpc)

### 3.1 Generate proto

```bash
python3 -m grpc gen-proto
```

### 3.2 รันแบบ Local (เครื่องเดียว)

Terminal A (Server):

```bash
python3 -m grpc server --host 0.0.0.0 --port 50051
```

Terminal B (Client):

```bash
python3 -m grpc client --host 127.0.0.1 --port 50051 --name NetworkYee
```

### 3.3 รันข้ามเครื่อง

Machine B (Client):

```bash
python3 -m grpc client --host <SERVER_LAN_IP> --port 50051 --name NetworkYee
```

### 3.4 Auto-discovery

```bash
python3 -m grpc client --discover --name NetworkYee
```

## 4) Firewall / Ports

- gRPC data: TCP `50051`
- gRPC discovery: UDP `50052`
- Haptic data: UDP `9000`
- Haptic discovery: UDP `9001`

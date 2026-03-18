# Getting Started

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

Open `http://127.0.0.1:8080` and use **Web Sim Client (Mouse Drag)**:
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

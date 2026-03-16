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

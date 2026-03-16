# Getting Started

```bash
# help
python3 -m app -h
python3 -m grpc -h

# run my app
python3 -m app simulate --samples 10 # test
python3 -m app receive --bind 0.0.0.0 --port 9000 --buffer 3 # server
python3 -m app send --host 127.0.0.1 --port 9000 --rate 100 # Local
python3 -m app send --host <SERVER_LAN_IP> --port 9000 --rate 100 # Machine

# run gRPC
python3 -m grpc gen-proto # generate protocol
python3 -m grpc server --host 0.0.0.0 --port 50051 # server + UDP discovery
python3 -m grpc client --host 127.0.0.1 --port 50051 --name NetworkYee # Local
python3 -m grpc client --host <SERVER_LAN_IP> --port 50051 --name NetworkYee # Machine [--timeout <value>]
python3 -m grpc client --discover --name NetworkYee # Broadcast discover IP + connect
```

> Ensure port `50051` is allowed through firewall on Machine A.
> For auto-discovery, also allow UDP port `50052`.

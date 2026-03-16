# Getting Started

``` bash
  python3 app
  python3 -m app simulate --samples 10
  python3 -m app receive --bind 0.0.0.0 --port 9000 --buffer 3
  python3 -m app send --host 127.0.0.1 --port 9000 --rate 100
  python3 -m grpc --help
  python3 -m grpc server --host 0.0.0.0 --port 50051
  python3 -m grpc client --host 127.0.0.1 --port 50051 --name NetworkYee
  python3 -m grpc gen-proto
  python3 grpc/server.py --host 0.0.0.0 --port 50051
  python3 grpc/client.py --host 127.0.0.1 --port 50051 --name NetworkYee
  bash grpc/gen_proto.sh
```

Cross-machine gRPC

``` bash
# Machine A (server)
python3 -m grpc server --host 0.0.0.0 --port 50051

# Machine B (client -> Machine A IP)
python3 -m grpc client --host <SERVER_LAN_IP> --port 50051 --name NetworkYee --timeout 5
```

> Ensure port `50051` is allowed through firewall on Machine A.

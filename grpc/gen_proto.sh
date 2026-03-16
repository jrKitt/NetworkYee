#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

python3 -m grpc_tools.protoc \
  -I "${SCRIPT_DIR}" \
  --python_out="${SCRIPT_DIR}" \
  --grpc_python_out="${SCRIPT_DIR}" \
  "${SCRIPT_DIR}/helloworld.proto"

echo "Generated: ${SCRIPT_DIR}/helloworld_pb2.py and ${SCRIPT_DIR}/helloworld_pb2_grpc.py"

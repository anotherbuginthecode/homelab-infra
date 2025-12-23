#!/usr/bin/env bash
set -euo pipefail

docker network create traefik-net >/dev/null 2>&1 || true
docker network create backend-net >/dev/null 2>&1 || true
docker network create observability-net >/dev/null 2>&1 || true

echo "Networks ready: traefik-net, backend-net, observability-net"

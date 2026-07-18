#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
[ -f .env ] || { echo 'ERROR: .env is missing. Copy .env.example and set secure values.'; exit 1; }
docker compose config >/dev/null
docker compose up -d --build --remove-orphans
./deploy/healthcheck.sh
echo 'Loyalyn deployment completed.'

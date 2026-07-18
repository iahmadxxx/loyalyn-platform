#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -f .env ]; then echo 'ERROR: .env is missing. Copy .env.example and set secure values.'; exit 1; fi
docker compose config >/dev/null
docker compose up -d --build
docker compose ps
curl --retry 10 --retry-delay 3 --fail http://127.0.0.1:8000/api/health
echo
echo 'Loyalyn deployment completed.'

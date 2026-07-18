#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose ps
printf '\nAPI: '
curl --retry 20 --retry-delay 3 --retry-connrefused --retry-all-errors --fail --silent --show-error http://127.0.0.1:8000/api/health
printf '\nFrontend: '
curl --retry 20 --retry-delay 3 --retry-connrefused --retry-all-errors --fail --silent --show-error --head http://127.0.0.1:3000 | head -n 1

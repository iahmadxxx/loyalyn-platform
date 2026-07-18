#!/usr/bin/env bash
set -euo pipefail
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"
python3 - <<'PY'
import json
from pathlib import Path
from urllib.parse import urlparse

lock = json.loads(Path('frontend/package-lock.json').read_text())
invalid = set()

def walk(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key == 'resolved' and isinstance(item, str):
                host = urlparse(item).netloc
                if host and host != 'registry.npmjs.org':
                    invalid.add(host)
            walk(item)
    elif isinstance(value, list):
        for item in value:
            walk(item)

walk(lock)
if invalid:
    raise SystemExit(f"Non-public npm registry hosts found: {sorted(invalid)}")
PY
grep -q '^registry=https://registry.npmjs.org/$' frontend/.npmrc
echo 'npm registry references are clean.'

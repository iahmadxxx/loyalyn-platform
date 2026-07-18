#!/usr/bin/env bash
set -euo pipefail
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"
python3 - <<'PY'
from pathlib import Path
p = Path('frontend/package-lock.json')
text = p.read_text()
old = 'https://packages.applied-caas-gateway1.internal.api.openai.org/artifactory/api/npm/npm-public/'
new = 'https://registry.npmjs.org/'
p.write_text(text.replace(old, new))
PY
grep -q 'registry.npmjs.org' frontend/package-lock.json
! grep -R -q 'applied-caas-gateway\|artifactory/api/npm' frontend/package-lock.json frontend/Dockerfile frontend/.npmrc
echo 'npm registry references are clean.'

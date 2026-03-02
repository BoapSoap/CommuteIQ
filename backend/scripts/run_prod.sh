#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${BACKEND_DIR}"

# In production, dependencies should already be installed.
# Optional ACS startup rebuild behavior is controlled by env:
# AUTO_BUILD_ACS_ON_STARTUP / ACS_BUILD_FORCE

exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"

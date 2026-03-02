#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${BACKEND_DIR}"

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

python -m pip install --upgrade pip
pip install -r requirements.txt

if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "Created backend/.env from .env.example. Update API keys before continuing."
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

if [ -z "${CENSUS_API_KEY:-}" ]; then
  echo "CENSUS_API_KEY missing in .env. Skipping ACS preprocessing."
elif [ ! -f "data/neighborhoods.geojson" ]; then
  echo "data/neighborhoods.geojson missing. Skipping ACS preprocessing."
else
  echo "Running ACS preprocessing..."
  python scripts/build_acs_neighborhoods.py
fi

exec uvicorn main:app --reload

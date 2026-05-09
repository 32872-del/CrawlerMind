#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

PYTHON_BIN="${PYTHON_BIN:-python3}"

if [ ! -d ".venv" ]; then
  "$PYTHON_BIN" -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
playwright install

if [ ! -f "clm_config.json" ]; then
  cp clm_config.example.json clm_config.json
  echo "Created clm_config.json. Edit it before enabling real LLM calls."
fi

echo "Setup complete. Activate with: source .venv/bin/activate"

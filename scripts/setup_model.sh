#!/bin/bash
# Install one registry model (config.MODELS) and pin its checkpoint hash. DOWNLOADS FILES — run only after
# the download has been approved. Nothing here runs a relaxation.
#
#   ./scripts/setup_model.sh mace-mpa-0-medium     # weights only (79.5 MB); uses the main venv (mace-torch)
#   ./scripts/setup_model.sh esen-30m-oam          # .envs/fairchem venv + gated checkpoint (accept the OMat24
#                                                  #   license on huggingface.co/fairchem/OMAT24 and `huggingface-cli login` first)
#   ./scripts/setup_model.sh sevennet-omni         # .envs/sevenn venv + checkpoint from figshare
#
# Afterwards: paste the printed sha256 into config.MODELS[<key>]["sha256"], then benchmark and run with
#   HARNESS_MODEL=<key> <python of that model> -m harness benchmark
set -euo pipefail
cd "$(dirname "$0")/.."
KEY="${1:?usage: setup_model.sh <model key>}"
read -r FILE URL ENV <<<"$(./uvw run --quiet python -c "
from harness.config import MODELS; m = MODELS['$KEY']; print(m['file'], m['url'], m['env'] or '-')")"
mkdir -p models
if [ ! -f "models/$FILE" ]; then
  case "$KEY" in
    esen-30m-oam) .tools/bin/uvx --from huggingface_hub huggingface-cli download fairchem/OMAT24 "$FILE" --local-dir models ;;
    *) curl -L --fail -o "models/$FILE" "$URL" ;;
  esac
fi
echo "sha256 of models/$FILE:"; shasum -a 256 "models/$FILE"
if [ "$ENV" != "-" ]; then
  PKGS=""
  case "$KEY" in
    esen-30m-oam) PKGS="fairchem-core" ;;
    sevennet-omni) PKGS="sevenn" ;;
  esac
  .tools/bin/uv venv --python 3.12 "$ENV"
  .tools/bin/uv pip install --python "$ENV/bin/python" -e . $PKGS
  echo "venv ready: $ENV (run the harness with $ENV/bin/python -m harness ..., HARNESS_MODEL=$KEY)"
fi

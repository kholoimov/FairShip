#!/usr/bin/env bash
set -euo pipefail

ship_root="$(cd "$(dirname "$0")/../.." && pwd)"
fairship_root="$ship_root/FairShip"
env_name="FairShip/latest-ci-release"

cd "$ship_root"
: "${SHIP_RELEASE:?SHIP_RELEASE is not set}"

source "/cvmfs/ship.cern.ch/${SHIP_RELEASE}/setUp.sh"

aliBuild build FairShip \
  --always-prefer-system \
  --config-dir "$SHIPDIST" \
  --defaults release \
  -z ci

if ! alienv_output="$(alienv load "$env_name" --no-refresh)"; then
  echo "ERROR: failed to load $env_name" >&2
  alienv q | grep FairShip || true
  exit 1
fi
eval "$alienv_output"

cd "$fairship_root"
python3 -m pytest tests/integration/test_simulation_references.py -m integration -v "$@"

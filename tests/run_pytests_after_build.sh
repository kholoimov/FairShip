#!/usr/bin/env bash
set -euo pipefail

ship_root="$(cd "$(dirname "$0")/../.." && pwd)"
fairship_root="$ship_root/FairShip"

cd "$ship_root"

: "${SHIP_RELEASE:?SHIP_RELEASE is not set}"

source "/cvmfs/ship.cern.ch/${SHIP_RELEASE}/setUp.sh"

aliBuild build FairShip \
  --always-prefer-system \
  --config-dir "$SHIPDIST" \
  --defaults release \
  -z ci

eval "$(alienv load FairShip/latest-ci-release --no-refresh)"

cd "$fairship_root"
python3 -m pytest tests/integration -m integration -v "$@"

#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "$script_dir/../.." && pwd)
work_dir=$(cd -- "$repo_root/.." && pwd)
output_dir=${FAIRSHIP_TEST_OUTPUT_DIR:-$repo_root/.pytest-sim-output}
mkdir -p "$output_dir"

build_command=${FAIRSHIP_BUILD_TEST_COMMAND:-"source /cvmfs/ship.cern.ch/26.04/setUp.sh && aliBuild build FairShip --force-rebuild FairShip --always-prefer-system --config-dir \"$SHIPDIST\" --defaults release -j ${FAIRSHIP_BUILD_TEST_JOBS:-100}"}
build_log="$output_dir/build_clean.log"

(
  cd "$work_dir"
  bash -lc "$build_command" | tee "$build_log"
)
touch "$output_dir/build_clean.ok"

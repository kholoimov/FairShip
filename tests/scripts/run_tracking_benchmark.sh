#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "$script_dir/../.." && pwd)
fairship_root=${FAIRSHIP:-$repo_root}
output_dir=${FAIRSHIP_TEST_OUTPUT_DIR:-$repo_root/.pytest-sim-output}
tag=${FAIRSHIP_TEST_TAG:-tracking_benchmark}
n_events=${FAIRSHIP_TRACKING_TEST_EVENTS:-1000}
seed=${FAIRSHIP_TRACKING_TEST_SEED:-42}
debug_level=${FAIRSHIP_TRACKING_TEST_FAIRLOGGER_DEBUG:-0}
pid=${FAIRSHIP_TRACKING_TEST_PID:-13}
estart=${FAIRSHIP_TRACKING_TEST_ESTART:-1.0}
eend=${FAIRSHIP_TRACKING_TEST_EEND:-100.0}
vz=${FAIRSHIP_TRACKING_TEST_VZ:-8300.0}
dx=${FAIRSHIP_TRACKING_TEST_DX:-200.0}
dy=${FAIRSHIP_TRACKING_TEST_DY:-300.0}
n_tracks=${FAIRSHIP_TRACKING_TEST_NTRACKS:-1}
tracking_reference=${FAIRSHIP_TRACKING_REFERENCE_JSON:-}

if [[ -n "${FAIRSHIP_TRACKING_ALIENV_PACKAGE:-}" ]]; then
  export FAIRSHIP_ALIENV_PACKAGE="$FAIRSHIP_TRACKING_ALIENV_PACKAGE"
fi

(
  cd "$output_dir"
  python3 "$fairship_root/macro/run_tracking_benchmark.py" \
    -n "$n_events" \
    --seed "$seed" \
    --debug "$debug_level" \
    --tag "$tag" \
    --output-json "$output_dir/tracking_metrics.json" \
    -o "$output_dir" \
    --pID "$pid" \
    --Estart "$estart" \
    --Eend "$eend" \
    --Vz "$vz" \
    --Dx "$dx" \
    --Dy "$dy" \
    --nTracks "$n_tracks"
)

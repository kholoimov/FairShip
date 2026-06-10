#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "$script_dir/../.." && pwd)

fairship_root=${FAIRSHIP:-$repo_root}
output_dir=${FAIRSHIP_TEST_OUTPUT_DIR:-$repo_root/.pytest-sim-output}
tag=${FAIRSHIP_TEST_TAG:-particle_gun_io}
if [[ -n "${FAIRSHIP_PARTICLE_GUN_ALIENV_PACKAGE:-}" ]]; then
  export FAIRSHIP_ALIENV_PACKAGE="$FAIRSHIP_PARTICLE_GUN_ALIENV_PACKAGE"
fi

n_events=${FAIRSHIP_PARTICLE_GUN_TEST_EVENTS:-100}
pid=${FAIRSHIP_PARTICLE_GUN_TEST_PID:-13}
estart=${FAIRSHIP_PARTICLE_GUN_TEST_ESTART:-1.0}
eend=${FAIRSHIP_PARTICLE_GUN_TEST_EEND:-10.0}
vz=${FAIRSHIP_PARTICLE_GUN_TEST_VZ:-8300.0}
dx=${FAIRSHIP_PARTICLE_GUN_TEST_DX:-50.0}
dy=${FAIRSHIP_PARTICLE_GUN_TEST_DY:-50.0}
debug_level=${FAIRSHIP_PARTICLE_GUN_TEST_FAIRLOGGER_DEBUG:-0}

python3 "$fairship_root/macro/run_simScript.py" \
  --tag "$tag" \
  --output "$output_dir" \
  -n "$n_events" \
  -s 42 \
  --debug "$debug_level" \
  --vacuums \
  PG \
  --pID "$pid" \
  --Estart "$estart" \
  --Eend "$eend" \
  --Vz "$vz" \
  --multiplePG \
  --Dx "$dx" \
  --Dy "$dy"

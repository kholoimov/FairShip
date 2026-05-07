#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "$script_dir/../.." && pwd)
fairship_root=${FAIRSHIP:-$repo_root}
output_dir=${FAIRSHIP_TEST_OUTPUT_DIR:-$repo_root/.pytest-sim-output}
tag=${FAIRSHIP_TEST_TAG:-pythia8_summary}
n_events=${FAIRSHIP_PYTHIA8_TEST_EVENTS:-1000}
debug_level=${FAIRSHIP_PYTHIA8_TEST_FAIRLOGGER_DEBUG:-0}

if [[ -n "${FAIRSHIP_PYTHIA8_ALIENV_PACKAGE:-}" ]]; then
  export FAIRSHIP_ALIENV_PACKAGE="$FAIRSHIP_PYTHIA8_ALIENV_PACKAGE"
fi
source "$script_dir/setup_fairship_env.sh"

python3 "$fairship_root/macro/run_simScript.py" \
  --Pythia8 \
  -t \
  -n "$n_events" \
  --debug "$debug_level" \
  -o "$output_dir" \
  --tag "$tag" \
  --seed 42

validation_stdout="$output_dir/sim_${tag}.validation.stdout"
python3 "$fairship_root/macro/validate_simulation_output.py" \
  -f "$output_dir/sim_${tag}.root" \
  -o "$output_dir/sim_${tag}.validation.json" \
  | tee "$validation_stdout" "$output_dir/sim_${tag}.validation.log"

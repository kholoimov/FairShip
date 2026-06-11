#!/usr/bin/env bash
set -euo pipefail

#line need to be configured
test_name="pixi_evtgen_summary"

#you can keep this part as it is
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "$script_dir/../.." && pwd)
output_dir=${FAIRSHIP_TEST_OUTPUT_DIR:-$repo_root/.pytest-pixi-output}
mkdir -p "$output_dir"

command_log="$output_dir/${test_name}.command.log"
exec > >(tee -a "$command_log") 2>&1
export PS4='+ ${BASH_SOURCE##*/}:${LINENO}: '
set -x

cd "$repo_root"

# put here your command to be run
pixi run python macro/run_simScript.py \
  --EvtGenDecayer \
  -t \
  -n 100 \
  --debug 0 \
  -o "$output_dir" \
  --tag evtgen_summary \
  --seed 42

# optional follow-up command for the same test
pixi run python macro/validate_simulation_output.py \
  -f "$output_dir/sim_evtgen_summary.root" \
  -o "$output_dir/sim_evtgen_summary.validation.json" \
  | tee "$output_dir/sim_evtgen_summary.validation.stdout" "$output_dir/sim_evtgen_summary.validation.log"

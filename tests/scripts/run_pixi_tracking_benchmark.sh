#!/usr/bin/env bash
set -euo pipefail

#line need to be configured
test_name="pixi_tracking_benchmark"

#you can keep this part as it is
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "$script_dir/../.." && pwd)
output_dir=${FAIRSHIP_TEST_OUTPUT_DIR:-$repo_root/.pytest-pixi-output}
mkdir -p "$output_dir"

command_log="$output_dir/${test_name}.command.log"
exec > >(tee -a "$command_log") 2>&1
export PS4='+ ${BASH_SOURCE##*/}:${LINENO}: '
set -x

cd "$output_dir"

# put here your command to be run
pixi run python "$repo_root/macro/run_tracking_benchmark.py" \
  -n 1000 \
  --seed 42 \
  --debug 0 \
  --tag tracking_benchmark \
  --output-json "$output_dir/tracking_metrics.json" \
  -o "$output_dir" \
  --pID 13 \
  --Estart 1.0 \
  --Eend 100.0 \
  --Vz 8300.0 \
  --Dx 200.0 \
  --Dy 300.0 \
  --nTracks 1

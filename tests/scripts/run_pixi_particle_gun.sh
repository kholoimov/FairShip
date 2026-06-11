#!/usr/bin/env bash
set -euo pipefail

#line need to be configured
test_name="pixi_particle_gun_io"

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
  --tag particle_gun_io \
  --output "$output_dir" \
  -n 100 \
  -s 42 \
  --debug 0 \
  --vacuums \
  PG \
  --pID 13 \
  --Estart 1.0 \
  --Eend 10.0 \
  --Vz 8300.0 \
  --multiplePG \
  --Dx 50.0 \
  --Dy 50.0

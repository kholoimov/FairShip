#!/usr/bin/env bash
set -euo pipefail

#line need to be configured
test_name="pixi_muonback_summary"

#you can keep this part as it is
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "$script_dir/../.." && pwd)
output_dir=${FAIRSHIP_TEST_OUTPUT_DIR:-$repo_root/.pytest-pixi-output}
mkdir -p "$output_dir"

command_log="$output_dir/${test_name}.command.log"
exec > >(tee -a "$command_log") 2>&1
export PS4='+ ${BASH_SOURCE##*/}:${LINENO}: '
set -x

input_file=${SHIP_TEST_INPUT:-${FAIRSHIP_SIM_TEST_INPUT:-/tmp/pythia8_Geant4_10.0_withCharmandBeauty0_mu.root}}
input_url=${FAIRSHIP_SIM_TEST_INPUT_URL:-https://cernbox.cern.ch/remote.php/dav/public-files/vdwtXtgM5P2Z0S5/pythia8_Geant4_10.0_withCharmandBeauty0_mu.root}

if [[ ! -f "$input_file" ]]; then
  mkdir -p "$(dirname "$input_file")"
  curl -L "$input_url" -o "$input_file"
fi

cd "$repo_root"

# put here your command to be run
pixi run python macro/run_simScript.py \
  -n 5000 \
  -i 100 \
  -f "$input_file" \
  -o "$output_dir" \
  --tag muonback_summary \
  --sameSeed 42 \
  --seed 42 \
  --MuonBack \
  --FollowMuon \
  --FastMuon

# optional follow-up command for the same test
pixi run python macro/validate_simulation_output.py \
  -f "$output_dir/sim_muonback_summary.root" \
  -o "$output_dir/sim_muonback_summary.validation.json" \
  | tee "$output_dir/sim_muonback_summary.validation.stdout" "$output_dir/sim_muonback_summary.validation.log"

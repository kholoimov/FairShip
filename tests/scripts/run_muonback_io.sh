#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "$script_dir/../.." && pwd)

fairship_root=${FAIRSHIP:-$repo_root}
output_dir=${FAIRSHIP_TEST_OUTPUT_DIR:-$repo_root/.pytest-sim-output}
tag=${FAIRSHIP_TEST_TAG:-muonback_io}
if [[ -n "${FAIRSHIP_SIM_IO_ALIENV_PACKAGE:-}" ]]; then
  export FAIRSHIP_ALIENV_PACKAGE="$FAIRSHIP_SIM_IO_ALIENV_PACKAGE"
fi
source "$script_dir/setup_fairship_env.sh"

input_file=${SHIP_TEST_INPUT:-${FAIRSHIP_SIM_IO_TEST_INPUT:-/tmp/pythia8_Geant4_10.0_withCharmandBeauty0_mu.root}}
n_events=${FAIRSHIP_SIM_IO_TEST_EVENTS:-100}
extra_args=${FAIRSHIP_SIM_IO_TEST_EXTRA_ARGS:---MuonBack --FollowMuon --FastMuon}

if [[ ! -f "$input_file" ]]; then
  echo "Muonback input file does not exist: $input_file" >&2
  echo "Set SHIP_TEST_INPUT or FAIRSHIP_SIM_IO_TEST_INPUT to point at a valid file." >&2
  exit 2
fi

python3 "$fairship_root/macro/run_simScript.py" \
  -n "$n_events" \
  -i 100 \
  -f "$input_file" \
  -o "$output_dir" \
  --tag "$tag" \
  --sameSeed 42 \
  --seed 42 \
  $extra_args

#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "$script_dir/../.." && pwd)
work_dir=$(cd -- "$repo_root/.." && pwd)

fairship_root=${FAIRSHIP:-$repo_root}
ship_release=${SHIP_RELEASE:-26.05}

# Avoid mixing the container Python with the one from the FairShip environment.
unset PYTHONHOME
unset PYTHONSTARTUP
unset PYTHONUSERBASE
export PYTHONPATH=${PYTHONPATH-}
export LD_LIBRARY_PATH=${LD_LIBRARY_PATH-}
export PATH=${PATH-}

local_sw_root=${ALIBUILD_SW_DIR:-}
if [[ -z "$local_sw_root" ]]; then
  local_sw_root=$(find "$work_dir/sw" -mindepth 1 -maxdepth 1 -type d -name "*_*" | head -n 1 || true)
fi

local_init_script=""
if [[ -n "$local_sw_root" && -f "$local_sw_root/FairShip/latest/etc/profile.d/init.sh" ]]; then
  local_init_script="$local_sw_root/FairShip/latest/etc/profile.d/init.sh"
fi

if [[ -z "${FAIRSHIP_ALIENV_PACKAGE:-}" ]]; then
  fairship_alienv_package="FairShip/latest-master-release"
else
  fairship_alienv_package=${FAIRSHIP_ALIENV_PACKAGE}
fi

set +u
source /cvmfs/ship.cern.ch/${ship_release}/setUp.sh
if [[ -n "$local_init_script" ]]; then
  source "$local_init_script"
else
  export ALIBUILD_WORK_DIR="$work_dir"
  eval "$(alienv load "${fairship_alienv_package}" --no-refresh)"
fi
set -u

export FAIRSHIP="$fairship_root"
export FAIRSHIP_ROOT="$fairship_root"
export VMCWORKDIR="$fairship_root"
export GEOMPATH="$fairship_root/geometry"
export CONFIG_DIR="$fairship_root/gconfig"
export OPENBLAS_NUM_THREADS=${OPENBLAS_NUM_THREADS:-1}
export OMP_NUM_THREADS=${OMP_NUM_THREADS:-1}
export MKL_NUM_THREADS=${MKL_NUM_THREADS:-1}
export NUMEXPR_NUM_THREADS=${NUMEXPR_NUM_THREADS:-1}
export PYTHONPATH="$fairship_root/python${PYTHONPATH:+:$PYTHONPATH}"

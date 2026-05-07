#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "$script_dir/../.." && pwd)

fairship_root=${FAIRSHIP:-$repo_root}
ship_release=${SHIP_RELEASE:-26.04}

# The CVMFS/FairShip setup scripts expect some variables to be unset-safe.
export PYTHONPATH=${PYTHONPATH-}
export LD_LIBRARY_PATH=${LD_LIBRARY_PATH-}
export PATH=${PATH-}

if [[ -z "${FAIRSHIP_ALIENV_PACKAGE:-}" ]]; then
  branch_name=$(git -C "$repo_root" rev-parse --abbrev-ref HEAD)
  branch_slug=${branch_name//\//-}
  fairship_alienv_package="FairShip/latest-${branch_slug}-release"
else
  fairship_alienv_package=${FAIRSHIP_ALIENV_PACKAGE}
fi

echo why_is_it_failing
set +u
source /cvmfs/ship.cern.ch/${ship_release}/setUp.sh
cd ../
eval "$(alienv load "${fairship_alienv_package}" --no-refresh)"
set -u
echo dont know

export FAIRSHIP="$fairship_root"
export PYTHONPATH="$fairship_root/python${PYTHONPATH:+:$PYTHONPATH}"

#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "$script_dir/../.." && pwd)

fairship_root=${FAIRSHIP:-$repo_root}
ship_release=${SHIP_RELEASE:-26.04}

if [[ -z "${FAIRSHIP_ALIENV_PACKAGE:-}" ]]; then
  branch_name=$(git -C "$repo_root" rev-parse --abbrev-ref HEAD)
  branch_slug=${branch_name//\//-}
  fairship_alienv_package="FairShip/latest-${branch_slug}-release"
else
  fairship_alienv_package=${FAIRSHIP_ALIENV_PACKAGE}
fi

source "/cvmfs/ship.cern.ch/${ship_release}/setUp.sh"
eval "$(alienv load "${fairship_alienv_package}" --no-refresh)"

export FAIRSHIP="$fairship_root"
export PYTHONPATH="$fairship_root/python${PYTHONPATH:+:$PYTHONPATH}"

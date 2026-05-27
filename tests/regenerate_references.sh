#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repo_root"

export FAIRSHIP=${FAIRSHIP:-$repo_root}
export FAIRSHIP_REGENERATE_REFERENCES=1

pytest tests/test_simulation_references.py "$@"

#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright CERN for the benefit of the SHiP Collaboration

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib


REPO_ROOT = Path(__file__).resolve().parents[1]
CASE_CONFIG_PATH = REPO_ROOT / "tests" / "pixi_reference_cases.toml"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Regenerate Pixi reference outputs")
    parser.add_argument(
        "-k",
        "--match",
        default=None,
        help="Only regenerate cases whose name contains this substring",
    )
    parser.add_argument(
        "--keep-output",
        action="store_true",
        help="Keep temporary case output directories under .reference-output",
    )
    return parser.parse_args()


def load_cases() -> list[dict[str, object]]:
    with CASE_CONFIG_PATH.open("rb") as handle:
        data = tomllib.load(handle)
    return data["case"]


def sanitize_tag(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", name)


def normalize_stdout(stdout: str, *, output_dir: Path) -> str:
    normalized = stdout.replace(str(output_dir), "{TMP_PATH}")
    normalized = re.sub(r"(?m)^(\+ [^:]+:\d+: )", "", normalized)
    return normalized.strip() + "\n"


def resolve_template(path_template: str, *, output_dir: Path) -> Path:
    return output_dir / path_template


def topo_sort_cases(cases: list[dict[str, object]]) -> list[dict[str, object]]:
    by_name = {case["name"]: case for case in cases}
    visited: set[str] = set()
    visiting: set[str] = set()
    ordered: list[dict[str, object]] = []

    def visit(name: str) -> None:
        if name in visited:
            return
        if name in visiting:
            raise RuntimeError(f"Cyclic dependency in Pixi reference cases at {name}")
        visiting.add(name)
        case = by_name[name]
        for dependency in case.get("depends_on", []):
            visit(dependency)
        visiting.remove(name)
        visited.add(name)
        ordered.append(case)

    for case in cases:
        visit(case["name"])

    return ordered


def run_case(case: dict[str, object], *, output_dir: Path) -> subprocess.CompletedProcess[str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["FAIRSHIP_TEST_OUTPUT_DIR"] = str(output_dir)
    env["FAIRSHIP_TEST_TAG"] = sanitize_tag(str(case["name"]))
    command = str(case["command"])
    bash_command = ["/bin/bash", "-lc", command]

    process = subprocess.Popen(
        bash_command,
        cwd=REPO_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    combined_output: list[str] = []
    assert process.stdout is not None
    for line in process.stdout:
        print(line, end="")
        combined_output.append(line)
    returncode = process.wait()
    stdout = "".join(combined_output)
    return subprocess.CompletedProcess(bash_command, returncode, stdout=stdout, stderr="")


def main() -> int:
    args = parse_args()
    cases = topo_sort_cases(load_cases())
    if args.match:
        wanted = {case["name"] for case in cases if args.match in str(case["name"])}
        expanded = set(wanted)
        by_name = {case["name"]: case for case in cases}
        for name in list(wanted):
            for dependency in by_name[name].get("depends_on", []):
                expanded.add(dependency)
        cases = [case for case in cases if case["name"] in expanded]

    output_root = REPO_ROOT / ".reference-output"
    output_root.mkdir(exist_ok=True)

    for case in cases:
        case_name = str(case["name"])
        print(f"\n=== Regenerating {case_name} ===")
        case_output_dir = output_root / sanitize_tag(case_name)
        if case_output_dir.exists():
            shutil.rmtree(case_output_dir)
        completed = run_case(case, output_dir=case_output_dir)
        expected_returncode = int(case.get("returncode", 0))
        if completed.returncode != expected_returncode:
            print(completed.stdout)
            print(
                f"Case {case_name} failed with return code {completed.returncode}, expected {expected_returncode}",
                file=sys.stderr,
            )
            return 1

        for output_template in case.get("expected_outputs", []):
            output_path = resolve_template(str(output_template), output_dir=case_output_dir)
            if not output_path.exists():
                print(f"Missing expected output for {case_name}: {output_path}", file=sys.stderr)
                return 1

        reference_path = REPO_ROOT / str(case["reference"])
        reference_path.write_text(normalize_stdout(completed.stdout, output_dir=case_output_dir), encoding="utf-8")
        print(f"Updated {reference_path}")

        if not args.keep_output:
            shutil.rmtree(case_output_dir)

    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright CERN for the benefit of the SHiP Collaboration

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
import xml.etree.ElementTree as ET


# we want to build and run FairShip from the parent directory of the FairShip folder
def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent

# making sure that folder for the test reports exists
def _reports_dir(repo_root: Path) -> Path:
    reports_dir = repo_root / "test_reports"
    reports_dir.mkdir(exist_ok=True)
    return reports_dir


def _python_tests_dir(repo_root: Path) -> Path:
    return repo_root / "tests" / "python"

# load all available tests from the "tests/python/cases"
def _load_matrix_cases(repo_root: Path) -> list[dict[str, object]]:
    python_dir = _python_tests_dir(repo_root)
    sys.path.insert(0, str(python_dir))
    from fairship_validation_runner import load_case_definitions

    config_dir = python_dir / "cases"
    return load_case_definitions(config_dir)


def _load_matrix_case_ids(repo_root: Path) -> list[str]:
    return [str(case["id"]) for case in _load_matrix_cases(repo_root)]

"""
build map based on case name in a format

{
    "build_clean": {...},
    "muonback_summary": {...},
    "pythia8_summary": {...},
}
"""
def _case_id_map(repo_root: Path) -> dict[str, dict[str, object]]:
    return {str(case["id"]): case for case in _load_matrix_cases(repo_root)}

# tests dependence map
def _dependency_closure(case_map: dict[str, dict[str, object]], selected: str) -> list[str]:
    ordered: list[str] = []
    visited: set[str] = set()

    def visit(case_id: str) -> None:
        if case_id in visited:
            return
        visited.add(case_id)
        for dependency in case_map[case_id].get("depends_on", []):
            visit(str(dependency))
        ordered.append(case_id)

    visit(selected)
    return ordered


def _pytest_executable() -> list[str]:
    return [sys.executable, "-m", "pytest"]


def _run_stage(name: str, command: list[str], repo_root: Path, env: dict[str, str] | None = None) -> dict[str, object]:
    print(f"\n=== {name} ===")
    print("Command:", " ".join(command))
    result = subprocess.run(command, cwd=repo_root, env=env)
    return {"name": name, "command": command, "returncode": result.returncode}


def _sum_junit_attributes(suites: list[ET.Element]) -> dict[str, str]:
    totals = {
        "tests": 0,
        "failures": 0,
        "errors": 0,
        "skipped": 0,
    }
    total_time = 0.0

    for suite in suites:
        for key in totals:
            totals[key] += int(float(suite.attrib.get(key, "0") or "0"))
        total_time += float(suite.attrib.get("time", "0") or "0")

    return {
        **{key: str(value) for key, value in totals.items()},
        "time": f"{total_time:.3f}",
    }

# combining all test results into one report file
def _combine_junit_reports(report_paths: list[Path], output_path: Path) -> Path | None:
    existing_reports = [path for path in report_paths if path.exists()]
    if not existing_reports:
        return None

    combined_root = ET.Element("testsuites")
    suites: list[ET.Element] = []

    for report_path in existing_reports:
        root = ET.parse(report_path).getroot()
        if root.tag == "testsuite":
            suites.append(root)
        elif root.tag == "testsuites":
            suites.extend(root.findall("testsuite"))
        else:
            raise ValueError(f"Unsupported JUnit XML root tag in {report_path}: {root.tag}")

    for suite in suites:
        combined_root.append(suite)

    combined_root.attrib.update(_sum_junit_attributes(suites))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(combined_root).write(output_path, encoding="utf-8", xml_declaration=True)
    return output_path


def _build_stage_command(reports_dir: Path) -> list[str]:
    return _pytest_executable() + [
        "-v",
        "-rA",
        "--tb=short",
        f"--junitxml={reports_dir / 'build.xml'}",
        "tests/python/test_build_clean.py",
    ]


def _runtime_stage_command(reports_dir: Path, jobs: int | None, test_name: str | None) -> list[str]:
    command = _pytest_executable() + [
        "-v",
        "-rA",
        "--tb=short",
        f"--junitxml={reports_dir / 'runtime.xml'}",
    ]
    if jobs and jobs > 1:
        command += ["-n", str(jobs)]
    test_filter = test_name if test_name else "not build_clean"
    command += ["-k", test_filter]
    command.append("tests/python/test_fairship_validation_matrix.py")
    return command


def _tracking_stage_command(reports_dir: Path) -> list[str]:
    return _pytest_executable() + [
        "-v",
        "-rA",
        "--tb=short",
        f"--junitxml={reports_dir / 'tracking.xml'}",
        "tests/python/test_tracking_benchmark.py",
    ]


def _print_summary(stages: list[dict[str, object]], report_paths: list[Path], combined_report: Path | None) -> None:
    print("\n=== Test Summary ===")
    for stage in stages:
        returncode = stage["returncode"]
        if returncode == 0:
            status = "PASSED"
        elif returncode is None:
            status = "SKIPPED"
        else:
            status = "FAILED"
        print(f"{status:7} {stage['name']}")

    print("\nJUnit reports:")
    for report_path in report_paths:
        if report_path.exists():
            print(f"  {report_path}")
    if combined_report is not None and combined_report.exists():
        print(f"  {combined_report}")


def _list_tests(repo_root: Path) -> int:
    print("Available tests:")
    for case_id in _load_matrix_case_ids(repo_root):
        print(f"  {case_id}")
    print("  tracking_benchmark")
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run FairShip tests with build-gated runtime execution."
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available test names and exit.",
    )
    parser.add_argument(
        "--test",
        default=None,
        help="Run only one named test. Runtime and tracking tests still require a successful build first.",
    )
    parser.add_argument(
        "--jobs",
        type=int,
        default=int(os.environ.get("FAIRSHIP_TEST_JOBS", "1")),
        help="Parallel pytest worker count for runtime matrix tests (default: FAIRSHIP_TEST_JOBS or 1).",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    repo_root = _repo_root()
    reports_dir = _reports_dir(repo_root)
    case_map = _case_id_map(repo_root)
    matrix_case_ids = list(case_map)
    runtime_case_ids = [case_id for case_id in matrix_case_ids if case_id != "build_clean"]
    all_tests = {"tracking_benchmark", *matrix_case_ids}

    if args.list:
        return _list_tests(repo_root)

    if args.test and args.test not in all_tests:
        print(f"Unknown test: {args.test}", file=sys.stderr)
        print("Use --list to see available tests.", file=sys.stderr)
        return 2

    stages: list[dict[str, object]] = []
    report_paths: list[Path] = []

    build_report = reports_dir / "build.xml"
    runtime_report = reports_dir / "runtime.xml"
    tracking_report = reports_dir / "tracking.xml"
    combined_report_path = reports_dir / "all_tests.xml"

    build_result = _run_stage("Build Validation", _build_stage_command(reports_dir), repo_root)
    stages.append(build_result)
    report_paths.append(build_report)

    if build_result["returncode"] != 0:
        if args.test and args.test == "build_clean":
            combined_report = _combine_junit_reports(report_paths, combined_report_path)
            _print_summary(stages, report_paths, combined_report)
            return int(build_result["returncode"])

        target_name = args.test or "runtime/tracking tests"
        stages.append(
            {
                "name": f"Blocked: {target_name}",
                "command": [],
                "returncode": None,
            }
        )
        combined_report = _combine_junit_reports(report_paths, combined_report_path)
        _print_summary(stages, report_paths, combined_report)
        return int(build_result["returncode"])

    if args.test == "build_clean":
        combined_report = _combine_junit_reports(report_paths, combined_report_path)
        _print_summary(stages, report_paths, combined_report)
        return 0

    if args.test == "tracking_benchmark":
        stages.append(
            _run_stage(
                "Tracking Benchmark Validation",
                _tracking_stage_command(reports_dir),
                repo_root,
            )
        )
        report_paths.append(tracking_report)
        combined_report = _combine_junit_reports(report_paths, combined_report_path)
        _print_summary(stages, report_paths, combined_report)
        return next(
            (int(stage["returncode"]) for stage in stages if stage["returncode"] not in (0, None)),
            0,
        )

    selected_runtime_cases: list[str] | None = None
    if args.test in runtime_case_ids:
        selected_runtime_cases = [
            case_id
            for case_id in _dependency_closure(case_map, args.test)
            if case_id != "build_clean"
        ]

    runtime_filter = None
    if selected_runtime_cases:
        runtime_filter = " or ".join(selected_runtime_cases)

    runtime_env = os.environ.copy()
    passed_tests = [entry for entry in runtime_env.get("FAIRSHIP_PASSED_TESTS", "").split(",") if entry]
    passed_tests.append("build_clean")
    runtime_env["FAIRSHIP_PASSED_TESTS"] = ",".join(sorted(set(passed_tests)))
    stages.append(
        _run_stage(
            "FairShip Runtime Tests",
            _runtime_stage_command(reports_dir, args.jobs, runtime_filter),
            repo_root,
            env=runtime_env,
        )
    )
    report_paths.append(runtime_report)

    if args.test is None:
        stages.append(
            _run_stage(
                "Tracking Benchmark Validation",
                _tracking_stage_command(reports_dir),
                repo_root,
            )
        )
        report_paths.append(tracking_report)

    combined_report = _combine_junit_reports(report_paths, combined_report_path)
    _print_summary(stages, report_paths, combined_report)
    return next(
        (int(stage["returncode"]) for stage in stages if stage["returncode"] not in (0, None)),
        0,
    )


if __name__ == "__main__":
    sys.exit(main())

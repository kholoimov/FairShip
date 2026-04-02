#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright CERN for the benefit of the SHiP Collaboration

import subprocess
import sys
from pathlib import Path


def run_stage(name, command, repo_root):
    print(f"\n=== {name} ===")
    print("Command:", " ".join(command))
    result = subprocess.run(command, cwd=repo_root)
    return {"name": name, "command": command, "returncode": result.returncode}


def main():
    repo_root = Path(__file__).resolve().parent.parent
    reports_dir = repo_root / "test_reports"
    reports_dir.mkdir(exist_ok=True)

    stages = []

    build_command = [
        "pytest",
        "-v",
        "-rA",
        "--tb=short",
        f"--junitxml={reports_dir / 'build.xml'}",
        "tests/test_build_clean.py",
    ]
    build_result = run_stage("Build Validation", build_command, repo_root)
    stages.append(build_result)

    if build_result["returncode"] == 0:
        validation_stages = [
            (
                "Simulation Validation",
                reports_dir / "simulation.xml",
                "tests/test_simulation_validation.py",
            ),
            (
                "Simulation IO Validation",
                reports_dir / "simulation_io.xml",
                "tests/test_simulation_io.py",
            ),
            (
                "Particle Gun IO Validation",
                reports_dir / "particle_gun_io.xml",
                "tests/test_particle_gun_io.py",
            ),
            (
                "Pythia8 Validation",
                reports_dir / "pythia8.xml",
                "tests/test_pythia8_validation.py",
            ),
            (
                "EvtGen Validation",
                reports_dir / "evtgen.xml",
                "tests/test_evtgen_validation.py",
            ),
            (
                "Tracking Benchmark Validation",
                reports_dir / "tracking.xml",
                "tests/test_tracking_benchmark.py",
            ),
        ]

        for name, report_path, test_path in validation_stages:
            command = [
                "pytest",
                "-v",
                "-rA",
                "--tb=short",
                f"--junitxml={report_path}",
                test_path,
            ]
            stages.append(run_stage(name, command, repo_root))
    else:
        for name, test_path in (
            ("Simulation Validation", "tests/test_simulation_validation.py"),
            ("Simulation IO Validation", "tests/test_simulation_io.py"),
            ("Particle Gun IO Validation", "tests/test_particle_gun_io.py"),
            ("Pythia8 Validation", "tests/test_pythia8_validation.py"),
            ("EvtGen Validation", "tests/test_evtgen_validation.py"),
            ("Tracking Benchmark Validation", "tests/test_tracking_benchmark.py"),
        ):
            stages.append(
                {
                    "name": name,
                    "command": ["pytest", test_path],
                    "returncode": None,
                }
            )

    print("\n=== Validation Summary ===")
    for stage in stages:
        if stage["returncode"] == 0:
            status = "PASSED"
        elif stage["returncode"] is None:
            status = "SKIPPED"
        else:
            status = "FAILED"
        print(f"{status:7} {stage['name']}")

    print("\nJUnit reports:")
    print(f"  {reports_dir / 'build.xml'}")
    print(f"  {reports_dir / 'simulation.xml'}")
    print(f"  {reports_dir / 'simulation_io.xml'}")
    print(f"  {reports_dir / 'particle_gun_io.xml'}")
    print(f"  {reports_dir / 'pythia8.xml'}")
    print(f"  {reports_dir / 'evtgen.xml'}")
    print(f"  {reports_dir / 'tracking.xml'}")

    for stage in stages:
        if stage["returncode"] not in (0, None):
            return stage["returncode"]
    return 0


if __name__ == "__main__":
    sys.exit(main())

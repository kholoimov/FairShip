#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright CERN for the benefit of the SHiP Collaboration

import argparse
import json
import os
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

import yaml


DEFAULT_INPUT_FILE = Path("/tmp/pythia8_Geant4_10.0_withCharmandBeauty0_mu.root")
DEFAULT_INPUT_URL = (
    "https://cernbox.cern.ch/remote.php/dav/public-files/vdwtXtgM5P2Z0S5/"
    "pythia8_Geant4_10.0_withCharmandBeauty0_mu.root"
)


def _repo_root():
    return Path(__file__).resolve().parent.parent


def _workdir(repo_root):
    return repo_root.parent


def _git_branch_name(repo_root):
    branch = os.environ.get("FAIRSHIP_GIT_BRANCH")
    if branch:
        return branch

    result = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _defaults_name():
    return os.environ.get("FAIRSHIP_ALIENV_DEFAULTS", "release")


def _alienv_package_name(repo_root):
    package = os.environ.get("FAIRSHIP_ALIENV_PACKAGE")
    if package:
        return package
    branch = _git_branch_name(repo_root)
    defaults = _defaults_name()
    return f"FairShip/latest-{branch}-{defaults}"


def _required_input_file():
    input_file = os.environ.get("SHIP_TEST_INPUT")
    if input_file:
        path = Path(input_file)
    else:
        path = DEFAULT_INPUT_FILE
        if not path.exists():
            urllib.request.urlretrieve(DEFAULT_INPUT_URL, path)
    if not path.exists():
        raise FileNotFoundError(
            "Simulation input file does not exist.\n"
            f"Checked path: {path}\n"
            "Override it with SHIP_TEST_INPUT if needed."
        )
    return path


def _shell_prefix(repo_root):
    return (
        "source /cvmfs/ship.cern.ch/26.03/setUp.sh && "
        f"eval \"$(alienv load {_alienv_package_name(repo_root)})\" && "
    )


def _run_shell_command(command, workdir, timeout):
    verbose = os.environ.get("FAIRSHIP_REFERENCE_DEBUG", "").lower() in {"1", "true", "yes", "on"}
    if verbose:
        print(f"\n[reference-gen] running in {workdir}")
        print(f"[reference-gen] command:\n{command}\n")
        process = subprocess.Popen(
            ["/bin/bash", "-lc", command],
            cwd=workdir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            shell=False,
        )
        combined_output = []
        assert process.stdout is not None
        for line in process.stdout:
            print(line, end="")
            combined_output.append(line)
        returncode = process.wait(timeout=timeout)
        output = "".join(combined_output)
        if returncode != 0:
            raise RuntimeError(
                "Reference generation command failed\n"
                f"Command: {command}\n"
                f"Workdir: {workdir}\n"
                f"Return code: {returncode}\n\n"
                f"STDOUT:\n{output}\n"
            )
        return subprocess.CompletedProcess(command, returncode, stdout=output, stderr="")

    result = subprocess.run(
        ["/bin/bash", "-lc", command],
        cwd=workdir,
        capture_output=True,
        text=True,
        timeout=timeout,
        shell=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "Reference generation command failed\n"
            f"Command: {command}\n"
            f"Workdir: {workdir}\n"
            f"Return code: {result.returncode}\n\n"
            f"STDOUT:\n{result.stdout}\n\n"
            f"STDERR:\n{result.stderr}"
        )
    return result


def _muonback_simulation_command(repo_root, output_dir, events):
    input_file = _required_input_file()
    return (
        _shell_prefix(repo_root)
        + f"python3 {repo_root / 'macro' / 'run_simScript.py'} "
        f"-n {events} "
        "-i 100 "
        "--MuonBack --FollowMuon --FastMuon "
        f"-f {input_file} "
        f"-o {output_dir} "
        "--tag muonback_fast_100 "
        "--sameSeed 42 "
        "--seed 42"
    )


def _particle_gun_simulation_command(repo_root, output_dir, events):
    return (
        _shell_prefix(repo_root)
        + f"python3 {repo_root / 'macro' / 'run_simScript.py'} "
        f"-n {events} "
        "-s 42 "
        "--debug 0 "
        "--vacuums "
        "--tag reference_run "
        f"-o {output_dir} "
        "PG "
        "--pID 13 "
        "--Estart 1.0 "
        "--Eend 10.0 "
        "--Vz 8300.0 "
        "--multiplePG "
        "--Dx 50.0 "
        "--Dy 50.0"
    )


def _pythia8_simulation_command(repo_root, output_dir, events):
    return (
        _shell_prefix(repo_root)
        + f"python3 {repo_root / 'macro' / 'run_simScript.py'} "
        "--Pythia8 "
        "-t "
        f"-n {events} "
        "--debug 0 "
        f"-o {output_dir} "
        "--tag pythia8_reference_run "
        "--seed 42"
    )


def _evtgen_simulation_command(repo_root, output_dir, events):
    return (
        _shell_prefix(repo_root)
        + f"python3 {repo_root / 'macro' / 'run_simScript.py'} "
        "--EvtGenDecayer "
        "-t "
        f"-n {events} "
        "--debug 0 "
        f"-o {output_dir} "
        "--tag evtgen_reference_run "
        "--seed 42"
    )


def _validation_command(repo_root, input_root, output_json):
    return (
        _shell_prefix(repo_root)
        + f"python3 {repo_root / 'macro' / 'validate_simulation_output.py'} "
        f"-f {input_root} "
        f"-o {output_json}"
    )


def _normalise_summary_json(path):
    payload = json.loads(path.read_text())
    payload.pop("input_file", None)
    return yaml.safe_dump(payload, sort_keys=True, default_flow_style=False)


def _generate_validation_summary(repo_root, workdir, config, reference_dir):
    with tempfile.TemporaryDirectory(prefix=f"fairship-{config['name']}-summary-") as tmpdir_name:
        tmpdir = Path(tmpdir_name)
        print(f"\n=== Regenerating {config['name']} summary reference ===")

        _run_shell_command(config["sim_command"](repo_root, tmpdir, config["summary_events"]), workdir, 7200)

        produced_root = tmpdir / config["produced_root"]
        produced_json = tmpdir / config["summary_json"].name
        _run_shell_command(_validation_command(repo_root, produced_root, produced_json), workdir, 3600)

        target_yaml = reference_dir / config["summary_yaml"]
        target_yaml.write_text(_normalise_summary_json(produced_json), encoding="utf-8")
        print(f"Wrote summary YAML: {target_yaml}")


def _generate_io_reference(repo_root, workdir, config, reference_dir):
    if not config.get("target_root"):
        return

    with tempfile.TemporaryDirectory(prefix=f"fairship-{config['name']}-io-") as tmpdir_name:
        tmpdir = Path(tmpdir_name)
        print(f"\n=== Regenerating {config['name']} ROOT I/O reference ===")

        _run_shell_command(config["sim_command"](repo_root, tmpdir, config["io_events"]), workdir, 7200)

        produced_root = tmpdir / config["produced_root"]
        target_root = reference_dir / config["target_root"]
        target_root.write_bytes(produced_root.read_bytes())
        print(f"Wrote ROOT reference: {target_root}")


def _generate_reference(repo_root, workdir, config):
    reference_dir = repo_root / "tests" / "reference"
    reference_dir.mkdir(parents=True, exist_ok=True)

    _generate_validation_summary(repo_root, workdir, config, reference_dir)
    _generate_io_reference(repo_root, workdir, config, reference_dir)


def _build_configs(muonback_events, muonback_io_events, particle_gun_events, particle_gun_io_events):
    return {
        "muonback": {
            "name": "muonback",
            "summary_events": muonback_events,
            "io_events": muonback_io_events,
            "sim_command": _muonback_simulation_command,
            "produced_root": "sim_muonback_fast_100.root",
            "target_root": "muonback_fast_100.root",
            "summary_json": Path("muonback_fast_100.json"),
            "summary_yaml": Path("muonback_fast_100.yaml"),
        },
        "particle_gun": {
            "name": "particle_gun",
            "summary_events": particle_gun_events,
            "io_events": particle_gun_io_events,
            "sim_command": _particle_gun_simulation_command,
            "produced_root": "sim_reference_run.root",
            "target_root": "sim_reference_run.root",
            "summary_json": Path("sim_reference_run.json"),
            "summary_yaml": Path("sim_reference_run.yaml"),
        },
        "pythia8": {
            "name": "pythia8",
            "summary_events": particle_gun_events,
            "sim_command": _pythia8_simulation_command,
            "produced_root": "sim_pythia8_reference_run.root",
            "summary_json": Path("pythia8_reference_run.json"),
            "summary_yaml": Path("pythia8_reference_run.yaml"),
        },
        "evtgen": {
            "name": "evtgen",
            "summary_events": particle_gun_events,
            "sim_command": _evtgen_simulation_command,
            "produced_root": "sim_evtgen_reference_run.root",
            "summary_json": Path("evtgen_reference_run.json"),
            "summary_yaml": Path("evtgen_reference_run.yaml"),
        },
    }


def build_parser():
    parser = argparse.ArgumentParser(
        description="Regenerate FairShip simulation YAML summaries and ROOT references."
    )
    parser.add_argument(
        "--target",
        choices=["all", "muonback", "particle_gun", "pythia8", "evtgen"],
        default="all",
        help="Which reference set to regenerate (default: all).",
    )
    parser.add_argument(
        "--muonback-events",
        type=int,
        default=5000,
        help="Number of events for the muon-background summary reference YAML (default: 5000).",
    )
    parser.add_argument(
        "--muonback-io-events",
        type=int,
        default=100,
        help="Number of events for the muon-background ROOT I/O reference (default: 100).",
    )
    parser.add_argument(
        "--particle-gun-events",
        type=int,
        default=5000,
        help="Number of events for the particle-gun summary reference YAML (default: 5000).",
    )
    parser.add_argument(
        "--particle-gun-io-events",
        type=int,
        default=100,
        help="Number of events for the particle-gun ROOT I/O reference (default: 100).",
    )
    parser.add_argument(
        "--pythia8-events",
        type=int,
        default=1000,
        help="Number of events for the Pythia8 reference (default: 1000).",
    )
    parser.add_argument(
        "--evtgen-events",
        type=int,
        default=1000,
        help="Number of events for the EvtGen reference (default: 1000).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Stream all subprocess output while generating references.",
    )
    return parser


def main():
    args = build_parser().parse_args()
    if args.verbose:
        os.environ["FAIRSHIP_REFERENCE_DEBUG"] = "1"
    if args.muonback_io_events > 100:
        raise ValueError(
            f"--muonback-io-events must be <= 100 for strict event-by-event I/O references, got {args.muonback_io_events}"
        )
    if args.particle_gun_io_events > 100:
        raise ValueError(
            "--particle-gun-io-events must be <= 100 for strict event-by-event I/O references, "
            f"got {args.particle_gun_io_events}"
        )
    repo_root = _repo_root()
    workdir = _workdir(repo_root)
    configs = _build_configs(
        args.muonback_events,
        args.muonback_io_events,
        args.particle_gun_events,
        args.particle_gun_io_events,
    )
    configs["pythia8"]["summary_events"] = args.pythia8_events
    configs["evtgen"]["summary_events"] = args.evtgen_events

    targets = ["muonback", "particle_gun", "pythia8", "evtgen"] if args.target == "all" else [args.target]

    for target in targets:
        _generate_reference(repo_root, workdir, configs[target])

    return 0


if __name__ == "__main__":
    sys.exit(main())

import json
import os
import subprocess
from pathlib import Path

import pytest
from simulation_reference_utils import compare_simulation_summary


DEFAULT_REFERENCE_JSON = Path("tests/reference/evtgen_reference_run.json")


def _repo_root():
    repo_root = os.environ.get("FAIRSHIP_REPO_ROOT")
    if repo_root:
        return Path(repo_root)
    cwd = Path.cwd()
    if cwd.name == "FairShip":
        return cwd
    return cwd / "FairShip"


def _run_workdir():
    workdir = os.environ.get("FAIRSHIP_EVTGEN_TEST_WORKDIR")
    if workdir:
        return Path(workdir)
    repo_root = _repo_root()
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
    package = os.environ.get("FAIRSHIP_EVTGEN_ALIENV_PACKAGE", os.environ.get("FAIRSHIP_ALIENV_PACKAGE"))
    if package:
        return package
    branch = _git_branch_name(repo_root)
    defaults = _defaults_name()
    return f"FairShip/latest-{branch}-{defaults}"


def _debug_enabled():
    return os.environ.get("FAIRSHIP_EVTGEN_TEST_DEBUG", "").lower() in {"1", "true", "yes", "on"}


def _run_shell_command(command, workdir, timeout):
    if not _debug_enabled():
        return subprocess.run(
            ["/bin/bash", "-lc", command],
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
        )

    print(f"\n[evtgen-test] running in {workdir}")
    print(f"[evtgen-test] command:\n{command}\n")

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
    return subprocess.CompletedProcess(command, returncode, stdout=output, stderr="")


def _reference_summary_file():
    reference = os.environ.get("FAIRSHIP_EVTGEN_REFERENCE_JSON")
    path = Path(reference) if reference else (_repo_root() / DEFAULT_REFERENCE_JSON)
    if not path.exists():
        pytest.fail(f"EvtGen JSON reference does not exist: {path}")
    return path


def _simulation_command(tmp_path, tag):
    repo_root = _repo_root()
    n_events = os.environ.get("FAIRSHIP_EVTGEN_TEST_EVENTS", "1000")
    debug = os.environ.get("FAIRSHIP_EVTGEN_TEST_FAIRLOGGER_DEBUG", "0")

    return (
        "source /cvmfs/ship.cern.ch/26.03/setUp.sh && "
        f"eval \"$(alienv load {_alienv_package_name(repo_root)})\" && "
        f"python3 {repo_root / 'macro' / 'run_simScript.py'} "
        "--EvtGenDecayer "
        "-t "
        f"-n {n_events} "
        f"--debug {debug} "
        f"-o {tmp_path} "
        f"--tag {tag} "
        "--seed 42"
    )


def _validation_command(tmp_path, tag):
    repo_root = _repo_root()
    sim_file = tmp_path / f"sim_{tag}.root"
    summary_file = tmp_path / f"sim_{tag}.validation.json"

    return (
        "source /cvmfs/ship.cern.ch/26.03/setUp.sh && "
        f"eval \"$(alienv load {_alienv_package_name(repo_root)})\" && "
        f"python3 {repo_root / 'macro' / 'validate_simulation_output.py'} "
        f"-f {sim_file} "
        f"-o {summary_file}"
    )


@pytest.mark.integration
@pytest.mark.timeout(7200)
def test_run_evtgen_and_validate_output(tmp_path):
    workdir = _run_workdir()
    tag = os.environ.get("FAIRSHIP_EVTGEN_TEST_TAG", "pytest_evtgen")
    reference = json.loads(_reference_summary_file().read_text())

    sim_command = _simulation_command(tmp_path, tag)
    sim_result = _run_shell_command(sim_command, workdir, 7200)

    (tmp_path / "evtgen.stdout").write_text(sim_result.stdout)
    (tmp_path / "evtgen.stderr").write_text(sim_result.stderr)
    (tmp_path / "evtgen.command").write_text(sim_command + "\n")

    assert sim_result.returncode == 0, (
        "EvtGen simulation command failed\n"
        f"Command: {sim_command}\n"
        f"Workdir: {workdir}\n"
        f"Return code: {sim_result.returncode}\n\n"
        f"STDOUT:\n{sim_result.stdout}\n\n"
        f"STDERR:\n{sim_result.stderr}"
    )

    sim_file = tmp_path / f"sim_{tag}.root"
    geo_file = tmp_path / f"geo_{tag}.root"
    par_file = tmp_path / f"params_{tag}.root"

    assert sim_file.exists(), f"Missing EvtGen simulation output file: {sim_file}"
    assert geo_file.exists(), f"Missing EvtGen geometry output file: {geo_file}"
    assert par_file.exists(), f"Missing EvtGen parameter output file: {par_file}"

    validation_command = _validation_command(tmp_path, tag)
    validation_result = _run_shell_command(validation_command, workdir, 3600)

    (tmp_path / "evtgen_validation.stdout").write_text(validation_result.stdout)
    (tmp_path / "evtgen_validation.stderr").write_text(validation_result.stderr)
    (tmp_path / "evtgen_validation.command").write_text(validation_command + "\n")

    assert validation_result.returncode == 0, (
        "EvtGen validation command failed\n"
        f"Command: {validation_command}\n"
        f"Workdir: {workdir}\n"
        f"Return code: {validation_result.returncode}\n\n"
        f"STDOUT:\n{validation_result.stdout}\n\n"
        f"STDERR:\n{validation_result.stderr}"
    )

    summary_file = tmp_path / f"sim_{tag}.validation.json"
    assert summary_file.exists(), f"Missing EvtGen validation summary JSON: {summary_file}"

    summary = json.loads(summary_file.read_text())

    assert summary["input_file"] == str(sim_file)
    assert summary["n_events"] == int(os.environ.get("FAIRSHIP_EVTGEN_TEST_EVENTS", "1000"))
    assert summary["metrics"]["mc_tracks"]["total"] > 0, "No MC tracks were recorded in EvtGen output"
    compare_simulation_summary(summary, reference)

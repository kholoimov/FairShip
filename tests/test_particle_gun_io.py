import json
import os
import subprocess
from pathlib import Path

import pytest
DEFAULT_REFERENCE_ROOT = Path("tests/reference/sim_reference_run.root")


def _repo_root():
    repo_root = os.environ.get("FAIRSHIP_REPO_ROOT")
    if repo_root:
        return Path(repo_root)
    cwd = Path.cwd()
    if cwd.name == "FairShip":
        return cwd
    return cwd / "FairShip"


def _run_workdir():
    workdir = os.environ.get("FAIRSHIP_PARTICLE_GUN_TEST_WORKDIR")
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
    package = os.environ.get("FAIRSHIP_PARTICLE_GUN_ALIENV_PACKAGE", os.environ.get("FAIRSHIP_ALIENV_PACKAGE"))
    if package:
        return package
    branch = _git_branch_name(repo_root)
    defaults = _defaults_name()
    return f"FairShip/latest-{branch}-{defaults}"


def _debug_enabled():
    return os.environ.get("FAIRSHIP_PARTICLE_GUN_TEST_DEBUG", "").lower() in {"1", "true", "yes", "on"}


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

    print(f"\n[particle-gun-test] running in {workdir}")
    print(f"[particle-gun-test] command:\n{command}\n")

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


def _reference_root_file():
    reference = os.environ.get("FAIRSHIP_PARTICLE_GUN_REFERENCE_ROOT")
    path = Path(reference) if reference else (_repo_root() / DEFAULT_REFERENCE_ROOT)
    if not path.exists():
        pytest.fail(f"Particle-gun ROOT reference does not exist: {path}")
    return path


def _n_events():
    n_events = int(os.environ.get("FAIRSHIP_PARTICLE_GUN_TEST_EVENTS", "100"))
    if n_events > 100:
        pytest.fail(
            "FAIRSHIP_PARTICLE_GUN_TEST_EVENTS must be <= 100 for event-by-event IO comparison, "
            f"got {n_events}"
        )
    return n_events


def _simulation_command(tmp_path, tag):
    repo_root = _repo_root()
    n_events = _n_events()
    pid = os.environ.get("FAIRSHIP_PARTICLE_GUN_TEST_PID", "13")
    estart = os.environ.get("FAIRSHIP_PARTICLE_GUN_TEST_ESTART", "1.0")
    eend = os.environ.get("FAIRSHIP_PARTICLE_GUN_TEST_EEND", "10.0")
    vz = os.environ.get("FAIRSHIP_PARTICLE_GUN_TEST_VZ", "8300.0")
    dx = os.environ.get("FAIRSHIP_PARTICLE_GUN_TEST_DX", "50.0")
    dy = os.environ.get("FAIRSHIP_PARTICLE_GUN_TEST_DY", "50.0")
    debug = os.environ.get("FAIRSHIP_PARTICLE_GUN_TEST_FAIRLOGGER_DEBUG", "0")

    return (
        "source /cvmfs/ship.cern.ch/26.03/setUp.sh && "
        f"eval \"$(alienv load {_alienv_package_name(repo_root)})\" && "
        f"python3 {repo_root / 'macro' / 'run_simScript.py'} "
        f"-n {n_events} "
        f"-s 42 "
        f"--debug {debug} "
        "--vacuums "
        f"--tag {tag} "
        f"-o {tmp_path} "
        "PG "
        f"--pID {pid} "
        f"--Estart {estart} "
        f"--Eend {eend} "
        f"--Vz {vz} "
        "--multiplePG "
        f"--Dx {dx} "
        f"--Dy {dy}"
    )


def _comparison_command(tmp_path, tag):
    repo_root = _repo_root()
    sim_file = tmp_path / f"sim_{tag}.root"
    reference_file = _reference_root_file()

    return (
        "source /cvmfs/ship.cern.ch/26.03/setUp.sh && "
        f"eval \"$(alienv load {_alienv_package_name(repo_root)})\" && "
        f"python3 {repo_root / 'macro' / 'compare_simulation_root_files.py'} "
        f"-r {reference_file} "
        f"-c {sim_file}"
    )


@pytest.mark.integration
@pytest.mark.timeout(7200)
def test_particle_gun_output_branch_layout(tmp_path):
    workdir = _run_workdir()
    tag = os.environ.get("FAIRSHIP_PARTICLE_GUN_TEST_TAG", "pytest_pg")

    sim_command = _simulation_command(tmp_path, tag)
    sim_result = _run_shell_command(sim_command, workdir, 7200)

    (tmp_path / "particle_gun.stdout").write_text(sim_result.stdout)
    (tmp_path / "particle_gun.stderr").write_text(sim_result.stderr)
    (tmp_path / "particle_gun.command").write_text(sim_command + "\n")

    assert sim_result.returncode == 0, (
        "Particle-gun simulation command failed\n"
        f"Command: {sim_command}\n"
        f"Workdir: {workdir}\n"
        f"Return code: {sim_result.returncode}\n\n"
        f"STDOUT:\n{sim_result.stdout}\n\n"
        f"STDERR:\n{sim_result.stderr}"
    )

    sim_file = tmp_path / f"sim_{tag}.root"
    assert sim_file.exists(), f"Missing particle-gun simulation output file: {sim_file}"

    validation_command = _comparison_command(tmp_path, tag)
    validation_result = _run_shell_command(validation_command, workdir, 3600)

    (tmp_path / "particle_gun_validation.stdout").write_text(validation_result.stdout)
    (tmp_path / "particle_gun_validation.stderr").write_text(validation_result.stderr)
    (tmp_path / "particle_gun_validation.command").write_text(validation_command + "\n")

    assert validation_result.returncode == 0, (
        "Particle-gun ROOT comparison failed\n"
        f"Command: {validation_command}\n"
        f"Workdir: {workdir}\n"
        f"Return code: {validation_result.returncode}\n\n"
        f"STDOUT:\n{validation_result.stdout}\n\n"
        f"STDERR:\n{validation_result.stderr}"
    )
    assert validation_result.stdout.strip().endswith("ROOT file comparison passed."), validation_result.stdout

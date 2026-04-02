import json
import os
import subprocess
import urllib.request
from pathlib import Path

import pytest
from simulation_reference_utils import compare_simulation_summary


DEFAULT_INPUT_FILE = Path(
    "/tmp/pythia8_Geant4_10.0_withCharmandBeauty0_mu.root"
)
DEFAULT_INPUT_URL = (
    "https://cernbox.cern.ch/remote.php/dav/public-files/vdwtXtgM5P2Z0S5/"
    "pythia8_Geant4_10.0_withCharmandBeauty0_mu.root"
)
DEFAULT_REFERENCE_JSON = Path("tests/reference/muonback_fast_100.json")


def _repo_root():
    repo_root = os.environ.get("FAIRSHIP_REPO_ROOT")
    if repo_root:
        return Path(repo_root)
    cwd = Path.cwd()
    if cwd.name == "FairShip":
        return cwd
    return cwd / "FairShip"


def _run_workdir():
    workdir = os.environ.get("FAIRSHIP_SIM_TEST_WORKDIR")
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
        pytest.fail(
            "Simulation input file does not exist.\n"
            f"Checked path: {path}\n"
            "Override it with SHIP_TEST_INPUT if needed."
        )
    return path


def _reference_summary_file():
    reference = os.environ.get("FAIRSHIP_SIM_TEST_REFERENCE_JSON")
    path = Path(reference) if reference else (_repo_root() / DEFAULT_REFERENCE_JSON)
    if not path.exists():
        if reference:
            pytest.fail(f"FAIRSHIP_SIM_TEST_REFERENCE_JSON does not exist: {path}")
        return None
    return path


def _debug_enabled():
    return os.environ.get("FAIRSHIP_SIM_TEST_DEBUG", "").lower() in {"1", "true", "yes", "on"}


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

    print(f"\n[simulation-test] running in {workdir}")
    print(f"[simulation-test] command:\n{command}\n")

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


def _simulation_command(tmp_path, tag):
    repo_root = _repo_root()
    input_file = _required_input_file()
    n_events = os.environ.get("FAIRSHIP_SIM_TEST_EVENTS", "5000")
    extra_args = os.environ.get("FAIRSHIP_SIM_TEST_EXTRA_ARGS", "--MuonBack --FollowMuon --FastMuon")

    return (
        "source /cvmfs/ship.cern.ch/26.03/setUp.sh && "
        f"eval \"$(alienv load {_alienv_package_name(repo_root)})\" && "
        f"python3 {repo_root / 'macro' / 'run_simScript.py'} "
        f"-n {n_events} "
        f"-i 100 "
        f"{extra_args} "
        f"-f {input_file} "
        f"-o {tmp_path} "
        f"--tag {tag} "
        f"--sameSeed 42 "
        f"--seed 42"
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
def test_run_simulation_and_validate_output(tmp_path):
    repo_root = _repo_root()
    workdir = _run_workdir()
    tag = os.environ.get("FAIRSHIP_SIM_TEST_TAG", "pytest_validation")
    reference_summary_file = _reference_summary_file()

    sim_command = _simulation_command(tmp_path, tag)
    sim_result = _run_shell_command(sim_command, workdir, 7200)

    (tmp_path / "simulation.stdout").write_text(sim_result.stdout)
    (tmp_path / "simulation.stderr").write_text(sim_result.stderr)
    (tmp_path / "simulation.command").write_text(sim_command + "\n")

    assert sim_result.returncode == 0, (
        "Simulation command failed\n"
        f"Command: {sim_command}\n"
        f"Workdir: {workdir}\n"
        f"Return code: {sim_result.returncode}\n\n"
        f"STDOUT:\n{sim_result.stdout}\n\n"
        f"STDERR:\n{sim_result.stderr}"
    )

    sim_file = tmp_path / f"sim_{tag}.root"
    geo_file = tmp_path / f"geo_{tag}.root"
    par_file = tmp_path / f"params_{tag}.root"

    assert sim_file.exists(), f"Missing simulation output file: {sim_file}"
    assert geo_file.exists(), f"Missing geometry output file: {geo_file}"
    assert par_file.exists(), f"Missing parameter output file: {par_file}"

    validation_command = _validation_command(tmp_path, tag)
    validation_result = _run_shell_command(validation_command, workdir, 3600)

    (tmp_path / "validation.stdout").write_text(validation_result.stdout)
    (tmp_path / "validation.stderr").write_text(validation_result.stderr)
    (tmp_path / "validation.command").write_text(validation_command + "\n")

    assert validation_result.returncode == 0, (
        "Validation command failed\n"
        f"Command: {validation_command}\n"
        f"Workdir: {workdir}\n"
        f"Return code: {validation_result.returncode}\n\n"
        f"STDOUT:\n{validation_result.stdout}\n\n"
        f"STDERR:\n{validation_result.stderr}"
    )

    summary_file = tmp_path / f"sim_{tag}.validation.json"
    assert summary_file.exists(), f"Missing validation summary JSON: {summary_file}"

    summary = json.loads(summary_file.read_text())

    assert summary["input_file"] == str(sim_file)
    assert summary["n_events"] > 0, "Simulation output contains zero events"
    assert "MCTrack" in summary["branches_present"], "MCTrack branch missing from cbmsim"
    assert summary["metrics"]["mc_tracks"]["total"] > 0, "No MC tracks were recorded"

    point_metrics = [
        metric_name
        for metric_name in ("sbt_hits", "ubt_hits", "straw_hits", "timedet_hits", "splitcal_hits")
        if metric_name in summary["metrics"]
    ]
    assert point_metrics, "Validation summary contains no detector hit metrics"
    assert any(summary["metrics"][metric_name]["total"] > 0 for metric_name in point_metrics), (
        "All detector hit metrics are zero\n"
        f"Summary: {json.dumps(summary, indent=2, sort_keys=True)}"
    )

    assert "Validation summary for" in validation_result.stdout
    assert str(sim_file) in validation_result.stdout

    if reference_summary_file is not None:
        reference_summary = json.loads(reference_summary_file.read_text())
        compare_simulation_summary(summary, reference_summary)

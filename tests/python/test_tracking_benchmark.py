import json
import os
import subprocess
from pathlib import Path

import pytest


def _repo_root():
    repo_root = os.environ.get("FAIRSHIP_REPO_ROOT")
    if repo_root:
        return Path(repo_root)
    cwd = Path.cwd()
    if cwd.name == "FairShip":
        return cwd
    return cwd / "FairShip"


def _run_workdir():
    workdir = os.environ.get("FAIRSHIP_TRACKING_TEST_WORKDIR")
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
    package = os.environ.get("FAIRSHIP_TRACKING_ALIENV_PACKAGE", os.environ.get("FAIRSHIP_ALIENV_PACKAGE"))
    if package:
        return package
    branch = _git_branch_name(repo_root)
    defaults = _defaults_name()
    return f"FairShip/latest-{branch}-{defaults}"


def _reference_metrics_file():
    reference = os.environ.get("FAIRSHIP_TRACKING_REFERENCE_JSON")
    if not reference:
        return None
    path = Path(reference)
    if not path.exists():
        pytest.fail(f"FAIRSHIP_TRACKING_REFERENCE_JSON does not exist: {path}")
    return path


def _debug_enabled():
    return os.environ.get("FAIRSHIP_TRACKING_TEST_DEBUG", "").lower() in {"1", "true", "yes", "on"}


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

    print(f"\n[tracking-test] running in {workdir}")
    print(f"[tracking-test] command:\n{command}\n")

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


def _shell_prefix():
    repo_root = _repo_root()
    return (
        "source /cvmfs/ship.cern.ch/26.03/setUp.sh && "
        f"eval \"$(alienv load {_alienv_package_name(repo_root)})\" && "
    )


def _simulation_command(tmp_path, tag):
    repo_root = _repo_root()
    n_events = os.environ.get("FAIRSHIP_TRACKING_TEST_EVENTS", "1000")
    seed = os.environ.get("FAIRSHIP_TRACKING_TEST_SEED", "42")
    debug = os.environ.get("FAIRSHIP_TRACKING_TEST_FAIRLOGGER_DEBUG", "0")

    return (
        _shell_prefix()
        + f"python3 {repo_root / 'macro' / 'run_simScript.py'} "
        f"-n {n_events} "
        f"-s {seed} "
        f"--debug {debug} "
        "--vacuums "
        "--SND "
        "--SND_design 2 "
        "--shieldName TRY_2025 "
        f"--tag {tag} "
        f"-o {tmp_path} "
        "PG "
        f"--pID {os.environ.get('FAIRSHIP_TRACKING_TEST_PID', '13')} "
        f"--Estart {os.environ.get('FAIRSHIP_TRACKING_TEST_ESTART', '1.0')} "
        f"--Eend {os.environ.get('FAIRSHIP_TRACKING_TEST_EEND', '100.0')} "
        f"--Vz {os.environ.get('FAIRSHIP_TRACKING_TEST_VZ', '8300.0')} "
        "--multiplePG "
        f"--Dx {os.environ.get('FAIRSHIP_TRACKING_TEST_DX', '200.0')} "
        f"--Dy {os.environ.get('FAIRSHIP_TRACKING_TEST_DY', '300.0')}"
    )


def _reconstruction_command(tmp_path, tag):
    repo_root = _repo_root()
    n_events = os.environ.get("FAIRSHIP_TRACKING_TEST_EVENTS", "1000")
    debug = os.environ.get("FAIRSHIP_TRACKING_TEST_FAIRLOGGER_DEBUG", "0")
    sim_file = tmp_path / f"sim_{tag}.root"
    geo_file = tmp_path / f"geo_{tag}.root"

    command = (
        _shell_prefix()
        + f"cd {tmp_path} && "
        + f"python3 {repo_root / 'macro' / 'ShipReco.py'} "
        f"-f {sim_file} "
        f"-g {geo_file} "
        f"-n {n_events} "
        "--realPR AR"
    )
    if debug != "0":
        command += " --Debug"
    return command


def _metrics_command(tmp_path, tag):
    repo_root = _repo_root()
    sim_file = tmp_path / f"sim_{tag}.root"
    geo_file = tmp_path / f"geo_{tag}.root"
    reco_file = tmp_path / f"sim_{tag}_rec.root"
    metrics_file = tmp_path / "tracking_metrics.json"
    histo_file = tmp_path / "tracking_benchmark_histos.root"

    return (
        _shell_prefix()
        + "python3 - <<'PY'\n"
        "import tracking_benchmark\n"
        f"bench = tracking_benchmark.TrackingBenchmark(r'{sim_file}', r'{reco_file}', r'{geo_file}')\n"
        "metrics = bench.compute_metrics()\n"
        f"bench.save_json(r'{metrics_file}')\n"
        f"bench.save_histograms(r'{histo_file}')\n"
        "bench.print_summary()\n"
        "PY"
    )


def _compare_against_reference(metrics, reference):
    assert metrics.keys() == reference.keys(), (
        "Tracking metric sections mismatch\n"
        f"Expected: {sorted(reference)}\n"
        f"Got: {sorted(metrics)}"
    )

    for section_name, section in reference.items():
        assert metrics[section_name].keys() == section.keys(), (
            f"Tracking metrics mismatch in section {section_name}\n"
            f"Expected: {sorted(section)}\n"
            f"Got: {sorted(metrics[section_name])}"
        )
        for metric_name, metric in section.items():
            assert metrics[section_name][metric_name] == metric, (
                f"Tracking metric mismatch for {section_name}.{metric_name}\n"
                f"Expected: {json.dumps(metric, indent=2, sort_keys=True)}\n"
                f"Got: {json.dumps(metrics[section_name][metric_name], indent=2, sort_keys=True)}"
            )


@pytest.mark.integration
@pytest.mark.timeout(7200)
def test_tracking_benchmark_validation(tmp_path):
    workdir = _run_workdir()
    reference_file = _reference_metrics_file()
    tag = os.environ.get("FAIRSHIP_TRACKING_TEST_TAG", "ci-benchmark")

    sim_file = tmp_path / f"sim_{tag}.root"
    geo_file = tmp_path / f"geo_{tag}.root"
    par_file = tmp_path / f"params_{tag}.root"
    reco_file = tmp_path / f"sim_{tag}_rec.root"
    metrics_file = tmp_path / "tracking_metrics.json"
    histo_file = tmp_path / "tracking_benchmark_histos.root"

    sim_command = _simulation_command(tmp_path, tag)
    sim_result = _run_shell_command(sim_command, workdir, 7200)
    (tmp_path / "tracking_sim.stdout").write_text(sim_result.stdout)
    (tmp_path / "tracking_sim.stderr").write_text(sim_result.stderr)
    (tmp_path / "tracking_sim.command").write_text(sim_command + "\n")

    assert sim_result.returncode == 0, (
        "Tracking simulation phase failed\n"
        f"Command: {sim_command}\n"
        f"Workdir: {workdir}\n"
        f"Return code: {sim_result.returncode}\n\n"
        f"STDOUT:\n{sim_result.stdout}\n\n"
        f"STDERR:\n{sim_result.stderr}"
    )
    assert sim_file.exists(), f"Missing simulation output file: {sim_file}"
    assert geo_file.exists(), f"Missing geometry output file: {geo_file}"
    assert par_file.exists(), f"Missing parameter output file: {par_file}"

    reco_command = _reconstruction_command(tmp_path, tag)
    reco_result = _run_shell_command(reco_command, workdir, 7200)
    (tmp_path / "tracking_reco.stdout").write_text(reco_result.stdout)
    (tmp_path / "tracking_reco.stderr").write_text(reco_result.stderr)
    (tmp_path / "tracking_reco.command").write_text(reco_command + "\n")

    assert reco_result.returncode == 0, (
        "Tracking reconstruction phase failed\n"
        f"Command: {reco_command}\n"
        f"Workdir: {workdir}\n"
        f"Return code: {reco_result.returncode}\n\n"
        f"STDOUT:\n{reco_result.stdout}\n\n"
        f"STDERR:\n{reco_result.stderr}"
    )
    assert reco_file.exists(), f"Missing reconstruction output file: {reco_file}"

    metrics_command = _metrics_command(tmp_path, tag)
    metrics_result = _run_shell_command(metrics_command, workdir, 3600)
    (tmp_path / "tracking_metrics.stdout").write_text(metrics_result.stdout)
    (tmp_path / "tracking_metrics.stderr").write_text(metrics_result.stderr)
    (tmp_path / "tracking_metrics.command").write_text(metrics_command + "\n")

    assert metrics_result.returncode == 0, (
        "Tracking metrics phase failed\n"
        f"Command: {metrics_command}\n"
        f"Workdir: {workdir}\n"
        f"Return code: {metrics_result.returncode}\n\n"
        f"STDOUT:\n{metrics_result.stdout}\n\n"
        f"STDERR:\n{metrics_result.stderr}"
    )

    assert metrics_file.exists(), f"Missing tracking metrics JSON: {metrics_file}"
    assert histo_file.exists(), f"Missing tracking histogram ROOT file: {histo_file}"
    assert histo_file.stat().st_size > 0, f"Tracking histogram file is empty: {histo_file}"

    metrics = json.loads(metrics_file.read_text())
    assert "tracking_benchmark" in metrics, "tracking_benchmark section missing from metrics JSON"
    benchmark = metrics["tracking_benchmark"]
    expected_events = int(os.environ.get("FAIRSHIP_TRACKING_TEST_EVENTS", "1000"))

    assert benchmark["n_events"]["value"] == expected_events
    assert benchmark["n_reconstructible"]["value"] > 0, "No reconstructible tracks found"
    assert benchmark["n_total_reco"]["value"] > 0, "No reconstructed tracks found"

    for metric_name in (
        "efficiency",
        "clone_rate",
        "ghost_rate",
        "dp_over_p_sigma",
        "dx_rms",
        "dy_rms",
        "dtx_rms",
        "dty_rms",
    ):
        assert metric_name in benchmark, f"Missing tracking metric: {metric_name}"
        assert "value" in benchmark[metric_name], f"Tracking metric has no value: {metric_name}"

    assert 0.0 <= benchmark["efficiency"]["value"] <= 1.0
    assert 0.0 <= benchmark["clone_rate"]["value"] <= 1.0
    assert 0.0 <= benchmark["ghost_rate"]["value"] <= 1.0

    if reference_file is not None:
        reference_metrics = json.loads(reference_file.read_text())
        _compare_against_reference(metrics, reference_metrics)

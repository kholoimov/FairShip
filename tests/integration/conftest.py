from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class SimChainOutputs:
    workdir: Path
    sim_file: Path
    geo_file: Path
    reco_file: Path
    ana_file: Path


def _build_runtime_env() -> dict[str, str]:
    env = os.environ.copy()
    pythonpath_entries = [str(REPO_ROOT), str(REPO_ROOT / "python")]
    existing_pythonpath = env.get("PYTHONPATH")
    if existing_pythonpath:
        pythonpath_entries.append(existing_pythonpath)
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_entries)
    env.setdefault("FAIRSHIP", str(REPO_ROOT))

    try:
        subprocess.run(
            [sys.executable, "-c", "import ROOT; import shipRoot_conf"],
            cwd=REPO_ROOT,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        pytest.skip(
            "Integration tests require a configured FairShip runtime "
            f"(ROOT + shipRoot_conf importable via {sys.executable}): {exc}"
        )

    return env


def _format_failure(command: list[str], cwd: Path, result: subprocess.CompletedProcess[str]) -> str:
    return "\n".join(
        [
            f"Command failed with exit code {result.returncode}",
            f"cwd: {cwd}",
            f"command: {' '.join(command)}",
            "",
            "stdout:",
            result.stdout,
            "",
            "stderr:",
            result.stderr,
        ]
    )


@pytest.fixture(scope="session")
def fairship_runtime_env() -> dict[str, str]:
    return _build_runtime_env()


@pytest.fixture
def integration_workspace(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def run_fairship(fairship_runtime_env: dict[str, str], integration_workspace: Path):
    def _run(script: str, *args: object, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        workdir = cwd or integration_workspace
        command = [sys.executable, str(REPO_ROOT / script), *(str(arg) for arg in args)]
        result = subprocess.run(
            command,
            cwd=workdir,
            env=fairship_runtime_env,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            pytest.fail(_format_failure(command, workdir, result), pytrace=False)
        return result

    return _run


@pytest.fixture(scope="session")
def sim_chain(
    fairship_runtime_env: dict[str, str], tmp_path_factory: pytest.TempPathFactory
) -> SimChainOutputs:
    workdir = tmp_path_factory.mktemp("sim-chain")

    commands = [
        [
            "macro/run_simScript.py",
            "--test",
            "--debug",
            "2",
            "--vacuums",
            "--SND",
            "--SND_design=all",
            "--shieldName",
            "TRY_2025",
            "--EvtGenDecayer",
            "--tag",
            "pytest-int",
        ],
        [
            "macro/ShipReco.py",
            "-f",
            "sim_pytest-int.root",
            "-g",
            "geo_pytest-int.root",
            "--patRec",
            "AR",
            "--Debug",
        ],
        [
            "macro/ShipAna.py",
            "-f",
            "sim_pytest-int.root",
            "-r",
            "sim_pytest-int_rec.root",
            "-g",
            "geo_pytest-int.root",
        ],
    ]

    for parts in commands:
        command = [sys.executable, str(REPO_ROOT / parts[0]), *parts[1:]]
        result = subprocess.run(
            command,
            cwd=workdir,
            env=fairship_runtime_env,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            pytest.fail(_format_failure(command, workdir, result), pytrace=False)

    outputs = SimChainOutputs(
        workdir=workdir,
        sim_file=workdir / "sim_pytest-int.root",
        geo_file=workdir / "geo_pytest-int.root",
        reco_file=workdir / "sim_pytest-int_rec.root",
        ana_file=workdir / "sim_pytest-int_ana.root",
    )

    for output_file in outputs.sim_file, outputs.geo_file, outputs.reco_file, outputs.ana_file:
        assert output_file.exists(), f"Expected output file was not created: {output_file}"

    return outputs

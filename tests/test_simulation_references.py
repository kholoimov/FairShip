from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib


REPO_ROOT = Path(__file__).resolve().parents[1]
CASE_CONFIG_PATH = REPO_ROOT / "tests" / "pytest_reference_cases.toml"
REGENERATE_ENV = "FAIRSHIP_REGENERATE_REFERENCES"
LIVE_LOGS_ENV = "FAIRSHIP_TEST_LIVE_LOGS"


def _load_cases() -> list[dict[str, str]]:
    with CASE_CONFIG_PATH.open("rb") as handle:
        data = tomllib.load(handle)
    return data["case"]


def _sanitize_tag(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", name)


def _resolve_template(path_template: str, *, tag: str, output_dir: Path) -> Path:
    return output_dir / path_template.format(tag=tag)


def _normalize_stdout(stdout: str, *, output_dir: Path, tag: str) -> str:
    normalized = stdout.replace(str(output_dir), "{TMP_PATH}")
    normalized = normalized.replace(str(output_dir / f"sim_{tag}.root"), f"{{TMP_PATH}}/sim_{tag}.root")
    normalized = normalized.replace(str(output_dir / f"geo_{tag}.root"), f"{{TMP_PATH}}/geo_{tag}.root")
    normalized = normalized.replace(str(output_dir / f"params_{tag}.root"), f"{{TMP_PATH}}/params_{tag}.root")
    normalized = normalized.replace(str(output_dir / f"sim_{tag}.validation.json"), f"{{TMP_PATH}}/sim_{tag}.validation.json")
    normalized = normalized.replace(str(output_dir / "tracking_metrics.json"), "{TMP_PATH}/tracking_metrics.json")
    normalized = normalized.replace(str(output_dir / "tracking_benchmark_histos.root"), "{TMP_PATH}/tracking_benchmark_histos.root")
    return normalized


def _run_case(case: dict[str, str], *, output_dir: Path) -> subprocess.CompletedProcess[str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    tag = _sanitize_tag(case["name"])

    env = os.environ.copy()
    env.setdefault("FAIRSHIP", str(REPO_ROOT))
    env["FAIRSHIP_TEST_OUTPUT_DIR"] = str(output_dir)
    env["FAIRSHIP_TEST_TAG"] = tag

    command = case["command"]
    bash_command = ["/bin/bash", "-lc", command]
    if os.environ.get(LIVE_LOGS_ENV, "").lower() in {"1", "true", "yes", "on"}:
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

    completed = subprocess.run(
        bash_command,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    return completed


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    if "case" not in metafunc.fixturenames:
        return
    cases = _load_cases()
    metafunc.parametrize("case", cases, ids=[case["name"] for case in cases])


def test_case_config_exists() -> None:
    assert CASE_CONFIG_PATH.exists(), f"Missing case configuration file: {CASE_CONFIG_PATH}"


@pytest.mark.reference
def test_simulation_reference(case: dict[str, str], tmp_path_factory: pytest.TempPathFactory) -> None:
    reference_path = REPO_ROOT / case["reference"]
    output_dir = tmp_path_factory.mktemp(f"{_sanitize_tag(case['name'])}-")
    assert reference_path.exists(), (
        f"Missing reference file: {reference_path}. "
        "Generate it with `bash tests/regenerate_references.sh`."
    )
    completed = _run_case(case, output_dir=output_dir)
    tag = _sanitize_tag(case["name"])
    stdout = _normalize_stdout(completed.stdout, output_dir=output_dir, tag=tag)
    stderr = completed.stderr
    expected_returncode = int(case.get("returncode", 0))
    expected_outputs = case.get("expected_outputs", [])

    if os.environ.get(REGENERATE_ENV) == "1":
        reference_path.parent.mkdir(parents=True, exist_ok=True)
        reference_path.write_text(stdout, encoding="utf-8")
        expected_stdout = stdout
    else:
        expected_stdout = reference_path.read_text(encoding="utf-8")

    assert completed.returncode == expected_returncode, (
        f"Return code mismatch for {case['name']} ({reference_path})\n"
        f"STDOUT:\n{stdout}\n"
        f"STDERR:\n{stderr}"
    )
    assert stdout == expected_stdout, (
        f"Stdout snapshot mismatch for {case['name']} ({reference_path})\n"
        f"STDOUT:\n{stdout}\n"
        f"STDERR:\n{stderr}"
    )

    for output_template in expected_outputs:
        output_path = _resolve_template(output_template, tag=tag, output_dir=output_dir)
        assert output_path.exists(), (
            f"Missing expected output for {case['name']}: {output_path}\n"
            f"STDOUT:\n{stdout}\n"
            f"STDERR:\n{stderr}"
        )

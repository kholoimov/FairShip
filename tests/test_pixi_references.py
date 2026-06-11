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
CASE_CONFIG_PATH = REPO_ROOT / "tests" / "pixi_reference_cases.toml"
LIVE_LOGS_ENV = "FAIRSHIP_TEST_LIVE_LOGS"
CASE_RESULTS: dict[str, bool] = {}


def _load_cases() -> list[dict[str, str]]:
    with CASE_CONFIG_PATH.open("rb") as handle:
        data = tomllib.load(handle)
    return data["case"]


def _sanitize_tag(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", name)


def _resolve_template(path_template: str, *, output_dir: Path) -> Path:
    return output_dir / path_template


def _normalize_stdout(stdout: str, *, output_dir: Path) -> str:
    normalized = stdout.replace(str(output_dir), "{TMP_PATH}")
    normalized = re.sub(r"(?m)^(\+ [^:]+:\d+: )", "", normalized)
    return normalized


def _run_case(case: dict[str, str], *, output_dir: Path) -> subprocess.CompletedProcess[str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    tag = _sanitize_tag(case["name"])

    env = os.environ.copy()
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

    return subprocess.run(
        bash_command,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    if "case" not in metafunc.fixturenames:
        return
    cases = _load_cases()
    metafunc.parametrize("case", cases, ids=[case["name"] for case in cases])


def test_pixi_case_config_exists() -> None:
    assert CASE_CONFIG_PATH.exists(), f"Missing case configuration file: {CASE_CONFIG_PATH}"


@pytest.mark.reference
def test_pixi_reference(case: dict[str, str], tmp_path_factory: pytest.TempPathFactory) -> None:
    for dependency in case.get("depends_on", []):
        if dependency not in CASE_RESULTS:
            pytest.skip(f"Dependency '{dependency}' has not run yet.")
        if not CASE_RESULTS[dependency]:
            pytest.skip(f"Dependency '{dependency}' did not pass.")

    reference_path = REPO_ROOT / case["reference"]
    output_dir = tmp_path_factory.mktemp(f"{_sanitize_tag(case['name'])}-")
    assert reference_path.exists(), f"Missing reference file: {reference_path}"

    completed = _run_case(case, output_dir=output_dir)
    stdout = _normalize_stdout(completed.stdout, output_dir=output_dir)
    stderr = completed.stderr
    expected_returncode = int(case.get("returncode", 0))
    expected_stdout = reference_path.read_text(encoding="utf-8").strip()
    stdout_match = case.get("stdout_match", "exact")

    try:
        assert completed.returncode == expected_returncode, (
            f"Return code mismatch for {case['name']} ({reference_path})\n"
            f"STDOUT:\n{stdout}\n"
            f"STDERR:\n{stderr}"
        )

        if stdout_match == "contains":
            assert expected_stdout in stdout, (
                f"Expected stdout fragment not found for {case['name']} ({reference_path})\n"
                f"EXPECTED FRAGMENT:\n{expected_stdout}\n"
                f"STDOUT:\n{stdout}\n"
                f"STDERR:\n{stderr}"
            )
        else:
            assert stdout == expected_stdout, (
                f"Stdout snapshot mismatch for {case['name']} ({reference_path})\n"
                f"STDOUT:\n{stdout}\n"
                f"STDERR:\n{stderr}"
            )

        for output_template in case.get("expected_outputs", []):
            output_path = _resolve_template(output_template, output_dir=output_dir)
            assert output_path.exists(), (
                f"Missing expected output for {case['name']}: {output_path}\n"
                f"STDOUT:\n{stdout}\n"
                f"STDERR:\n{stderr}"
            )
    except Exception:
        CASE_RESULTS[case["name"]] = False
        raise
    else:
        CASE_RESULTS[case["name"]] = True

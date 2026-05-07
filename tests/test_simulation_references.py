from __future__ import annotations

import json
import os
import re
import shlex
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


def _load_cases() -> list[dict[str, str]]:
    with CASE_CONFIG_PATH.open("rb") as handle:
        data = tomllib.load(handle)
    return data["case"]


def _sanitize_tag(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", name)


def _resolve_template(path_template: str, *, tag: str, output_dir: Path) -> Path:
    return output_dir / path_template.format(tag=tag)


def _run_case(case: dict[str, str], *, output_dir: Path) -> subprocess.CompletedProcess[str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    tag = _sanitize_tag(case["name"])

    env = os.environ.copy()
    env.setdefault("FAIRSHIP", str(REPO_ROOT))
    env["FAIRSHIP_TEST_OUTPUT_DIR"] = str(output_dir)
    env["FAIRSHIP_TEST_TAG"] = tag

    command = case["command"]
    completed = subprocess.run(
        command,
        shell=True,
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
    expected = json.loads(reference_path.read_text(encoding="utf-8"))
    completed = _run_case(case, output_dir=output_dir)
    stdout = completed.stdout
    stderr = completed.stderr

    if os.environ.get(REGENERATE_ENV) == "1":
        refreshed = {
            "command": shlex.split(case["command"]),
            "returncode": completed.returncode,
            "stdout_contains": expected.get("stdout_contains", []),
            "stderr_contains": expected.get("stderr_contains", []),
            "expected_outputs": expected["expected_outputs"],
        }
        reference_path.parent.mkdir(parents=True, exist_ok=True)
        reference_path.write_text(json.dumps(refreshed, indent=2) + "\n", encoding="utf-8")

    assert shlex.split(case["command"]) == expected["command"], f"Command drift for {case['name']} ({reference_path})"
    assert completed.returncode == expected["returncode"], (
        f"Return code mismatch for {case['name']} ({reference_path})"
    )

    for expected_fragment in expected["stdout_contains"]:
        assert expected_fragment in stdout, f"Missing stdout fragment in {case['name']}: {expected_fragment}"
    for expected_fragment in expected["stderr_contains"]:
        assert expected_fragment in stderr, f"Missing stderr fragment in {case['name']}: {expected_fragment}"
    for output_template in expected["expected_outputs"]:
        output_path = _resolve_template(output_template, tag=_sanitize_tag(case["name"]), output_dir=output_dir)
        assert output_path.exists(), f"Missing expected output for {case['name']}: {output_path}"

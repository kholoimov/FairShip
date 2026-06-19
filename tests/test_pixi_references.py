from __future__ import annotations

import difflib
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
CASE_DEPENDENCY_OK: dict[str, bool] = {}
CASE_WARNING_COUNTS: dict[str, int] = {}


def _load_cases() -> list[dict[str, str]]:
    with CASE_CONFIG_PATH.open("rb") as handle:
        data = tomllib.load(handle)
    return data["case"]


def _sanitize_tag(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", name)


def _resolve_template(path_template: str, *, output_dir: Path) -> Path:
    return output_dir / path_template


def _command_log_path(case: dict[str, str], *, output_dir: Path) -> Path:
    return output_dir / f"{_sanitize_tag(case['name'])}.command.log"


def _normalize_stdout(stdout: str, *, output_dir: Path) -> str:
    normalized = stdout.replace(str(output_dir), "{TMP_PATH}")
    normalized = re.sub(r"(?m)^(\+ [^:]+:\d+: )", "", normalized)
    return "\n".join(line.rstrip() for line in normalized.splitlines()).strip()


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


def _case_output_text(case: dict[str, str], completed: subprocess.CompletedProcess[str], *, output_dir: Path) -> str:
    command_log = _command_log_path(case, output_dir=output_dir)
    if command_log.exists():
        return command_log.read_text(encoding="utf-8")
    return completed.stdout


def _unified_diff(expected: str, actual: str, *, reference_path: Path) -> str:
    return "\n".join(
        difflib.unified_diff(
            expected.splitlines(),
            actual.splitlines(),
            fromfile=str(reference_path),
            tofile="actual_stdout",
            lineterm="",
        )
    )


def _check_build_output(case: dict[str, str], stdout: str) -> tuple[bool, str | None]:
    if case["name"] != "pixi_build":
        return True, None

    warning_count = len(re.findall(r"WARNING|warning", stdout))
    CASE_WARNING_COUNTS[case["name"]] = warning_count

    if re.search(r"ERROR|error", stdout):
        return False, "Build output contains ERROR/error"
    return True, None


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
        if dependency not in CASE_DEPENDENCY_OK:
            pytest.skip(f"Dependency '{dependency}' has not run yet.")
        if not CASE_DEPENDENCY_OK[dependency]:
            pytest.skip(f"Dependency '{dependency}' did not pass.")

    reference_path = REPO_ROOT / case["reference"]
    output_dir = tmp_path_factory.mktemp(f"{_sanitize_tag(case['name'])}-")
    assert reference_path.exists(), f"Missing reference file: {reference_path}"

    completed = _run_case(case, output_dir=output_dir)
    stdout = _normalize_stdout(_case_output_text(case, completed, output_dir=output_dir), output_dir=output_dir)
    stderr = completed.stderr
    expected_returncode = int(case.get("returncode", 0))
    expected_stdout = "\n".join(line.rstrip() for line in reference_path.read_text(encoding="utf-8").splitlines()).strip()

    try:
        assert completed.returncode == expected_returncode, (
            f"Return code mismatch for {case['name']} ({reference_path})\n"
            f"STDOUT:\n{stdout}\n"
            f"STDERR:\n{stderr}"
        )

        dependency_ok, build_issue = _check_build_output(case, stdout)
        CASE_DEPENDENCY_OK[case["name"]] = dependency_ok
        assert build_issue is None, (
            f"{build_issue} for {case['name']} ({reference_path})\n"
            f"STDOUT:\n{stdout}\n"
            f"STDERR:\n{stderr}"
        )
        warning_count = CASE_WARNING_COUNTS.get(case["name"], 0)
        if warning_count > 0:
            print(f"{case['name']} warning count: {warning_count}")

        assert stdout == expected_stdout, (
            f"Stdout snapshot mismatch for {case['name']} ({reference_path})\n"
            f"DIFF:\n{_unified_diff(expected_stdout, stdout, reference_path=reference_path)}\n"
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
        CASE_DEPENDENCY_OK.setdefault(case["name"], False)
        raise
    else:
        CASE_RESULTS[case["name"]] = True
        CASE_DEPENDENCY_OK[case["name"]] = True

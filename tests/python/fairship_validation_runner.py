#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright CERN for the benefit of the SHiP Collaboration

from __future__ import annotations

import json
import os
import subprocess
import urllib.request
from pathlib import Path
from typing import Any

import pytest
import yaml

from build_clean_runner import run_build_clean_validation


DEFAULT_INPUT_FILE = Path("/tmp/pythia8_Geant4_10.0_withCharmandBeauty0_mu.root")
DEFAULT_INPUT_URL = (
    "https://cernbox.cern.ch/remote.php/dav/public-files/vdwtXtgM5P2Z0S5/"
    "pythia8_Geant4_10.0_withCharmandBeauty0_mu.root"
)
DEFAULT_SETUP_SCRIPT = "/cvmfs/ship.cern.ch/26.03/setUp.sh"


def _repo_root() -> Path:
    repo_root = os.environ.get("FAIRSHIP_REPO_ROOT")
    if repo_root:
        return Path(repo_root)
    cwd = Path.cwd()
    if cwd.name == "FairShip":
        return cwd
    return cwd / "FairShip"


def _run_workdir(case: dict[str, Any], repo_root: Path) -> Path:
    workdir_env = case.get("workdir_env")
    if workdir_env:
        workdir = os.environ.get(workdir_env)
        if workdir:
            return Path(workdir)
    return repo_root.parent


def _git_branch_name(repo_root: Path) -> str:
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


def _defaults_name() -> str:
    return os.environ.get("FAIRSHIP_ALIENV_DEFAULTS", "release")


def _alienv_package_name(repo_root: Path, case: dict[str, Any]) -> str:
    for env_name in case.get("package_envs", []):
        package = os.environ.get(env_name)
        if package:
            return package

    package = os.environ.get("FAIRSHIP_ALIENV_PACKAGE")
    if package:
        return package

    branch = _git_branch_name(repo_root)
    defaults = _defaults_name()
    return f"FairShip/latest-{branch}-{defaults}"


def _required_input_file() -> Path:
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


def _debug_enabled(case: dict[str, Any]) -> bool:
    debug_env = case.get("debug_env")
    if not debug_env:
        return False
    return os.environ.get(debug_env, "").lower() in {"1", "true", "yes", "on"}


def _render_template(value: str, context: dict[str, Any]) -> str:
    return value.format(**context)


def _resolve_value(spec: Any, context: dict[str, Any]) -> Any:
    if not isinstance(spec, dict):
        if isinstance(spec, str):
            return _render_template(spec, context)
        return spec

    if spec.get("source") == "required_input_file":
        return str(_required_input_file())

    value = None
    env_name = spec.get("env")
    if env_name:
        value = os.environ.get(env_name)

    if value in (None, "") and "default" in spec:
        default_value = spec["default"]
        value = _render_template(default_value, context) if isinstance(default_value, str) else default_value

    if value in (None, "") and spec.get("required"):
        pytest.fail(f"Missing required environment override: {env_name}")

    if spec.get("type") == "int":
        value = int(value)
        max_value = spec.get("max")
        if max_value is not None and value > max_value:
            message = spec.get("max_message")
            if message:
                pytest.fail(message.format(value=value, max=max_value, env=env_name))
            pytest.fail(f"{env_name} must be <= {max_value}, got {value}")

    return value


def _shell_prefix(repo_root: Path, case: dict[str, Any]) -> str:
    setup_script = case.get("setup_script", DEFAULT_SETUP_SCRIPT)
    return (
        f"source {setup_script} && "
        f'eval "$(alienv load {_alienv_package_name(repo_root, case)})" && '
    )


def _run_shell_command(
    command: str,
    workdir: Path,
    timeout: int,
    debug_enabled: bool,
    label: str,
) -> subprocess.CompletedProcess[str]:
    if not debug_enabled:
        return subprocess.run(
            ["/bin/bash", "-lc", command],
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
        )

    print(f"\n[{label}] running in {workdir}")
    print(f"[{label}] command:\n{command}\n")

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


def _normalize_payload(payload: Any, normalization: dict[str, Any]) -> Any:
    if not normalization:
        return payload

    drop_keys = set(normalization.get("drop_keys", []))
    if isinstance(payload, dict):
        return {
            key: _normalize_payload(value, normalization)
            for key, value in payload.items()
            if key not in drop_keys
        }
    if isinstance(payload, list):
        return [_normalize_payload(item, normalization) for item in payload]
    return payload


def _load_structured_file(path: Path, file_format: str | None = None) -> Any:
    if file_format == "json" or path.suffix == ".json":
        return json.loads(path.read_text())
    return yaml.safe_load(path.read_text())


def _dump_yaml_text(payload: Any) -> str:
    return yaml.safe_dump(payload, sort_keys=True, default_flow_style=False)


def _write_step_artifacts(tmp_path: Path, step_name: str, command: str, result: subprocess.CompletedProcess[str]) -> None:
    artifact_prefix = tmp_path / step_name
    artifact_prefix.with_suffix(".command").write_text(command + "\n")
    artifact_prefix.with_suffix(".stdout").write_text(result.stdout)
    artifact_prefix.with_suffix(".stderr").write_text(result.stderr)


def _assert_step_success(
    step_name: str,
    command: str,
    workdir: Path,
    result: subprocess.CompletedProcess[str],
) -> None:
    assert result.returncode == 0, (
        f"{step_name} command failed\n"
        f"Command: {command}\n"
        f"Workdir: {workdir}\n"
        f"Return code: {result.returncode}\n\n"
        f"STDOUT:\n{result.stdout}\n\n"
        f"STDERR:\n{result.stderr}"
    )


def _validate_yaml_snapshot(
    validation: dict[str, Any],
    context: dict[str, Any],
) -> None:
    source_path = Path(_render_template(validation["source"], context))
    reference_path = Path(_render_template(validation["reference"], context))
    assert source_path.exists(), f"Missing validation source file: {source_path}"
    assert reference_path.exists(), f"Missing validation reference file: {reference_path}"

    payload = _load_structured_file(source_path, validation.get("source_format"))
    normalized = _normalize_payload(payload, validation.get("normalize", {}))
    actual_text = _dump_yaml_text(normalized)

    artifact_path = validation.get("artifact")
    if artifact_path:
        Path(_render_template(artifact_path, context)).write_text(actual_text)

    expected_text = reference_path.read_text()
    assert actual_text == expected_text, (
        f"YAML snapshot mismatch for {source_path}\n"
        f"Reference: {reference_path}\n"
        f"Actual normalized snapshot:\n{actual_text}"
    )


def _validate_step_stdout(validation: dict[str, Any], step_results: dict[str, subprocess.CompletedProcess[str]]) -> None:
    step_name = validation["step"]
    result = step_results[step_name]
    stdout = result.stdout

    contains = validation.get("contains")
    if contains is not None:
        assert contains in stdout, (
            f"Expected stdout from step '{step_name}' to contain:\n{contains}\n\nActual stdout:\n{stdout}"
        )

    endswith = validation.get("endswith")
    if endswith is not None:
        assert stdout.strip().endswith(endswith), (
            f"Expected stdout from step '{step_name}' to end with:\n{endswith}\n\nActual stdout:\n{stdout}"
        )


def _validate_file_exists(validation: dict[str, Any], context: dict[str, Any]) -> None:
    path = Path(_render_template(validation["path"], context))
    assert path.exists(), f"Missing expected file: {path}"


def load_case_definitions(config_dir: Path) -> list[dict[str, Any]]:
    cases_by_id = {}
    for config_path in sorted(config_dir.glob("*.yaml")):
        config = yaml.safe_load(config_path.read_text())
        case = config["test"]
        cases_by_id[case["id"]] = case

    visiting: set[str] = set()
    visited: set[str] = set()
    ordered: list[dict[str, Any]] = []

    def visit(case_id: str) -> None:
        if case_id in visited:
            return
        if case_id in visiting:
            raise ValueError(f"Cyclic dependency detected at test case '{case_id}'")
        if case_id not in cases_by_id:
            raise ValueError(f"Unknown dependency '{case_id}' referenced by test cases")

        visiting.add(case_id)
        case = cases_by_id[case_id]
        for dependency in case.get("depends_on", []):
            visit(dependency)
        visiting.remove(case_id)
        visited.add(case_id)
        ordered.append(case)

    for case_id in sorted(cases_by_id):
        visit(case_id)

    return ordered


def load_pytest_cases(config_dir: Path) -> list[Any]:
    parameters = []
    for case in load_case_definitions(config_dir):
        marks = [pytest.mark.integration]
        timeout = case.get("timeout")
        if timeout is not None:
            marks.append(pytest.mark.timeout(timeout))
        parameters.append(pytest.param(case, id=case["id"], marks=marks))
    return parameters


def run_validation_case(case: dict[str, Any], tmp_path: Path) -> None:
    if case.get("runner") == "build_clean":
        run_build_clean_validation(tmp_path)
        return

    repo_root = _repo_root()
    workdir = _run_workdir(case, repo_root)
    debug = _debug_enabled(case)

    context: dict[str, Any] = {
        "repo_root": str(repo_root),
        "tmp_path": str(tmp_path),
    }
    for key, spec in case.get("context", {}).items():
        context[key] = _resolve_value(spec, context)

    step_results: dict[str, subprocess.CompletedProcess[str]] = {}

    for step in case.get("runs", []):
        step_name = step["name"]
        timeout = step.get("timeout", case.get("timeout", 7200))
        command = _render_template(step["command"], context)
        if step.get("use_ship_env", True):
            command = _shell_prefix(repo_root, case) + command

        result = _run_shell_command(
            command,
            workdir,
            timeout,
            debug,
            f"{case['id']}:{step_name}",
        )
        _write_step_artifacts(tmp_path, step_name, command, result)
        _assert_step_success(step_name, command, workdir, result)
        step_results[step_name] = result

        for output in step.get("outputs", []):
            output_path = Path(_render_template(output, context))
            assert output_path.exists(), f"Missing output from step '{step_name}': {output_path}"

    for validation in case.get("validations", []):
        validation_type = validation["type"]
        if validation_type == "yaml_snapshot":
            _validate_yaml_snapshot(validation, context)
        elif validation_type == "step_stdout":
            _validate_step_stdout(validation, step_results)
        elif validation_type == "file_exists":
            _validate_file_exists(validation, context)
        else:
            raise ValueError(f"Unknown validation type: {validation_type}")

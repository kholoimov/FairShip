# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright CERN for the benefit of the SHiP Collaboration

"""Run shell-configured tests and compare their terminal output."""

from __future__ import annotations

import argparse
import atexit
import difflib
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
REPOSITORY_ROOT = HERE.parent.parent
TEST_CASES = HERE / "test_cases.yaml"
SKIP_PATTERNS = HERE / "skip_patterns.conf"
VALID_TEST_NAME = re.compile(r"[A-Za-z0-9_.-]+")
COMPLETED_TESTS: set[str] = set()
KEEP_TEST_OUTPUT = os.environ.get("FAIRSHIP_KEEP_TEST_OUTPUT") == "1"
TEST_WORKDIR_ROOT = Path(tempfile.mkdtemp(prefix="fairship-tests-"))
if not KEEP_TEST_OUTPUT:
    atexit.register(shutil.rmtree, TEST_WORKDIR_ROOT, ignore_errors=True)


@dataclass(frozen=True)
class TestCase:
    name: str
    script: Path
    reference: Path
    dependencies: tuple[str, ...]


def test_cases() -> list[TestCase]:
    """Return and validate the tests declared by the configuration file."""
    try:
        configuration = yaml.safe_load(TEST_CASES.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise RuntimeError(f"Invalid YAML in {TEST_CASES}: {error}") from error

    if not isinstance(configuration, dict) or set(configuration) != {"tests"}:
        raise RuntimeError(f"{TEST_CASES} must contain exactly one top-level 'tests' key")
    configured_tests = configuration["tests"]
    if not isinstance(configured_tests, list) or not configured_tests:
        raise RuntimeError(f"'tests' in {TEST_CASES} must be a non-empty list")

    cases: list[TestCase] = []
    for index, configured_test in enumerate(configured_tests, start=1):
        location = f"{TEST_CASES} test #{index}"
        if isinstance(configured_test, dict) and set(configured_test) == {"name"}:
            name = configured_test["name"]
            dependencies = []
        elif isinstance(configured_test, dict) and set(configured_test) == {"name", "depends_on"}:
            name = configured_test["name"]
            dependencies = configured_test["depends_on"]
        else:
            raise RuntimeError(
                f"{location} must be a test name or a mapping containing 'name' and optional 'depends_on'"
            )
        if not isinstance(name, str) or not name:
            raise RuntimeError(f"{location} must be a non-empty test name")
        if VALID_TEST_NAME.fullmatch(name) is None:
            raise RuntimeError(f"Invalid test name {name!r} in {location}")
        if not isinstance(dependencies, list) or not all(
            isinstance(dependency, str) and dependency for dependency in dependencies
        ):
            raise RuntimeError(f"'depends_on' in {location} must be a list of non-empty test names")
        if len(dependencies) != len(set(dependencies)):
            raise RuntimeError(f"Duplicate dependencies for {name!r} in {location}")

        script = (HERE / "scripts" / f"{name}.sh").resolve()
        reference = (HERE / "references" / f"{name}.txt").resolve()
        if not script.is_file():
            raise RuntimeError(f"Test script does not exist for {name!r}: {script}")
        if not script.stat().st_mode & 0o111:
            raise RuntimeError(f"Test script is not executable for {name!r}: {script}")

        cases.append(TestCase(name=name, script=script, reference=reference, dependencies=tuple(dependencies)))

    names = [case.name for case in cases]
    if len(names) != len(set(names)):
        raise RuntimeError(f"Duplicate test names in {TEST_CASES}")

    known_names = set(names)
    for case in cases:
        unknown = set(case.dependencies) - known_names
        if unknown:
            raise RuntimeError(f"Unknown dependencies for {case.name!r} in {TEST_CASES}: {', '.join(sorted(unknown))}")
        if case.name in case.dependencies:
            raise RuntimeError(f"Test {case.name!r} cannot depend on itself in {TEST_CASES}")

    cases_by_name = {case.name: case for case in cases}
    visited: set[str] = set()
    visiting: list[str] = []

    def validate_acyclic(name: str) -> None:
        if name in visited:
            return
        if name in visiting:
            cycle = visiting[visiting.index(name) :] + [name]
            raise RuntimeError(f"Dependency cycle in {TEST_CASES}: {' -> '.join(cycle)}")
        visiting.append(name)
        for dependency in cases_by_name[name].dependencies:
            validate_acyclic(dependency)
        visiting.pop()
        visited.add(name)

    for name in names:
        validate_acyclic(name)

    return cases


def test_names() -> list[str]:
    """Return the configured test names for pytest parameterization."""
    return [case.name for case in test_cases()]


def dependency_groups() -> dict[str, str]:
    """Map every test to its dependency-connected xdist group."""
    cases = test_cases()
    neighbours = {case.name: set(case.dependencies) for case in cases}
    for case in cases:
        for dependency in case.dependencies:
            neighbours[dependency].add(case.name)

    groups: dict[str, str] = {}
    for case in cases:
        if case.name in groups:
            continue
        group_name = case.name
        pending = [case.name]
        while pending:
            name = pending.pop()
            if name in groups:
                continue
            groups[name] = group_name
            pending.extend(neighbours[name])
    return groups


def workdir_for(test_name: str) -> Path:
    """Return the shared working directory for a test's dependency group."""
    group_name = dependency_groups()[test_name]
    workdir = TEST_WORKDIR_ROOT / group_name
    workdir.mkdir(parents=True, exist_ok=True)
    return workdir


def _test_case(test_name: str) -> TestCase:
    try:
        return next(case for case in test_cases() if case.name == test_name)
    except StopIteration:
        raise RuntimeError(f"Unknown FairShip test: {test_name}") from None


def _compile_wildcard(pattern: str) -> re.Pattern[str]:
    """Compile a full-line pattern in which only ``*`` is special."""
    expression = ".*".join(re.escape(part) for part in pattern.split("*"))
    return re.compile(expression)


def _patterns_for(test_name: str) -> list[re.Pattern[str]]:
    known_tests = set(test_names())
    patterns: list[str] = []
    current_selector: str | None = None
    for line_number, raw_line in enumerate(SKIP_PATTERNS.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if raw_line.startswith("test "):
            current_selector = line.removeprefix("test ").strip()
            if not current_selector:
                raise RuntimeError(f"Missing test name in {SKIP_PATTERNS}:{line_number}")
            if current_selector != "*" and current_selector not in known_tests:
                raise RuntimeError(f"Unknown test name {current_selector!r} in {SKIP_PATTERNS}:{line_number}")
        elif not raw_line[:1].isspace():
            raise RuntimeError(f"Expected 'test NAME' or an indented pattern in {SKIP_PATTERNS}:{line_number}")
        elif current_selector is None:
            raise RuntimeError(f"Pattern outside a test block in {SKIP_PATTERNS}:{line_number}")
        elif current_selector in {"*", test_name}:
            patterns.append(line)

    return [_compile_wildcard(pattern) for pattern in patterns]


def run(test_name: str) -> tuple[int, str]:
    """Run one configured test, returning its status and normalized output."""
    case = _test_case(test_name)
    environment = os.environ.copy()
    environment["FAIRSHIP_ROOT"] = str(REPOSITORY_ROOT)
    result = subprocess.run(
        [str(case.script)],
        cwd=workdir_for(test_name),
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    patterns = _patterns_for(test_name)
    lines = result.stdout.splitlines(keepends=True)
    output = "".join(line for line in lines if not any(pattern.fullmatch(line.rstrip("\r\n")) for pattern in patterns))
    return result.returncode, output


def assert_matches_reference(test_name: str) -> None:
    """Run a test after its dependencies and compare each result."""
    def assert_test(name: str) -> None:
        if name in COMPLETED_TESTS:
            return
        case = _test_case(name)
        for dependency in case.dependencies:
            assert_test(dependency)

        returncode, output = run(name)
        assert returncode == 0, f"{name} exited with status {returncode}\n\n{output}"

        path = case.reference
        assert path.exists(), f"Missing reference file {path}. Run {HERE / 'regenerate_references.sh'}."
        expected = path.read_text(encoding="utf-8")
        diff = "".join(
            difflib.unified_diff(
                expected.splitlines(keepends=True),
                output.splitlines(keepends=True),
                fromfile=str(path),
                tofile=f"{name} (current output)",
            )
        )
        assert not diff, f"Terminal output changed for {name}:\n\n{diff}"
        COMPLETED_TESTS.add(name)

    assert_test(test_name)


def regenerate() -> None:
    """Replace all reference files with current successful output."""
    completed: set[str] = set()

    def regenerate_test(name: str) -> None:
        if name in completed:
            return
        case = _test_case(name)
        for dependency in case.dependencies:
            regenerate_test(dependency)

        returncode, output = run(name)
        if returncode != 0:
            raise RuntimeError(
                f"{case.name} exited with status {returncode}; references were not fully regenerated\n\n{output}"
            )
        case.reference.parent.mkdir(parents=True, exist_ok=True)
        case.reference.write_text(output, encoding="utf-8")
        print(f"wrote {case.reference}")
        completed.add(name)

    for case in test_cases():
        regenerate_test(case.name)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--regenerate", action="store_true", help="replace reference files with current output")
    args = parser.parse_args()
    if args.regenerate:
        regenerate()
    else:
        parser.error("no action requested")


if __name__ == "__main__":
    main()

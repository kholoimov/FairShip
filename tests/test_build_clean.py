import os
import re
import shlex
import subprocess
from pathlib import Path

import pytest


WARNING_PATTERNS = [
    re.compile(r"\bwarning:"),
    re.compile(r"\bwarning \d+\b", re.IGNORECASE),
]

ERROR_PATTERNS = [
    re.compile(r"\berror:"),
    re.compile(r"\bfatal error:"),
    re.compile(r"undefined reference to"),
]


def _build_command():
    return os.environ.get(
        "FAIRSHIP_BUILD_TEST_COMMAND",
        (
            "echo \"Loading SHiP environment...\" && "
            "source /cvmfs/ship.cern.ch/26.03/setUp.sh && "
            "echo \"Building FairShip...\" && "
            "aliBuild build FairShip "
            "--force-rebuild FairShip "
            "--always-prefer-system "
            "--config-dir \"$SHIPDIST\" "
            "--defaults release "
            f"-j {os.environ.get('FAIRSHIP_BUILD_TEST_JOBS', '100')}"
        ),
    )


def _build_workdir():
    workdir = os.environ.get("FAIRSHIP_BUILD_TEST_WORKDIR")
    if workdir:
        return Path(workdir)
    cwd = Path.cwd()
    if cwd.name == "FairShip":
        return cwd.parent
    return cwd


def _git_branch_name(workdir):
    branch = os.environ.get("FAIRSHIP_GIT_BRANCH")
    if branch:
        return branch

    result = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=workdir,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _defaults_name():
    return os.environ.get("FAIRSHIP_ALIENV_DEFAULTS", "release")


def _alienv_package_name(workdir):
    package = os.environ.get("FAIRSHIP_ALIENV_PACKAGE")
    if package:
        return package
    branch = _git_branch_name(workdir)
    defaults = _defaults_name()
    return f"FairShip/latest-{branch}-{defaults}"


def _warning_allowlist():
    raw = os.environ.get("FAIRSHIP_BUILD_WARNING_ALLOWLIST", "")
    return [re.compile(pattern) for pattern in raw.splitlines() if pattern.strip()]


def _find_matches(output, patterns, allowlist):
    matches = []
    for line in output.splitlines():
        if any(pattern.search(line) for pattern in patterns):
            if any(pattern.search(line) for pattern in allowlist):
                continue
            matches.append(line)
    return matches


@pytest.mark.integration
@pytest.mark.timeout(7200)
def test_build_has_no_warnings_or_errors(tmp_path):
    """
    Run the configured build command and fail if the build log contains warnings
    or errors.

    Environment overrides:
    - FAIRSHIP_BUILD_TEST_COMMAND: exact shell command to run
    - FAIRSHIP_BUILD_TEST_WORKDIR: directory where the command should run
    - FAIRSHIP_BUILD_WARNING_ALLOWLIST: newline-separated regexes to ignore
    - FAIRSHIP_BUILD_TEST_JOBS: parallel job count for the default aliBuild command

    Default behavior:
    - Source `/cvmfs/ship.cern.ch/26.03/setUp.sh`
    - Run the usual aliBuild-based FairShip build with your standard flags
    """

    command = _build_command()
    workdir = _build_workdir()
    allowlist = _warning_allowlist()
    alienv_package = _alienv_package_name(workdir)

    result = subprocess.run(
        command,
        cwd=workdir,
        capture_output=True,
        text=True,
        timeout=7200,
        shell=True,
        executable="/bin/bash",
    )

    stdout = result.stdout
    stderr = result.stderr
    combined_output = stdout + ("\n" if stdout and stderr else "") + stderr

    (tmp_path / "build.stdout").write_text(stdout)
    (tmp_path / "build.stderr").write_text(stderr)
    (tmp_path / "build.command").write_text(command + "\n")
    (tmp_path / "alienv_package.txt").write_text(alienv_package + "\n")

    assert result.returncode == 0, (
        "Build command failed\n"
        f"Command: {command}\n"
        f"Workdir: {workdir}\n"
        f"Return code: {result.returncode}\n\n"
        f"STDOUT:\n{stdout}\n\n"
        f"STDERR:\n{stderr}"
    )

    warning_matches = _find_matches(combined_output, WARNING_PATTERNS, allowlist)
    error_matches = _find_matches(combined_output, ERROR_PATTERNS, allowlist)

    assert not error_matches, (
        "Build log contains error lines\n"
        + "\n".join(error_matches[:50])
        + ("\n..." if len(error_matches) > 50 else "")
    )

    assert not warning_matches, (
        "Build log contains warning lines\n"
        + "\n".join(warning_matches[:50])
        + ("\n..." if len(warning_matches) > 50 else "")
    )

    assert alienv_package in stdout, (
        "Expected aliBuild environment name was not mentioned in build output\n"
        f"Expected package: {alienv_package}\n\n"
        f"STDOUT:\n{stdout}"
    )

# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright CERN for the benefit of the SHiP Collaboration

"""Pytest configuration for FairShip regression tests."""

from __future__ import annotations

import os

import pytest
from _pytest.terminal import TerminalReporter


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--keep-output",
        action="store_true",
        help="preserve the FairShip test working directory",
    )


def pytest_configure(config: pytest.Config) -> None:
    if config.getoption("--keep-output"):
        os.environ["FAIRSHIP_KEEP_TEST_OUTPUT"] = "1"
    config._fairship_output_paths = []


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    from .harness import dependency_groups

    groups = dependency_groups()
    for item in items:
        callspec = getattr(item, "callspec", None)
        if callspec is None or "test_name" not in callspec.params:
            continue
        test_name = callspec.params["test_name"]
        item.add_marker(pytest.mark.xdist_group(name=groups[test_name]))


def pytest_sessionfinish(session: pytest.Session) -> None:
    if session.config.getoption("--keep-output") and hasattr(session.config, "workeroutput"):
        from .harness import TEST_WORKDIR_ROOT

        session.config.workeroutput["fairship_test_output"] = str(TEST_WORKDIR_ROOT)


def pytest_testnodedown(node: object) -> None:
    output_path = node.workeroutput.get("fairship_test_output")
    if output_path:
        node.config._fairship_output_paths.append(output_path)


def pytest_terminal_summary(terminalreporter: TerminalReporter) -> None:
    if not terminalreporter.config.getoption("--keep-output"):
        return

    output_paths = terminalreporter.config._fairship_output_paths
    if not output_paths:
        from .harness import TEST_WORKDIR_ROOT

        output_paths = [str(TEST_WORKDIR_ROOT)]
    for output_path in sorted(output_paths):
        terminalreporter.write_sep("=", f"FairShip test files kept in {output_path}")

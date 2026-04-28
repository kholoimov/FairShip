#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright CERN for the benefit of the SHiP Collaboration

from pathlib import Path
import os
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fairship_validation_runner import load_pytest_cases, run_validation_case


CONFIG_PATH = Path(__file__).with_name("cases")
CASE_RESULTS: dict[str, bool] = {
    case_id: True
    for case_id in os.environ.get("FAIRSHIP_PASSED_TESTS", "").split(",")
    if case_id.strip()
}


@pytest.mark.parametrize("case", load_pytest_cases(CONFIG_PATH))
def test_fairship_validation_case(case, tmp_path):
    failed_dependencies = [dependency for dependency in case.get("depends_on", []) if CASE_RESULTS.get(dependency) is False]
    missing_dependencies = [dependency for dependency in case.get("depends_on", []) if dependency not in CASE_RESULTS]

    if failed_dependencies:
        CASE_RESULTS[case["id"]] = False
        pytest.fail(
            f"Dependency failure for {case['id']}: {', '.join(failed_dependencies)}"
        )

    if missing_dependencies:
        CASE_RESULTS[case["id"]] = False
        pytest.fail(
            f"Dependencies were not executed before {case['id']}: {', '.join(missing_dependencies)}"
        )

    try:
        run_validation_case(case, tmp_path)
    except Exception:
        CASE_RESULTS[case["id"]] = False
        raise
    else:
        CASE_RESULTS[case["id"]] = True

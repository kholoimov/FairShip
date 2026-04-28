#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright CERN for the benefit of the SHiP Collaboration

from pathlib import Path

import pytest

from fairship_validation_runner import load_pytest_cases, run_validation_case


CONFIG_PATH = Path(__file__).with_name("fairship_validation_cases.yaml")


@pytest.mark.parametrize("case", load_pytest_cases(CONFIG_PATH))
def test_fairship_validation_case(case, tmp_path):
    run_validation_case(case, tmp_path)

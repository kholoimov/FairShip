# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright CERN for the benefit of the SHiP Collaboration

"""Configured FairShip regression tests."""

import pytest

from .harness import assert_matches_reference, test_names as terminal_test_names


@pytest.mark.parametrize("test_name", terminal_test_names())
def test_fairship(test_name: str) -> None:
    assert_matches_reference(test_name)

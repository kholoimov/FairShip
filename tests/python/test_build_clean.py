import pytest

from build_clean_runner import run_build_clean_validation


@pytest.mark.integration
@pytest.mark.timeout(7200)
def test_build_has_no_warnings_or_errors(tmp_path):
    run_build_clean_validation(tmp_path)

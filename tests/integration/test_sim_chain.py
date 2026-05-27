from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


def test_sim_chain_produces_expected_root_files(sim_chain) -> None:
    assert sim_chain.sim_file.exists()
    assert sim_chain.geo_file.exists()
    assert sim_chain.reco_file.exists()
    assert sim_chain.ana_file.exists()


def test_geometry_overlap_check_passes(sim_chain, run_fairship) -> None:
    result = run_fairship(
        "python/experimental/check_overlaps.py",
        "--geofile",
        sim_chain.geo_file.name,
        cwd=sim_chain.workdir,
    )
    assert "Overlap" not in result.stdout


def test_analysis_example_runs_on_generated_files(sim_chain, run_fairship) -> None:
    run_fairship(
        "examples/analysis_example.py",
        "-f",
        sim_chain.sim_file.name,
        "-r",
        sim_chain.reco_file.name,
        "-g",
        sim_chain.geo_file.name,
        cwd=sim_chain.workdir,
    )
    assert (sim_chain.workdir / "preselectionparameters.root").exists()

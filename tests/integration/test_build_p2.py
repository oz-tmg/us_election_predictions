"""Integration test: the complete P2 polling/simulation/model-card build runs offline."""

from __future__ import annotations

from pathlib import Path

from election_prediction.build_p2 import build


def test_p2_build_offline(tmp_path: Path):
    results = build(tmp_path, allow_network=False)

    assert (tmp_path / "data/silver/poll_toplines.parquet").exists()
    assert (tmp_path / "data/gold/polling_averages.parquet").exists()
    assert (tmp_path / "data/gold/polling_blended_presidential.parquet").exists()
    assert (tmp_path / "reports/polling_forecast_report.md").exists()
    assert (tmp_path / "reports/model_cards/polling_average_v0.md").exists()
    assert (tmp_path / "reports/p2_results.json").exists()

    assert results["data_mode"]["polls"] == "synthetic"
    assert results["polling"]["validation"]["ok"]
    assert results["polling"]["n_averages"] > 0
    simulation = results["simulation"]
    assert 0 <= simulation["electoral_college"]["p_dem_majority"] <= 1
    units = simulation["unit_distributions"]
    assert len(units) == results["polling"]["n_averages"]
    assert units["dem_win_prob"].between(0, 1).all()

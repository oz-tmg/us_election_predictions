"""Integration test: the full P1 build runs offline and writes reports."""

from __future__ import annotations

from pathlib import Path

from election_prediction.build_p1 import build


def test_p1_build_offline(tmp_path: Path):
    results = build(tmp_path, allow_network=False)

    # gold artifacts
    assert (tmp_path / "data/gold/presidential_panel.parquet").exists()
    assert (tmp_path / "data/gold/house_partisanship_score.parquet").exists()
    assert (tmp_path / "data/gold/acs_state_features.parquet").exists()
    assert (tmp_path / "data/silver/tiger_state_2024.parquet").exists()
    assert (tmp_path / "data/silver/tiger_county_2024.parquet").exists()
    assert (tmp_path / "data/silver/tiger_cd_2024.parquet").exists()

    # reports
    assert (tmp_path / "reports/forecast_backtest_report.md").exists()
    assert (tmp_path / "reports/model_cards/presidential_fundamentals_v0.md").exists()
    assert (tmp_path / "reports/p1_results.json").exists()

    pres = results["presidential"]
    assert pres["baseline_backtest"]["n"] > 0
    assert 0 <= pres["baseline_backtest"]["winner_accuracy"] <= 1
    # calibration metrics present
    assert "brier" in pres["demographics_eval"]
    # presidential simulation produced an EC probability
    assert 0 <= pres["simulation"]["electoral_college"]["p_dem_majority"] <= 1
    # house seats simulated
    assert results["house"]["seat_simulation"]["n_units"] > 0
    assert results["data_mode"]["census_tiger"] == "synthetic"
    assert all(checks["ok"] for checks in results["tiger"].values())

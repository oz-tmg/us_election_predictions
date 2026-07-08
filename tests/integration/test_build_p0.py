"""Integration test: the full P0 build runs offline and produces valid outputs."""
from __future__ import annotations

from pathlib import Path

from election_prediction.pipelines_cli import build


def test_p0_build_offline(tmp_path: Path):
    result = build(tmp_path, allow_network=False)
    assert result["ok"], result["report"]
    assert all(m == "synthetic" for m in result["modes"].values())

    # medallion outputs exist
    assert (tmp_path / "data/silver/election_returns.parquet").exists()
    assert (tmp_path / "data/silver/geography.parquet").exists()
    assert (tmp_path / "data/gold/race_results.parquet").exists()
    assert (tmp_path / "reports/data_quality_report.md").exists()

    # a manifest was written per office and checksummed
    manifests = list((tmp_path / "data/manifests").glob("*.json"))
    assert len(manifests) == 3

    # report internals
    rep = result["report"]
    assert rep["overall_ok"]
    assert rep["duplicate_keys"]["race_table_race_id"] == 0
    assert rep["vote_reconciliation"]["races_mismatched"] == 0
    assert set(rep["coverage"]["offices"]) == {"president", "us_house", "us_senate"}

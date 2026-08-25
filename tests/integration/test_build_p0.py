"""Integration test: the full P0 build runs offline and produces valid outputs."""

from __future__ import annotations

import json
from pathlib import Path

import election_prediction.pipelines_cli as pipelines_cli
from election_prediction.data import synthetic
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


def test_manual_sources_are_manifested_as_real(monkeypatch, tmp_path: Path):
    def manual_fixture(office, raw_dir, *, allow_network, require_live):
        path = synthetic.write_fixture(office, raw_dir / f"dataset={office}/manual")
        return path, "manual"

    monkeypatch.setattr(pipelines_cli, "_acquire", manual_fixture)
    result = build(tmp_path, require_live=True)

    assert set(result["modes"].values()) == {"manual"}
    manifests = [json.loads(path.read_text()) for path in (tmp_path / "data/manifests").glob("*.json")]
    assert len(manifests) == 3
    assert all(not manifest["source_id"].endswith("_synthetic") for manifest in manifests)
    assert all(manifest["acquisition_method"] == "manual_export" for manifest in manifests)
    assert all(manifest["validation_status"] == "passed" for manifest in manifests)
    assert all(manifest["row_count"] > 0 for manifest in manifests)

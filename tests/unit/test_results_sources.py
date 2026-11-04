"""Synthetic source preservation and capture provenance, never live election outcomes."""

import json
from pathlib import Path

import pandas as pd
import pytest

from election_prediction import build_results_2026 as cli
from election_prediction.data import results_sources as sources


def test_catalog_exact_fifty_states():
    frame = sources.load_catalog()
    assert len(frame) == 50 and not frame.state_po.duplicated().any()
    assert frame.extraction_status.isin(sources.EXTRACTION_STATUSES).all()
    # A tested parser must point at a reconciliation report that exists and passed.
    for row in frame[frame.extraction_status.eq("parser_tested_2024")].itertuples():
        report = Path(row.extraction_evidence)
        assert report.is_file(), report
        summary = json.loads(report.read_text())
        assert summary["states"][row.state_po]["reconciliation"]["passed"], row.state_po


def test_catalog_refuses_untested_upgrade_and_unknown_access(tmp_path):
    frame = pd.read_csv(sources.CATALOG, dtype=str).fillna("")
    upgraded = frame.copy()
    upgraded.loc[0, "extraction_status"] = "parser_tested_2024"
    upgraded.loc[0, "extraction_evidence"] = ""
    upgraded.to_csv(tmp_path / "a.csv", index=False)
    with pytest.raises(ValueError, match="reconciliation report"):
        sources.load_catalog(tmp_path / "a.csv")
    odd = frame.copy()
    odd["download_access"] = "works_probably"
    odd.to_csv(tmp_path / "b.csv", index=False)
    with pytest.raises(ValueError, match="download_access"):
        sources.load_catalog(tmp_path / "b.csv")


def test_source_preservation_checksum_and_exclusive_write(tmp_path):
    raw = tmp_path / "aggregate.txt"
    raw.write_text("synthetic aggregate only")
    kwargs = {
        "state": "VA",
        "url": "https://example.gov/results",
        "retrieved_at": "2020-11-05T01:00:00Z",
        "directory": tmp_path / "evidence",
    }
    path = sources.preserve_source(raw, **kwargs)
    record = json.loads(path.read_text())
    frame = pd.DataFrame([{"state_po": "VA", "source_url": kwargs["url"], "retrieved_on": "2020-11-05"}])
    sources.verify_evidence(frame, [path])
    with pytest.raises(FileExistsError):
        sources.preserve_source(raw, **kwargs)
    Path(record["raw_path"]).write_text("changed")
    with pytest.raises(ValueError, match="checksum"):
        sources.verify_evidence(frame, [path])


@pytest.mark.parametrize("retrieved_at", ["2020-11-05T01:00:00", "2999-11-05T01:00:00Z"])
def test_retrieval_requires_real_timezone_and_not_future(tmp_path, retrieved_at):
    raw = tmp_path / "aggregate.txt"
    raw.write_text("synthetic")
    with pytest.raises(ValueError):
        sources.preserve_source(
            raw,
            state="VA",
            url="https://example.gov/results",
            retrieved_at=retrieved_at,
            directory=tmp_path / "evidence",
        )


def test_missing_source_evidence_and_wrong_date_fail(tmp_path):
    frame = pd.DataFrame(
        [{"state_po": "VA", "source_url": "https://example.gov/results", "retrieved_on": "2020-11-05"}]
    )
    with pytest.raises(ValueError, match="no preserved"):
        sources.verify_evidence(frame, [])
    raw = tmp_path / "aggregate.txt"
    raw.write_text("synthetic")
    path = sources.preserve_source(
        raw,
        state="VA",
        url="https://example.gov/results",
        retrieved_at="2020-11-06T01:00:00Z",
        directory=tmp_path / "evidence",
    )
    with pytest.raises(ValueError, match="no preserved"):
        sources.verify_evidence(frame, [path])


def test_production_cli_requires_raw_evidence(tmp_path):
    incoming = tmp_path / "incoming.csv"
    incoming.write_text(
        "state_po,district_num,office,dem_votes,rep_votes,other_votes,certified,source_url,retrieved_on\n"
        "VA,1,us_house,100,90,0,False,https://example.gov/results,2020-11-05\n"
    )
    with pytest.raises(ValueError, match="production capture requires"):
        cli.main(["capture", "--snapshot", str(incoming)])


def test_evidence_timestamp_is_utc_date_even_at_local_midnight(tmp_path):
    raw = tmp_path / "aggregate.txt"
    raw.write_text("synthetic")
    path = sources.preserve_source(
        raw,
        state="VA",
        url="https://example.gov/results",
        retrieved_at="2020-11-03T23:30:00-08:00",
        directory=tmp_path / "evidence",
    )
    assert json.loads(path.read_text())["retrieved_on"] == "2020-11-04"

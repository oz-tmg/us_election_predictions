"""Incumbent filing status: what FEC can support, and what it must refuse to claim."""

from __future__ import annotations

import pandas as pd

from election_prediction.features import filings


def _universe(rows: list[dict] | None = None) -> pd.DataFrame:
    base = {
        "geography_id": "g1",
        "office": "us_house",
        "state_po": "GA",
        "district_num": 1.0,
        "election_cycle": 2026,
        "incumbent_name": "JANE DOE",
        "incumbent_party": "DEMOCRAT",
        "incumbent_status": "unknown",
    }
    return pd.DataFrame([{**base, **r} for r in (rows or [{}])])


def _roster(rows: list[dict] | None = None) -> pd.DataFrame:
    base = {
        "candidate_id": "H6GA01001",
        "fec_name": "DOE, JANE",
        "office": "us_house",
        "state_po": "GA",
        "district_num": 1,
        "fec_party": "DEM",
        "election_year": 2026,
        "cycle": 2026,
    }
    return pd.DataFrame([{**base, **r} for r in (rows or [{}])])


def test_a_matched_incumbent_is_filed_with_a_candidate_id():
    out = filings.resolve_incumbent_status(_universe(), _roster(), cycle=2026)
    row = out.iloc[0]
    assert row["incumbent_status"] == "filed"
    assert row["incumbent_candidate_id"] == "H6GA01001"
    assert row["incumbent_status_source"] == "fec_api"
    assert "H6GA01001" in row["incumbent_status_evidence"]


def test_an_unmatched_incumbent_is_not_found_and_never_called_retired():
    """Absence missed ~88% of 2022-24 House departures, so it cannot mean retirement."""
    out = filings.resolve_incumbent_status(
        _universe([{"incumbent_name": "SOMEBODY ELSE"}]), _roster(), cycle=2026
    )
    row = out.iloc[0]
    assert row["incumbent_status"] == "not_found"
    assert "not evidence of either" in row["incumbent_status_evidence"]


def test_a_seat_with_no_incumbent_stays_unknown_rather_than_not_found():
    """An open seat has no member to have failed to file."""
    out = filings.resolve_incumbent_status(_universe([{"incumbent_name": None}]), _roster(), cycle=2026)
    assert out.iloc[0]["incumbent_status"] == "unknown"
    assert "no incumbent identified" in out.iloc[0]["incumbent_status_evidence"]


def test_no_fec_roster_leaves_every_status_unknown():
    """The pre-FEC state of the pipeline is not an error."""
    out = filings.resolve_incumbent_status(_universe(), None, cycle=2026)
    assert out.iloc[0]["incumbent_status"] == "unknown"
    assert out.iloc[0]["incumbent_match_method"] == "no_fec_roster"
    assert filings.validate_filings(out)["ok"]


def test_an_office_absent_from_the_roster_is_not_read_as_a_missing_filing():
    """A House-only pull must not report every senator as not_found."""
    out = filings.resolve_incumbent_status(
        _universe([{"office": "us_senate", "state_po": "WY", "district_num": None}]), _roster(), cycle=2026
    )
    assert out.iloc[0]["incumbent_status"] == "unknown"
    assert out.iloc[0]["incumbent_match_method"] == "no_fec_roster"


def test_the_module_never_emits_a_status_fec_cannot_support():
    """nominated needs primary results; withdrawn needs per-cycle filing history."""
    out = filings.resolve_incumbent_status(
        _universe([{}, {"geography_id": "g2", "district_num": 2.0, "incumbent_name": "NOT FILED"}]),
        _roster(),
        cycle=2026,
    )
    assert set(out["incumbent_status"]) <= set(filings.FEC_DERIVABLE_STATUSES) | {"unknown"}
    rep = filings.validate_filings(out)
    assert rep["ok"] and rep["status.rows_claiming_unsupported"] == 0


def test_the_vocabulary_ranks_nomination_above_filing():
    """A member past their primary is a stronger claim than one who merely filed."""
    order = filings.INCUMBENT_STATUSES
    assert order.index("nominated") > order.index("filed") > order.index("unknown")


def test_a_fabricated_status_fails_validation():
    out = filings.resolve_incumbent_status(_universe(), _roster(), cycle=2026)
    out.loc[0, "incumbent_status"] = "nominated"
    rep = filings.validate_filings(out)
    assert not rep["ok"]
    assert rep["status.rows_claiming_unsupported"] == 1


def test_a_status_without_evidence_fails_validation():
    out = filings.resolve_incumbent_status(_universe(), _roster(), cycle=2026)
    out.loc[0, "incumbent_status_evidence"] = ""
    assert not filings.validate_filings(out)["provenance.evidence_present"]


# ------------------------------------------------------- the party resolution (P0-003)
def test_fec_fills_a_party_the_returns_left_blank():
    """Wyoming 2020 carries a null party, which is why Lummis needed a hand override."""
    out = filings.resolve_incumbent_status(
        _universe([{"incumbent_name": "CYNTHIA M LUMMIS", "incumbent_party": None}]),
        _roster([{"fec_name": "LUMMIS, CYNTHIA M", "fec_party": "REP"}]),
        cycle=2026,
    )
    assert filings.resolved_incumbent_party(out).iloc[0] == "REPUBLICAN"


def test_the_returns_party_wins_a_disagreement_with_fec():
    """MEDSL describes the ballot the votes were cast on; FEC only fills a gap."""
    out = filings.resolve_incumbent_status(
        _universe([{"incumbent_party": "DEMOCRAT"}]), _roster([{"fec_party": "REP"}]), cycle=2026
    )
    assert filings.resolved_incumbent_party(out).iloc[0] == "DEMOCRAT"


def test_an_unmatched_seat_with_no_party_resolves_to_nothing_usable():
    out = filings.resolve_incumbent_status(
        _universe([{"incumbent_name": "NOBODY HERE", "incumbent_party": None}]), _roster(), cycle=2026
    )
    assert filings.resolved_incumbent_party(out).iloc[0] not in {"DEMOCRAT", "REPUBLICAN"}


# ------------------------------------------------------------------------- summary
def test_the_summary_reports_the_split_and_the_caveats():
    out = filings.resolve_incumbent_status(
        _universe([{}, {"geography_id": "g2", "district_num": 2.0, "incumbent_name": "NOT FILED"}]),
        _roster(),
        cycle=2026,
    )
    s = filings.filings_summary(out)
    assert s["seats"] == 2 and s["by_status"]["filed"] == 1 and s["filed_share"] == 0.5
    assert any("not renominated" in c or "not that they were renominated" in c for c in s["caveats"])
    assert any("not retirement" in c for c in s["caveats"])

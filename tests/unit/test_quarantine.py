"""Reconciliation quarantine (CLAUDE.md §6 — documented exclusion, not a silent fix)."""

from __future__ import annotations

import pandas as pd

from election_prediction.data import quarantine
from election_prediction.data.validation import validate_silver_returns


def _race(race_id: str, votes: list[int], total: int) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "race_id": race_id,
                "cycle": 2024,
                "office": "us_house",
                "state_po": "NY",
                "district_num": 13,
                "candidate": f"CAND {i}",
                "candidatevotes": v,
                "totalvotes": total,
            }
            for i, v in enumerate(votes)
        ]
    )


def test_reconciling_race_is_retained():
    returns = _race("good", [60, 40], 100)
    retained, quarantined, manifest = quarantine.split_quarantine(returns)
    assert len(retained) == 2
    assert quarantined.empty
    assert manifest.empty


def test_mismatched_race_is_quarantined_with_a_reason():
    returns = pd.concat([_race("good", [60, 40], 100), _race("bad", [60, 60], 100)])
    retained, quarantined, manifest = quarantine.split_quarantine(returns)

    assert set(retained["race_id"]) == {"good"}
    assert set(quarantined["race_id"]) == {"bad"}
    assert len(manifest) == 1
    row = manifest.iloc[0]
    assert row["race_id"] == "bad"
    assert row["difference"] == 20
    assert row["reason"], "every quarantined race must carry a documented reason"


def test_unreported_race_is_not_quarantined():
    """A race with no reported total is the unopposed sentinel, not a reconciliation failure."""
    returns = _race("unopposed", [pd.NA], pd.NA).astype({"candidatevotes": "Int64", "totalvotes": "Int64"})
    retained, quarantined, manifest = quarantine.split_quarantine(returns)
    assert len(retained) == 1
    assert manifest.empty


def test_quarantine_makes_the_reconciliation_gate_pass():
    """The quarantine rule and the validation gate must not be able to disagree."""
    returns = pd.concat([_race("good", [60, 40], 100), _race("bad", [60, 60], 100)])
    assert not validate_silver_returns(returns, required_columns=[]).ok

    retained, _, _ = quarantine.split_quarantine(returns)
    report = validate_silver_returns(retained, required_columns=[])
    frame = report.to_frame()
    recon = frame[frame["check"] == "votes.reconcile_to_total"]
    assert len(recon) == 1 and recon.iloc[0]["status"] == "PASS"


def test_summarize_reports_share_of_races():
    returns = pd.concat([_race("good", [60, 40], 100), _race("bad", [60, 60], 100)])
    _, _, manifest = quarantine.split_quarantine(returns)
    stats = quarantine.summarize(manifest, races_total=returns["race_id"].nunique())
    assert stats["quarantined_races"] == 1
    assert stats["races_total"] == 2
    assert stats["pct_of_races"] == 50.0
    assert stats["by_reason"]


def test_unnamed_party_line_rows_are_not_duplicates():
    """MEDSL records aggregate minor-party votes with no candidate name.

    Several such rows share a race and an empty candidate name but sit on different
    party lines. They are real counted votes that reconcile to the race total, so the
    natural key includes the party line rather than treating them as duplicates.
    """

    def row(candidate: str, party: str, votes: int) -> dict:
        return {
            "race_id": "r",
            "candidate": candidate,
            "party": party,
            "candidatevotes": votes,
            "totalvotes": 100,
        }

    returns = pd.DataFrame(
        [
            row("SMITH", "DEMOCRAT", 60),
            row("", "INDEPENDENT", 30),
            row("", "SOCIALIST LABOR", 10),
        ]
    )
    report = validate_silver_returns(returns, required_columns=[])
    frame = report.to_frame()
    key = frame[frame["check"] == "keys.unique_race_candidate_party"]
    assert len(key) == 1 and key.iloc[0]["status"] == "PASS"

    # A true double-count on the same party line is still caught.
    dupe = pd.concat([returns, returns.iloc[[0]]], ignore_index=True)
    frame = validate_silver_returns(dupe, required_columns=[]).to_frame()
    key = frame[frame["check"] == "keys.unique_race_candidate_party"]
    assert key.iloc[0]["status"] == "FAIL"

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


# ---- runoffs are distinct contests ---------------------------------------------------------
# Louisiana's 2002 5th district ran an all-party primary in October and a runoff in December,
# both under stage GEN. Collapsed into one race its candidate votes summed 357,119 against a
# reported total of 184,657. Split on the `runoff` flag the file already carried, each round
# reconciles exactly: seven candidates to 184,657 and two to 172,462.
#
# This matters forward, not just for 2002: `score_preregistration` registered the rule that
# "Georgia and Louisiana can run to a December runoff", so a 2026 runoff would hit the same
# collapse while scoring the sealed forecast.


def _la_2002_rows():
    """The real Louisiana 2002 5th district rows, both rounds."""
    primary = [
        ("CLYDE C HOLLOWAY", 42573),
        ("JACK WRIGHT", 3581),
        ("LEE FLETCHER", 45278),
        ("ROBERT J BARHAM", 34533),
        ("RODNEY ALEXANDER", 52952),
        ("SAM HOUSTON MELTON JR", 4595),
        ("VINSON MOUSER", 1145),
    ]
    runoff = [("LEE FLETCHER", 85744), ("RODNEY ALEXANDER", 86718)]
    rows = [
        {
            "year": "2002",
            "state_po": "LA",
            "office": "US HOUSE",
            "district": "5",
            "stage": "GEN",
            "special": "FALSE",
            "runoff": flag,
            "candidate": name,
            "party": "OTHER",
            "writein": "FALSE",
            "mode": "TOTAL",
            "candidatevotes": votes,
            "totalvotes": total,
        }
        for flag, total, bloc in (("FALSE", 184657, primary), ("TRUE", 172462, runoff))
        for name, votes in bloc
    ]
    return pd.DataFrame(rows)


def test_a_runoff_is_a_separate_race_from_the_round_that_preceded_it():
    """Also pins that the key reads MEDSL's TRUE/FALSE strings, since `bool("FALSE")` is True."""
    from election_prediction.data import medsl

    df = _la_2002_rows()
    df["cycle"] = 2002
    df["district_num"] = 5
    df["office"] = "us_house"
    ids = medsl._race_id(df)  # strings left as the file writes them, deliberately
    assert ids.nunique() == 2
    assert set(ids) == {"2002_us_house_la_05_gen", "2002_us_house_la_05_gen_runoff"}


def test_the_mode_collapse_key_separates_the_rounds_too():
    """Omitting `runoff` here merged the rounds *before* the race key could split them,
    which assigned Fletcher's and Alexander's primary votes to the runoff and turned one
    quarantined race into two."""
    from election_prediction.data import medsl

    out, _ = medsl.collapse_vote_modes(_la_2002_rows())
    assert len(out) == 9, "no row may be merged across rounds"
    by_round = out.groupby("runoff")["candidatevotes"].sum().to_dict()
    assert by_round["FALSE"] == 184657
    assert by_round["TRUE"] == 172462

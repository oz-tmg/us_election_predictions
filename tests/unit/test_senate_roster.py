from pathlib import Path

import pandas as pd
import pytest

from election_prediction.features import race_universe, senate_roster


def test_official_roster_and_special_schedule_reconcile_the_live_chamber():
    roster = senate_roster.load_roster("data/reference/senate_roster_2026-10-18.csv")
    specials = pd.read_csv("data/reference/senate_specials_2026.csv")
    scheduled = senate_roster.scheduled_seats(roster, specials, cycle=2026)
    report = senate_roster.reconcile(roster, scheduled)
    assert report["seats_projected"] == 35
    assert report["holdovers"] == 65
    assert report["current_democratic_caucus"] == 47
    assert report["democratic_holdovers"] == 34
    assert set(scheduled.loc[scheduled.election_type.eq("special"), "state_po"]) == {"FL", "OH"}


def test_roster_replaces_a_resigned_regular_winner_and_adds_specials():
    roster = senate_roster.load_roster("data/reference/senate_roster_2026-10-18.csv")
    specials = pd.read_csv("data/reference/senate_specials_2026.csv")
    empty = pd.DataFrame(
        columns=[
            "office",
            "cycle",
            "stage",
            "candidatevotes",
            "geography_id",
            "candidate",
            "party_simplified",
            "state_po",
            "district_num",
        ]
    )
    universe, _ = race_universe.build_race_universe(
        empty, empty, cycle=2026, senate_roster=roster, senate_specials=specials
    )
    assert len(universe) == 35
    assert universe.set_index("state_po").loc["OH", "incumbent_name"] == "Jon Husted"
    assert universe["race_key"].is_unique


def test_duplicate_seat_and_unknown_caucus_are_rejected(tmp_path: Path):
    roster = senate_roster.load_roster("data/reference/senate_roster_2026-10-18.csv")
    path = tmp_path / "roster.csv"
    pd.concat([roster, roster.iloc[:1]]).to_csv(path, index=False)
    with pytest.raises(ValueError, match="duplicate"):
        senate_roster.load_roster(path)
    roster.loc[0, "caucus_party"] = "UNKNOWN"
    roster.to_csv(path, index=False)
    with pytest.raises(ValueError, match="caucus"):
        senate_roster.load_roster(path)

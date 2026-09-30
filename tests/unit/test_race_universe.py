"""Prospective race universe and canonical cycle table (P0-001)."""

from __future__ import annotations

import pandas as pd
import pytest

from election_prediction.features import race_universe as ru


@pytest.mark.parametrize(
    ("year", "expected"),
    [(2024, "2024-11-05"), (2026, "2026-11-03"), (2028, "2028-11-07"), (2032, "2032-11-02")],
)
def test_election_day_is_first_tuesday_after_first_monday(year, expected):
    day = ru.election_day(year)
    assert day.isoformat() == expected
    assert day.strftime("%A") == "Tuesday"


def _senate_rows(rows: list[tuple]) -> pd.DataFrame:
    """(cycle, state, candidate, party, votes, stage, special) -> silver-shaped frame."""
    return pd.DataFrame(
        [
            {
                "office": "us_senate",
                "cycle": c,
                "state_po": st,
                "geography_id": f"state:{st}",
                "district_num": pd.NA,
                "candidate": cand,
                "party_simplified": party,
                "candidatevotes": votes,
                "stage": stage,
                "special": special,
            }
            for c, st, cand, party, votes, stage, special in rows
        ]
    )


def test_senate_class_is_derived_from_the_six_year_rotation():
    returns = _senate_rows(
        [
            (2020, "AK", "A", "REPUBLICAN", 100, "gen", False),
            (2020, "GA", "B", "DEMOCRAT", 100, "gen", False),
            (2022, "NV", "C", "DEMOCRAT", 100, "gen", False),
            # A 2020 special fills another class's term and must not add a state.
            (2020, "AZ", "D", "DEMOCRAT", 100, "gen", True),
        ]
    )
    assert ru.senate_states_up(returns, 2026) == ["AK", "GA"]
    assert ru.senate_states_up(returns, 2028) == ["NV"]


def test_senate_incumbent_is_the_same_class_not_the_most_recent_winner():
    """Both of a state's seats share one geography_id; 'most recent' returns the wrong one."""
    returns = _senate_rows(
        [
            (2020, "AK", "CLASS II HOLDER", "REPUBLICAN", 100, "gen", False),
            (2022, "AK", "CLASS III HOLDER", "REPUBLICAN", 100, "gen", False),
        ]
    )
    universe, _ = ru.build_race_universe(returns, pd.DataFrame(columns=["cycle", "office"]), cycle=2026)
    row = universe[universe["office"] == "us_senate"].iloc[0]
    assert row["incumbent_name"] == "CLASS II HOLDER"
    assert row["last_contested_cycle"] == 2020


def test_a_runoff_supersedes_the_general_it_follows():
    """Georgia 2020: Perdue led the November general but lost the January 2021 runoff."""
    returns = _senate_rows(
        [
            (2020, "GA", "PERDUE", "REPUBLICAN", 2_462_617, "gen", False),
            (2020, "GA", "OSSOFF", "DEMOCRAT", 2_374_519, "gen", False),
            (2021, "GA", "OSSOFF", "DEMOCRAT", 2_269_262, "runoff", False),
            (2021, "GA", "PERDUE", "REPUBLICAN", 2_213_979, "runoff", False),
        ]
    )
    universe, _ = ru.build_race_universe(returns, pd.DataFrame(columns=["cycle", "office"]), cycle=2026)
    row = universe[universe["office"] == "us_senate"].iloc[0]
    assert row["incumbent_name"] == "OSSOFF", "the runoff decides the seat, not the general"


def test_same_cycle_runoff_also_supersedes():
    """Georgia 2022 filed its runoff in the same cycle as the general."""
    returns = _senate_rows(
        [
            (2022, "GA", "LEADER", "REPUBLICAN", 900, "gen", False),
            (2022, "GA", "WINNER", "DEMOCRAT", 800, "gen", False),
            (2022, "GA", "WINNER", "DEMOCRAT", 700, "gen runoff", False),
            (2022, "GA", "LEADER", "REPUBLICAN", 600, "gen runoff", False),
        ]
    )
    universe, _ = ru.build_race_universe(returns, pd.DataFrame(columns=["cycle", "office"]), cycle=2028)
    row = universe[universe["office"] == "us_senate"].iloc[0]
    assert row["incumbent_name"] == "WINNER"


def test_candidates_are_never_invented():
    """The universe is a seat list, not a candidate list — filings are a separate source."""
    returns = _senate_rows([(2020, "AK", "HOLDER", "REPUBLICAN", 100, "gen", False)])
    universe, coverage = ru.build_race_universe(
        returns, pd.DataFrame(columns=["cycle", "office"]), cycle=2026
    )
    assert (universe["incumbent_status"] == "unknown").all()
    assert any("filings" in item for item in coverage["not_derivable"])


def test_cycle_table_marks_governor_out_of_coverage_rather_than_omitting_it():
    returns = _senate_rows([(2020, "AK", "HOLDER", "REPUBLICAN", 100, "gen", False)])
    table = ru.build_cycle_table([2026], returns).set_index("office")
    assert table.loc["governor", "coverage"] == "out_of_coverage"
    assert table.loc["president", "election_type"] == "not_held", "2026 is not a presidential year"
    assert table.loc["us_house", "seats"] == 435


# ---- RD-001: boundary confidence comes from the register, not the decade ----------------


def _house_seats(states: list[tuple[str, int]]) -> pd.DataFrame:
    """(state, district) -> the seat frame ``build_race_universe`` accepts."""
    return pd.DataFrame(
        [
            {"geography_id": f"state:{st}|district:cong_{d:02d}", "state_po": st, "district_num": float(d)}
            for st, d in states
        ]
    )


def test_without_a_register_every_house_seat_is_unverified():
    """No sourced map information means say so, not guess. project_house then refuses."""
    universe, coverage = ru.build_race_universe(
        _senate_rows([(2020, "AK", "HOLDER", "REPUBLICAN", 100, "gen", False)]),
        pd.DataFrame(columns=["cycle", "office"]),
        cycle=2026,
        seat_universe=_house_seats([("TX", 1), ("GA", 1)]),
    )
    house = universe[universe["office"] == "us_house"]
    assert set(house["boundary_confidence"]) == {"unverified"}
    assert coverage["house_by_boundary_confidence"] == {"unverified": 2}


def test_with_the_register_each_seat_gets_its_state_s_sourced_confidence():
    from election_prediction.features import plan_versions as pv

    universe, coverage = ru.build_race_universe(
        _senate_rows([(2020, "AK", "HOLDER", "REPUBLICAN", 100, "gen", False)]),
        pd.DataFrame(columns=["cycle", "office"]),
        cycle=2026,
        seat_universe=_house_seats([("TX", 1), ("GA", 1), ("MO", 1)]),
        plans=pv.PlanVersions.load(),
    )
    house = universe[universe["office"] == "us_house"].set_index("state_po")
    assert house.loc["TX", "boundary_confidence"] == "redrawn"
    assert house.loc["GA", "boundary_confidence"] == "unchanged"  # no register row -> decennial
    # Missouri: enjoined 2025 map, votes its 2022 map. Territory unchanged, litigation live.
    assert house.loc["MO", "boundary_confidence"] == "unchanged"
    assert house.loc["MO", "litigation_risk"] == "active"
    assert coverage["redrawn_states"] == ["TX"]
    assert coverage["litigation_active_states"] == ["MO"]


def test_litigation_never_leaks_into_the_boundary_judgement():
    """Missouri's prior is valid; a register that marked it redrawn would discard it."""
    from election_prediction.features import plan_versions as pv

    plans = pv.PlanVersions.load()
    assert plans.litigation_risk("MO", 2026) == "active"
    assert plans.boundary_confidence("MO", 2026) == "unchanged"

"""Incumbency (F-001), Senate baseline (P1-003), and national-swing adjustment (P1-004)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from election_prediction.features import incumbency
from election_prediction.models.baseline import generic_ballot as gb
from election_prediction.models.baseline import senate


def _returns(rows: list[dict]) -> pd.DataFrame:
    """Minimal silver-shaped returns frame."""
    return pd.DataFrame(rows).assign(
        office=lambda d: d.get("office", "us_house"),
        special=lambda d: d.get("special", False),
    )


def _house_race(cycle: int, district: int, candidates: list[tuple[str, str, int]]) -> list[dict]:
    return [
        {
            "race_id": f"{cycle}_us_house_ va_{district}".replace(" ", ""),
            "cycle": cycle,
            "office": "us_house",
            "state_po": "VA",
            "district_num": district,
            "geography_id": f"cong_district:51:{district:02d}",
            "candidate": name,
            "party_simplified": party,
            "candidatevotes": votes,
            "special": False,
        }
        for name, party, votes in candidates
    ]


# ------------------------------------------------------------------ plan eras
@pytest.mark.parametrize(
    ("cycle", "expected"),
    [(1976, 1972), (1980, 1972), (1982, 1982), (2000, 1992), (2002, 2002), (2022, 2022), (2024, 2022)],
)
def test_plan_era_boundaries(cycle, expected):
    """Maps are redrawn for the election two years after each decennial census."""
    assert incumbency.plan_era(cycle) == expected


# ---------------------------------------------------------------- incumbency
def test_incumbent_running_is_detected():
    returns = _returns(
        _house_race(2014, 1, [("JANE SMITH", "DEMOCRAT", 100), ("BOB JONES", "REPUBLICAN", 90)])
        + _house_race(2016, 1, [("JANE SMITH", "DEMOCRAT", 110), ("AL RAY", "REPUBLICAN", 80)])
    )
    inc = incumbency.build_incumbency(returns, "us_house").set_index("cycle")

    assert inc.loc[2016, "incumbent_running"]
    assert not inc.loc[2016, "open_seat"]
    assert inc.loc[2016, "incumbent_name"] == "JANE SMITH"
    assert inc.loc[2016, "incumbent_party"] == "DEMOCRAT"
    assert inc.loc[2016, "incumbent_won"]


def test_open_seat_when_prior_winner_absent():
    returns = _returns(
        _house_race(2014, 1, [("JANE SMITH", "DEMOCRAT", 100)])
        + _house_race(2016, 1, [("NEW PERSON", "DEMOCRAT", 100), ("AL RAY", "REPUBLICAN", 90)])
    )
    inc = incumbency.build_incumbency(returns, "us_house").set_index("cycle")

    assert inc.loc[2016, "open_seat"]
    assert not inc.loc[2016, "incumbent_running"]


def test_no_incumbency_claimed_across_a_redistricting_boundary():
    """District 1 in 2020 is not the same territory as district 1 in 2022."""
    returns = _returns(
        _house_race(2020, 1, [("JANE SMITH", "DEMOCRAT", 100), ("BOB JONES", "REPUBLICAN", 90)])
        + _house_race(2022, 1, [("JANE SMITH", "DEMOCRAT", 110), ("AL RAY", "REPUBLICAN", 80)])
    )
    inc = incumbency.build_incumbency(returns, "us_house").set_index("cycle")

    assert inc.loc[2022, "redistricting_break"]
    assert not inc.loc[2022, "incumbent_running"], "must not claim incumbency across a redraw"
    assert not inc.loc[2022, "open_seat"], "an unusable prior is not the same as an open seat"
    assert pd.isna(inc.loc[2022, "incumbent_name"])


def test_senate_looks_back_six_years_not_two():
    """A two-year lookback would cross Senate classes and invent a phantom incumbent."""
    rows = []
    for cycle, cands in [
        (2012, [("ANN LEE", "DEMOCRAT", 100), ("RON PAZ", "REPUBLICAN", 90)]),
        (2014, [("KAY WEST", "REPUBLICAN", 100), ("DAN OTT", "DEMOCRAT", 90)]),
        (2018, [("ANN LEE", "DEMOCRAT", 105), ("MAX ROE", "REPUBLICAN", 95)]),
    ]:
        rows += [
            {
                "race_id": f"{cycle}_us_senate_va",
                "cycle": cycle,
                "office": "us_senate",
                "state_po": "VA",
                "district_num": pd.NA,
                "geography_id": "state:51",
                "candidate": name,
                "party_simplified": party,
                "candidatevotes": votes,
                "special": False,
            }
            for name, party, votes in cands
        ]
    inc = incumbency.build_incumbency(_returns(rows), "us_senate").set_index("cycle")

    # 2018 inherits from 2012 (same class), not from 2014 (the other seat).
    assert inc.loc[2018, "incumbent_running"]
    assert inc.loc[2018, "incumbent_name"] == "ANN LEE"
    # 2014 has no six-year predecessor in this fixture, so it claims nothing.
    assert not inc.loc[2014, "prior_available"]


def test_name_normalization_ignores_punctuation_only():
    assert incumbency.normalize_name("MARIO DIAZ-BALART") == incumbency.normalize_name("MARIO DIAZ BALART")
    assert incumbency.normalize_name("O'ROURKE, BETO") != incumbency.normalize_name("ROURKE, BET")


# ------------------------------------------------------- national swing (P1-004)
def _swing_panel(national_swings: dict[int, float], n_districts: int = 40) -> pd.DataFrame:
    """Districts that follow the national swing exactly, plus deterministic noise."""
    rows = []
    rng = np.random.default_rng(0)
    for cycle, ns in national_swings.items():
        for d in range(n_districts):
            rows.append(
                {
                    "geography_id": f"cong_district:51:{d:02d}",
                    "cycle": cycle,
                    "plan_era": incumbency.plan_era(cycle),
                    "district_swing": ns + rng.normal(0, 0.01),
                    "national_swing": ns,
                }
            )
    return pd.DataFrame(rows)


def test_swing_ratio_recovers_uniform_swing():
    est = gb.estimate_swing_ratio(_swing_panel({2014: -0.02, 2016: 0.01, 2018: 0.05}))
    assert est["status"] == "ok"
    assert est["swing_ratio"] == pytest.approx(1.0, abs=0.05), "uniform swing must recover beta ~ 1"


def test_swing_ratio_is_unidentified_with_a_single_cycle():
    """One cycle gives every district the same national swing; the slope is arbitrary."""
    est = gb.estimate_swing_ratio(_swing_panel({2024: 0.03}))
    assert est["status"] == "unidentified"
    assert "swing_ratio" not in est, "an arbitrary slope must not be reported as an estimate"


def test_apply_national_swing_shifts_and_clips():
    baseline = pd.DataFrame({"two_party_dem_share": [0.50, 0.98]})
    out = gb.apply_national_swing(baseline, national_swing=0.04, swing_ratio=1.0)
    assert out.loc[0, "adjusted_dem_share"] == pytest.approx(0.54)
    assert out.loc[1, "adjusted_dem_share"] == 1.0, "shares stay in [0, 1]"


# ----------------------------------------------------------- senate (P1-003)
def test_white_house_party_uses_electoral_votes_not_popular_vote():
    """2000 and 2016 diverge; the sitting president must follow the Electoral College."""
    race_table = pd.DataFrame(
        [
            # CA votes Dem heavily (big popular margin) but loses the EC to the rest.
            {
                "office": "president",
                "cycle": 2016,
                "state_po": "CA",
                "two_party_dem_share": 0.80,
                "total_votes": 100,
            },
            {
                "office": "president",
                "cycle": 2016,
                "state_po": "TX",
                "two_party_dem_share": 0.45,
                "total_votes": 10,
            },
            {
                "office": "president",
                "cycle": 2016,
                "state_po": "FL",
                "two_party_dem_share": 0.49,
                "total_votes": 10,
            },
            {
                "office": "president",
                "cycle": 2016,
                "state_po": "PA",
                "two_party_dem_share": 0.49,
                "total_votes": 10,
            },
            {
                "office": "president",
                "cycle": 2016,
                "state_po": "OH",
                "two_party_dem_share": 0.47,
                "total_votes": 10,
            },
        ]
    )
    assert senate._white_house_party(race_table).loc[2016] == "REPUBLICAN"

"""Regional reversion scenario (South Texas, 2026-10-29). Synthetic fixtures only."""

from __future__ import annotations

import pandas as pd
import pytest

from election_prediction.scenarios import regional_reversion as rr

REGION = ["48001"]


def _county_votes() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "cycle": [2020, 2020, 2024, 2024],
            "county_fips": ["48001", "48003", "48001", "48003"],
            "dem_votes": [60, 40, 45, 38],
            "rep_votes": [40, 60, 55, 62],
        }
    )


def test_excess_swing_is_region_minus_state() -> None:
    s = rr.measure_swing(_county_votes(), REGION, from_cycle=2020, to_cycle=2024)
    assert s.region_swing == pytest.approx(-0.15)
    assert s.state_swing == pytest.approx(0.415 - 0.5)
    assert s.excess_swing == pytest.approx(-0.15 - (0.415 - 0.5))


def test_missing_region_county_is_refused() -> None:
    with pytest.raises(ValueError, match="missing"):
        rr.measure_swing(_county_votes(), ["48999"], from_cycle=2020, to_cycle=2024)


def _blocks() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "block_id": ["480010001001000", "480030001001000", "480030001001001"],
            "new_district": [1, 1, 2],
            "dem_votes": [30.0, 20.0, 40.0],
            "rep_votes": [10.0, 40.0, 60.0],
        }
    )


def test_district_region_share_uses_block_county() -> None:
    shares = rr.district_region_share(_blocks(), REGION).set_index("new_district")
    assert shares.loc[1, "region_share"] == pytest.approx(40 / 100)
    assert shares.loc[2, "region_share"] == 0
    assert rr.statewide_region_share(_blocks(), REGION) == pytest.approx(40 / 200)


def test_adjustment_reverses_part_of_the_excess_swing_in_state_only() -> None:
    shares = rr.district_region_share(_blocks(), REGION)
    adjust = rr.reversion_adjustment(
        state_po="TX", district_shares=shares, statewide_share=0.2, excess_swing=-0.1, fraction=0.5
    )
    house = pd.DataFrame(
        {"state_po": ["TX", "TX", "OK"], "district_num": [1.0, 2.0, 1.0], "mean_dem_share": [0.4, 0.4, 0.4]}
    )
    out = adjust(house, "us_house")
    assert out["mean_dem_share"].tolist() == pytest.approx([0.4 + 0.5 * 0.1 * 0.4, 0.4, 0.4])
    senate = pd.DataFrame(
        {"state_po": ["TX", "OK"], "district_num": [None, None], "mean_dem_share": [0.5, 0.5]}
    )
    assert adjust(senate, "us_senate")["mean_dem_share"].tolist() == pytest.approx(
        [0.5 + 0.5 * 0.1 * 0.2, 0.5]
    )


def test_fraction_outside_unit_interval_is_refused() -> None:
    with pytest.raises(ValueError):
        rr.reversion_adjustment(
            state_po="TX",
            district_shares=pd.DataFrame({"new_district": [], "region_share": []}),
            statewide_share=0.0,
            excess_swing=-0.1,
            fraction=1.5,
        )

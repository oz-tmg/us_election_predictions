"""Old-to-new vote transfer, built (RD-003).

The two properties worth pinning hardest are **vote conservation** — a transfer that loses
or invents votes is worse than the fallback it replaces — and the handling of county-level
ballots, which in Virginia 2020 are 63.7% of the vote and belong to no precinct at all.
"""

from __future__ import annotations

import pandas as pd
import pytest

from election_prediction import build_plan_transfer as bpt
from election_prediction.features import block_crosswalk, plan_transfer


def _votes(rows):
    """rows: (county_fips, precinct, dem, rep)."""
    df = pd.DataFrame(rows, columns=["county_fips", "precinct", "dem_votes", "rep_votes"])
    df["is_pseudo"] = df["precinct"].str.startswith(bpt.PSEUDO_PRECINCT_PREFIXES)
    df["vtd_key"] = df["precinct"].map(block_crosswalk.normalise_precinct_code)
    df.loc[df["is_pseudo"], "vtd_key"] = None
    df["precinct_id"] = df["county_fips"] + "|" + df["precinct"]
    return df


def _block_vtd(rows):
    """rows: (block_id, county_fips, vtd_key)."""
    return pd.DataFrame(rows, columns=["block_id", "county_fips", "vtd_key"]).assign(
        vtd_key=lambda d: d["vtd_key"].astype(str), vtd_code=lambda d: d["vtd_key"]
    )


def _block_pop(rows):
    return pd.DataFrame(rows, columns=["block_id", "pop"])


def test_a_precincts_votes_are_split_across_its_blocks_by_population():
    votes = _votes([("51001", "101 - A", 300.0, 100.0)])
    bv = _block_vtd([("b1", "51001", "101"), ("b2", "51001", "101")])
    bp = _block_pop([("b1", 300.0), ("b2", 100.0)])
    out, stats = bpt.apportion_to_blocks(votes, bv, bp)

    assert out["dem_votes"].sum() == pytest.approx(300.0)
    assert out["rep_votes"].sum() == pytest.approx(100.0)
    assert out.set_index("block_id")["dem_votes"].to_dict() == pytest.approx({"b1": 225.0, "b2": 75.0})
    assert stats["votes_placed"] == pytest.approx(stats["votes_offered"])


def test_a_precinct_whose_blocks_are_all_unpopulated_is_split_evenly_not_dropped():
    """It still cast votes. A zero-population block is a Census artefact, not an absence."""
    votes = _votes([("51001", "101 - A", 10.0, 10.0)])
    bv = _block_vtd([("b1", "51001", "101"), ("b2", "51001", "101")])
    bp = _block_pop([("b1", 0.0), ("b2", 0.0)])
    out, stats = bpt.apportion_to_blocks(votes, bv, bp)
    assert out["dem_votes"].sum() == pytest.approx(10.0)
    assert out["dem_votes"].tolist() == pytest.approx([5.0, 5.0])


def test_county_level_ballots_are_spread_by_turnout_not_by_population():
    """Virginia reports 63.7% of its 2020 presidential vote in two pseudo-precincts per locality.

    They are weighted by the precinct-level vote already placed in each block, so the method
    does not assume absentee voters are distributed like residents. Here block b1 holds all
    the precinct-level turnout despite b2 holding most of the population, so the absentee
    block follows the turnout.
    """
    votes = _votes(
        [
            ("51001", "101 - A", 100.0, 0.0),
            ("51001", "# AB - CENTRAL ABSENTEE PRECINCT", 40.0, 10.0),
        ]
    )
    bv = _block_vtd([("b1", "51001", "101")])
    bp = _block_pop([("b1", 1.0), ("b2", 999.0)])
    out, stats = bpt.apportion_to_blocks(votes, bv, bp)

    assert stats["votes_from_county_aggregates"] == pytest.approx(50.0)
    assert out["dem_votes"].sum() == pytest.approx(140.0)
    assert set(out["block_id"]) == {"b1"}, "b2 has no measured turnout, so it gets no absentee vote"


def test_votes_in_a_county_with_no_placed_turnout_are_reported_not_spread_statewide():
    """Unplaceable has to be a number someone can see."""
    votes = _votes(
        [
            ("51001", "101 - A", 100.0, 0.0),
            ("51003", "# AB - CENTRAL ABSENTEE PRECINCT", 70.0, 0.0),
        ]
    )
    bv = _block_vtd([("b1", "51001", "101")])
    bp = _block_pop([("b1", 10.0)])
    out, stats = bpt.apportion_to_blocks(votes, bv, bp)
    assert stats["votes_unplaceable"] == pytest.approx(70.0)
    assert out["dem_votes"].sum() == pytest.approx(100.0), "they must not land in another county"


def test_a_precinct_with_no_matching_vtd_is_allocated_by_county_not_dropped():
    """North Carolina's one-stop batches carry real vote and no VTD code.

    Dropping them cost 47% of the state. A precinct whose code does not resolve knows its
    county and not its blocks, which is the same position as a central absentee block.
    """
    votes = _votes([("51001", "101 - A", 10.0, 0.0), ("51001", "999 - GHOST", 5.0, 0.0)])
    bv = _block_vtd([("b1", "51001", "101")])
    bp = _block_pop([("b1", 1.0)])
    out, stats = bpt.apportion_to_blocks(votes, bv, bp)
    assert stats["precincts_unmatched"] == 1
    assert stats["votes_unmatched_to_a_vtd"] == pytest.approx(5.0)
    assert "51001|999 - GHOST" in stats["unmatched_precincts"]
    assert stats["votes_unplaceable"] == 0.0, "its county is known, so it is placeable"
    assert out["dem_votes"].sum() == pytest.approx(15.0), "no vote may be lost"


def test_the_source_gate_refuses_a_run_whose_licences_were_not_reviewed():
    """Dropping a source from the gate to make a run succeed is what the gate prevents."""
    with pytest.raises(plan_transfer.UnregisteredSourceError, match="census_baf_2020"):
        plan_transfer.assert_sources_registered({"census_pl94171_2020": "ok"})
    assert set(plan_transfer.REQUIRED_SOURCES) <= set(bpt.SOURCES)


# ---- the same-office control ---------------------------------------------------------------
# The --backtest comparison answers the operational question (does a transferred prior beat
# the fallback at predicting the next House result) but conflates geography error with four
# years and a change of office. This control removes the second.


def _transferred(rows):
    """rows: (new_district, transferred_dem_share)."""
    df = pd.DataFrame(rows, columns=["new_district", "transferred_dem_share"])
    df["state_po"] = "VA"
    df["unsplit_share"] = 0.8
    df["old_district_majority_share"] = 0.7
    return df


def test_the_control_separates_the_national_swing_from_the_geography_error(tmp_path):
    """A uniform offset is a swing and shows in the mean; scatter is geography and shows in sd."""
    baseline = pd.DataFrame(
        {
            "state_po": ["VA"] * 3,
            "district_num": [1, 2, 3],
            "baseline_dem_share": [0.40, 0.50, 0.60],
            "baseline_quality": ["ok"] * 3,
        }
    )
    path = tmp_path / "cd_presidential_baseline_2024.parquet"
    baseline.to_parquet(path, index=False)

    # Every district off by exactly +0.02: a swing, not a transfer defect.
    out = bpt.same_office_control(path, _transferred([(1, 0.42), (2, 0.52), (3, 0.62)]), "VA")
    assert out["mean_error"] == pytest.approx(0.02)
    assert out["sd_error"] == pytest.approx(0.0, abs=1e-9)
    assert out["mae"] == pytest.approx(0.02)


def test_the_control_skips_rather_than_inventing_a_score_without_overlap(tmp_path):
    baseline = pd.DataFrame(
        {
            "state_po": ["TX"],
            "district_num": [1],
            "baseline_dem_share": [0.4],
            "baseline_quality": ["ok"],
        }
    )
    path = tmp_path / "b.parquet"
    baseline.to_parquet(path, index=False)
    assert "skipped" in bpt.same_office_control(path, _transferred([(1, 0.4)]), "VA")


def test_an_unmeasured_sigma_is_refused():
    with pytest.raises(plan_transfer.TransferSigmaUnmeasured, match="unmeasured"):
        plan_transfer.transfer_sigma_from_backtest({"beats_fallback": True})


def test_a_transfer_that_loses_to_the_fallback_is_refused():
    """The projection already has the fallback; a worse replacement is a regression."""
    with pytest.raises(plan_transfer.TransferSigmaUnmeasured, match="does not beat"):
        plan_transfer.transfer_sigma_from_backtest(
            {
                "transfer_sigma": 0.02,
                "beats_fallback": False,
                "transfer_mae": 0.14,
                "state_lean_fallback_mae": 0.12,
            }
        )


def test_the_measured_virginia_sigma_is_accepted():
    """Virginia 2020->2022: transfer MAE 0.0314 against a fallback 0.1253."""
    assert plan_transfer.transfer_sigma_from_backtest(
        {
            "transfer_sigma": 0.0184,
            "beats_fallback": True,
            "transfer_mae": 0.0314,
            "state_lean_fallback_mae": 0.1253,
        }
    ) == pytest.approx(0.0184)


def test_actual_shares_come_from_certified_returns_on_a_two_party_basis(tmp_path):
    returns = pd.DataFrame(
        {
            "office": ["us_house"] * 3,
            "cycle": [2022] * 3,
            "state_po": ["VA"] * 3,
            "district_num": [1, 1, 1],
            "party_simplified": ["DEMOCRAT", "REPUBLICAN", "LIBERTARIAN"],
            "candidatevotes": [60, 40, 1000],
        }
    )
    path = tmp_path / "returns.parquet"
    returns.to_parquet(path, index=False)
    out = bpt._actual_from_house_returns(path, "VA", 2022)
    assert out["actual_dem_share"].iloc[0] == pytest.approx(0.6), "third parties distort raw margins"


# ---- the usability gate -------------------------------------------------------------------
# Texas is why this exists. Its transfer placed zero votes, produced an empty table, and the
# build wrote data/gold/plan_transfer_tx_2024.parquet and exited 0. A gold artefact that
# exists is a claim that it is usable.


def test_the_placement_floor_is_high_enough_to_catch_a_total_failure():
    """Measured placement by state: VA 100%, NC 86%, FL 82%, AL 5%, TX 0%."""
    assert bpt.MIN_PLACED_SHARE >= 0.90
    assert 0.052 < bpt.MIN_PLACED_SHARE and 0.0 < bpt.MIN_PLACED_SHARE


def test_a_state_whose_precincts_do_not_carry_vtd_codes_places_almost_nothing():
    """Alabama's returns name precincts "PREC 4010 - GARDENDALE CIVIC C" -- not a code.

    The join is by code, so it finds nothing, and the honest output is a refusal rather than
    a prior built from the 5% that happened to match.
    """
    votes = _votes([("01073", "PREC 4010 - GARDENDALE CIVIC C", 900.0, 100.0)])
    bv = _block_vtd([("b1", "01073", "4010")])
    bp = _block_pop([("b1", 10.0)])
    out, stats = bpt.apportion_to_blocks(votes, bv, bp)
    # "PREC" is the leading token, so no code matches and nothing can be placed.
    assert stats["votes_unplaceable"] == pytest.approx(1000.0)
    assert out.empty

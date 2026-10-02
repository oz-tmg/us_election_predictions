"""Old-to-new vote transfer (RD-003): the gates, and the three components that must not merge.

Synthetic fixtures only — no real block, BAF or precinct data is committed. These pin the
contract so that when real data lands the failure modes are already caught.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from election_prediction.features import plan_transfer as pt

SOURCES = dict.fromkeys(pt.REQUIRED_SOURCES, "registered 2026-09-30")


def _inputs(precincts: pd.DataFrame, assignments: pd.DataFrame) -> pt.TransferInputs:
    blocks = pd.DataFrame(
        {"block_id": assignments["block_id"], "state_po": "VA", "vap": 100}
    ).drop_duplicates("block_id")
    return pt.TransferInputs(blocks=blocks, assignments=assignments, precincts=precincts)


def _simple() -> pt.TransferInputs:
    """Two precincts, each wholly inside one new district, each from one old district."""
    precincts = pd.DataFrame(
        [
            {"precinct_id": "p1", "block_id": "b1", "state_po": "VA", "old_district": 1,
             "dem_votes": 600, "rep_votes": 400},
            {"precinct_id": "p2", "block_id": "b2", "state_po": "VA", "old_district": 2,
             "dem_votes": 300, "rep_votes": 700},
        ]
    )
    assignments = pd.DataFrame([{"block_id": "b1", "new_district": 1}, {"block_id": "b2", "new_district": 2}])
    return _inputs(precincts, assignments)


# ---- gates -----------------------------------------------------------------------------


def test_a_transfer_refuses_to_run_against_unregistered_sources():
    """Acquisition here is gated on a licence review; the gate lives in code, not prose."""
    with pytest.raises(pt.UnregisteredSourceError, match="dataset-registry"):
        pt.transfer(_simple(), sources={"census_baf_2020": "registered"})


def test_every_required_source_must_be_named():
    for drop in pt.REQUIRED_SOURCES:
        partial = {k: v for k, v in SOURCES.items() if k != drop}
        with pytest.raises(pt.UnregisteredSourceError, match=drop):
            pt.transfer(_simple(), sources=partial)


# ---- the arithmetic --------------------------------------------------------------------


def test_an_unsplit_single_source_precinct_transfers_its_share_exactly():
    out = pt.transfer(_simple(), sources=SOURCES).set_index("new_district")
    assert out.loc[1, "transferred_dem_share"] == pytest.approx(0.6)
    assert out.loc[2, "transferred_dem_share"] == pytest.approx(0.3)
    assert out.loc[1, "unsplit_share"] == pytest.approx(1.0)
    assert out.loc[1, "old_district_majority_share"] == pytest.approx(1.0)
    assert out.loc[1, "geocoded_share"] == pytest.approx(1.0)


def test_a_precinct_split_across_two_new_districts_lowers_only_the_unsplit_component():
    """The split is real; the other two components should not move because of it."""
    precincts = pd.DataFrame(
        [
            {"precinct_id": "p1", "block_id": "b1", "state_po": "VA", "old_district": 1,
             "dem_votes": 600, "rep_votes": 400},
            {"precinct_id": "p1", "block_id": "b2", "state_po": "VA", "old_district": 1,
             "dem_votes": 200, "rep_votes": 800},
        ]
    )
    assignments = pd.DataFrame([{"block_id": "b1", "new_district": 1}, {"block_id": "b2", "new_district": 2}])
    out = pt.transfer(_inputs(precincts, assignments), sources=SOURCES).set_index("new_district")
    assert out.loc[1, "unsplit_share"] == pytest.approx(0.0)
    assert out.loc[1, "old_district_majority_share"] == pytest.approx(1.0)
    assert out.loc[1, "geocoded_share"] == pytest.approx(1.0)


def test_a_new_district_blended_from_two_old_ones_lowers_only_the_majority_component():
    precincts = pd.DataFrame(
        [
            {"precinct_id": "p1", "block_id": "b1", "state_po": "VA", "old_district": 1,
             "dem_votes": 500, "rep_votes": 500},
            {"precinct_id": "p2", "block_id": "b2", "state_po": "VA", "old_district": 2,
             "dem_votes": 500, "rep_votes": 500},
        ]
    )
    assignments = pd.DataFrame([{"block_id": "b1", "new_district": 1}, {"block_id": "b2", "new_district": 1}])
    out = pt.transfer(_inputs(precincts, assignments), sources=SOURCES).set_index("new_district")
    assert out.loc[1, "old_district_majority_share"] == pytest.approx(0.5)
    assert out.loc[1, "unsplit_share"] == pytest.approx(1.0)
    assert out.loc[1, "n_source_old_districts"] == 2


def test_ungeocoded_vote_lowers_only_the_geocoded_component():
    precincts = pd.DataFrame(
        [
            {"precinct_id": "p1", "block_id": "b1", "state_po": "VA", "old_district": 1,
             "dem_votes": 600, "rep_votes": 400},
            {"precinct_id": "p2", "block_id": "bX", "state_po": "VA", "old_district": 1,
             "dem_votes": 500, "rep_votes": 500},  # bX has no assignment
        ]
    )
    assignments = pd.DataFrame([{"block_id": "b1", "new_district": 1}])
    out = pt.transfer(_inputs(precincts, assignments), sources=SOURCES).set_index("new_district")
    assert out.loc[1, "geocoded_share"] == pytest.approx(0.5)
    assert out.loc[1, "unsplit_share"] == pytest.approx(1.0)
    assert out.loc[1, "transferred_dem_share"] == pytest.approx(0.6)


def test_the_three_components_are_reported_separately_and_never_collapsed():
    """A single score would hide which of three different failures a district has."""
    out = pt.transfer(_simple(), sources=SOURCES)
    for c in pt.CONFIDENCE_COMPONENTS:
        assert c in out.columns
    assert not any("confidence_score" in c or "overall" in c for c in out.columns)


# ---- the backtest and its sigma ---------------------------------------------------------


def _backtest(transfer_err: float, fallback_err: float) -> dict:
    rng = np.random.default_rng(0)
    n = 40
    actual = pd.DataFrame(
        {
            "state_po": "VA",
            "new_district": range(n),
            "actual_dem_share": rng.uniform(0.35, 0.65, n),
        }
    )
    transferred = pd.DataFrame(
        {
            "state_po": "VA",
            "new_district": range(n),
            "transferred_dem_share": actual["actual_dem_share"] + transfer_err,
            "unsplit_share": 0.9,
            "old_district_majority_share": 0.8,
            "geocoded_share": 0.99,
        }
    )
    fallback = pd.DataFrame(
        {"state_po": ["VA"], "state_pres_lean_share": [actual["actual_dem_share"].mean() + fallback_err]}
    )
    return pt.backtest_transfer(transferred, actual, state_lean_fallback=fallback)


def test_the_backtest_measures_sigma_rather_than_assuming_it():
    res = _backtest(transfer_err=0.01, fallback_err=0.20)
    assert res["transfer_mae"] == pytest.approx(0.01, abs=1e-9)
    assert res["beats_fallback"] and res["beats_no_prior"]
    assert np.isfinite(res["transfer_sigma"])
    assert pt.transfer_sigma_from_backtest(res) == pytest.approx(res["transfer_sigma"])


def test_a_transfer_that_loses_to_the_fallback_is_refused():
    """The projection already has the fallback; a worse prior must not replace it."""
    res = _backtest(transfer_err=0.30, fallback_err=0.0)
    assert not res["beats_fallback"]
    with pytest.raises(pt.TransferSigmaUnmeasured, match="does not beat"):
        pt.transfer_sigma_from_backtest(res)


def test_an_unmeasured_sigma_is_refused_rather_than_defaulted():
    with pytest.raises(pt.TransferSigmaUnmeasured, match="unmeasured"):
        pt.transfer_sigma_from_backtest({"beats_fallback": True})


def test_the_backtest_reports_both_comparators_the_plan_names():
    res = _backtest(transfer_err=0.01, fallback_err=0.20)
    assert "no_prior_mae" in res and "state_lean_fallback_mae" in res
    assert res["confidence_components"].keys() == set(pt.CONFIDENCE_COMPONENTS)

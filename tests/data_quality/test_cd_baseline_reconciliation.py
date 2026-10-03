"""Per-state reconciliation of CD presidential baselines against certified state returns.

A state's congressional districts partition the state, so its CD baselines must sum back to
the two-party share the certified state-level return reports. Counting rows is not
validation (CLAUDE.md §3); reconciling totals is.

These exist because three defects got through a build that reported "50 files ok":

1. **County-aggregate vote was discarded.** States that report early/absentee ballots in a
   county-wide pseudo-precinct lost that vote wherever the county spanned two districts —
   29.7% of Virginia 2020, 29.6% of Washington 2020 (one precinct), 25.5% of Alabama.
   Mail ballots in 2020 leaned Democratic, so the loss was not neutral: Virginia's CD
   aggregate read 0.4918 against a certified 0.5515.
2. **Zero-vote district rows created phantom ambiguity.** Alabama lists every district
   touching a county on every precinct row in it, at zero votes for the ones the precinct
   is not in. Counting districts *present* made all 390 precincts of its split counties
   unresolvable.
3. **Fusion lines were counted as third-party vote.** New York lets a candidate appear on
   several party lines; Biden carried 386,627 votes on ``WORKING FAMILIES`` and Trump
   296,360 on ``CONSERVATIVE``. Classifying by party label alone dropped both from the
   two-party count, so New York recovered **92.2%** of its certified two-party presidential
   vote — at a *share* only 0.0046 off, because the two fusion blocks were of similar size.
   This one is the reason both a share check and a total check exist here: the share check
   cannot see it.
4. **A state was read twice.** The 2020 drop ships North Carolina as both
   ``2020-nc-precinct-general.csv`` and a ``-sorted`` re-cut, and summing both put North
   Carolina's baselines at 180% of its certified vote.

Each one is a *per-state* failure, so the check is per state. The set below is every state
that failed the gate plus controls that passed, read from the raw drop rather than from a
build report, so a stale artifact cannot make them pass.
"""

from __future__ import annotations

import functools
from pathlib import Path

import pandas as pd
import pytest

from election_prediction import build_cd_baselines as bcb_module
from election_prediction.build_cd_baselines import RECONCILIATION_TOLERANCE
from election_prediction.features import cd_baseline

RAW = Path("data/raw")
PANEL = Path("data/gold/presidential_panel.parquet")

# (state, cycle). The 2020 group is the seven states the gate failed plus two controls that
# passed; the 2024 group is the state that failed and the four that came closest.
CASES = [
    # failed on discarded county-aggregate vote
    ("VA", 2020),
    ("WA", 2020),
    ("MS", 2020),
    ("OK", 2020),
    # failed on phantom ambiguity from zero-vote district rows
    ("AL", 2020),
    # failed on being read twice
    ("NC", 2020),
    # errored outright: county_fips is blank on 0.18% of Rhode Island's rows, and an
    # all-or-nothing county key turned that into a failure for the whole state
    ("RI", 2020),
    # the extreme case: 78% of New Jersey 2020 arrives as county-level blocks, so all 12
    # districts are flagged heavily_allocated -- it must still reconcile in aggregate
    ("NJ", 2020),
    # passes the share gate at -0.4% and fails the vote-total gate at +13.4%: its file mixes
    # precinct rows with municipality rows, counting 241,958 Bergen County votes twice
    ("NJ", 2024),
    # failed the vote-*total* check while passing the share check: fusion voting put
    # 386,627 Biden votes (WORKING FAMILIES) and 296,360 Trump votes (CONSERVATIVE) in the
    # third-party bucket, so New York recovered 92.2% of its certified two-party vote at a
    # share only 0.0046 off
    ("NY", 2020),
    ("CT", 2020),
    # controls: these reconciled before the fix and must still reconcile
    ("MN", 2020),
    ("ND", 2020),
    ("GA", 2020),
    # 2024 states the vote-total gate flags, pinned so that a re-download which fixes one
    # fails this test and forces the exception list to be updated rather than left stale
    ("LA", 2024),
    ("OK", 2024),
    ("IN", 2024),
    # 2024: AZ failed the gate; the rest were the closest calls
    ("AZ", 2024),
    ("FL", 2024),
    ("TN", 2024),
    ("GA", 2024),
    ("NJ", 2024),
    ("VA", 2024),
]

# Indiana's 2020 file is incomplete *at source* — 53 of 92 counties, 2.15m of 3.03m
# presidential votes, and the missing share is disproportionately Republican (Trump
# 1,168,807 of a certified 1,729,519; Biden 937,215 of 1,242,416). No amount of allocation
# recovers a county that is absent, so Indiana is expected to fail the gate and the point of
# the test is that it is *flagged* rather than used. See docs/dataset-registry.md.
EXPECTED_SOURCE_GAPS = {("IN", 2020)}

# States whose *vote total* is wrong at source, so the total check is expected to fail and
# the point of the test is that it does. Each is flagged by the build, never used quietly.
#
#   NJ 2024  +13.4%  mixes precinct rows with municipality rows (241,958 Bergen votes twice)
#   LA 2024  -48.5%  the file carries 1,038,976 of ~1,975,375 certified presidential votes
#   OK 2024  -12.2%  omits OK-03's House race, so a whole district cannot be resolved
#   IN 2024   +5.1%  share lands at 0.4037 against 0.4035, so only the total sees it
EXPECTED_VOTE_TOTAL_FAILURES = {("NJ", 2024), ("LA", 2024), ("OK", 2024), ("IN", 2024)}


def _file(state: str, cycle: int) -> Path | None:
    directory = RAW / f"source=medsl/dataset=precinct_by_state/vintage={cycle}"
    for name in (
        f"{cycle}-{state.lower()}-precinct-general.csv",
        f"{cycle}_{state.lower()}_precinct_general.csv",
    ):
        if (directory / name).is_file():
            return directory / name
    return None


@pytest.fixture(scope="module")
def certified() -> pd.DataFrame:
    if not PANEL.is_file():
        pytest.skip(f"no certified panel at {PANEL}")
    return pd.read_parquet(PANEL)


@functools.cache
def _build(state: str, cycle: int) -> tuple[pd.DataFrame, dict]:
    """Cached: these files run to hundreds of megabytes and several tests share each one."""
    path = _file(state, cycle)
    if path is None:
        return None, None
    return cd_baseline.presidential_by_cd(path)


def _aggregate(state: str, cycle: int) -> tuple[pd.DataFrame, dict]:
    df, stats = _build(state, cycle)
    if df is None:
        pytest.skip(f"no {cycle} precinct file for {state} in {RAW}")
    return df, stats


@pytest.mark.parametrize(("state", "cycle"), CASES)
def test_state_cd_baselines_reconcile_to_the_certified_state_share(state, cycle, certified):
    df, stats = _aggregate(state, cycle)
    expected = certified[(certified["cycle"] == cycle) & (certified["state_po"] == state)]
    if expected.empty:
        pytest.skip(f"{state} {cycle} not in the certified panel")

    got = df["dem_votes"].sum() / df["two_party_votes"].sum()
    want = float(expected["two_party_dem_share"].iloc[0])
    assert got == pytest.approx(want, abs=RECONCILIATION_TOLERANCE), (
        f"{state} {cycle}: CD aggregate {got:.4f} vs certified {want:.4f}; "
        f"{stats['share_directly_observed']:.1%} of the vote resolved directly, "
        f"{stats['votes_unallocatable']:,.0f} votes could not be allocated"
    )


# Tolerance for the vote-*total* check below, held identical to the build's own gate so the
# two cannot disagree. The share check cannot see a duplication that is proportional across
# parties; only totals catch that. Measured deviations across the case list are 0.00% for
# most states and 0.25% at the top (New York 2020, whose files carry a `BLANK` ballot row its
# total omits) against New Jersey 2024's **+13.4%**, so 1% separates the benign from the
# broken with room to spare.
VOTE_TOTAL_TOLERANCE = bcb_module.VOTE_TOTAL_TOLERANCE


@pytest.fixture(scope="module")
def certified_two_party_votes() -> pd.Series:
    path = Path("data/silver/election_returns.parquet")
    if not path.is_file():
        pytest.skip(f"no silver returns at {path}")
    df = pd.read_parquet(path)
    major = df[(df["office"] == "president") & (df["party_simplified"].isin(["DEMOCRAT", "REPUBLICAN"]))]
    return major.groupby(["cycle", "state_po"])["candidatevotes"].sum()


@pytest.mark.parametrize(("state", "cycle"), CASES)
def test_collapsing_vote_modes_neither_loses_nor_duplicates_votes(state, cycle, certified_two_party_votes):
    """Vote-total reconciliation, which the share check cannot do (CLAUDE.md §3).

    A mode counted twice for both parties alike leaves the two-party *share* untouched and
    the two-party *total* inflated. MEDSL's mode conventions are genuinely inconsistent —
    Delaware and Indiana 2024 publish a ``TOTAL`` row alongside breakdowns, North Carolina
    2020 publishes breakdowns only, Alabama 2020 publishes a county-level ``ABSENTEE`` row
    beside precinct ``TOTAL`` rows — so this is the check that earns the right to use any
    of them. ``IN`` is excluded: its 2020 file is missing 39 counties at source.
    """
    if (state, cycle) in EXPECTED_SOURCE_GAPS:
        pytest.skip(f"{state} {cycle} is a known source gap")
    if (cycle, state) not in certified_two_party_votes.index:
        pytest.skip(f"{state} {cycle} not in the silver returns")

    df, _ = _aggregate(state, cycle)
    got = float(df["two_party_votes"].sum())
    want = float(certified_two_party_votes.loc[(cycle, state)])
    within = abs(got / want - 1) <= VOTE_TOTAL_TOLERANCE
    detail = (
        f"{state} {cycle}: precinct two-party total {got:,.0f} vs certified {want:,.0f} "
        f"({got / want - 1:+.4%})"
    )
    if (state, cycle) in EXPECTED_VOTE_TOTAL_FAILURES:
        assert not within, f"{detail} — this was a known source defect; if it is fixed, "
        "remove it from EXPECTED_VOTE_TOTAL_FAILURES rather than loosening the gate"
    else:
        assert within, detail


@pytest.mark.parametrize(("state", "cycle"), CASES)
def test_no_presidential_vote_is_silently_discarded(state, cycle):
    """Every vote is either resolved, allocated, or counted as unallocatable."""
    _, stats = _aggregate(state, cycle)
    accounted = (
        stats["state_presidential_votes"] * stats["share_directly_observed"]
        + stats["votes_allocated"]
        + stats["votes_unallocatable"]
    )
    assert accounted == pytest.approx(stats["state_presidential_votes"], rel=1e-3), (
        f"{state} {cycle}: {stats['state_presidential_votes']:,.0f} presidential votes but "
        f"{accounted:,.0f} accounted for"
    )


def test_a_state_read_twice_is_refused_rather_than_summed():
    """North Carolina's ``-sorted`` re-cut put its baselines at 180% of certified."""
    from election_prediction.data import governor

    files = governor.find_precinct_files(RAW, 2020)
    if not files:
        pytest.skip("no 2020 precinct drop")
    assert not [f for f in files if "sorted" in f.stem.lower()]
    states = [governor.state_from_filename(f) for f in files]
    assert len(states) == len(set(states)), f"a state appears twice: {sorted(states)}"


def test_indianas_source_gap_is_flagged_not_quietly_used():
    """A source that is missing 39 of 92 counties must fail the gate, not pass it."""
    state, cycle = next(iter(EXPECTED_SOURCE_GAPS))
    if not PANEL.is_file():
        pytest.skip(f"no certified panel at {PANEL}")
    df, _ = _aggregate(state, cycle)
    panel = pd.read_parquet(PANEL)
    from election_prediction import build_cd_baselines as bcb

    out, report = bcb.reconcile(df, panel, cycle)
    assert report["states_failing"] == [state]
    assert set(out["baseline_quality"]) == {bcb.QUALITY_FAILS_RECONCILIATION}


# ---- the allocation's own error -------------------------------------------------------------
# Allocation is an estimate and its error is measured, not asserted. ``backtest_allocation``
# pools a state's precinct-level early/absentee vote up to county level, allocates it back,
# and compares against the precinct detail the same file contains. See
# ``scripts/backtest_cd_allocation.py`` and ``reports/cd_allocation_backtest.json``.


def test_allocation_is_near_free_where_little_of_a_district_is_allocated():
    """The measured curve: below 10% allocated, MAE was 0.0001 across 48 districts.

    This is the band almost every production district sits in, so it is the claim that
    actually carries the baselines. North Carolina 2024 breaks absentee-by-mail out per
    precinct, which is 3.9% of its vote — the same order as the real unresolved share in
    most states.
    """
    path = _file("NC", 2024)
    if path is None:
        pytest.skip("no NC 2024 precinct file")
    r = cd_baseline.backtest_allocation(path, pooled_modes=frozenset({"ABSENTEE BY MAIL"}))
    assert r["status"] == "ok"
    assert r["share_of_vote_pooled"] < 0.10
    assert r["mae"] < 0.001, r["mae"]
    assert r["max_abs_error"] < 0.005, r["max_abs_error"]


def test_allocation_degrades_when_most_of_a_district_is_allocated():
    """Arizona 2024 pooled whole: 77% allocated, and CD-3 lands 19 points out.

    The point of this test is that the degradation is real and bounded, so a consumer has a
    reason to treat ``heavily_allocated`` as a refusal rather than a note. Maricopa County
    spans seven districts; spreading a county block across seven by turnout is a far weaker
    claim than spreading it across two.
    """
    path = _file("AZ", 2024)
    if path is None:
        pytest.skip("no AZ 2024 precinct file")
    r = cd_baseline.backtest_allocation(path)
    assert r["status"] == "ok"
    assert r["share_of_vote_pooled"] > 0.70
    assert r["mae"] > 0.01, "a 77%-allocated state must not look as good as a 4% one"
    worst = max(r["districts"], key=lambda d: abs(d["error"]))
    assert abs(worst["error"]) > 0.10
    assert worst["allocated_share"] > cd_baseline.MAX_ALLOCATED_SHARE, (
        "the district the method gets most wrong must be one the quality flag catches"
    )


def test_the_flag_threshold_sits_below_the_measured_knee():
    """``MAX_ALLOCATED_SHARE`` is deliberately conservative against the measured curve."""
    assert cd_baseline.MAX_ALLOCATED_SHARE <= 0.75

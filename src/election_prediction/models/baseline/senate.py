"""Senate fundamentals baseline (P1-003).

A transparent, polls-free baseline for statewide two-party Democratic Senate vote
share. The predictors are the ones the backlog says should be hard to beat: how the
state votes for president relative to the nation, whether an incumbent is running and
for which party, and the midterm penalty on the party holding the White House.

Governor is deliberately **not** covered here — not for lack of a source, but because
MEDSL publishes no multi-decade gubernatorial series comparable to its president/senate/
house files. Governor returns are spread across `State Office-Level Returns 2016`
(state-level, our exact schema, guestbook-gated) and the precinct-level per-state files
for 2018-2024, which need aggregating up to statewide totals. See
`docs/dataset-registry.md`. The machinery below is office-agnostic and reusable for
governor once those returns land, and the key predictor — state presidential lean — is
already available for every state.

Design notes:

* The partisanship anchor is the state's *presidential* lean, not its previous Senate
  result. Senate seats come up every six years, so the previous result for a seat is
  two cycles stale and heavily contaminated by that year's candidates. Presidential
  vote is measured on every state every four years and is the cleaner partisanship
  signal (PROJECT_CONTEXT §7).
* The naive bar is therefore "this state votes for Senate exactly as it last voted for
  president", which is a genuinely hard baseline to beat.
* Vote share and win probability stay separate (CLAUDE.md §7): this returns a mean and
  a residual sigma, and the correlated simulation layer turns those into probabilities.
"""

from __future__ import annotations

import pandas as pd

from ...features import incumbency as incumbency_features
from .presidential import OLSModel, backtest_leave_one_cycle_out

SENATE_PANEL_COLUMNS = [
    "race_id",
    "cycle",
    "office",
    "state_po",
    "state_fips",
    "geography_id",
    "two_party_dem_share",
    "state_pres_lean",
    "pres_dem_share_state",
    "national_pres_dem_share",
    "incumbent_dem",
    "incumbent_rep",
    "open_seat",
    "midterm",
    "midterm_penalty",
    "uncontested_flag",
]

DEFAULT_FEATURES = [
    "state_pres_lean",
    "incumbent_dem",
    "incumbent_rep",
    "midterm_penalty",
]

NAIVE_FEATURE = "pres_dem_share_state"


def _presidential_reference(race_table: pd.DataFrame) -> pd.DataFrame:
    """State presidential two-party share and national share, per presidential cycle."""
    pres = race_table[race_table["office"] == "president"].dropna(subset=["two_party_dem_share"]).copy()
    national = (
        pres.groupby("cycle")
        .apply(
            lambda g: (g["two_party_dem_share"] * g["total_votes"]).sum() / g["total_votes"].sum(),
            include_groups=False,
        )
        .rename("national_pres_dem_share")
    )
    out = pres[["cycle", "state_po", "two_party_dem_share"]].rename(
        columns={"two_party_dem_share": "pres_dem_share_state"}
    )
    return out.merge(national, on="cycle", how="left")


def _white_house_party(race_table: pd.DataFrame) -> pd.Series:
    """Party holding the White House going into each cycle, derived from the returns.

    The winner of each presidential election is taken on **electoral votes**, not the
    national popular vote, so 2000 and 2016 are handled correctly.
    """
    from ..simulation import ELECTORAL_VOTES

    pres = race_table[race_table["office"] == "president"].dropna(subset=["two_party_dem_share"])
    winners = {}
    for cycle, g in pres.groupby("cycle"):
        ev = g["state_po"].map(lambda s: ELECTORAL_VOTES.get(s, 0))
        dem_ev = int(ev[g["two_party_dem_share"] > 0.5].sum())
        total_ev = int(ev.sum())
        winners[int(cycle)] = "DEMOCRAT" if dem_ev * 2 > total_ev else "REPUBLICAN"
    return pd.Series(winners, name="white_house_party").sort_index()


def build_senate_panel(race_table: pd.DataFrame, returns: pd.DataFrame) -> pd.DataFrame:
    """State x cycle Senate panel with presidential lean, incumbency, and midterm terms."""
    sen = race_table[race_table["office"] == "us_senate"].dropna(subset=["two_party_dem_share"]).copy()

    # Most recent presidential result at or before each Senate cycle.
    pres_ref = _presidential_reference(race_table)
    sen = pd.merge_asof(
        sen.sort_values("cycle"),
        pres_ref.sort_values("cycle").rename(columns={"cycle": "pres_cycle"}),
        left_on="cycle",
        right_on="pres_cycle",
        by="state_po",
        direction="backward",
    )
    sen["state_pres_lean"] = sen["pres_dem_share_state"] - sen["national_pres_dem_share"]

    # Incumbency (F-001), derived from the full candidate roster.
    inc = incumbency_features.build_incumbency(returns, "us_senate")
    sen = sen.merge(
        inc[["race_id", "incumbent_running", "incumbent_party", "open_seat"]],
        on="race_id",
        how="left",
    )
    running = sen["incumbent_running"].fillna(False)
    sen["incumbent_dem"] = (running & (sen["incumbent_party"] == "DEMOCRAT")).astype(float)
    sen["incumbent_rep"] = (running & (sen["incumbent_party"] == "REPUBLICAN")).astype(float)
    sen["open_seat"] = sen["open_seat"].fillna(False).astype(bool)

    # Midterm penalty: the president's party historically loses ground in midterms, so
    # the term is signed toward the *out* party and is zero in presidential years.
    wh = _white_house_party(race_table)
    sen["midterm"] = (sen["cycle"] % 4 == 2).astype(float)
    wh_at = sen["cycle"].map(
        lambda c: wh.reindex(wh.index[wh.index <= c]).iloc[-1] if (wh.index <= c).any() else None
    )
    sen["midterm_penalty"] = sen["midterm"] * wh_at.map({"DEMOCRAT": -1.0, "REPUBLICAN": 1.0}).fillna(0.0)

    return sen.reindex(columns=SENATE_PANEL_COLUMNS).sort_values(["cycle", "state_po"]).reset_index(drop=True)


def backtest(panel: pd.DataFrame, features: list[str] | None = None) -> tuple[pd.DataFrame, dict]:
    """Leave-one-cycle-out backtest against the state's presidential lean as the bar."""
    return backtest_leave_one_cycle_out(panel, features or DEFAULT_FEATURES, naive_feature=NAIVE_FEATURE)


def fit_full(panel: pd.DataFrame, features: list[str] | None = None) -> OLSModel:
    """Fit on all usable rows, for forward forecasting / simulation inputs."""
    return OLSModel(features=list(features or DEFAULT_FEATURES)).fit(panel)

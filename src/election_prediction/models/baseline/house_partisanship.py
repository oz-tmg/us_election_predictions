"""House district partisanship score (P1-002 / F-003).

A PVI-style standardized lean for each congressional district: how much more
Democratic (or Republican) the district votes than the nation, averaged over the
available House cycles. This is a transparent prior for district forecasting; it is
explicitly tied to a cycle range and (where known) a redistricting plan version,
because boundary changes break historical baselines (CLAUDE.md §6, PROJECT_CONTEXT §16).

Score convention: positive = more Democratic than the national House environment,
in two-party vote-share points (e.g. +0.06 ≈ "D+6").
"""

from __future__ import annotations

import pandas as pd

SCORE_COLUMNS = [
    "geography_id",
    "state_po",
    "district_num",
    "n_cycles",
    "cycles",
    "mean_dem_share",
    "national_mean",
    "partisanship_score",
    "lean_label",
]


def _national_by_cycle(house: pd.DataFrame) -> pd.Series:
    w = house["total_votes"]
    return (
        house.assign(w=w)
        .groupby("cycle")[["two_party_dem_share", "w"]]
        .apply(lambda g: (g["two_party_dem_share"] * g["w"]).sum() / g["w"].sum())
    )


def _label(score: float) -> str:
    pts = round(score * 100)
    if abs(pts) < 1:
        return "EVEN"
    return f"{'D' if pts > 0 else 'R'}+{abs(pts)}"


def build_partisanship_score(
    house_input: pd.DataFrame, *, exclude_uncontested: bool = True, plan_version: str | None = None
) -> pd.DataFrame:
    """Compute the district partisanship score from district x cycle two-party shares."""
    df = house_input.copy()
    if exclude_uncontested and "uncontested_flag" in df.columns:
        df = df[~df["uncontested_flag"]]

    nat = _national_by_cycle(df)
    df = df.merge(nat.rename("national_dem_share"), on="cycle", how="left")
    df["relative_lean"] = df["two_party_dem_share"] - df["national_dem_share"]

    grp = df.groupby(["geography_id", "state_po", "district_num"])
    out = grp.agg(
        n_cycles=("cycle", "nunique"),
        cycles=("cycle", lambda s: sorted(set(s))),
        mean_dem_share=("two_party_dem_share", "mean"),
        national_mean=("national_dem_share", "mean"),
        partisanship_score=("relative_lean", "mean"),
    ).reset_index()
    out["lean_label"] = out["partisanship_score"].map(_label)
    if plan_version:
        out["plan_version"] = plan_version
    return (
        out[SCORE_COLUMNS + (["plan_version"] if plan_version else [])]
        .sort_values(["state_po", "district_num"])
        .reset_index(drop=True)
    )

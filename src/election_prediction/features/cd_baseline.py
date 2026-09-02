"""Presidential two-party vote by congressional district (F-002 at CD grain).

This project's presidential returns are **state-level only**, which left every
congressional-district baseline dependent on a third-party tracker. That is the binding
constraint on compiling special elections: results come from state election boards, but
``baseline_dem_share`` had no in-house source at all.

MEDSL's per-state precinct files close the gap without any new download, because each
file carries *every* office on the same precinct rows. A precinct's congressional
district can therefore be read off its ``US HOUSE`` rows, and the ``US PRESIDENT`` rows
in those same precincts aggregated up to district level. Same file, same precinct
identifiers, no cross-source geography join — the same property that made the governor
coattails table tractable.

**Precincts that span more than one district are excluded, not allocated.** Splitting a
precinct's presidential vote across districts would need a population or vote-share
crosswalk this project does not have, and inventing one would put unquantified error into
a baseline that other work then treats as ground truth. Exclusions are counted and
returned so the loss is visible; in Virginia 2024 they are 18 of 2,669 precincts (0.7%).

Coverage is bounded by which precinct drops have been downloaded — 2020 and 2024 at the
time of writing (``docs/dataset-registry.md``).
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from ..data import governor, medsl

CD_BASELINE_COLUMNS = [
    "cycle",
    "state_po",
    "district_num",
    "geography_id",
    "dem_votes",
    "rep_votes",
    "two_party_votes",
    "baseline_dem_share",
    "n_precincts",
    "vote_share_of_state_median",
    "baseline_quality",
]

HOUSE_OFFICES = frozenset({"US HOUSE", "US HOUSE OF REPRESENTATIVES"})

# A district whose recovered two-party vote falls far below its state's median district
# is under-covered, not genuinely low-turnout: congressional districts are drawn to equal
# population. Arizona 2024 is the live example — precinct splits in Phoenix and Tucson
# leave AZ-03/06/07 at 0.54/0.27/0.26 of the state median, so AZ-07's baseline rests on
# about a quarter of its votes. Virginia, by contrast, spans 0.78-1.16. The threshold is
# a documented heuristic, not an estimated quantity; it exists so an under-covered
# baseline cannot silently become the denominator of an overperformance calculation.
#
# It flags "verify before use", not "this is wrong". Districts are equal in *population*,
# not in turnout, so seats with many non-citizens or low-propensity voters genuinely cast
# fewer votes -- TX-29, TX-33 and CA-22 fit that profile and may be false positives. The
# extreme cases (AZ-06/07 near 0.26) are too low to be turnout alone.
MIN_VOTE_SHARE_OF_STATE_MEDIAN = 0.6


def _norm(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().upper()


def read_president_and_house(path: Path) -> pd.DataFrame:
    """Read one state's precinct file, keeping president and U.S. House rows."""
    sep = "\t" if path.suffix.lower() == ".tab" else ","
    df = pd.read_csv(path, dtype=str, sep=sep, low_memory=False)
    df.columns = [c.strip().lower() for c in df.columns]
    if "office" not in df.columns:
        raise ValueError(f"{path.name}: no 'office' column")

    office = df["office"].map(_norm)
    keep = office.isin(governor.PRESIDENT_OFFICES) | office.isin(HOUSE_OFFICES)
    out = df[keep].copy()
    out["office"] = office[keep].map(lambda o: "president" if o in governor.PRESIDENT_OFFICES else "us_house")
    if "stage" in out.columns:
        stage = out["stage"].astype(str).str.strip().str.lower()
        out = out[stage.isin(medsl.GENERAL_STAGES)]
    if "votes" in out.columns:
        out = out.rename(columns={"votes": "candidatevotes"})
    out["candidatevotes"] = pd.to_numeric(out["candidatevotes"], errors="coerce").fillna(0)
    if "candidate" in out.columns:
        out = out[out["candidate"].map(governor.is_real_candidate)]
    if "state_po" not in out.columns or out["state_po"].isna().all():
        out["state_po"] = governor.state_from_filename(path)
    return out.reset_index(drop=True)


def _precinct_key(df: pd.DataFrame) -> pd.Series:
    parts = [
        df.get(c, pd.Series([""] * len(df), index=df.index)).fillna("").astype(str)
        for c in ("county_fips", "jurisdiction_fips", "precinct")
    ]
    return parts[0] + "|" + parts[1] + "|" + parts[2]


def presidential_by_cd(path: Path) -> tuple[pd.DataFrame, dict]:
    """District-level presidential two-party share for one state's precinct file."""
    raw = read_president_and_house(path)
    if raw.empty:
        return pd.DataFrame(columns=CD_BASELINE_COLUMNS), {"status": "no_rows"}

    collapsed, _ = governor.collapse_precinct_modes(raw)
    collapsed["_precinct"] = _precinct_key(collapsed)

    # Map precinct -> congressional district from the US HOUSE rows.
    house = collapsed[collapsed["office"] == "us_house"].copy()
    house["_cd"] = pd.to_numeric(house.get("district"), errors="coerce")
    mapping = house.dropna(subset=["_cd"]).groupby("_precinct")["_cd"].nunique()
    single = set(mapping[mapping == 1].index)
    ambiguous = set(mapping[mapping > 1].index)
    cd_of = house[house["_precinct"].isin(single)].dropna(subset=["_cd"]).groupby("_precinct")["_cd"].first()

    pres = collapsed[collapsed["office"] == "president"].copy()
    n_pres_precincts = pres["_precinct"].nunique()
    pres = pres[pres["_precinct"].isin(single)]
    pres["district_num"] = pres["_precinct"].map(cd_of).astype(int)

    parties = pres.apply(medsl._canon_party, axis=1, result_type="expand")
    pres["party_simplified"] = parties[1]
    pres["cycle"] = pd.to_numeric(pres.get("year"), errors="coerce").astype("Int64")

    grp = pres.groupby(["cycle", "state_po", "state_fips", "district_num"], dropna=False)
    out = grp.apply(
        lambda g: pd.Series(
            {
                "dem_votes": g.loc[g["party_simplified"] == "DEMOCRAT", "candidatevotes"].sum(),
                "rep_votes": g.loc[g["party_simplified"] == "REPUBLICAN", "candidatevotes"].sum(),
                "n_precincts": g["_precinct"].nunique(),
            }
        ),
        include_groups=False,
    ).reset_index()

    out["two_party_votes"] = out["dem_votes"] + out["rep_votes"]
    two = out["two_party_votes"].where(out["two_party_votes"] > 0)
    out["baseline_dem_share"] = out["dem_votes"] / two
    out["geography_id"] = [
        f"state:{sf}|district:cong_{int(d):02d}"
        for sf, d in zip(out["state_fips"], out["district_num"], strict=True)
    ]

    median = out["two_party_votes"].median()
    out["vote_share_of_state_median"] = (
        (out["two_party_votes"] / median).round(3) if median and median > 0 else float("nan")
    )
    out["baseline_quality"] = out["vote_share_of_state_median"].map(
        lambda x: "ok" if pd.notna(x) and x >= MIN_VOTE_SHARE_OF_STATE_MEDIAN else "under_covered"
    )

    stats = {
        "status": "ok",
        "districts_under_covered": int((out["baseline_quality"] == "under_covered").sum()),
        "state": governor.state_from_filename(path),
        "districts": int(len(out)),
        "precincts_used": int(pres["_precinct"].nunique()),
        "precincts_total": int(n_pres_precincts),
        # Split precincts are dropped rather than allocated; see the module docstring.
        "precincts_ambiguous_excluded": int(len(ambiguous)),
    }
    return out.reindex(columns=CD_BASELINE_COLUMNS), stats


def build_cd_baselines(
    raw_dir: Path, vintage: int, states: list[str] | None = None
) -> tuple[pd.DataFrame, list[dict]]:
    """Presidential CD baselines for a cycle, optionally limited to ``states``."""
    files = governor.find_precinct_files(raw_dir, vintage)
    if states:
        wanted = {s.upper() for s in states}
        files = [f for f in files if governor.state_from_filename(f) in wanted]
    frames, all_stats = [], []
    for path in files:
        try:
            df, stats = presidential_by_cd(path)
        except Exception as e:  # one bad state must not sink the cycle
            all_stats.append(
                {
                    "status": "error",
                    "state": governor.state_from_filename(path),
                    "error": f"{type(e).__name__}: {e}",
                }
            )
            continue
        all_stats.append(stats)
        if len(df):
            frames.append(df)
    combined = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=CD_BASELINE_COLUMNS)
    return combined, all_stats

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

**The county-aggregate problem.** Many states do not report early, absentee or mail
ballots at precinct level. They report them in a *pseudo-precinct* that covers a whole
county — Virginia's ``# AB - CENTRAL ABSENTEE PRECINCT``, King County's ``COUNTYWIDE``,
Alabama's ``COUNTY FLOATING``, Mecklenburg's ``ABSENTEE BY MAIL``. Where that county spans
two or more congressional districts the pseudo-precinct cannot be resolved to one
district, and an earlier version of this module therefore *excluded* it. In 2020 that
silently discarded 29.7% of Virginia's presidential vote (53 precincts), 29.6% of
Washington's (one precinct: King ``COUNTYWIDE``) and 25.5% of Alabama's — and because
mail ballots in 2020 leaned heavily Democratic, the loss was not neutral. Virginia's CD
aggregate came out at 0.4918 against a certified 0.5515: a six-point bias presented as
a baseline.

So unresolved vote is now **allocated within its own county**, in proportion to the
turnout the county's resolvable precincts recorded in each district, and **separately for
each party** so the ballots keep their own partisan composition:

    district d's share of county c's absentee Democratic vote
        = (resolvable presidential votes in c ∩ d) / (resolvable presidential votes in c)

The weight is *turnout*, not party share, so the method does not assume county absentee
voters lean the way county election-day voters did; it assumes only that they live where
the county's other voters live. A county wholly inside one district is not an allocation
at all — the block is assigned outright and is exact, which is most counties. Counties
with no resolvable vote at all cannot be allocated and are reported as such.

Two other causes of unresolved vote go through the same path: a genuinely split precinct
(it spans districts), and a precinct with presidential rows but no ``US HOUSE`` rows
(6.4% of New Jersey 2024, 2.7% of Florida 2024).

Allocation is **measured, not asserted**. ``backtest_allocation`` pools a state's
precinct-level absentee vote up to county level, re-allocates it, and compares against the
truth the file already contains — see ``reports/cd_allocation_backtest.json`` and
``tests/unit/test_cd_baseline_reconciliation.py``. Every district carries
``allocated_share``, the fraction of its two-party vote that was allocated rather than
directly observed, so a consumer can refuse an estimate that rests mostly on allocation.

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
    "allocated_two_party_votes",
    "allocated_share",
    "vote_share_of_state_median",
    "baseline_quality",
]

HOUSE_OFFICES = frozenset({"US HOUSE", "US HOUSE OF REPRESENTATIVES"})

# A single-district state's "district" is not a number, and not the same non-number twice.
# MEDSL's 2020 files write Alaska, Delaware, Vermont and Wyoming as district ``000``; its
# 2024 files write ``STATEWIDE`` (AK, VT) or ``AT-LARGE`` (DE, WY). Parsing the field as a
# number drops the 2024 spelling to NaN, which deleted seven states from the 2024 national
# build -- AK, DE, ND, SD, VT, WY and the District of Columbia -- while every other state
# reconciled. They are mapped to **0**, the convention the rest of the stack already uses
# (``medsl.py`` coerces an unparseable House district to 0 and ``geography_id`` renders it
# ``cong_00``).
AT_LARGE_LABELS = frozenset({"STATEWIDE", "AT-LARGE", "AT LARGE", "ATLARGE", "AL"})

# How a district's recovered vote compares with its state's median district. **Reported,
# never routed on.** It was once the under-coverage flag, on the reasoning that districts
# are drawn to equal population, so a district far below the state median must be missing
# votes. That reasoning is wrong, and measurably so: districts are equal in *population*,
# not in turnout, and the four districts it flagged in 2020 — AZ-07, CA-21, TX-29, TX-33,
# all majority-Hispanic seats with large non-citizen populations — recover 99-102% of their
# own certified House vote. They cast fewer ballots; nothing is missing.
#
# Worse, it missed the real holes. New York 2020 recovers 92.2% of its certified two-party
# presidential vote — 661,470 votes absent at source — across districts the median test
# called fine, and NJ-04 recovers 66% of its certified House vote at a median ratio of
# 0.755. Under-coverage is now flagged in ``build_cd_baselines`` against each district's own
# certified House return, which is a measurement rather than an inference from a neighbour.
MIN_VOTE_SHARE_OF_STATE_MEDIAN = 0.6

# A district whose two-party vote is mostly *allocated* county-aggregate vote rather than
# directly observed precinct vote is flagged. The threshold is a documented heuristic, not
# an estimated quantity: above it the baseline is largely a statement about where a
# county's voters live rather than a measurement of how a district voted. In practice no
# district in 2020 or 2024 exceeds it, because county-aggregate blocks are a minority of
# any county's vote; it exists so that a future source which reports almost everything at
# county level cannot pass as precinct data.
MAX_ALLOCATED_SHARE = 0.5
QUALITY_HEAVILY_ALLOCATED = "heavily_allocated"
QUALITY_UNDER_COVERED = "under_covered"
QUALITY_OK = "ok"


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


def _major_party(df: pd.DataFrame) -> pd.Series:
    """DEMOCRAT / REPUBLICAN / OTHER, not trusting ``party_simplified`` alone.

    MEDSL's precinct files carry a state's own party name in ``party_detailed`` and
    sometimes fail to map it: Minnesota's Democratic candidate is
    ``DEMOCRATIC FARMER LABOR`` and North Dakota's is ``DEMOCRATIC-NPL``, both of which
    arrive with ``party_simplified = OTHER``. Matching the simplified column literally put
    **zero** Democratic votes in both states and produced baselines of 0.000 that looked
    like data rather than like a bug -- the state-level file has no such problem, so
    nothing upstream caught it.

    So the simplified label is used when it already names a major party, and otherwise the
    detailed label is consulted. The build's reconciliation gate is the backstop for
    anything this still gets wrong.
    """
    simple = df.get("party_simplified", pd.Series("", index=df.index)).astype(str).str.upper().str.strip()
    detailed = df.get("party_detailed", pd.Series("", index=df.index)).astype(str).str.upper().str.strip()
    out = pd.Series("OTHER", index=df.index)
    out[detailed.str.contains("DEMOCRAT", na=False)] = "DEMOCRAT"
    out[detailed.str.contains("REPUBLICAN", na=False)] = "REPUBLICAN"
    out[simple == "DEMOCRAT"] = "DEMOCRAT"
    out[simple == "REPUBLICAN"] = "REPUBLICAN"

    # Fusion voting: one candidate on several party lines is one candidate, and the lines
    # that are not the major-party line must not read as third-party votes. New York 2020 is
    # the case -- Biden carried 386,627 votes on WORKING FAMILIES and Trump 296,360 on
    # CONSERVATIVE -- and dropping them put New York's recovered two-party vote at 92.2% of
    # certified. The *share* barely moved (+0.0046, because the two fusion blocks were of
    # similar size), which is exactly why only the vote-*total* check caught it.
    # docs/methodology.md lists fusion voting as requiring explicit handling;
    # `medsl._collapse_fusion` does it for the state-level path and this module did not.
    #
    # The label is propagated by **candidate**, never by party, so two distinct candidates
    # are never merged. A candidate with no major-party line anywhere stays OTHER.
    if "candidate" in df.columns:
        name = df["candidate"].fillna("").astype(str).str.upper().str.strip()
        major = out.where(out != "OTHER")
        resolved = major.groupby(name).transform(lambda g: g.dropna().iloc[0] if g.notna().any() else None)
        out = out.where(resolved.isna(), resolved)
    return out


def _precinct_key(df: pd.DataFrame) -> pd.Series:
    parts = [
        df.get(c, pd.Series([""] * len(df), index=df.index)).fillna("").astype(str)
        for c in ("county_fips", "jurisdiction_fips", "precinct")
    ]
    return parts[0] + "|" + parts[1] + "|" + parts[2]


#: Candidate county keys, coarsest first. Order matters: county-aggregate blocks are
#: reported at *county* level, so a finer key (``jurisdiction_fips``, a municipality) would
#: put the absentee block in a bucket containing none of the county's precincts and make it
#: unallocatable. The chain is a per-row coalesce rather than a choice of column — Rhode
#: Island 2020 leaves ``county_fips`` blank on 0.18% of rows, which an all-or-nothing rule
#: turned into a failure for the whole state.
COUNTY_KEY_COLUMNS = ("county_fips", "county_name", "jurisdiction_fips", "jurisdiction_name")


def _district_number(district: pd.Series | None) -> pd.Series:
    """Parse a House district label, recognising a single-district state's spelling of 0."""
    if district is None:
        return pd.Series(dtype="float64")
    label = district.fillna("").astype(str).str.strip().str.upper()
    out = pd.to_numeric(label, errors="coerce")
    return out.where(~label.isin(AT_LARGE_LABELS), 0.0)


def _county_key(df: pd.DataFrame) -> pd.Series:
    """The county (or New England municipality, or Virginia independent city) of a precinct.

    County-aggregate pseudo-precincts are allocated *within* this unit, so the key has to be
    the unit the source aggregates to. Rows where no candidate column has a value get an
    empty key; they are reported as unallocatable rather than pooled together, since an
    empty key is not a place.
    """
    present = [c for c in COUNTY_KEY_COLUMNS if c in df.columns]
    if not present:
        raise ValueError(f"no usable county key; expected one of {COUNTY_KEY_COLUMNS}")
    key = pd.Series("", index=df.index, dtype="object")
    for col in present:
        s = df[col].fillna("").astype(str).str.strip()
        key = key.where(key.ne(""), s)
    return key


_TALLY_COLUMNS = ["cycle", "state_po", "state_fips", "district_num", "dem_votes", "rep_votes", "n_precincts"]


def _tally(pres: pd.DataFrame) -> pd.DataFrame:
    """Directly observed district totals: votes whose precinct resolves to one district.

    An empty frame still has to carry the columns: a state can have *no* precinct-level
    presidential vote at all and arrive entirely through allocation.
    """
    if not len(pres):
        return pd.DataFrame(columns=_TALLY_COLUMNS)
    grp = pres.groupby(["cycle", "state_po", "state_fips", "district_num"], dropna=False)
    return grp.apply(
        lambda g: pd.Series(
            {
                "dem_votes": g.loc[g["_major_party"] == "DEMOCRAT", "candidatevotes"].sum(),
                "rep_votes": g.loc[g["_major_party"] == "REPUBLICAN", "candidatevotes"].sum(),
                "n_precincts": g["_precinct"].nunique(),
            }
        ),
        include_groups=False,
    ).reset_index()


def _weights(frame: pd.DataFrame, value: str) -> pd.DataFrame:
    """Normalise ``value`` within each county to give each district's share of it."""
    w = frame.groupby(["_county", "district_num"], as_index=False)[value].sum()
    w = w.rename(columns={value: "_w"})
    w = w[w["_w"] > 0]
    total = w.groupby("_county", as_index=False)["_w"].sum().rename(columns={"_w": "_wt"})
    w = w.merge(total, on="_county")
    w = w[w["_wt"] > 0].copy()
    w["_frac"] = w["_w"] / w["_wt"]
    return w[["_county", "district_num", "_frac"]]


def allocate_within_county(
    resolved: pd.DataFrame, unresolved: pd.DataFrame, house_weights: pd.DataFrame | None = None
) -> tuple[pd.DataFrame, dict]:
    """Spread each county's unresolved vote across its districts by that county's turnout.

    The weight for district ``d`` in county ``c`` is ``c ∩ d``'s share of all presidential
    vote in ``c`` that *did* resolve to a district — turnout, deliberately not party share,
    so a county's mail ballots are not assumed to lean the way its election-day ballots
    did. Allocation runs per party, so the block keeps its own composition.

    A county with one district gets the whole block and the result is exact, which is most
    counties. For a county with **no** precinct-level presidential vote at all — King
    County, Washington reports 2020 countywide and nothing finer, 1.21m votes — the
    fallback weight is the county's own ``US HOUSE`` vote by district, which that same
    countywide row does break out. Those are the same ballots counted by the same officials;
    the residual error is differential roll-off between president and House within a
    district, not a guess about geography. ``weight_source`` records which was used.

    A county with neither weight cannot be allocated; its vote is reported in
    ``votes_unallocatable`` rather than quietly spread over the state.

    Returns ``(district_num, dem_allocated, rep_allocated)`` and the stats.
    """
    empty = pd.DataFrame(columns=["district_num", "dem_allocated", "rep_allocated"])
    stats = {
        "votes_unresolved": float(unresolved["candidatevotes"].sum()) if len(unresolved) else 0.0,
        "votes_allocated": 0.0,
        "votes_allocated_on_house_weights": 0.0,
        "votes_unallocatable": 0.0,
        "precincts_unresolved": int(unresolved["_precinct"].nunique()) if len(unresolved) else 0,
        "counties_single_district": 0,
        "counties_split": 0,
    }
    if not len(unresolved):
        return empty, stats

    # An empty county key is not a place: those rows cannot weight anything.
    resolved = resolved[resolved["_county"].ne("")] if len(resolved) else resolved
    w = (
        _weights(resolved, "candidatevotes")
        if len(resolved)
        else _weights(pd.DataFrame(columns=["_county", "district_num", "candidatevotes"]), "candidatevotes")
    )
    w["weight_source"] = "precinct_president"

    # Counties the presidential weight cannot reach fall back to House vote in the same
    # county. Only those counties: a measured weight is never overridden by a proxy.
    if house_weights is not None and len(house_weights):
        gap = house_weights[~house_weights["_county"].isin(set(w["_county"]))].copy()
        if len(gap):
            gap["weight_source"] = "county_us_house"
            w = pd.concat([w, gap], ignore_index=True)

    if not len(w):
        stats["votes_unallocatable"] = stats["votes_unresolved"]
        return empty, stats

    per_county_districts = w.groupby("_county")["district_num"].nunique()
    stats["counties_single_district"] = int((per_county_districts == 1).sum())
    stats["counties_split"] = int((per_county_districts > 1).sum())

    blocks = unresolved.groupby(["_county", "_major_party"], as_index=False)["candidatevotes"].sum()
    joined = blocks.merge(w, on="_county", how="left")

    orphan = joined["district_num"].isna()
    stats["votes_unallocatable"] = float(
        blocks.loc[blocks["_county"].isin(joined.loc[orphan, "_county"]), "candidatevotes"].sum()
    )
    joined = joined[~orphan].copy()
    if not len(joined):
        return empty, stats

    joined["_alloc"] = joined["candidatevotes"] * joined["_frac"]
    stats["votes_allocated"] = float(joined["_alloc"].sum())
    stats["votes_allocated_on_house_weights"] = float(
        joined.loc[joined["weight_source"] == "county_us_house", "_alloc"].sum()
    )

    wide = (
        joined.pivot_table(index="district_num", columns="_major_party", values="_alloc", aggfunc="sum")
        .reindex(columns=["DEMOCRAT", "REPUBLICAN"])
        .fillna(0.0)
        .reset_index()
        .rename(columns={"DEMOCRAT": "dem_allocated", "REPUBLICAN": "rep_allocated"})
    )
    return wide[["district_num", "dem_allocated", "rep_allocated"]], stats


def _prepare(path: Path, *, collapse: bool = True) -> tuple[pd.DataFrame, pd.DataFrame, set, set]:
    """Collapsed presidential rows with party and district attached, plus county weights.

    **A district row with zero votes does not put a precinct in that district.** Alabama's
    file lists every district that touches a county on *every* precinct row in it, giving
    the districts the precinct is not in a full slate of candidates at zero votes. Counting
    districts present made all 390 precincts of Alabama's seven split counties look
    ambiguous, which discarded a quarter of the state's presidential vote — and because
    those counties are Jefferson, Montgomery and Tuscaloosa, the quarter was the
    Democratic quarter. So the precinct-to-district map is built from House rows with
    **positive** votes; a precinct whose House race is reported as all-zero is unresolved
    and goes through allocation rather than being assigned on a formality.
    """
    raw = read_president_and_house(path)
    if raw.empty:
        return pd.DataFrame(), pd.DataFrame(), set(), set()

    # ``collapse=False`` keeps one row per voting mode, which the allocation backtest needs
    # in order to pool a mode up to county level. It is only safe where a state does not
    # publish a ``TOTAL`` row alongside its breakdowns; the backtest checks that.
    collapsed, _ = governor.collapse_precinct_modes(raw) if collapse else (raw.copy(), {})
    collapsed["_precinct"] = _precinct_key(collapsed)
    collapsed["_county"] = _county_key(collapsed)

    house = collapsed[collapsed["office"] == "us_house"].copy()
    house["district_num"] = _district_number(house.get("district"))
    house = house.dropna(subset=["district_num"])
    voted = house[house["candidatevotes"] > 0]

    mapping = voted.groupby("_precinct")["district_num"].nunique()
    single = set(mapping[mapping == 1].index)
    ambiguous = set(mapping[mapping > 1].index)
    cd_of = voted[voted["_precinct"].isin(single)].groupby("_precinct")["district_num"].first()

    # Fallback allocation weights: congressional turnout per county x district. Used only
    # for counties with no precinct-level presidential vote at all.
    # Same rule as the presidential weight: an empty county key is not a place, so those
    # rows must not pool into one statewide bucket that then looks like a county.
    with_county = voted[voted["_county"].ne("")] if len(voted) else voted
    house_weights = _weights(with_county, "candidatevotes") if len(with_county) else pd.DataFrame()

    pres = collapsed[collapsed["office"] == "president"].copy()
    parties = pres.apply(medsl._canon_party, axis=1, result_type="expand")
    pres["party_simplified"] = parties[1]
    pres["_major_party"] = _major_party(pres)
    pres["cycle"] = pd.to_numeric(pres.get("year"), errors="coerce").astype("Int64")
    pres["district_num"] = pres["_precinct"].map(cd_of)
    return pres, house_weights, single, ambiguous


def presidential_by_cd(path: Path) -> tuple[pd.DataFrame, dict]:
    """District-level presidential two-party share for one state's precinct file."""
    pres, house_weights, single, ambiguous = _prepare(path)
    if not len(pres):
        return pd.DataFrame(columns=CD_BASELINE_COLUMNS), {"status": "no_rows"}

    n_pres_precincts = pres["_precinct"].nunique()
    state_total = float(pres["candidatevotes"].sum())

    resolved = pres[pres["district_num"].notna()].copy()
    resolved["district_num"] = resolved["district_num"].astype(int)
    unresolved = pres[pres["district_num"].isna()].copy()

    out = _tally(resolved)
    alloc, astats = allocate_within_county(resolved, unresolved, house_weights)
    # Outer, not left: a district can exist only in the allocated vote. Washington's 7th is
    # wholly inside King County, which reported 2020 countywide, so it has no
    # precinct-level presidential vote of its own and a left join would drop the seat.
    out = out.merge(alloc, on="district_num", how="outer")
    for col, series in (
        ("cycle", pres["cycle"]),
        ("state_po", pres["state_po"]),
        ("state_fips", pres["state_fips"]),
    ):
        if col in out.columns and series.notna().any():
            out[col] = out[col].fillna(series.dropna().iloc[0])
    out[["dem_votes", "rep_votes", "n_precincts", "dem_allocated", "rep_allocated"]] = out[
        ["dem_votes", "rep_votes", "n_precincts", "dem_allocated", "rep_allocated"]
    ].fillna(0.0)
    out["district_num"] = out["district_num"].astype(int)
    out["n_precincts"] = out["n_precincts"].astype(int)
    out = out.sort_values("district_num").reset_index(drop=True)
    out["allocated_two_party_votes"] = out["dem_allocated"] + out["rep_allocated"]
    out["dem_votes"] = out["dem_votes"] + out["dem_allocated"]
    out["rep_votes"] = out["rep_votes"] + out["rep_allocated"]
    out = out.drop(columns=["dem_allocated", "rep_allocated"])

    out["two_party_votes"] = out["dem_votes"] + out["rep_votes"]
    two = out["two_party_votes"].where(out["two_party_votes"] > 0)
    out["baseline_dem_share"] = out["dem_votes"] / two
    out["allocated_share"] = (out["allocated_two_party_votes"] / two).round(4)
    out["geography_id"] = [
        f"state:{sf}|district:cong_{int(d):02d}"
        for sf, d in zip(out["state_fips"], out["district_num"], strict=True)
    ]

    median = out["two_party_votes"].median()
    out["vote_share_of_state_median"] = (
        (out["two_party_votes"] / median).round(3) if median and median > 0 else float("nan")
    )

    # Only what one file can establish on its own. Under-coverage needs an external
    # comparator -- the district's certified House return -- and is decided in the build.
    out["baseline_quality"] = out["allocated_share"].map(
        lambda v: QUALITY_HEAVILY_ALLOCATED if pd.notna(v) and v > MAX_ALLOCATED_SHARE else QUALITY_OK
    )

    stats = {
        "status": "ok",
        "state": governor.state_from_filename(path),
        "districts": int(len(out)),
        "districts_heavily_allocated": int((out["baseline_quality"] == QUALITY_HEAVILY_ALLOCATED).sum()),
        "precincts_used": int(resolved["_precinct"].nunique()),
        "precincts_total": int(n_pres_precincts),
        # Split and county-aggregate precincts are allocated within their county rather
        # than dropped; see the module docstring. What could not be allocated at all is
        # the only remaining loss, and it is reported rather than inferred from a total.
        "precincts_ambiguous": int(len(ambiguous)),
        "state_presidential_votes": state_total,
        "share_directly_observed": (
            round(float(resolved["candidatevotes"].sum()) / state_total, 4) if state_total else None
        ),
        **{k: (round(v, 4) if isinstance(v, float) else v) for k, v in astats.items()},
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

    # A state that arrives twice must never be summed. ``REDUNDANT_STEM_MARKERS`` catches
    # the variant naming seen so far; this catches the next one. Both copies are dropped
    # and the state is reported as an error, because a named hole is recoverable and a
    # doubled baseline is not: North Carolina reported 180% of its certified vote while
    # every file read "ok".
    if len(combined):
        dupes = sorted(
            combined.groupby(["state_po", "district_num"])
            .size()
            .pipe(lambda s: s[s > 1])
            .index.get_level_values(0)
            .unique()
        )
        for state in dupes:
            all_stats.append(
                {
                    "status": "error",
                    "state": state,
                    "error": f"DuplicateStateFiles: {state} appeared in more than one file in "
                    f"the {vintage} drop; both copies dropped rather than summed",
                }
            )
        combined = combined[~combined["state_po"].isin(dupes)].reset_index(drop=True)
    return combined, all_stats


# ---- measuring the allocation -------------------------------------------------------------
# Allocation is an estimate, so its error is measured rather than asserted. The test bed is
# a state that reports early and absentee ballots *at precinct level* — North Carolina and
# Arizona in 2024 do, 79% and 77% of their vote respectively. Pooling exactly those ballots
# up to county level reproduces the condition the 2020 files are in (North Carolina 2020
# pooled its absentee into ``ABSENTEE BY MAIL``; Arizona's 2024 splits are the same shape),
# allocating them back gives an estimate, and the file's own precinct detail is the truth.
#
# Same state, same counties, same districts, same electorate: the comparison is not a proxy.

#: Modes a state typically reports only at county level. Anything whose label is not plainly
#: election-day is pooled, because that is the direction the real sources fail in.
ELECTION_DAY_MODES = frozenset({"ELECTION DAY", "TOTAL", "ELECTION DAY - CURBSIDE"})


def backtest_allocation(path: Path, pooled_modes: frozenset[str] | None = None) -> dict:
    """Pool a state's precinct-level early/absentee vote to county level and allocate it back.

    Returns per-district truth, estimate and error, plus the summary statistics. A district
    is only compared where the truth is itself observed, so the measurement is of the
    allocation and not of the source's coverage.
    """
    pres, house_weights, _, _ = _prepare(path, collapse=False)
    if not len(pres) or "mode" not in pres.columns:
        return {"status": "no_modes", "state": governor.state_from_filename(path)}

    # Refuse rather than double-count: a state publishing TOTAL *and* breakdowns cannot be
    # read uncollapsed, so it is not a valid test bed (Delaware and Indiana 2024 do this).
    labels = pres["mode"].fillna("TOTAL").astype(str).str.strip().str.upper()
    if labels.eq("TOTAL").any() and labels.nunique() > 1:
        return {"status": "total_alongside_breakdowns", "state": governor.state_from_filename(path)}

    resolvable = pres[pres["district_num"].notna()].copy()
    resolvable["district_num"] = resolvable["district_num"].astype(int)
    if not len(resolvable):
        return {"status": "nothing_resolvable", "state": governor.state_from_filename(path)}

    mode = resolvable["mode"].fillna("TOTAL").astype(str).str.strip().str.upper()
    pooled = mode.isin(pooled_modes) if pooled_modes is not None else ~mode.isin(ELECTION_DAY_MODES)
    if not pooled.any():
        return {"status": "nothing_to_pool", "state": governor.state_from_filename(path)}

    def tally(frame: pd.DataFrame) -> pd.DataFrame:
        g = frame.groupby("district_num")
        return pd.DataFrame(
            {
                "dem": g.apply(
                    lambda x: x.loc[x["_major_party"] == "DEMOCRAT", "candidatevotes"].sum(),
                    include_groups=False,
                ),
                "rep": g.apply(
                    lambda x: x.loc[x["_major_party"] == "REPUBLICAN", "candidatevotes"].sum(),
                    include_groups=False,
                ),
            }
        )

    truth = tally(resolvable)
    truth["truth_dem_share"] = truth["dem"] / (truth["dem"] + truth["rep"]).where(
        (truth["dem"] + truth["rep"]) > 0
    )

    kept = resolvable[~pooled]
    held = resolvable[pooled].copy()
    held["district_num"] = pd.NA  # the county-aggregate condition

    alloc, astats = allocate_within_county(kept, held, house_weights)
    est = tally(kept).reindex(truth.index).fillna(0.0)
    alloc = alloc.set_index("district_num").reindex(truth.index).fillna(0.0)
    est["dem"] = est["dem"] + alloc["dem_allocated"]
    est["rep"] = est["rep"] + alloc["rep_allocated"]
    est["est_dem_share"] = est["dem"] / (est["dem"] + est["rep"]).where((est["dem"] + est["rep"]) > 0)

    two = (est["dem"] + est["rep"]).where((est["dem"] + est["rep"]) > 0)
    cmp = pd.DataFrame(
        {
            "truth_dem_share": truth["truth_dem_share"],
            "est_dem_share": est["est_dem_share"],
            # The same column production carries, so the error can be read off it.
            "allocated_share": (alloc["dem_allocated"] + alloc["rep_allocated"]) / two,
        }
    ).dropna(subset=["truth_dem_share", "est_dem_share"])
    cmp["error"] = cmp["est_dem_share"] - cmp["truth_dem_share"]

    pooled_votes = float(held["candidatevotes"].sum())
    total_votes = float(resolvable["candidatevotes"].sum())
    return {
        "status": "ok",
        "state": governor.state_from_filename(path),
        "cycle": int(pd.to_numeric(resolvable["cycle"], errors="coerce").dropna().iloc[0]),
        "pooled_modes": sorted(mode[pooled].unique().tolist()),
        "share_of_vote_pooled": round(pooled_votes / total_votes, 4) if total_votes else None,
        "districts_compared": int(len(cmp)),
        "mae": round(float(cmp["error"].abs().mean()), 5),
        "max_abs_error": round(float(cmp["error"].abs().max()), 5),
        "p90_abs_error": round(float(cmp["error"].abs().quantile(0.9)), 5),
        "mean_error": round(float(cmp["error"].mean()), 5),
        "votes_unallocatable": astats["votes_unallocatable"],
        "districts": [
            {
                "district_num": int(i),
                "truth_dem_share": round(float(r.truth_dem_share), 5),
                "est_dem_share": round(float(r.est_dem_share), 5),
                "error": round(float(r.error), 5),
                "allocated_share": round(float(r.allocated_share), 5),
            }
            for i, r in cmp.iterrows()
        ],
    }

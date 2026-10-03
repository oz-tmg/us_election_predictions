"""Build presidential two-party vote by congressional district, per cycle (F-002 at CD grain).

``features/cd_baseline.py`` has been able to do this since it was written, but it had no
caller: the one file in ``data/gold`` was produced ad hoc and covers 8 states. That is the
binding constraint on NE-002, because a special election's overperformance is measured
against its district's presidential baseline, and a baseline that exists for 8 states
cannot support a compilation across four cycles.

This makes it a build. One command, one vintage, a gold table and a report that states its
own coverage — including which states failed and why, rather than a quiet short table.

**Which baseline a special election uses** is the most recent presidential *before* it, on
the district lines in force at the time:

    special in 2017-2020  ->  2016 presidential, 2012-era lines
    special in 2021-2024  ->  2020 presidential, 2012-era lines through 2021,
                              2022-era lines from 2022
    special in 2025-2026  ->  2024 presidential, 2022-era lines

The 2022-era wrinkle matters and is not handled here: a 2020 precinct file assigns
precincts to districts using its own ``us_house`` rows, so a 2020 build is on 2012-era
lines by construction. A 2022-or-later special needs 2020 presidential vote re-aggregated
onto 2022 lines, which is RD-003's vote transfer, not this module. Builds are therefore
labelled with the lines they are on, and a consumer that needs the other thing is told so
rather than handed a near-miss.

Run:  ep-build-cd-baselines --vintage 2020
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

import pandas as pd

from .features import cd_baseline
from .features.incumbency import plan_era

# Presidential cycles only -- a midterm precinct drop carries no president rows.
PRESIDENTIAL_VINTAGES = (2016, 2020, 2024)

# A state's CD baselines must sum back to the share its certified state-level return
# reports. One point is loose enough for the precincts this build deliberately drops
# (a precinct spanning two districts is excluded, not allocated) and tight enough to
# catch a state that is actually broken.
#
# This gate exists because the first national run shipped Minnesota and North Dakota at
# 0.000 Democratic -- MEDSL's precinct files label their Democratic candidates
# DEMOCRATIC FARMER LABOR and DEMOCRATIC-NPL, which simplified to OTHER. The build
# reported "50 files ok" and the table looked complete. Counting rows is not validation;
# reconciling totals is (CLAUDE.md §3).
RECONCILIATION_TOLERANCE = 0.01
QUALITY_FAILS_RECONCILIATION = "fails_reconciliation"

# A state with no certified comparator is not a state whose data disagrees with one, and
# flattening the two reads as an accusation against the precinct file. New York 2024 is the
# case and it is nobody's bug: `data/quarantine.py` excludes a race whose candidate votes do
# not *exactly* equal its reported total, and New York's 2024 files carry a `BLANK` ballot
# row the total excludes — 874 votes in 8,381,429, or 0.010%. The exclusion is deliberate
# (CLAUDE.md §6: a documented uniform exclusion, never a cause-specific patch), so New York
# has no 2024 presidential row in silver, so this gate has nothing to compare against. Its
# precinct file is fine: it reconciles to 1.0025 of its own raw two-party total.
#
# So "unknown" keeps its own label. It still refuses to read as fine — that was the point of
# failing an absent state in the first place — without claiming the data is wrong.
QUALITY_NO_COMPARATOR = "no_certified_comparator"

# A state's recovered two-party *total*, against the certified total. The share gate above
# cannot see a duplication that is proportional across parties, and one state does exactly
# that: New Jersey's 2024 file mixes two geographic levels. Bergen County publishes 562 real
# precinct rows ("Allendale 1", "Allendale 2", ...) carrying both mode breakdowns and a
# matching TOTAL, **and** 144 municipality rows ("Allendale", "Allendale Provisional")
# carrying only a TOTAL -- the same 241,958 votes a second time. Summing both puts New
# Jersey 13.4% over certified while its share lands within 0.4%, so a share-only gate passes
# it and ships counts that are half fiction.
#
# This flags rather than de-duplicates. The only structural discriminator available is "a
# key with a TOTAL and no breakdowns, in a county where other keys have both", and a genuine
# small precinct whose votes all arrived by one mode would match that rule and be deleted.
# Dropping real votes to tidy a total is worse than reporting the total as untrustworthy.
#
# The tolerance matches the share gate's. Measured deviations across the states checked are
# 0.00% for most, 0.06% (VA 2024) and 0.25% (NY 2020, the BLANK-ballot-row quirk) at the
# top, against New Jersey's 13.4% -- so 1% separates the benign from the broken with room to
# spare.
VOTE_TOTAL_TOLERANCE = 0.01
QUALITY_FAILS_VOTE_TOTAL = "fails_vote_total"

# A district can be missing from a precinct drop without any state failing, because the
# precinct-to-district map is read off ``US HOUSE`` rows and an **uncontested** House race
# produces none. Florida's 25th in 2020 is the case: Mario Diaz-Balart ran unopposed, so the
# file carries no House rows for it, so none of its precincts resolve -- and its presidential
# vote is then allocated into the neighbouring districts that share its counties. The state
# reconciles perfectly and a seat is simply absent, with its vote in the wrong place.
#
# Counting districts cannot catch that; only comparing against an independent list of which
# districts existed can. The certified House returns in silver are that list
# (``mit_us_house_returns``, 436 state-district pairs for 2020), so any district they carry
# and the baseline does not is reported by name.
HOUSE_RETURNS_PATH = Path("data/silver/election_returns.parquet")

# A district's recovered two-party presidential vote, over the total vote its own certified
# U.S. House return reports. The two are close by construction — the same ballots, minus
# roll-off and third-party House votes — so across 402 districts in 2020 the ratio has a
# median of 1.002 and a standard deviation of 0.062. Below 0.90 (the 5th percentile) the
# district is missing vote, and this is the *measurement* that replaced an inference from
# the state median, which produced four false positives and missed two real holes.
#
# Flags "verify before use", not "wrong". A district whose House race was uncontested has a
# genuinely low House total and so a *high* ratio, which is never flagged — safe by
# direction. A district with no certified House return at all cannot be judged and is left
# alone rather than condemned.
MIN_COVERAGE_VS_HOUSE_VOTE = 0.90
QUALITY_UNDER_COVERED = "under_covered"

# Worst first: a state that fails reconciliation is wrong at a scale that makes its
# districts moot; a district missing vote is worse than one whose vote is present but placed
# by estimate.
QUALITY_PRECEDENCE = (
    QUALITY_FAILS_RECONCILIATION,
    QUALITY_FAILS_VOTE_TOTAL,
    QUALITY_NO_COMPARATOR,
    QUALITY_UNDER_COVERED,
    cd_baseline.QUALITY_HEAVILY_ALLOCATED,
    cd_baseline.QUALITY_OK,
)


def _r4(v: object) -> float | None:
    return None if pd.isna(v) else round(float(v), 4)


def reconcile(df: pd.DataFrame, panel: pd.DataFrame, vintage: int) -> tuple[pd.DataFrame, dict]:
    """Compare each state's CD aggregate to its certified state-level two-party share.

    Districts in a state that fails are marked ``fails_reconciliation`` rather than being
    dropped: a short table invites a silent join, whereas a flagged one forces a consumer
    to decide. The flag is per state because the failure mode is per state.
    """
    if not len(df):
        return df, {"states_checked": 0, "states_failing": [], "worst": []}

    certified = (
        panel[panel["cycle"] == vintage][["state_po", "two_party_dem_share"]]
        .rename(columns={"two_party_dem_share": "state_certified_share"})
        .drop_duplicates("state_po")
    )
    agg = df.groupby("state_po").agg(_d=("dem_votes", "sum"), _t=("two_party_votes", "sum"))
    agg["cd_aggregate_share"] = agg["_d"] / agg["_t"].where(agg["_t"] > 0)
    agg = agg.drop(columns=["_d", "_t"]).reset_index().merge(certified, on="state_po", how="left")
    agg["share_diff"] = agg["cd_aggregate_share"] - agg["state_certified_share"]
    agg["reconciles"] = agg["share_diff"].abs() <= RECONCILIATION_TOLERANCE

    out = df.merge(
        agg[["state_po", "cd_aggregate_share", "state_certified_share", "share_diff", "reconciles"]],
        on="state_po",
        how="left",
    )
    absent = out["state_certified_share"].isna()
    failed = out["reconciles"].fillna(False).eq(False) & ~absent
    out.loc[failed, "baseline_quality"] = QUALITY_FAILS_RECONCILIATION
    out.loc[absent, "baseline_quality"] = QUALITY_NO_COMPARATOR

    worst = agg.reindex(agg["share_diff"].abs().sort_values(ascending=False).index).head(8)
    report = {
        "tolerance": RECONCILIATION_TOLERANCE,
        "states_checked": int(agg["state_certified_share"].notna().sum()),
        "states_failing": sorted(
            agg.loc[
                ~agg["reconciles"].fillna(False) & agg["state_certified_share"].notna(), "state_po"
            ].tolist()
        ),
        # Reported separately: there is nothing to compare these against, which is a
        # different claim from "they disagree".
        "states_without_a_comparator": sorted(
            agg.loc[agg["state_certified_share"].isna(), "state_po"].tolist()
        ),
        "median_abs_diff": float(agg["share_diff"].abs().median()),
        "worst": [
            {
                "state_po": r.state_po,
                "cd_aggregate_share": _r4(r.cd_aggregate_share),
                "state_certified_share": _r4(r.state_certified_share),
                "share_diff": _r4(r.share_diff),
            }
            for r in worst.itertuples()
        ],
    }
    return out, report


def flag_vote_total_mismatch(
    df: pd.DataFrame, returns: pd.DataFrame, vintage: int
) -> tuple[pd.DataFrame, dict]:
    """Compare each state's recovered two-party total with its certified two-party total.

    Vote-total reconciliation, which the share gate cannot do: a duplication that is
    proportional across parties leaves the share untouched and the total inflated. Adds
    ``certified_two_party_votes`` and ``vote_total_ratio``; flags the state's districts
    ``fails_vote_total`` beyond ``VOTE_TOTAL_TOLERANCE``. A state with no certified total
    keeps whatever ``reconcile`` already said about it.
    """
    needed = {"office", "cycle", "state_po", "party_simplified", "candidatevotes"}
    if not needed <= set(returns.columns) or not len(returns) or not len(df):
        return df, {"skipped": f"no certified presidential totals for {vintage}; UNCHECKED"}
    rows = returns[
        (returns["office"] == "president")
        & (returns["cycle"] == vintage)
        & (returns["party_simplified"].isin(["DEMOCRAT", "REPUBLICAN"]))
    ]
    if not len(rows):
        return df, {"skipped": f"no certified presidential totals for {vintage}; UNCHECKED"}

    certified = (
        rows.groupby("state_po", as_index=False)["candidatevotes"]
        .sum()
        .rename(columns={"candidatevotes": "certified_two_party_votes"})
    )
    out = df.merge(certified, on="state_po", how="left")
    per_state = (
        out.groupby("state_po")
        .agg(got=("two_party_votes", "sum"), want=("certified_two_party_votes", "first"))
        .dropna()
    )
    per_state["ratio"] = per_state["got"] / per_state["want"].where(per_state["want"] > 0)
    failing = sorted(per_state.index[(per_state["ratio"] - 1).abs() > VOTE_TOTAL_TOLERANCE])

    out["vote_total_ratio"] = out["state_po"].map(per_state["ratio"]).round(5)
    bad = out["state_po"].isin(failing)
    rank = {q: i for i, q in enumerate(QUALITY_PRECEDENCE)}
    out.loc[bad, "baseline_quality"] = [
        q if rank.get(q, len(rank)) < rank[QUALITY_FAILS_VOTE_TOTAL] else QUALITY_FAILS_VOTE_TOTAL
        for q in out.loc[bad, "baseline_quality"]
    ]
    return out, {
        "tolerance": VOTE_TOTAL_TOLERANCE,
        "states_checked": int(len(per_state)),
        "states_failing": failing,
        "median_ratio": _r4(per_state["ratio"].median()),
        "worst": [
            {
                "state_po": state,
                "recovered_two_party_votes": int(r.got),
                "certified_two_party_votes": int(r.want),
                "ratio": _r4(r.ratio),
            }
            for state, r in per_state.reindex(
                (per_state["ratio"] - 1).abs().sort_values(ascending=False).index
            )
            .head(6)
            .iterrows()
        ],
    }


def flag_under_covered(df: pd.DataFrame, house: pd.DataFrame, vintage: int) -> tuple[pd.DataFrame, dict]:
    """Compare each district's recovered vote with its own certified House return.

    Adds ``certified_house_votes`` and ``coverage_vs_house_vote``, and downgrades the
    district's ``baseline_quality`` where the ratio falls below
    ``MIN_COVERAGE_VS_HOUSE_VOTE``. A state already failing reconciliation keeps that flag:
    see ``QUALITY_PRECEDENCE``.
    """
    rows = house[(house["office"] == "us_house") & (house["cycle"] == vintage)]
    if not len(rows) or not len(df):
        return df, {"skipped": f"no certified us_house returns for {vintage}; coverage UNCHECKED"}

    totals = (
        rows.assign(district_num=pd.to_numeric(rows["district_num"], errors="coerce"))
        .dropna(subset=["district_num"])
        .groupby(["state_po", "district_num"], as_index=False)["candidatevotes"]
        .sum()
        .rename(columns={"candidatevotes": "certified_house_votes"})
    )
    totals["district_num"] = totals["district_num"].astype(int)

    out = df.copy()
    out["district_num"] = out["district_num"].astype(int)
    out = out.merge(totals, on=["state_po", "district_num"], how="left")
    # Cast to float *before* masking. Pandas evaluates nullable-integer arithmetic on the
    # underlying data including masked slots, so `Int64.where(> 0)` still carries a literal
    # 0 into the division and raises ZeroDivisionError. A float NaN does not. Louisiana 2024
    # is the live case: its all-party primary leaves a district with no certified House vote.
    house_votes = pd.to_numeric(out["certified_house_votes"], errors="coerce").astype("float64")
    house_votes = house_votes.where(house_votes > 0)
    two_party = pd.to_numeric(out["two_party_votes"], errors="coerce").astype("float64")
    out["coverage_vs_house_vote"] = (two_party / house_votes).round(4)

    short = out["coverage_vs_house_vote"] < MIN_COVERAGE_VS_HOUSE_VOTE
    rank = {q: i for i, q in enumerate(QUALITY_PRECEDENCE)}
    out.loc[short, "baseline_quality"] = [
        q if rank.get(q, len(rank)) < rank[QUALITY_UNDER_COVERED] else QUALITY_UNDER_COVERED
        for q in out.loc[short, "baseline_quality"]
    ]

    flagged = out.loc[short].sort_values("coverage_vs_house_vote")
    return out, {
        "threshold": MIN_COVERAGE_VS_HOUSE_VOTE,
        "districts_checked": int(out["coverage_vs_house_vote"].notna().sum()),
        "districts_unjudgeable": int(out["coverage_vs_house_vote"].isna().sum()),
        "districts_under_covered": int(short.sum()),
        "median_coverage": _r4(out["coverage_vs_house_vote"].median()),
        "worst": [
            {
                "district": f"{r.state_po}-{int(r.district_num):02d}",
                "coverage_vs_house_vote": _r4(r.coverage_vs_house_vote),
                "two_party_votes": int(r.two_party_votes),
                "certified_house_votes": int(r.certified_house_votes),
            }
            for r in flagged.head(10).itertuples()
        ],
    }


def district_coverage(df: pd.DataFrame, house: pd.DataFrame, vintage: int) -> dict:
    """Which districts the certified House returns carry that the baseline does not.

    Reported per state and by name. The reverse direction is reported too: a district in the
    baseline that no certified return mentions means the drop's own ``district`` values
    disagree with the cycle's apportionment, which is a different bug and worth seeing.
    """
    # DC elects a non-voting delegate, not one of the 435 congressional districts. The
    # certified House returns carry the race; the apportioned-seat universe does not.
    rows = house[(house["office"] == "us_house") & (house["cycle"] == vintage) & (house["state_po"] != "DC")]
    expected = {
        (s, int(d))
        for s, d in rows[["state_po", "district_num"]].dropna().drop_duplicates().itertuples(index=False)
    }
    if not expected:
        return {"skipped": f"no certified us_house returns for {vintage}"}
    have = (
        {
            (s, int(d))
            for s, d in df[["state_po", "district_num"]].dropna().drop_duplicates().itertuples(index=False)
        }
        if len(df)
        else set()
    )
    missing, extra = sorted(expected - have), sorted(have - expected)
    by_state: dict[str, list[int]] = {}
    for state, district in missing:
        by_state.setdefault(state, []).append(district)
    return {
        "districts_expected": len(expected),
        "districts_present": len(have),
        "districts_missing": len(missing),
        # Named, not counted. A missing district's presidential vote does not vanish: it is
        # allocated into whichever districts share its counties, so the seats around it are
        # wrong too.
        "missing_by_state": by_state,
        "districts_not_in_certified_returns": [f"{s}-{d:02d}" for s, d in extra],
    }


def build(
    raw_dir: Path,
    vintage: int,
    states: list[str] | None = None,
    panel_path: Path | None = None,
    house_path: Path | None = None,
) -> tuple[pd.DataFrame, dict]:
    """Baselines for one cycle, with a coverage report that does not hide failures."""
    if vintage not in PRESIDENTIAL_VINTAGES:
        raise ValueError(
            f"vintage {vintage} is not a presidential cycle; a midterm precinct drop has no "
            f"president rows. Expected one of {PRESIDENTIAL_VINTAGES}."
        )
    df, stats = cd_baseline.build_cd_baselines(raw_dir, vintage, states)

    panel_path = panel_path or Path("data/gold/presidential_panel.parquet")
    if panel_path.is_file():
        df, recon = reconcile(df, pd.read_parquet(panel_path), vintage)
    else:
        recon = {"skipped": f"no certified panel at {panel_path}; baselines are UNRECONCILED"}

    house_path = house_path or HOUSE_RETURNS_PATH
    if house_path.is_file():
        house = pd.read_parquet(house_path)
        coverage = district_coverage(df, house, vintage)
        df, totals = flag_vote_total_mismatch(df, house, vintage)
        df, under = flag_under_covered(df, house, vintage)
    else:
        missing = f"no certified House returns at {house_path}; coverage UNCHECKED"
        coverage, under, totals = ({"skipped": missing},) * 3

    ok = [s for s in stats if s.get("status") != "error"]
    errors = [s for s in stats if s.get("status") == "error"]
    report = {
        "vintage": vintage,
        "district_lines": plan_era(vintage),
        "generated_on": date.today().isoformat(),
        "files_read": len(stats),
        "files_ok": len(ok),
        "files_errored": len(errors),
        "districts": int(len(df)),
        "states_covered": int(df["state_po"].nunique()) if len(df) else 0,
        "baseline_quality": (df["baseline_quality"].value_counts().sort_index().to_dict() if len(df) else {}),
        # Named, not counted: a state missing from a national baseline is a hole someone
        # downstream will otherwise discover as a silent join failure.
        "errors": [{"state": e.get("state"), "error": e.get("error")} for e in errors],
        "reconciliation": recon,
        "district_coverage": coverage,
        "under_coverage": under,
        "vote_totals": totals,
        "states_missing": sorted(
            set(_expected_states(stats)) - set(df["state_po"].unique() if len(df) else [])
        ),
    }
    return df, report


def _expected_states(stats: list[dict]) -> list[str]:
    return [s.get("state") for s in stats if s.get("state")]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Presidential two-party vote by congressional district")
    ap.add_argument("--vintage", type=int, required=True, choices=PRESIDENTIAL_VINTAGES)
    ap.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    ap.add_argument("--gold-dir", type=Path, default=Path("data/gold"))
    ap.add_argument("--reports-dir", type=Path, default=Path("reports"))
    ap.add_argument("--states", nargs="*", default=None, help="limit to these postal codes")
    args = ap.parse_args(argv)

    df, report = build(args.raw_dir, args.vintage, args.states)

    args.gold_dir.mkdir(parents=True, exist_ok=True)
    out = args.gold_dir / f"cd_presidential_baseline_{args.vintage}.parquet"
    df.to_parquet(out, index=False)

    args.reports_dir.mkdir(parents=True, exist_ok=True)
    rpt = args.reports_dir / f"cd_baseline_{args.vintage}.json"
    rpt.write_text(json.dumps(report, indent=2, default=str))

    print(
        f"CD presidential baselines, {args.vintage} (district lines: {report['district_lines']}-era)\n"
        f"  districts: {report['districts']} across {report['states_covered']} states\n"
        f"  files: {report['files_ok']} ok, {report['files_errored']} errored\n"
        f"  quality: {report['baseline_quality']}"
    )
    if report["errors"]:
        print(f"  ERRORED STATES: {[e['state'] for e in report['errors']]}")
    if report["states_missing"]:
        print(f"  MISSING FROM OUTPUT: {report['states_missing']}")
    cov = report.get("district_coverage", {})
    if cov.get("districts_missing"):
        print(
            f"  MISSING DISTRICTS: {cov['districts_missing']} of {cov['districts_expected']} "
            f"-> {cov['missing_by_state']}"
        )
        print("      (an uncontested House race leaves no rows to map precincts by;")
        print("       the seat's presidential vote lands in whichever districts share its counties)")
    elif cov.get("districts_expected"):
        print(f"  district coverage: {cov['districts_present']}/{cov['districts_expected']}")
    tot = report.get("vote_totals", {})
    if tot.get("states_failing"):
        print(
            f"  FAILS VOTE TOTAL (>{tot['tolerance']:.0%} off certified two-party votes): "
            f"{tot['states_failing']}"
        )
        for w in tot["worst"][:3]:
            print(
                f"      {w['state_po']}: recovered {w['recovered_two_party_votes']:,} vs "
                f"certified {w['certified_two_party_votes']:,} ({w['ratio']:.4f})"
            )
    und = report.get("under_coverage", {})
    if und.get("districts_under_covered"):
        print(
            f"  UNDER-COVERED: {und['districts_under_covered']} districts below "
            f"{und['threshold']:.0%} of their certified House vote"
        )
        for w in und["worst"][:5]:
            print(
                f"      {w['district']}: {w['two_party_votes']:,} presidential vs "
                f"{w['certified_house_votes']:,} House ({w['coverage_vs_house_vote']:.3f})"
            )
    recon = report.get("reconciliation", {})
    if recon.get("states_failing"):
        print(f"  FAILS RECONCILIATION (>{recon['tolerance']:.0%} off certified): {recon['states_failing']}")
        for w in recon["worst"][:5]:
            print(
                f"      {w['state_po']}: CD {w['cd_aggregate_share']} "
                f"vs certified {w['state_certified_share']}"
            )
    if recon.get("states_without_a_comparator"):
        print(
            f"  NO CERTIFIED COMPARATOR: {recon['states_without_a_comparator']} "
            f"(quarantined upstream; the precinct file is not implicated)"
        )
    if not recon.get("states_failing") and recon.get("states_checked"):
        n = recon["states_checked"]
        print(f"  reconciles against certified state shares: {n}/{n}")
    print(f"  -> {out}\n  -> {rpt}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

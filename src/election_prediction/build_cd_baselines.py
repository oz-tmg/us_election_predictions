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
    failed = out["reconciles"].fillna(False).eq(False)
    out.loc[failed, "baseline_quality"] = QUALITY_FAILS_RECONCILIATION

    worst = agg.reindex(agg["share_diff"].abs().sort_values(ascending=False).index).head(8)
    report = {
        "tolerance": RECONCILIATION_TOLERANCE,
        "states_checked": int(agg["state_certified_share"].notna().sum()),
        "states_failing": sorted(agg.loc[~agg["reconciles"].fillna(False), "state_po"].tolist()),
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


def build(
    raw_dir: Path,
    vintage: int,
    states: list[str] | None = None,
    panel_path: Path | None = None,
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
        "baseline_quality": (
            df["baseline_quality"].value_counts().sort_index().to_dict() if len(df) else {}
        ),
        # Named, not counted: a state missing from a national baseline is a hole someone
        # downstream will otherwise discover as a silent join failure.
        "errors": [
            {"state": e.get("state"), "error": e.get("error")} for e in errors
        ],
        "reconciliation": recon,
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
    recon = report.get("reconciliation", {})
    if recon.get("states_failing"):
        print(
            f"  FAILS RECONCILIATION (>{recon['tolerance']:.0%} off certified): "
            f"{recon['states_failing']}"
        )
        for w in recon["worst"][:5]:
            print(
                f"      {w['state_po']}: CD {w['cd_aggregate_share']} "
                f"vs certified {w['state_certified_share']}"
            )
    elif recon.get("states_checked"):
        n = recon["states_checked"]
        print(f"  reconciles against certified state shares: {n}/{n}")
    print(f"  -> {out}\n  -> {rpt}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

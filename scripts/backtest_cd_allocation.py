"""Measure the error that county-aggregate allocation puts into a CD presidential baseline.

Many states do not report early, absentee or mail ballots at precinct level; they report
them in a pseudo-precinct covering a whole county. ``features/cd_baseline`` allocates that
block across the county's districts in proportion to the turnout its resolvable precincts
recorded in each (see that module's docstring). This script measures how wrong that is.

The test bed is a state that reports those same ballots **at precinct level**, so the file
contains its own ground truth. North Carolina and Arizona 2024 both do — 76% and 77% of
their vote. Pooling a mode up to county level reproduces exactly the condition the 2020
files are in, allocating it back gives the estimate, and the precinct detail is the truth.
Same state, same counties, same districts, same electorate: not a proxy.

Each mode is pooled separately as well as all together, which traces error against the
*share of a district's vote that was allocated* — the ``allocated_share`` column every
production row carries. That is the point: a consumer can look up the error that applies to
the district in front of them rather than a single national average.

Run:  python scripts/backtest_cd_allocation.py
Out:  reports/cd_allocation_backtest.json
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

import pandas as pd

from election_prediction.features import cd_baseline

# States whose 2024 file breaks early/absentee out by precinct, and so can be used as the
# truth. Both are large, both contain a county spanning many districts (Mecklenburg over
# two, Maricopa over seven), so the hard case is represented rather than averaged away.
TEST_BEDS = (("NC", 2024), ("AZ", 2024))

# Bins for the error curve. They are reporting bins, not a fitted model: the relationship
# is reported as measured error per band, not as a coefficient nobody can audit.
BINS = [0.0, 0.10, 0.25, 0.50, 0.75, 1.0]


def _path(raw_dir: Path, state: str, cycle: int) -> Path:
    return (
        raw_dir
        / f"source=medsl/dataset=precinct_by_state/vintage={cycle}"
        / f"{cycle}-{state.lower()}-precinct-general.csv"
    )


def run(raw_dir: Path) -> dict:
    runs, rows = [], []
    for state, cycle in TEST_BEDS:
        path = _path(raw_dir, state, cycle)
        if not path.is_file():
            runs.append({"state": state, "cycle": cycle, "status": "file_missing"})
            continue
        full = cd_baseline.backtest_allocation(path)
        if full["status"] != "ok":
            runs.append({"state": state, "cycle": cycle, "status": full["status"]})
            continue
        # All modes together, then each on its own, to span the range of pooled shares.
        subsets = [full["pooled_modes"]] + [[m] for m in full["pooled_modes"]]
        for subset in subsets:
            r = (
                full
                if subset == full["pooled_modes"]
                else cd_baseline.backtest_allocation(path, pooled_modes=frozenset(subset))
            )
            if r["status"] != "ok":
                continue
            runs.append({k: v for k, v in r.items() if k != "districts"})
            for d in r["districts"]:
                rows.append({"state": r["state"], "cycle": r["cycle"], "pooled": "+".join(subset), **d})

    curve = []
    if rows:
        df = pd.DataFrame(rows)
        df["band"] = pd.cut(df["allocated_share"], BINS, include_lowest=True)
        for band, g in df.groupby("band", observed=True):
            curve.append(
                {
                    "allocated_share_band": f"{band.left:.2f}-{band.right:.2f}",
                    "districts": int(len(g)),
                    "mae": round(float(g["error"].abs().mean()), 5),
                    "p90_abs_error": round(float(g["error"].abs().quantile(0.9)), 5),
                    "max_abs_error": round(float(g["error"].abs().max()), 5),
                }
            )

    return {
        "generated_on": date.today().isoformat(),
        "method": (
            "Pool a state's precinct-level early/absentee vote to county level, allocate it "
            "back with features.cd_baseline.allocate_within_county, and compare each "
            "district's two-party Democratic share against the file's own precinct detail."
        ),
        "test_beds": [f"{s} {c}" for s, c in TEST_BEDS],
        "runs": runs,
        "error_vs_allocated_share": curve,
        "districts": rows,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    ap.add_argument("--out", type=Path, default=Path("reports/cd_allocation_backtest.json"))
    args = ap.parse_args(argv)

    report = run(args.raw_dir)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, default=str))

    print("Allocation error by share of a district's vote that was allocated\n")
    print(f"{'band':>12}  {'districts':>9}  {'MAE':>8}  {'p90':>8}  {'max':>8}")
    for c in report["error_vs_allocated_share"]:
        print(
            f"{c['allocated_share_band']:>12}  {c['districts']:>9}  {c['mae']:>8.4f}  "
            f"{c['p90_abs_error']:>8.4f}  {c['max_abs_error']:>8.4f}"
        )
    print(f"\n  -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

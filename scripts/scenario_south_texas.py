#!/usr/bin/env python
"""South Texas reversion scenario: a dated scenario run beside a refresh, never instead of it.

    python scripts/scenario_south_texas.py --as-of 2026-10-29 --fraction 0.5

1. Measure the border counties' 2020->2024 presidential swing against the state's
   (county votes from ``data/gold/governor_county_returns.parquet``, which reproduce the
   certified statewide shares).
2. Rebuild the registered Texas 2024 -> TX_2025 block allocation (the same call and
   sources as ``plan_transfer_tx_2024``) and measure each new district's share of its
   two-party vote cast in those counties. The rebuilt district shares must reproduce the
   registered transferred prior, or the run stops.
3. Re-run the refresh's projection with the refresh's own Senate specification and
   correlation parameters, moving Texas seat means by
   ``-fraction * excess_swing * region_share`` before the correlated simulation.

Writes ``reports/scenario_south_texas_<as_of>/``. The sealed pre-registration and the
refresh are read, never written.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, "src")
sys.path.insert(0, "scripts")

from project_2026 import main as project  # noqa: E402

from election_prediction import build_plan_transfer  # noqa: E402
from election_prediction.data.manifest import sha256_file  # noqa: E402
from election_prediction.features import block_crosswalk  # noqa: E402
from election_prediction.models import simulation  # noqa: E402
from election_prediction.scenarios import regional_reversion as rr  # noqa: E402

TX = {
    "state": "TX",
    "from_cycle": 2024,
    "state_fips": "48",
    "baf_zip": Path("data/raw/source=census_baf/vintage=2020/BlockAssign_ST48_TX_2020.zip"),
    "block_zip": Path(
        "data/raw/source=census_tiger/dataset=tabblock20/vintage=2022/tl_2022_48_tabblock20.zip"
    ),
    "plan_zip": Path("data/raw/source=state_plans/dataset=cd2026/state=TX/planc2333.zip"),
    "district_column": "District",
    "raw_dir": Path("data/raw"),
    "precinct_boundaries": Path(
        "data/raw/source=texas_tlc/dataset=vtd2024/snapshot=2026-10-18/vtds_24pg.zip"
    ),
    "precinct_column": "CNTYVTD",
    "old_plan": Path("data/raw/source=tiger/dataset=cd/vintage=2024/state=48/tl_2024_48_cd119.zip"),
}
REGISTERED_PRIOR = Path("data/gold/plan_transfer_tx_2024.parquet")
PRIOR_TOLERANCE = 0.002


def county_votes() -> pd.DataFrame:
    g = pd.read_parquet("data/gold/governor_county_returns.parquet")
    g = g[(g["state_po"] == "TX") & (g["office"] == "president")]
    g = g[g["party_simplified"].isin(["DEMOCRAT", "REPUBLICAN"])]
    wide = g.pivot_table(
        index=["cycle", "county_fips"], columns="party_simplified", values="votes", aggfunc="sum"
    ).reset_index()
    return wide.rename(columns={"DEMOCRAT": "dem_votes", "REPUBLICAN": "rep_votes"})


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--as-of", required=True)
    ap.add_argument("--fraction", type=float, default=0.5, help="share of the excess swing that reverses")
    args = ap.parse_args(argv)
    refresh = Path("reports") / f"refresh_{args.as_of}"
    if not (refresh / "senate_specification_gate.json").is_file():
        raise SystemExit(f"{refresh}: run scripts/refresh_2026.py --as-of {args.as_of} first")
    output = Path("reports") / f"scenario_south_texas_{args.as_of}"
    output.mkdir(parents=True, exist_ok=True)

    swing = rr.measure_swing(county_votes(), rr.SOUTH_TEXAS_BORDER_FIPS, from_cycle=2020, to_cycle=2024)

    _, at_block, stats = build_plan_transfer.build(**TX)
    # build() returns blocks before the new-district join; repeat the join it makes inside
    # plan_transfer.transfer so the weights rest on the same block assignment.
    block_new, _ = block_crosswalk.block_to_new_district(
        TX["block_zip"], TX["plan_zip"], district_column=TX["district_column"]
    )
    at_block = at_block.dropna(subset=["old_district"]).merge(
        block_new[["block_id", "new_district"]], on="block_id", how="left"
    )
    shares = rr.district_region_share(at_block, rr.SOUTH_TEXAS_BORDER_FIPS)
    statewide = rr.statewide_region_share(at_block, rr.SOUTH_TEXAS_BORDER_FIPS)
    registered = pd.read_parquet(REGISTERED_PRIOR)
    registered["new_district"] = registered["new_district"].astype(str).str.extract(r"(\d+)")[0].astype(int)
    check = shares.merge(registered[["new_district", "transferred_dem_share"]], on="new_district")
    worst = float((check["dem_share"] - check["transferred_dem_share"]).abs().max())
    if len(check) != 38 or worst > PRIOR_TOLERANCE:
        raise SystemExit(f"rebuilt allocation does not reproduce the registered prior (worst {worst:.4f})")
    shares.to_csv(output / "district_region_shares.csv", index=False)

    gate = json.loads((refresh / "senate_specification_gate.json").read_text())
    correlations = json.loads((refresh / "correlation_evaluation.json").read_text())
    scenario = {
        "name": "south_texas_reversion",
        "assumption": (
            f"{args.fraction:.0%} of the Texas border counties' 2020->2024 presidential swing in "
            "excess of the statewide swing reverses in 2026."
        ),
        "fraction": args.fraction,
        "region": rr.SOUTH_TEXAS_BORDER_FIPS,
        "swing": swing.to_dict(),
        "statewide_region_share": statewide,
        "house_rule": "Texas seat mean += -fraction * excess_swing * district region share",
        "senate_rule": "Texas Senate mean += -fraction * excess_swing * statewide region share",
        "prior_reproduction_max_abs_error": worst,
        "base_refresh": str(refresh),
        "not_measured": (
            "No 2026 vote, poll or special election from the region supports or rejects the "
            "assumption; county aggregates say nothing about how any group of voters moved."
        ),
    }
    adjust = rr.reversion_adjustment(
        state_po="TX",
        district_shares=shares,
        statewide_share=statewide,
        excess_swing=swing.excess_swing,
        fraction=args.fraction,
    )
    text = io.StringIO()
    with contextlib.redirect_stdout(text):
        payload = project(
            as_of=args.as_of,
            reports_dir=output,
            correlation_params=simulation.CorrelationParams(**correlations["house"]["selected_parameters"]),
            senate_correlation_params=simulation.CorrelationParams(
                **correlations["senate"]["selected_parameters"]
            ),
            senate_features=gate["features"],
            seat_adjustment=adjust,
            scenario=scenario,
        )
    (output / "projection_2026.txt").write_text(text.getvalue())
    pd.DataFrame(payload["seats"]).to_csv(output / "projection_seats.csv", index=False)
    summary = {
        "as_of": args.as_of,
        "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "working_tree_changes": subprocess.check_output(["git", "diff", "--stat"], text=True),
        "scenario": scenario,
        "transfer_stats": {k: stats[k] for k in ("precinct_votes", "apportionment")},
        "inputs": {
            str(p): sha256_file(p)
            for p in [
                *(v for v in TX.values() if isinstance(v, Path) and v.is_file()),
                REGISTERED_PRIOR,
                Path("data/gold/governor_county_returns.parquet"),
            ]
        },
        "code_sha256": {
            p: sha256_file(Path(p))
            for p in (
                "scripts/scenario_south_texas.py",
                "src/election_prediction/scenarios/regional_reversion.py",
                "scripts/project_2026.py",
            )
        },
    }
    (output / "scenario_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print(
        json.dumps(
            {
                "swing": swing.to_dict(),
                "statewide_region_share": statewide,
                "prior_reproduction_max_abs_error": worst,
            },
            indent=2,
        )
    )
    print(f"scenario -> {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

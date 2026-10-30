"""Measure all available redrawn-state transfers; never automatically admit a prior."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from election_prediction import build_plan_transfer as transfer

STATES = {"AL": "01", "CA": "06", "FL": "12", "LA": "22", "NC": "37", "OH": "39", "TN": "47", "UT": "49"}


def main() -> None:
    output = Path("reports/refresh_2026-10-21/transfers")
    output.mkdir(parents=True, exist_ok=True)
    raw = Path("data/raw")
    races = pd.read_parquet("data/gold/race_results.parquet")
    summaries = {}
    for state, fips in STATES.items():
        record = {}
        for cycle in (2020, 2024):
            try:
                table, _, report = transfer.build(
                    state,
                    cycle,
                    raw / f"source=census_baf/vintage=2020/BlockAssign_ST{fips}_{state}_2020.zip",
                    raw
                    / f"source=census_tiger/dataset=tabblock20/vintage=2022/tl_2022_{fips}_tabblock20.zip",
                    raw / f"source=census_tiger/dataset=cd118/vintage=2023/tl_2023_{fips}_cd118.zip"
                    if cycle == 2020
                    else None,
                    raw,
                    fips,
                    old_plan=raw
                    / f"source=tiger/dataset=cd/vintage=2024/state={fips}/tl_2024_{fips}_cd119.zip"
                    if cycle == 2024
                    else None,
                    new_block_equivalency=raw / "source=census_cd120_bef/snapshot=2026-10-21/cd120.zip"
                    if cycle == 2024
                    else None,
                )
                certified = races[
                    races.cycle.eq(cycle) & races.office.eq("president") & races.state_po.eq(state)
                ]
                offered = report["precinct_votes"]["two_party_votes"]
                expected = float(certified.dem_votes.sum() + certified.rep_votes.sum())
                report["statewide_reconciliation"] = {
                    "parsed_two_party_votes": offered,
                    "certified_two_party_votes": expected,
                    "passed": abs(offered - expected) < 1,
                }
                if cycle == 2020:
                    actual = transfer._actual_from_house_returns(
                        Path("data/silver/election_returns.parquet"), state, 2022
                    )
                    lean = transfer._state_lean(Path("data/gold/presidential_panel.parquet"), state, cycle)
                    report["backtest"] = transfer.plan_transfer.backtest_transfer(
                        table, actual, state_lean_fallback=lean
                    )
                placed = report["apportionment"]["votes_placed"] / max(offered, 1)
                report["usability"] = {
                    "placed_share": placed,
                    "usable": placed >= 0.999 and report["statewide_reconciliation"]["passed"],
                    "admitted": False,
                    "reason": "Candidate only; state-specific calibration and register review required",
                }
                table.to_parquet(output / f"{state.lower()}_{cycle}.parquet", index=False)
                record[str(cycle)] = report
            except (ValueError, FileNotFoundError, KeyError) as exc:
                record[str(cycle)] = {"status": "blocked", "error": str(exc)}
            status = "blocked" if "error" in record[str(cycle)] else "measured"
            print(f"transfer audit {state} {cycle}: {status}", flush=True)
        (output / f"{state.lower()}.json").write_text(json.dumps(record, indent=2))
        summaries[state] = record
    (output / "audit.json").write_text(json.dumps(summaries, indent=2))


if __name__ == "__main__":
    main()

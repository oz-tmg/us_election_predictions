"""Authoritative source spot-checks for publication-grade builds.

These checks complement internal schema and vote-reconciliation gates with small,
independently published benchmarks. The benchmark file is Tier 0 aggregate data and
records its official source URLs for reproducibility.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

DEFAULT_BENCHMARKS = Path(__file__).resolve().parents[3] / "data/reference/source_validation_benchmarks.json"


def load_benchmarks(path: str | Path = DEFAULT_BENCHMARKS) -> dict:
    return json.loads(Path(path).read_text())


def validate_senate_totals(returns: pd.DataFrame, benchmarks: dict) -> dict:
    """Compare MEDSL 2022 Senate race totals with official FEC state totals."""
    values = benchmarks["fec_2022_senate_general"]["values"]
    rows = []
    for state_po, expected in values.items():
        race = returns[
            (returns["office"] == "us_senate")
            & (returns["cycle"] == 2022)
            & (returns["state_po"] == state_po)
            & (~returns["special"].astype(bool))
        ]
        totals = race["totalvotes"].dropna().astype(int).unique().tolist()
        observed = totals[0] if len(totals) == 1 else None
        rows.append(
            {
                "state": state_po,
                "expected": int(expected),
                "observed": observed,
                "match": observed == int(expected),
            }
        )
    return {"ok": all(row["match"] for row in rows), "rows": rows}


def validate_acs_populations(features: pd.DataFrame, benchmarks: dict) -> dict:
    """Compare standardized ACS populations with published B01003 estimates."""
    values = benchmarks["acs_2023_state_population"]["values"]
    rows = []
    for state_fips, expected in values.items():
        match = features[features["state_fips"] == state_fips]
        observed = int(match["total_population"].iloc[0]) if len(match) == 1 else None
        rows.append(
            {
                "state_fips": state_fips,
                "expected": int(expected),
                "observed": observed,
                "match": observed == int(expected),
            }
        )
    return {"ok": all(row["match"] for row in rows), "rows": rows}


def validate_live_sources(
    returns: pd.DataFrame,
    acs_features: pd.DataFrame,
    benchmark_path: str | Path = DEFAULT_BENCHMARKS,
) -> dict:
    benchmarks = load_benchmarks(benchmark_path)
    senate = validate_senate_totals(returns, benchmarks)
    acs = validate_acs_populations(acs_features, benchmarks)
    return {
        "ok": senate["ok"] and acs["ok"],
        "senate": senate,
        "acs": acs,
        "sources": {
            "senate": benchmarks["fec_2022_senate_general"]["source_url"],
            "acs": benchmarks["acs_2023_state_population"]["source_url"],
        },
    }


def write_report(validation: dict, path: str | Path) -> Path:
    """Write the compact authoritative-source validation report."""
    path = Path(path)
    lines = [
        "# Source Validation Report",
        "",
        f"_Generated: {datetime.now(UTC).isoformat(timespec='seconds')}_",
        "",
        "> Tier 0 public aggregate benchmarks; no personal records.",
        "",
        "## MEDSL Senate spot-check",
        "",
        f"Official benchmark: {validation['sources']['senate']}",
        "",
        "| State | FEC certified total | MEDSL total | Match |",
        "|---|---:|---:|:---:|",
    ]
    for row in validation["senate"]["rows"]:
        observed = f"{row['observed']:,}" if row["observed"] is not None else "missing"
        lines.append(
            f"| {row['state']} | {row['expected']:,} | {observed} | {'YES' if row['match'] else 'NO'} |"
        )

    lines.extend(
        [
            "",
            "## ACS state population spot-check",
            "",
            f"Official benchmark: {validation['sources']['acs']}",
            "",
            "| State FIPS | Published B01003 | Standardized feature | Match |",
            "|---|---:|---:|:---:|",
        ]
    )
    for row in validation["acs"]["rows"]:
        observed = f"{row['observed']:,}" if row["observed"] is not None else "missing"
        lines.append(
            f"| {row['state_fips']} | {row['expected']:,} | {observed} | {'YES' if row['match'] else 'NO'} |"
        )

    lines.extend(
        [
            "",
            "## Overall",
            "",
            (
                "**PASS** — all authoritative spot-checks matched."
                if validation["ok"]
                else "**FAIL** — one or more authoritative spot-checks did not match."
            ),
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines))
    return path

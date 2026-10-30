#!/usr/bin/env python
"""Texas historical context: certified county returns aggregated to named regions.

    python scripts/texas_context.py --as-of 2026-10-29

Two-party Democratic share for governor (2018, 2022) and president (2020, 2024) by region,
from ``data/gold/governor_county_returns.parquet`` (MEDSL precinct files aggregated to
county; statewide totals reproduce the certified shares). Regions are fixed county lists
named here. These are aggregates of counties: they say nothing about how any group of
voters moved (PROJECT_CONTEXT.md §16, ecological fallacy). Governor history is context
only; there is no governor model.

Writes ``reports/texas_context_<as_of>/region_history.csv`` and ``README.md``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, "src")

from election_prediction.data.manifest import sha256_file  # noqa: E402
from election_prediction.scenarios.regional_reversion import SOUTH_TEXAS_BORDER_FIPS  # noqa: E402

SOURCE = Path("data/gold/governor_county_returns.parquet")
REGIONS: dict[str, list[str]] = {
    "South Texas border": sorted(SOUTH_TEXAS_BORDER_FIPS.values()),
    "Dallas suburbs": ["Collin", "Denton", "Rockwall", "Kaufman", "Ellis"],
    "Houston suburbs": ["Fort Bend", "Montgomery", "Brazoria", "Galveston"],
    "Austin suburbs": ["Williamson", "Hays"],
    "Urban cores": ["Harris", "Dallas", "Travis", "Bexar", "Tarrant"],
}


def region_history(county: pd.DataFrame) -> pd.DataFrame:
    tx = county[(county["state_po"] == "TX") & county["party_simplified"].isin(["DEMOCRAT", "REPUBLICAN"])]
    wide = tx.pivot_table(
        index=["cycle", "office", "county_name"], columns="party_simplified", values="votes", aggfunc="sum"
    ).reset_index()
    known = set(wide["county_name"])
    rows = []
    for region, counties in {**REGIONS, "Texas statewide": None}.items():
        if counties is not None:
            upper = [c.upper() for c in counties]
            missing = sorted(set(upper) - known)
            if missing:
                raise ValueError(f"{region}: counties missing from the source: {missing}")
            part = wide[wide["county_name"].isin(upper)]
        else:
            part = wide
        for (cycle, office), g in part.groupby(["cycle", "office"]):
            d, r = g["DEMOCRAT"].sum(), g["REPUBLICAN"].sum()
            rows.append(
                {
                    "region": region,
                    "counties": "all 254" if counties is None else ", ".join(counties),
                    "office": office,
                    "cycle": int(cycle),
                    "two_party_dem_share": d / (d + r),
                    "two_party_votes": d + r,
                    "n_counties": int(g["county_name"].nunique()),
                }
            )
    return pd.DataFrame(rows).sort_values(["region", "cycle"]).reset_index(drop=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--as-of", required=True)
    args = ap.parse_args(argv)
    output = Path("reports") / f"texas_context_{args.as_of}"
    output.mkdir(parents=True, exist_ok=True)
    history = region_history(pd.read_parquet(SOURCE))
    history.to_csv(output / "region_history.csv", index=False)
    meta = {
        "as_of": args.as_of,
        "source": str(SOURCE),
        "source_sha256": sha256_file(SOURCE),
        "regions": REGIONS,
        "caveat": (
            "County aggregates; no inference about any group of voters. Governor history is context only."
        ),
    }
    (output / "context.json").write_text(json.dumps(meta, indent=2))
    pivot = history.pivot_table(index="region", columns=["office", "cycle"], values="two_party_dem_share")
    (output / "README.md").write_text(
        f"# Texas context ({args.as_of})\n\nTwo-party Democratic share by region, certified returns.\n\n"
        + "```\n"
        + pivot.round(3).to_string()
        + "\n```"
        + "\n\nCounty aggregates only; governor history is context, not a model prior.\n"
    )
    print(pivot.round(3).to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

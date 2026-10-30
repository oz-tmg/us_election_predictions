"""Build a dated, deliberately unpromoted generic-ballot cross-check from cited public facts."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import pandas as pd

from .data.manifest import sha256_file
from .data.public_sources import snapshot
from .features.national_fundamentals import target
from .polling import generic, schema


def build(*, as_of: str) -> dict:
    output = Path("reports") / f"refresh_{as_of}"
    output.mkdir(parents=True, exist_ok=True)
    reference = Path("data/reference/generic_ballot_2026.csv")
    raw = pd.read_csv(reference)
    if raw.published_on.isna().any() or (pd.to_datetime(raw.retrieved_on) > pd.Timestamp(as_of)).any():
        raise ValueError("live poll facts need explicit publication/retrieval dates no later than as-of")
    for row in raw.to_dict(orient="records"):
        snapshot(
            row["source_url"],
            Path(f"data/raw/source=pollster_generic_ballot_compiled/snapshot={as_of}/{row['poll_id']}.html"),
            source_id="pollster_generic_ballot_compiled",
            owner=row["pollster"],
            expect="html",
        )
    copied = Path(
        f"data/raw/source=pollster_generic_ballot_compiled/snapshot={as_of}/sha256={sha256_file(reference)}/polls.csv"
    )
    copied.parent.mkdir(parents=True, exist_ok=True)
    if not copied.exists():
        shutil.copyfile(reference, copied)
    snapshot(
        "Per-row source_url in the compiled CSV",
        copied,
        source_id="pollster_generic_ballot_compiled",
        owner="Cited original pollster releases",
        expect="csv",
        redistribution_allowed=True,
    )
    polls = schema.standardize_polls(raw, source_id="pollster_generic_ballot_compiled", snapshot_date=as_of)
    polls.to_csv(output / "generic_ballot_polls.csv", index=False)
    races = pd.read_parquet("data/gold/race_results.parquet")
    targets = pd.DataFrame(
        [
            {"cycle": cycle, "actual_dem_share": target(races, cycle=cycle, white_house_party="DEMOCRAT")}
            for cycle in range(1996, 2026, 2)
        ]
    )
    path = Path(
        "data/raw/source=538_generic_ballot_archive/snapshot=2026-10-21/generic_topline_historical.csv"
    )
    historical = generic.historical_topline_check(pd.read_csv(path), targets)
    result = {
        "as_of": as_of,
        "historical_attribution": {
            "owner": "FiveThirtyEight",
            "source_url": "https://github.com/fivethirtyeight/data/tree/master/congress-generic-ballot",
            "license": "CC BY 4.0",
            "transformations": "October 20 cutoffs; two-party normalization; MEDSL House comparison",
        },
        "estimate": generic.estimate(polls, as_of=as_of, historical=historical).to_dict(),
        "historical_topline_sha256": sha256_file(path),
        "compiled_sha256": sha256_file(copied),
        "poll_level_archive_status": "Quarantined: inconsistent CSV field counts; no rows skipped",
    }
    (output / "generic_ballot_cross_check.json").write_text(json.dumps(result, indent=2, default=str))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", required=True)
    build(as_of=parser.parse_args().as_of)


if __name__ == "__main__":
    main()

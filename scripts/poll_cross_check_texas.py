#!/usr/bin/env python
"""Texas poll cross-check: hand-compiled releases averaged and set beside the fundamentals.

    python scripts/poll_cross_check_texas.py --as-of 2026-10-29

Reads ``data/reference/texas_polls_2026.csv`` (registered ``texas_polls_2026_compiled``),
snapshots it immutably with a manifest, validates it against the poll schema, and
averages it with ``polling.average.average_polls``. The result is a **cross-check**: it is
written beside the refresh, never blended into the band — no backtested poll/fundamentals
weight exists and house effects are not estimated (NE-003, P2-003 are unbuilt).

Writes ``reports/poll_cross_check_texas_<as_of>/``.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, "src")

from election_prediction.data.manifest import SourceManifest, sha256_file  # noqa: E402
from election_prediction.data.privacy import PrivacyTier  # noqa: E402
from election_prediction.polling import average, schema  # noqa: E402

SOURCE_ID = "texas_polls_2026_compiled"
COMPILED = Path("data/reference/texas_polls_2026.csv")
HALF_LIVES = (21.0, 10.0)  # default, and a faster-decay sensitivity


def snapshot(as_of: str) -> Path:
    checksum = sha256_file(COMPILED)
    raw = Path(f"data/raw/source={SOURCE_ID}/snapshot={as_of}/sha256={checksum}") / COMPILED.name
    raw.parent.mkdir(parents=True, exist_ok=True)
    if raw.exists() and sha256_file(raw) != checksum:
        raise ValueError(f"immutable compilation snapshot already exists: {raw}")
    if not raw.exists():
        shutil.copyfile(COMPILED, raw)
    manifest = SourceManifest.for_snapshot(
        raw_path=raw,
        source_id=f"{SOURCE_ID}_{checksum[:12]}",
        dataset_name=COMPILED.name,
        source_owner="Pollsters named per row (hand-compiled by Savepoint Analytics)",
        source_url="source_url per compiled row",
        privacy_tier=PrivacyTier.PUBLIC_AGGREGATE,
        license_or_terms=(
            "Topline facts cited per row; no release prose or crosstabs reproduced (NE-000 route)."
        ),
        permitted_use="Nonpartisan aggregate research; cross-check beside the fundamentals band.",
        prohibited_use="No blending into the forecast without a backtested weight; no respondent data.",
        office_coverage=["us_senate", "governor"],
        geography_coverage=["state"],
        election_cycle="2026",
        owner="Alex Oswald (data steward)",
        acquisition_method="manual_compilation",
        required_attribution="Each pollster as named per row",
        file_format="csv",
    )
    manifest.validation_status = "passed"
    manifest.row_count = len(pd.read_csv(COMPILED, comment="#"))
    manifest.write()
    return raw


def governor_history() -> dict[int, float]:
    g = pd.read_parquet("data/gold/governor_county_returns.parquet")
    g = g[(g["state_po"] == "TX") & (g["office"] == "governor")]
    out = {}
    for cycle, x in g.groupby("cycle"):
        d = x.loc[x["party_simplified"] == "DEMOCRAT", "votes"].sum()
        r = x.loc[x["party_simplified"] == "REPUBLICAN", "votes"].sum()
        out[int(cycle)] = float(d / (d + r))
    return out


def fundamentals(path: Path) -> list[dict]:
    seats = pd.read_csv(path)
    tx = seats[(seats["office"] == "us_senate") & (seats["state_po"] == "TX")]
    return tx[["assumption", "mean_dem_share", "sigma", "dem_win_prob"]].to_dict(orient="records")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--as-of", required=True)
    args = ap.parse_args(argv)
    output = Path("reports") / f"poll_cross_check_texas_{args.as_of}"
    output.mkdir(parents=True, exist_ok=True)

    raw = snapshot(args.as_of)
    compiled = pd.read_csv(raw, comment="#")
    polls = schema.standardize_polls(compiled, source_id=SOURCE_ID, snapshot_date=args.as_of)
    checks = schema.validate_polls(polls)
    if not checks["ok"]:
        raise SystemExit(f"poll validation failed: {checks}")
    excluded = polls[polls["internal"] | polls["sponsor_partisan"].ne("NONE")]
    eligible = polls.drop(excluded.index)

    averages = {}
    for half_life in HALF_LIVES:
        for label, frame in (
            ("all", eligible),
            ("likely_voters_only", eligible[eligible.population == "LV"]),
        ):
            avg = average.average_polls(frame, reference_date=args.as_of, half_life_days=half_life)
            averages[f"half_life_{half_life:g}d_{label}"] = avg.to_dict(orient="records")
    polls.assign(retrieved_on=compiled["retrieved_on"].values, note=compiled["note"].values).to_csv(
        output / "polls.csv", index=False
    )

    refresh = Path("reports") / f"refresh_{args.as_of}" / "projection_seats.csv"
    scenario = Path("reports") / f"scenario_south_texas_{args.as_of}" / "projection_seats.csv"
    payload = {
        "as_of": args.as_of,
        "status": "cross-check only; not blended into the projection",
        "source_id": SOURCE_ID,
        "snapshot": str(raw),
        "snapshot_sha256": sha256_file(raw),
        "validation": checks,
        "excluded_from_average": excluded["poll_id"].tolist(),
        "method": {
            "average": (
                "polling.average.average_polls: exponential time decay, sqrt sample size, LV 1.0 / RV 0.85"
            ),
            "half_lives_days": list(HALF_LIVES),
            "house_effects": "not estimated (P2-003 unbuilt); none applied",
            "poll_error_floor": 0.025,
        },
        "averages": averages,
        "fundamentals_senate": {
            "refresh": fundamentals(refresh) if refresh.is_file() else None,
            "south_texas_scenario": fundamentals(scenario) if scenario.is_file() else None,
        },
        "governor_history_two_party_dem": governor_history(),
        "governor_model": "none: no governor projection exists; history is context, not a prior",
        "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
    }
    (output / "poll_average.json").write_text(json.dumps(payload, indent=2, default=str))
    main_avg = pd.DataFrame(averages[f"half_life_{HALF_LIVES[0]:g}d_all"])
    print(
        main_avg[["office", "poll_mean_dem_share", "poll_sigma", "n_polls", "n_pollsters"]].to_string(
            index=False
        )
    )
    print(f"cross-check -> {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

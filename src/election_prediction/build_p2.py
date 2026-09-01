"""End-to-end P2 polling baseline build (MVP steps 5–7).

Runs P1, ingests governed public poll toplines (or an explicitly labelled synthetic
fixture), computes a transparent polling average, blends it with the presidential
fundamentals prior, and runs the existing correlated simulation. Outputs include state
vote-share intervals, win probabilities, Electoral College uncertainty, a standardized
model card, and a concise scenario report.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from .build_p1 import build as build_p1
from .config import load_dotenv
from .data import acquire
from .data.manifest import SourceManifest
from .data.privacy import PrivacyTier
from .models import simulation
from .models.baseline import presidential
from .polling import (
    average_polls,
    blend_with_fundamentals,
    build_synthetic_poll_fixture,
    standardize_polls,
    validate_polls,
)
from .polling.schema import read_poll_csv
from .reporting.model_cards import write_polling_forecast_report, write_polling_model_card


def _snapshot_poll_input(base: Path, poll_path: Path | None, raw: pd.DataFrame, *, synthetic: bool) -> Path:
    snapshot = date.today().isoformat()
    source = "synthetic_polls" if synthetic else "public_polls"
    if synthetic:
        filename = "SYNTHETIC_poll_toplines.csv"
    else:
        assert poll_path is not None
        filename = poll_path.name
    destination = base / f"data/raw/source={source}/dataset=toplines/snapshot={snapshot}/{filename}"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if synthetic:
        raw.to_csv(destination, index=False)
    elif poll_path is not None and poll_path.resolve() != destination.resolve():
        shutil.copy2(poll_path, destination)
    return destination


def _write_poll_manifest(
    raw_path: Path,
    base: Path,
    *,
    source_id: str,
    synthetic: bool,
    row_count: int,
) -> Path:
    manifest = SourceManifest.for_snapshot(
        raw_path=raw_path,
        source_id=source_id,
        dataset_name=(
            "Synthetic Public Poll Topline Fixture" if synthetic else "Mixed Public Pollster Toplines"
        ),
        source_owner="Savepoint Analytics" if synthetic else "Mixed public pollster releases",
        source_url=(
            "https://example.invalid/synthetic-poll-fixture"
            if synthetic
            else "https://github.com/oz-tmg/us_election_predictions"
        ),
        privacy_tier=PrivacyTier.PUBLIC_AGGREGATE,
        license_or_terms=(
            "Project-generated fictional fixture."
            if synthetic
            else "Row-level source_url controls; verify each pollster's terms before redistribution."
        ),
        permitted_use="Nonpartisan aggregate research, reproducibility tests, and calibration analysis.",
        prohibited_use=(
            "Never present synthetic toplines as observed polls."
            if synthetic
            else "No respondent-level data, personal targeting, or redistribution beyond source terms."
        ),
        office_coverage=["president"],
        geography_coverage=["state"],
        election_cycle="multi",
        owner="project-owner (data steward)",
        acquisition_method="generated_fixture" if synthetic else "manual_export",
        redistribution_allowed=synthetic,
        file_format="csv",
        required_attribution=(
            "Synthetic fixture — no external attribution."
            if synthetic
            else "Cite every row-level pollster/source URL."
        ),
        known_caveats=(
            "SYNTHETIC fictional polling data — pipeline testing only."
            if synthetic
            else "Mixed-source toplines require per-row methodology and license review."
        ),
    )
    manifest.validation_status = "passed"
    manifest.row_count = row_count
    manifest.unique_key = ["poll_id"]
    return manifest.write(base / "data/manifests")


def _jsonable(obj):
    if isinstance(obj, dict):
        return {key: _jsonable(value) for key, value in obj.items()}
    if isinstance(obj, pd.DataFrame):
        return obj.to_dict("records")
    if isinstance(obj, (np.floating, np.integer)):
        return obj.item()
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj


def build(
    base: Path,
    *,
    poll_path: Path | None = None,
    reference_date: str | date | None = None,
    allow_network: bool = True,
    require_live: bool = False,
) -> dict:
    base = Path(base)
    poll_path = Path(poll_path) if poll_path is not None else None
    if require_live and poll_path is None:
        raise acquire.AcquisitionError("--require-live requires --polls with governed public toplines.")
    if poll_path is not None and not poll_path.is_file():
        raise acquire.AcquisitionError(f"Poll topline file does not exist: {poll_path}")

    p1 = build_p1(base, allow_network=allow_network, require_live=require_live)
    panel = pd.read_parquet(base / "data/gold/presidential_panel.parquet")
    predictions, _ = presidential.backtest_leave_one_cycle_out(
        panel, ["lag_dem_share", "national_dem_share", "college_share"]
    )
    if predictions.empty:
        raise acquire.InvalidResponse("P2 requires at least one backtested presidential cycle.")
    latest_cycle = int(predictions["cycle"].max())
    latest = predictions[predictions["cycle"] == latest_cycle].copy()
    as_of = pd.Timestamp(reference_date or f"{latest_cycle}-11-01").date()

    synthetic = poll_path is None
    if synthetic:
        raw = build_synthetic_poll_fixture(latest, cycle=latest_cycle, reference_date=as_of)
        source_id = f"synthetic_public_polls_{latest_cycle}"
    else:
        assert poll_path is not None
        raw = read_poll_csv(poll_path)
        source_id = f"public_poll_toplines_{date.today():%Y%m%d}"

    raw_path = _snapshot_poll_input(base, poll_path, raw, synthetic=synthetic)
    polls = standardize_polls(raw, source_id=source_id, snapshot_date=date.today())
    checks = validate_polls(polls)
    if not checks["ok"]:
        raise acquire.InvalidResponse(f"Poll topline validation failed: {checks}")
    _write_poll_manifest(
        raw_path,
        base,
        source_id=source_id,
        synthetic=synthetic,
        row_count=len(polls),
    )

    target = polls[(polls["office"] == "president") & (polls["cycle"] == latest_cycle)]
    if target.empty:
        raise acquire.InvalidResponse(
            f"P2 v0 needs presidential polls for backtested cycle {latest_cycle}; none were supplied."
        )
    averages = average_polls(target, reference_date=as_of)
    used_poll_count = int(averages["n_polls"].sum())
    blended = blend_with_fundamentals(latest, averages)
    sim = simulation.simulate_presidential(blended)

    silver_dir = base / "data/silver"
    gold_dir = base / "data/gold"
    reports_dir = base / "reports"
    for directory in (silver_dir, gold_dir, reports_dir):
        directory.mkdir(parents=True, exist_ok=True)
    polls.to_parquet(silver_dir / "poll_toplines.parquet", index=False)
    averages.to_parquet(gold_dir / "polling_averages.parquet", index=False)
    blended.to_parquet(gold_dir / "polling_blended_presidential.parquet", index=False)

    results = {
        "polling": {
            "cycle": latest_cycle,
            "as_of": as_of.isoformat(),
            "n_polls": used_poll_count,
            "n_poll_rows_supplied": int(len(target)),
            "n_averages": int(len(averages)),
            "mean_effective_polls": float(averages["effective_polls"].mean()),
            "validation": checks,
        },
        "simulation": sim,
        "data_mode": {**p1["data_mode"], "polls": "synthetic" if synthetic else "manual"},
    }
    write_polling_model_card(results, reports_dir, synthetic=synthetic)
    report = write_polling_forecast_report(results, reports_dir, synthetic=synthetic)
    (reports_dir / "p2_results.json").write_text(json.dumps(_jsonable(results), indent=2) + "\n")

    ec = sim["electoral_college"]
    print("\n=== P2 polling baseline summary ===")
    print(
        f"  Polls: {used_poll_count} across {len(averages)} state/geography averages "
        f"(mode={'synthetic' if synthetic else 'manual'})"
    )
    print(
        f"  Correlated sim mean Dem EV: {ec['mean_dem_ev']:.0f} | "
        f"P(Dem EC majority): {ec['p_dem_majority']:.3f}"
    )
    print(f"  Report -> {report}")
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the P2 polling + simulation baseline.")
    parser.add_argument("--base", default=".")
    parser.add_argument("--polls", type=Path, help="governed public poll-topline CSV")
    parser.add_argument("--as-of", help="polling average reference date (YYYY-MM-DD)")
    parser.add_argument("--offline", action="store_true", help="use synthetic fixtures and no network")
    parser.add_argument(
        "--require-live",
        action="store_true",
        help="require real P0/P1 inputs and an explicit --polls file",
    )
    args = parser.parse_args(argv)
    if args.offline and args.require_live:
        parser.error("--offline and --require-live are mutually exclusive")
    if loaded := load_dotenv(Path(args.base) / ".env"):
        print(f"Loaded {len(loaded)} local settings from .env: {', '.join(sorted(loaded))}", flush=True)
    try:
        build(
            Path(args.base),
            poll_path=args.polls,
            reference_date=args.as_of,
            allow_network=not args.offline,
            require_live=args.require_live,
        )
    except (acquire.AcquisitionError, ValueError) as exc:
        print(f"\nP2 build FAILED:\n  {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

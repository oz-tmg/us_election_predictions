"""End-to-end P0 build (``ep-build-p0``).

Runs the data-and-entity foundation reproducibly from a clean checkout:

    raw (download or synthetic) -> manifest -> bronze -> validate
      -> silver election_returns -> geography spine -> gold race table
      -> validate -> data-quality report

Live MEDSL download is attempted first. When a source cannot be acquired the build
either falls back to a clearly-labelled synthetic fixture (default, so the pipeline
is always exercised) or fails outright under ``--require-live``, which is the mode to
use for anything whose numbers will be published.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

import pandas as pd

from .config import load_dotenv
from .data import acquire, medsl, synthetic
from .data.manifest import SourceManifest
from .data.privacy import PrivacyTier
from .data.validation import validate_geography_table, validate_silver_returns
from .evaluation.data_quality import build_quality_report, write_report
from .features.race_table import build_race_table
from .geography.canonical import build_geography_table

OFFICES = ["president", "us_senate", "us_house"]


def _acquire(office: str, raw_dir: Path, *, allow_network: bool,
             require_live: bool) -> tuple[Path, str]:
    """Return (path, mode) where mode is 'live', 'manual', or 'synthetic'.

    Under ``require_live`` an unacquirable source raises instead of degrading to a
    fixture — a build that silently substitutes synthetic data can otherwise report
    success while modelling fiction (CLAUDE.md §4 reproducibility).
    """
    if allow_network:
        try:
            path = medsl.download_medsl(office, raw_dir)
            mode = "manual" if path.parent.name == "manual" else "live"
            return path, mode
        except acquire.ManualAcquisitionRequired as e:
            print(f"\n  ! {e.instructions()}\n", file=sys.stderr)
            if require_live:
                raise
        except acquire.AcquisitionError as e:
            print(f"  ! {e}", file=sys.stderr)
            if require_live:
                raise

    if require_live:
        raise acquire.AcquisitionError(
            f"--require-live was set but {office} could not be acquired live."
        )

    fx_dir = raw_dir / f"source=medsl/dataset={office}/snapshot={date.today():%Y-%m-%d}"
    return synthetic.write_fixture(office, fx_dir), "synthetic"


def build(base: Path, *, allow_network: bool = True, require_live: bool = False) -> dict:
    base = Path(base)
    raw_dir = base / "data/raw"
    silver_dir = base / "data/silver"
    gold_dir = base / "data/gold"
    manifests_dir = base / "data/manifests"
    reports_dir = base / "reports"
    for d in (silver_dir, gold_dir, manifests_dir, reports_dir):
        d.mkdir(parents=True, exist_ok=True)

    snapshot_date = date.today().isoformat()
    silver_parts = []
    modes = {}
    transform_stats = {}

    for office in OFFICES:
        print(f"[{office}] acquiring…")
        csv_path, mode = _acquire(office, raw_dir, allow_network=allow_network,
                                  require_live=require_live)
        modes[office] = mode
        src = medsl.MEDSL_SOURCES[office]

        # manifest (checksums the raw snapshot; enforces Tier 0-2 at construction)
        manifest = SourceManifest.for_snapshot(
            raw_path=csv_path,
            source_id=src.source_id + ("" if mode == "live" else "_synthetic"),
            dataset_name=src.dataset_name + ("" if mode == "live" else " [SYNTHETIC FIXTURE]"),
            source_owner="MIT Election Data and Science Lab",
            source_url=src.url,
            privacy_tier=PrivacyTier.PUBLIC_AGGREGATE,
            license_or_terms=medsl.LICENSE,
            permitted_use="Public nonpartisan research, aggregate reporting with citation.",
            prohibited_use="No repurposing for solicitation, targeting, or partisan advantage.",
            office_coverage=[office],
            geography_coverage=[src.geog_level],
            election_cycle=src.election_cycle,
            owner="project-owner (data steward)",
            required_attribution=medsl.ATTRIBUTION,
            known_caveats=("SYNTHETIC fictional data — not real returns." if mode == "synthetic"
                           else "Coverage/lag vary by office and year."),
        )
        mpath = manifest.write(manifests_dir)

        # bronze -> silver
        bronze = medsl.parse_bronze(csv_path, office,
                                    source_id=manifest.source_id, snapshot_date=snapshot_date)
        silver, stats = medsl.standardize_silver_with_stats(bronze, office)
        silver_parts.append(silver)
        transform_stats[office] = stats
        print(f"  raw={csv_path.name} mode={mode} rows={len(silver)} manifest={mpath.name}")
        if stats.get("dropped_non_general"):
            print(f"    dropped {stats['dropped_non_general']:,} non-general-stage rows")
        if stats.get("fusion_candidates_merged"):
            print(f"    merged {stats['fusion_candidates_merged']:,} fusion-voting candidate lines")
        if stats.get("mode_rows_collapsed"):
            print(f"    collapsed {stats['mode_rows_collapsed']:,} per-mode rows")

    returns = pd.concat(silver_parts, ignore_index=True)

    # geography spine (seeded from observed geography in returns)
    geography = build_geography_table(returns)

    # validate silver
    vr = validate_silver_returns(returns, required_columns=medsl.SILVER_COLUMNS)
    vg = validate_geography_table(geography)
    print("\n" + vr.summary())
    print(vg.summary())

    # gold race table
    race_table = build_race_table(returns)

    # persist medallion outputs
    returns.to_parquet(silver_dir / "election_returns.parquet", index=False)
    geography.to_parquet(silver_dir / "geography.parquet", index=False)
    race_table.to_parquet(gold_dir / "race_results.parquet", index=False)
    # also CSV mirrors for easy inspection
    returns.to_csv(silver_dir / "election_returns.csv", index=False)
    race_table.to_csv(gold_dir / "race_results.csv", index=False)

    # data-quality report
    report = build_quality_report(returns, race_table, geography,
                                  data_modes=modes, transform_stats=transform_stats)
    rpath = write_report(report, reports_dir)
    print(f"\nData-quality report -> {rpath}")

    ok = vr.ok and vg.ok and report["overall_ok"]
    print(f"\nP0 build {'PASSED' if ok else 'FAILED'} "
          f"(modes: {modes}, races={report['coverage']['races']})")
    return {"ok": ok, "modes": modes, "report": report,
            "returns": returns, "race_table": race_table, "geography": geography}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build the P0 data-and-entity foundation.")
    ap.add_argument("--base", default=".", help="repo root (default: cwd)")
    ap.add_argument("--offline", action="store_true",
                    help="skip the live download and use synthetic fixtures")
    ap.add_argument("--require-live", action="store_true",
                    help="fail instead of falling back to synthetic fixtures "
                         "(use for any run whose numbers will be published)")
    args = ap.parse_args(argv)
    if args.offline and args.require_live:
        ap.error("--offline and --require-live are mutually exclusive")
    if loaded := load_dotenv(Path(args.base) / ".env"):
        print(f"Loaded {len(loaded)} local settings from .env: {', '.join(sorted(loaded))}",
              flush=True)
    try:
        result = build(Path(args.base), allow_network=not args.offline,
                       require_live=args.require_live)
    except acquire.AcquisitionError as e:
        print(f"\nP0 build FAILED — could not acquire real data:\n  {e}", file=sys.stderr)
        return 2
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

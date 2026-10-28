"""``ep-export-dashboard``: turn committed build artefacts into dashboard run bundles.

Each subcommand reads artefacts that an existing build already wrote and re-shapes them;
nothing here fits, simulates or re-derives a number. In particular seat distributions and
chamber-control probabilities are copied from the correlated simulation's own output, never
recomputed from per-seat probabilities (that would treat seats as independent — CLAUDE.md
§2.6).

    ep-export-dashboard refresh reports/refresh_2026-10-22
    ep-export-dashboard preregistration reports/preregistration_2026-11-03.json
    ep-export-dashboard backtest reports/p1_results.json --as-of 2026-09-01
    ep-export-dashboard history data/gold/race_results.parquet

Bundles are written to ``data/gold/dashboard_bundles/<tier>/<run_id>/`` (git-ignored with
the rest of gold) and are immutable: re-exporting an existing run raises unless
``--replace`` is given. Upload with ``gcloud storage rsync`` (docs/deployment-plan.md).
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pandas as pd

from election_prediction.dashboard.bundle import (
    MANIFEST_NAME,
    TABLE_COLUMNS,
    BundleError,
    RunKind,
    RunManifest,
    Tier,
)

DEFAULT_OUT = Path("data/gold/dashboard_bundles")

# Columns a source may lack; every other declared column is required.
OPTIONAL_COLUMNS = {"seats": {"incumbent_party", "litigation_risk", "boundary_confidence"}}

CORRELATION_CAVEAT = (
    "The national/regional/state error split is asserted, not estimated; the seat range is "
    "sensitive to it (PROJECT_CONTEXT.md §16)."
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _source_key(path: Path) -> str:
    """Repo-relative where possible, so a manifest never records a home-directory path."""
    try:
        return str(path.resolve().relative_to(Path.cwd().resolve()))
    except ValueError:
        return path.name


def _sources(*paths: Path) -> dict[str, str]:
    return {_source_key(p): sha256_file(p) for p in paths if p.exists()}


def _git_commit(path: Path) -> str | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(path if path.is_dir() else path.parent), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return out.stdout.strip() or None


def _select_columns(name: str, df: pd.DataFrame) -> pd.DataFrame:
    declared = TABLE_COLUMNS[name]
    optional = OPTIONAL_COLUMNS.get(name, set())
    missing = [c for c in declared if c not in df.columns and c not in optional]
    if missing:
        raise BundleError(f"table {name!r} is missing required columns {missing}")
    out = df.reindex(columns=list(declared))
    return out.reset_index(drop=True)


def write_bundle(
    out_root: Path,
    manifest: RunManifest,
    tables: Mapping[str, pd.DataFrame] | None = None,
    documents: Mapping[str, Any] | None = None,
    *,
    replace: bool = False,
) -> Path:
    """Write one bundle atomically. Only the declared columns of each table are kept."""
    tables = dict(tables or {})
    documents = dict(documents or {})
    if set(tables) != set(manifest.tables):
        raise BundleError(f"tables {sorted(tables)} != manifest {sorted(manifest.tables)}")
    if set(documents) != set(manifest.documents):
        raise BundleError(f"documents {sorted(documents)} != manifest {sorted(manifest.documents)}")

    target = out_root / manifest.tier.value / manifest.run_id
    if target.exists() and not replace:
        raise BundleError(f"{target} exists; bundles are immutable (pass --replace to rebuild)")
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{manifest.run_id}-", dir=target.parent))
    try:
        for name, df in tables.items():
            _select_columns(name, df).to_parquet(staging / f"{name}.parquet", index=False)
        for name, doc in documents.items():
            (staging / f"{name}.json").write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
        (staging / MANIFEST_NAME).write_text(manifest.to_json())
        if target.exists():
            shutil.rmtree(target)
        staging.rename(target)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return target


# --- projections ------------------------------------------------------------------------


def _band_document(
    band_results: Sequence[Mapping[str, Any]],
    conclusions: Sequence[str],
    national_environment: Mapping[str, Any],
    **extra: Any,
) -> dict[str, Any]:
    if not band_results:
        raise BundleError("a projection bundle needs at least one band assumption")
    ne_keys = ("estimator", "status", "identified", "band", "assumptions", "caveats", "provenance")
    return {
        "band_results": list(band_results),
        "conclusions": list(conclusions),
        "national_environment": {k: national_environment.get(k) for k in ne_keys},
        **extra,
    }


def _coverage_sentence(house_coverage: Mapping[str, Any] | None) -> str:
    by_source = (house_coverage or {}).get("seats_by_source") or {}
    if not by_source:
        return ""
    parts = [
        f"{by_source.get('model', 0)} on unchanged boundaries",
        f"{by_source.get('model_transferred', 0)} with a transferred prior",
        f"{by_source.get('fallback_state_lean', 0)} on a state-lean fallback (least informed)",
    ]
    return " House seats: " + ", ".join(parts) + "."


def export_refresh(
    refresh_dir: Path,
    out_root: Path = DEFAULT_OUT,
    *,
    kind: RunKind = RunKind.REFRESH,
    run_id: str | None = None,
    replace: bool = False,
) -> Path:
    seats_path = refresh_dir / "projection_seats.csv"
    band_paths = sorted(refresh_dir.glob("national_environment_*.json"))
    if len(band_paths) != 1:
        raise BundleError(f"{refresh_dir}: expected one national_environment_*.json, got {band_paths}")
    band_path = band_paths[0]
    summary_path = refresh_dir / "refresh_summary.json"

    ne = json.loads(band_path.read_text())
    refresh_summary = json.loads(summary_path.read_text()) if summary_path.exists() else {}
    as_of = refresh_summary.get("as_of") or ne["generated_on"]
    sources = _sources(seats_path, band_path, summary_path)

    doc = _band_document(
        ne["band_results"],
        ne.get("conclusions", []),
        ne["national_environment"],
        correlation_parameters=ne.get("correlation_parameters"),
        house_coverage=ne.get("house_coverage"),
        senate_coverage=ne.get("senate_coverage"),
    )
    caveats = (*ne["national_environment"].get("caveats", []), CORRELATION_CAVEAT)
    manifest = RunManifest(
        run_id=run_id or refresh_dir.name,
        kind=kind,
        tier=Tier.VAULT,
        title=f"Internal refresh as of {as_of}",
        as_of=as_of,
        summary=" ".join(doc["conclusions"]) + _coverage_sentence(ne.get("house_coverage")),
        tables=("seats",),
        documents=("band",),
        offices=("us_house", "us_senate"),
        caveats=caveats,
        sources=sources,
        source_git_commit=refresh_summary.get("git_commit"),
        exporter_git_commit=_git_commit(Path.cwd()),
        exported_on=dt.date.today().isoformat(),
    )
    seats = pd.read_csv(seats_path)
    return write_bundle(out_root, manifest, {"seats": seats}, {"band": doc}, replace=replace)


def export_preregistration(
    prereg_json: Path,
    out_root: Path = DEFAULT_OUT,
    *,
    seats_csv: Path | None = None,
    replace: bool = False,
) -> Path:
    seats_path = seats_csv or prereg_json.with_name(prereg_json.stem + "_seats.csv")
    reg = json.loads(prereg_json.read_text())
    doc = _band_document(
        reg["predictions"]["band"],
        reg.get("conclusions", []),
        reg["national_environment"],
        house_coverage=(reg.get("coverage") or {}).get("house"),
        seal={
            "status": reg.get("status"),
            "what_this_is": reg.get("what_this_is"),
            "registered_on": reg.get("registered_on"),
            "election_date": reg.get("election_date"),
            "evaluation_plan": reg.get("evaluation_plan"),
            "predictions_sha256": reg.get("predictions_sha256"),
            "data_snapshots": reg.get("data_snapshots"),
        },
    )
    manifest = RunManifest(
        run_id=prereg_json.stem,
        kind=RunKind.PREREGISTRATION,
        tier=Tier.VAULT,
        title=f"Pre-registered prediction, sealed {reg['registered_on']}",
        as_of=reg["registered_on"],
        summary=" ".join(doc["conclusions"]) + _coverage_sentence(doc["house_coverage"]),
        tables=("seats",),
        documents=("band",),
        offices=("us_house", "us_senate"),
        caveats=(*reg.get("declared_defects", []), CORRELATION_CAVEAT),
        sources=_sources(prereg_json, seats_path),
        source_git_commit=reg.get("git_commit_at_registration"),
        exporter_git_commit=_git_commit(Path.cwd()),
        exported_on=dt.date.today().isoformat(),
    )
    seats = pd.read_csv(seats_path)
    return write_bundle(out_root, manifest, {"seats": seats}, {"band": doc}, replace=replace)


# --- diagnostics ------------------------------------------------------------------------

_BACKTEST_OFFICES = {
    "president": ("presidential", "demographics_eval", "demographics_backtest"),
    "us_house": ("house", "evaluation", "backtest"),
    "us_senate": ("senate", "evaluation", "backtest"),
}


def export_backtest(
    p1_json: Path,
    out_root: Path = DEFAULT_OUT,
    *,
    as_of: str | None = None,
    replace: bool = False,
) -> Path:
    p1 = json.loads(p1_json.read_text())
    as_of = as_of or dt.date.fromtimestamp(p1_json.stat().st_mtime).isoformat()
    offices: dict[str, Any] = {}
    for office, (key, eval_key, bt_key) in _BACKTEST_OFFICES.items():
        ev, bt = p1[key][eval_key], p1[key][bt_key]
        offices[office] = {
            "n": ev["n"],
            "mae_vote_share": ev["mae_vote_share"],
            "naive_persistence_mae": bt["naive_persistence_mae"],
            "winner_accuracy": bt["winner_accuracy"],
            "brier": ev["brier"],
            "log_score": ev["log_score"],
            "ece": ev["ece"],
            "coverage_90": ev["coverage_90"],
            "coverage_95": ev["coverage_95"],
            "calibration_curve": ev["calibration_curve"],
        }
    manifest = RunManifest(
        run_id=f"backtest_{as_of}",
        kind=RunKind.BACKTEST,
        tier=Tier.VAULT,
        title=f"Leave-one-cycle-out backtest ({as_of})",
        as_of=as_of,
        summary=(
            "Fundamentals baselines scored on held-out cycles of certified returns. Each office "
            "is compared with naive persistence; win probabilities are scored by Brier, log "
            "score, calibration error and interval coverage."
        ),
        documents=("diagnostics",),
        offices=tuple(offices),
        caveats=(
            "Historical backtest only: it measures held-out past cycles, not 2026.",
            "Quarantined races are excluded; see the quarantine sensitivity test.",
        ),
        sources=_sources(p1_json),
        exporter_git_commit=_git_commit(Path.cwd()),
        exported_on=dt.date.today().isoformat(),
    )
    doc = {"offices": offices, "quarantine_sensitivity": p1.get("quarantine_sensitivity")}
    return write_bundle(out_root, manifest, documents={"diagnostics": doc}, replace=replace)


# --- historical results -----------------------------------------------------------------


def export_history(race_results: Path, out_root: Path = DEFAULT_OUT, *, replace: bool = False) -> Path:
    df = pd.read_parquet(race_results)
    df["race_type"] = df["race_id"].str.rsplit("_", n=1).str[-1]
    snapshot = str(df["snapshot_date"].max())
    cycles = f"{int(df['cycle'].min())}–{int(df['cycle'].max())}"
    manifest = RunManifest(
        run_id=f"certified_results_{snapshot}",
        kind=RunKind.HISTORICAL,
        tier=Tier.PUBLIC,
        title=f"Certified results {cycles}",
        as_of=snapshot,
        summary=(
            f"Certified presidential, Senate and House returns, {cycles}, as standardised by "
            "MIT Election Data and Science Lab. Shares are two-party Democratic vote share."
        ),
        tables=("results",),
        offices=tuple(sorted(df["office"].unique())),
        caveats=(
            "Uncontested races are shown as uncontested, never as a 100–0 share.",
            "Third-party votes are excluded from the two-party share.",
        ),
        sources=_sources(race_results),
        exporter_git_commit=_git_commit(Path.cwd()),
        exported_on=dt.date.today().isoformat(),
    )
    return write_bundle(out_root, manifest, {"results": df}, replace=replace)


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="ep-export-dashboard", description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help="bundle root")
    ap.add_argument("--replace", action="store_true", help="rebuild an existing bundle")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("refresh", help="a reports/refresh_<date>/ directory")
    p.add_argument("path", type=Path)
    p.add_argument("--kind", choices=[RunKind.REFRESH.value, RunKind.SCENARIO.value], default="refresh")
    p.add_argument("--run-id")
    p = sub.add_parser("preregistration", help="a reports/preregistration_<date>.json seal")
    p.add_argument("path", type=Path)
    p = sub.add_parser("backtest", help="reports/p1_results.json")
    p.add_argument("path", type=Path)
    p.add_argument("--as-of", help="date the backtest was generated (default: file mtime)")
    p = sub.add_parser("history", help="data/gold/race_results.parquet")
    p.add_argument("path", type=Path)
    args = ap.parse_args(argv)

    try:
        if args.cmd == "refresh":
            out = export_refresh(
                args.path, args.out, kind=RunKind(args.kind), run_id=args.run_id, replace=args.replace
            )
        elif args.cmd == "preregistration":
            out = export_preregistration(args.path, args.out, replace=args.replace)
        elif args.cmd == "backtest":
            out = export_backtest(args.path, args.out, as_of=args.as_of, replace=args.replace)
        else:
            out = export_history(args.path, args.out, replace=args.replace)
    except BundleError as exc:
        print(f"ep-export-dashboard: {exc}", file=sys.stderr)
        return 1
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

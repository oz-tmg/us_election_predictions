"""Capture and assemble 2026 results for scoring the sealed forecast.

Two subcommands, because capture and use are different acts with different urgency:

    ep-results-2026 capture --snapshot <csv> [--observed-on YYYY-MM-DD]
    ep-results-2026 actual  [--as-of YYYY-MM-DD]

``capture`` appends a dated, validated, never-overwritten snapshot. It is the urgent one:
certification status is observable only while it is happening, and `data/results_2026.py`
explains why no later download recovers it.

``actual`` collapses the snapshots into the frame
``evaluation/score_preregistration`` consumes, and reports how many seats are not yet
certified so the ``as_of`` rule stays visible rather than implied.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from .data import results_2026, results_sources
from .data.manifest import sha256_file
from .geography import reference as ref


def _state_fips_map() -> dict[str, str]:
    """Postal -> FIPS, from the canonical geography table rather than a second copy of it."""
    return {postal: ref.by_postal(postal).fips for postal in ref.STATES}


def capture(args: argparse.Namespace) -> int:
    frame = pd.read_csv(args.snapshot, dtype=str)
    evidence = args.source_evidence or []
    production = (
        args.directory or results_2026.SNAPSHOT_DIR
    ).resolve() == results_2026.SNAPSHOT_DIR.resolve()
    if production and not evidence:
        raise ValueError("production capture requires --source-evidence from preserved raw releases")
    if evidence:
        results_sources.verify_evidence(frame, evidence)
    path = results_2026.write_snapshot(frame, observed_on=args.observed_on, directory=args.directory)
    manifest = {"compiled_sha256": sha256_file(path), "source_evidence": [str(p.resolve()) for p in evidence]}
    with path.with_suffix(".manifest.json").open("x") as handle:
        json.dump(manifest, handle, indent=2)
    stored = pd.read_csv(path)
    certified = stored["certified"].astype(str).str.upper().isin({"TRUE", "T", "Y", "YES", "1"})
    print(
        f"captured {len(stored)} seats observed {path.stem.split('=', 1)[1]}\n"
        f"  certified so far: {int(certified.sum())} of {len(stored)}\n"
        f"  -> {path}"
    )
    return 0


def actual(args: argparse.Namespace) -> int:
    snapshots = results_2026.read_snapshots(args.directory)
    if not len(snapshots):
        print(
            f"no snapshots in {args.directory or results_2026.SNAPSHOT_DIR}.\n"
            "Nothing can be scored until results are captured, and certification status "
            "cannot be recovered after the fact — capture early and often."
        )
        return 1

    as_of = pd.Timestamp(args.as_of) if args.as_of else pd.Timestamp(datetime.now(UTC).date())
    ledger = results_2026.certification_ledger(snapshots, as_of=str(as_of.date()))
    frame = results_2026.to_actual(ledger, state_fips=_state_fips_map())

    certified_on = pd.to_datetime(frame["certified_on"], errors="coerce")
    scoreable = certified_on.notna() & (certified_on <= as_of)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(args.out, index=False)
    used_snapshots = sorted(
        snapshots.loc[pd.to_datetime(snapshots["observed_on"]) <= as_of, "observed_on"].unique().tolist()
    )
    summary = {
        "as_of": str(as_of.date()),
        "seats": int(len(frame)),
        "certified_by_as_of": int(scoreable.sum()),
        "not_yet_certified": int((~scoreable).sum()),
        "snapshots": used_snapshots,
        "missing_states": sorted(set(ref.STATES) - {"DC", "PR"} - set(frame.state_po)),
        "coverage_is_complete": False,
    }
    (args.out.with_suffix(".summary.json")).write_text(json.dumps(summary, indent=2))
    print(
        f"as of {summary['as_of']}: {summary['certified_by_as_of']} of {summary['seats']} seats "
        f"certified, {summary['not_yet_certified']} unscored\n"
        f"  built from {len(used_snapshots)} snapshot(s)\n  -> {args.out}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="command", required=True)

    cap = sub.add_parser("capture", help="append a dated snapshot of compiled results")
    cap.add_argument("--snapshot", type=Path, required=True, help="compiled CSV")
    cap.add_argument("--observed-on", default=None, help="defaults to today")
    cap.add_argument("--directory", type=Path, default=None)
    cap.add_argument("--source-evidence", nargs="+", type=Path, help="preserved release .source.json files")
    cap.set_defaults(func=capture)

    source = sub.add_parser("preserve-source", help="preserve a manually reviewed public aggregate release")
    source.add_argument("--file", type=Path, required=True)
    source.add_argument("--state", required=True)
    source.add_argument("--url", required=True)
    source.add_argument("--retrieved-at", required=True, help="actual ISO retrieval timestamp with timezone")
    source.add_argument("--aggregate-only", action="store_true", required=True)
    source.set_defaults(
        func=lambda a: (
            print(
                results_sources.preserve_source(a.file, state=a.state, url=a.url, retrieved_at=a.retrieved_at)
            )
            or 0
        )
    )

    probe = sub.add_parser("check-sources", help="probe 50-state landing pages without collecting results")
    probe.add_argument("--out", type=Path, required=True)
    probe.set_defaults(func=lambda a: results_sources.probe_catalog(output=a.out) and 0)

    act = sub.add_parser("actual", help="assemble the frame the scorer consumes")
    act.add_argument("--as-of", default=None, help="defaults to today")
    act.add_argument("--directory", type=Path, default=None)
    act.add_argument("--out", type=Path, default=Path("data/gold/actual_us_house_2026.csv"))
    act.set_defaults(func=actual)

    args = ap.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())

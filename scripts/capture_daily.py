#!/usr/bin/env python
"""One command for the day's results capture: fetch, preserve, extract, capture once.

    python scripts/capture_daily.py --dry-run          # everything except the ledger write
    python scripts/capture_daily.py                     # today's UTC observation
    python scripts/capture_daily.py --certified NC=https://www.ncsbe.gov/...certification

For every state with a registered fetcher (``data/state_fetchers.py``: honest download
and a parser proven against 2024 certified results) this downloads the official release,
preserves it with its retrieval time and checksum (``results_sources.preserve_source``),
extracts every U.S. House and Senate race, checks the state's races against the frozen
universe, and compiles ONE snapshot for the UTC day. The ledger takes one observation per
UTC day, so all states go into the same capture; the run refuses before fetching if the
day's slot is already taken.

Certification is never inferred. A state is marked certified only when the operator
passes ``--certified STATE=<URL of the certification evidence>``, and never when the
release labels itself unofficial. The run writes ``reports/captures/capture_<date>.json``,
the committed index of what the git-ignored ledger now holds. A state that fails (blocked,
changed layout, incomplete) is reported and left out; the others are still captured.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, "src")

from election_prediction import build_results_2026  # noqa: E402
from election_prediction.data import (  # noqa: E402
    results_2026,
    results_sources,
    state_fetchers,
    state_parsers,  # noqa: E402,F401  (registers parsers)
)
from election_prediction.data import state_extraction as se  # noqa: E402
from election_prediction.data.manifest import sha256_file  # noqa: E402

UNIVERSE = Path("reports/refresh_2026-10-29/projection_seats.csv")
REPORT_DIR = Path("reports/captures")


def expected_races(universe: Path, state: str) -> set[tuple[str, int | None]]:
    seats = pd.read_csv(universe)
    seats = seats[seats["state_po"] == state].drop_duplicates(["office", "geography_id"])
    return {
        (o, None if o == "us_senate" else int(d))
        for o, d in zip(seats["office"], seats["district_num"], strict=True)
    }


def check_coverage(extracted: pd.DataFrame, expected: set[tuple[str, int | None]], state: str) -> None:
    got = {
        (o, None if o == "us_senate" else int(d))
        for o, d in zip(extracted["office"], extracted["district_num"], strict=True)
    }
    if not expected:
        raise ValueError(f"{state}: no races in the frozen universe")
    missing, extra = expected - got, got - expected
    if missing or extra:
        raise ValueError(
            f"{state}: coverage mismatch, missing {sorted(missing, key=str)}, extra {sorted(extra, key=str)}"
        )


def parse_certified(values: list[str]) -> dict[str, str]:
    out = {}
    for value in values:
        state, sep, url = value.partition("=")
        if not sep or not url.startswith("https://") or len(state) != 2:
            raise SystemExit(f"--certified expects STATE=https://evidence-url, got {value!r}")
        out[state.upper()] = url
    return out


def run(
    *,
    states: list[str],
    certified: dict[str, str],
    dry_run: bool,
    ledger_dir: Path | None,
    evidence_dir: Path | None,
    report_dir: Path,
    universe: Path,
    observed_on: str | None = None,
) -> dict:
    observed_on = observed_on or datetime.now(UTC).date().isoformat()
    ledger = ledger_dir or results_2026.SNAPSHOT_DIR
    slot = ledger / f"snapshot={observed_on}.csv"
    if slot.exists() and not dry_run:
        raise SystemExit(f"{slot} exists: today's UTC slot is taken (one observation per UTC day)")
    unknown = sorted(set(states) - set(state_fetchers.FETCHERS))
    if unknown:
        raise SystemExit(f"no fetcher for {unknown}; capture those states manually (runbook)")

    work = Path(tempfile.mkdtemp(prefix="capture-"))
    if dry_run:
        ledger = work / "ledger"
        evidence_dir = work / "evidence"
    frames, evidence, report_states, failures = [], [], {}, {}
    for state in states:
        try:
            release = state_fetchers.FETCHERS[state](work)
            if state in certified and release.labelled == "unofficial":
                raise ValueError(f"{state}: release labels itself unofficial; refusing --certified")
            manifest = results_sources.preserve_source(
                release.path,
                state=state,
                url=release.source_url,
                retrieved_at=release.retrieved_at,
                **({"directory": evidence_dir} if evidence_dir else {}),
            )
            record = json.loads(manifest.read_text())
            extracted = se.extract(state, [Path(record["raw_path"])])
            check_coverage(extracted, expected_races(universe, state), state)
            frames.append(
                se.to_snapshot(
                    extracted,
                    source_url=record["source_url"],
                    retrieved_on=record["retrieved_on"],
                    certified=state in certified,
                )
            )
            evidence.append(manifest)
            report_states[state] = {
                "seats": int(len(extracted)),
                "certified": state in certified,
                "certification_evidence": certified.get(state),
                "labelled": release.labelled,
                "source_url": release.source_url,
                "retrieved_at": release.retrieved_at,
                "sha256": record["checksum_sha256"],
            }
        except Exception as exc:  # noqa: BLE001 - one state's failure must not lose the others
            failures[state] = f"{type(exc).__name__}: {exc}"
    if not frames:
        raise SystemExit(f"nothing captured; failures: {failures}")

    compiled = work / f"compiled_{observed_on}.csv"
    pd.concat(frames, ignore_index=True).to_csv(compiled, index=False)
    args = argparse.Namespace(
        snapshot=compiled, observed_on=observed_on, directory=ledger, source_evidence=evidence
    )
    build_results_2026.capture(args)
    report = {
        "observed_on": observed_on,
        "dry_run": dry_run,
        "seats": int(sum(s["seats"] for s in report_states.values())),
        "certified_seats": int(sum(s["seats"] for s in report_states.values() if s["certified"])),
        "states": report_states,
        "failures": failures,
        "snapshot_sha256": sha256_file(ledger / f"snapshot={observed_on}.csv"),
        "universe": str(universe),
    }
    if not dry_run:
        report_dir.mkdir(parents=True, exist_ok=True)
        (report_dir / f"capture_{observed_on}.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--states", nargs="+", default=sorted(state_fetchers.FETCHERS))
    ap.add_argument("--certified", action="append", default=[], metavar="STATE=URL")
    ap.add_argument("--dry-run", action="store_true", help="fetch and validate; write nothing to the ledger")
    ap.add_argument("--universe", type=Path, default=UNIVERSE)
    args = ap.parse_args(argv)
    report = run(
        states=[s.upper() for s in args.states],
        certified=parse_certified(args.certified),
        dry_run=args.dry_run,
        ledger_dir=None,
        evidence_dir=None,
        report_dir=REPORT_DIR,
        universe=args.universe,
    )
    print(json.dumps({k: v for k, v in report.items() if k != "states"}, indent=2))
    for state, info in report["states"].items():
        print(f"  {state}: {info['seats']} seats, certified={info['certified']}, labelled {info['labelled']}")
    return 1 if report["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

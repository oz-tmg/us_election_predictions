#!/usr/bin/env python
"""One command for the day's results capture: fetch, preserve, extract, capture once.

    python scripts/capture_daily.py --dry-run          # everything except the ledger write
    python scripts/capture_daily.py                     # today's UTC observation
    python scripts/capture_daily.py --certified NC=https://www.ncsbe.gov/...certification

For every state with a registered fetcher (``data/state_fetchers.py`` and
``data/state_layouts/``: an honest download and a parser that is either proven against
2024 certified results or, where the 2026 layout is new, cross-checked against the
state's own summary; the report names which) this downloads the official release,
preserves it with its retrieval time and checksum (``results_sources.preserve_source``),
extracts every U.S. House and Senate race, checks the state's races against the frozen
universe, and compiles ONE snapshot for the UTC day. The ledger takes one observation per
UTC day, so all states go into the same capture; the run refuses before fetching if the
day's slot is already taken.

Certification is never inferred. A state is marked certified only when the operator
passes ``--certified STATE=<URL of the certification evidence>``, and never when the
release labels itself unofficial. An accepted attestation is written to
``data/reference/certifications_2026.csv`` and applied to every later capture, because
the ledger reads a certified seat that later appears uncertified as a revocation. To
revoke, remove the state's row from that file and say why in the commit.

The run writes ``reports/captures/capture_<date>.json``,
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
    state_layouts,  # noqa: E402,F401  (registers the changed-layout states)
    state_parsers,  # noqa: E402,F401  (registers parsers)
)
from election_prediction.data import state_extraction as se  # noqa: E402
from election_prediction.data.manifest import sha256_file  # noqa: E402

UNIVERSE = Path("reports/refresh_2026-10-29/projection_seats.csv")
REPORT_DIR = Path("reports/captures")
ATTESTATIONS = Path("data/reference/certifications_2026.csv")
ATTESTATION_COLUMNS = ["state_po", "certification_evidence", "first_captured_on"]


def load_attestations(path: Path) -> pd.DataFrame:
    """Certifications the operator has already attested, one row per state."""
    if not path.is_file():
        return pd.DataFrame(columns=ATTESTATION_COLUMNS)
    frame = pd.read_csv(path, dtype=str).fillna("")
    if list(frame.columns) != ATTESTATION_COLUMNS or frame.state_po.duplicated().any():
        raise SystemExit(f"{path}: expected columns {ATTESTATION_COLUMNS}, one row per state")
    if not frame.certification_evidence.str.startswith("https://").all():
        raise SystemExit(f"{path}: every attestation needs an https evidence URL")
    return frame


def record_attestations(path: Path, new: dict[str, str], observed_on: str) -> None:
    """Append newly captured attestations; an existing row is never rewritten."""
    known = load_attestations(path)
    rows = [
        {"state_po": state, "certification_evidence": url, "first_captured_on": observed_on}
        for state, url in sorted(new.items())
        if state not in set(known.state_po)
    ]
    if rows:
        path.parent.mkdir(parents=True, exist_ok=True)
        pd.concat([known, pd.DataFrame(rows)], ignore_index=True).to_csv(path, index=False)


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
    attestations: Path | None = None,
) -> dict:
    observed_on = observed_on or datetime.now(UTC).date().isoformat()
    ledger = ledger_dir or results_2026.SNAPSHOT_DIR
    # Earlier attestations carry forward; a new --certified for the same state does not
    # replace the evidence already on record.
    carried = (
        dict(zip(*(load_attestations(attestations)[c] for c in ATTESTATION_COLUMNS[:2]), strict=True))
        if attestations
        else {}
    )
    certified = {**certified, **carried}
    slot = ledger / f"snapshot={observed_on}.csv"
    if slot.exists() and not dry_run:
        raise SystemExit(f"{slot} exists: today's UTC slot is taken (one observation per UTC day)")
    trust = results_sources.load_catalog().set_index("state_po")["extraction_status"]
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
            if trust.get(state, "manual_review_pending") == "manual_review_pending":
                raise ValueError(f"{state}: parser has no recorded test or cross-check")
            fetched = state_fetchers.FETCHERS[state](work)
            releases = fetched if isinstance(fetched, list) else [fetched]
            labels = {r.labelled for r in releases}
            if state in certified and "unofficial" in labels:
                raise ValueError(f"{state}: release labels itself unofficial; refusing --certified")
            # Each release is preserved and extracted on its own, so every row names the
            # file it came from; a later release (e.g. a recount) replaces the same race.
            parts: list[pd.DataFrame] = []
            records = []
            support: list[Path] = []
            preserved = []
            for release in releases:
                manifest = results_sources.preserve_source(
                    release.path,
                    state=state,
                    url=release.source_url,
                    retrieved_at=release.retrieved_at,
                    **({"directory": evidence_dir} if evidence_dir else {}),
                )
                record = json.loads(manifest.read_text())
                records.append((manifest, record))
                if release.role == "support":
                    support.append(Path(record["raw_path"]))
                else:
                    preserved.append(record)
            for record in preserved:
                part = se.extract(state, [Path(record["raw_path"]), *support])
                part = part.assign(_url=record["source_url"], _retrieved_on=record["retrieved_on"])
                keys = ["office", "district_num"]
                parts = [
                    p.merge(part[keys], on=keys, how="left", indicator=True)
                    .query("_merge == 'left_only'")
                    .drop(columns="_merge")
                    for p in parts
                ]
                parts.append(part)
            extracted = pd.concat(parts, ignore_index=True)
            check_coverage(extracted, expected_races(universe, state), state)
            for (url, day), group in extracted.groupby(["_url", "_retrieved_on"]):
                frames.append(
                    se.to_snapshot(
                        group.drop(columns=["_url", "_retrieved_on"]),
                        source_url=url,
                        retrieved_on=day,
                        certified=state in certified,
                    )
                )
            evidence.extend(m for m, _ in records)
            report_states[state] = {
                "seats": int(len(extracted)),
                "parser_status": trust[state],
                "certified": state in certified,
                "certification_evidence": certified.get(state),
                "certification_carried_forward": state in carried,
                "labelled": "unofficial"
                if "unofficial" in labels
                else (labels.pop() if len(labels) == 1 else "mixed"),
                "releases": [
                    {
                        "source_url": r["source_url"],
                        "retrieved_at": r["retrieved_at"],
                        "sha256": r["checksum_sha256"],
                    }
                    for _, r in records
                ],
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
        if attestations:
            captured = {s: certified[s] for s, info in report_states.items() if info["certified"]}
            record_attestations(attestations, captured, observed_on)
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
        attestations=ATTESTATIONS,
    )
    print(json.dumps({k: v for k, v in report.items() if k != "states"}, indent=2))
    for state, info in report["states"].items():
        print(f"  {state}: {info['seats']} seats, certified={info['certified']}, labelled {info['labelled']}")
    return 1 if report["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

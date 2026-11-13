#!/usr/bin/env python
"""Interim scorecard: every frozen run, scored on the seats certified so far.

    python scripts/interim_scorecard.py --as-of 2026-11-20

Scores each run in ``reports/comparison_set_2026-11-03.json`` (the sealed registration,
both refreshes and the scenario) with the registered scorer
(``evaluation.score_preregistration.score``) on the same as-of ledger. Nothing is
selected: every assumption of every run is reported, with its denominators.

- Only seats the ledger observed as **certified** (and resolved) by ``--as-of`` are
  scored. Unofficial counts are never scored.
- The seal is verified by its own digest. The other runs are not sealed registrations:
  their files must match the SHA-256 recorded in the comparison set, or the run stops.
- Chamber error and the registered failure condition stay ``not_evaluable`` until every
  registered House seat has a scoreable outcome (the scorer enforces this).
- A scorecard is never overwritten; a later as-of date is a new file.

Writes ``reports/scorecards/scorecard_asof_<date>.json`` and ``.md``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, "src")

from election_prediction.build_results_2026 import _state_fips_map  # noqa: E402
from election_prediction.data import results_2026  # noqa: E402
from election_prediction.data.manifest import sha256_file  # noqa: E402
from election_prediction.evaluation import score_preregistration as sp  # noqa: E402
from election_prediction.reporting import preregistration as prereg  # noqa: E402

COMPARISON_SET = Path("reports/comparison_set_2026-11-03.json")
OUT_DIR = Path("reports/scorecards")


class FrozenRunChanged(ValueError):
    """A frozen comparison run no longer matches its recorded checksum."""


def load_run(run: dict) -> tuple[dict, str]:
    """A registration-shaped dict for one comparison-set run, and how it was verified."""
    for name, digest in run["sha256"].items():
        if sha256_file(Path(name)) != digest:
            raise FrozenRunChanged(f"{name} does not match the comparison set; refusing to score it")
    files = [Path(f) for f in run["files"]]
    if "predictions_sha256" in run:
        registration = sp.load_registration(files[0])
        sp.verify_seal(registration)
        return registration, "sealed registration: digest verified"
    seats = pd.read_csv(next(f for f in files if f.suffix == ".csv"))
    band = json.loads(next(f for f in files if f.suffix == ".json").read_text())
    predictions = {"band": band["band_results"], "seats": seats.to_dict(orient="records")}
    registration = {
        "election_date": "2026-11-03",
        "registered_on": band.get("generated_on"),
        "predictions": predictions,
        # Not a seal: the digest only satisfies the scorer's self-check. The guarantee
        # for this run is the file checksum verified above.
        "predictions_sha256": prereg._digest(predictions),
        "evaluation_plan": {},
        "declared_defects": [],
    }
    return registration, "frozen run: file SHA-256 verified against the comparison set"


def actual_frame(ledger_dir: Path | None, as_of: str) -> tuple[pd.DataFrame, dict]:
    snapshots = results_2026.read_snapshots(ledger_dir)
    if not len(snapshots):
        raise SystemExit("no snapshots in the ledger; nothing to score")
    ledger = results_2026.certification_ledger(snapshots, as_of=as_of)
    frame = results_2026.to_actual(ledger, state_fips=_state_fips_map())
    certified = pd.to_datetime(frame["certified_on"], errors="coerce")
    scoreable = certified.notna() & (certified <= pd.Timestamp(as_of))
    observed = pd.to_datetime(snapshots["observed_on"]) <= pd.Timestamp(as_of)
    coverage = {
        "seats_observed": int(len(frame)),
        "seats_certified_by_as_of": int(scoreable.sum()),
        "states_observed": sorted(frame["state_po"].unique()),
        "states_with_certified_seats": sorted(frame.loc[scoreable, "state_po"].unique()),
        "snapshots_used": sorted(snapshots.loc[observed, "observed_on"].astype(str).unique().tolist()),
    }
    return frame, coverage


def build(*, as_of: str, ledger_dir: Path | None, comparison_set: Path = COMPARISON_SET) -> dict:
    frozen = json.loads(comparison_set.read_text())
    actual, coverage = actual_frame(ledger_dir, as_of)
    runs = {}
    for run in frozen["runs"]:
        registration, verified = load_run(run)
        result = sp.score(sp.ScoringInputs(registration, actual, as_of, void_geographies={}))
        runs[run["run_id"]] = {"role": run["role"], "verified": verified, **result}
    return {
        "as_of": as_of,
        "interim": True,
        "what_this_is": (
            "Scores on seats certified by the as-of date only. Not a verdict on any run: the "
            "certified subset is not a random sample of seats, and chamber-level error and the "
            "registered failure condition are not evaluable until every House seat is scoreable."
        ),
        "void_geographies": "none asserted (no map changed after sealing has been recorded)",
        "coverage": coverage,
        "scoring_rule": frozen["scoring"],
        "runs": runs,
    }


def to_markdown(card: dict) -> str:
    cov = card["coverage"]
    lines = [
        f"# Interim scorecard, as of {card['as_of']}",
        "",
        card["what_this_is"],
        "",
        f"Seats observed: {cov['seats_observed']} in {len(cov['states_observed'])} states. "
        f"**Certified and scoreable: {cov['seats_certified_by_as_of']}** "
        f"({', '.join(cov['states_with_certified_seats']) or 'none'}). "
        f"Ledger snapshots used: {len(cov['snapshots_used'])}.",
        "",
    ]
    for run_id, run in card["runs"].items():
        lines += [f"## {run_id}", "", f"{run['role']}. {run['verified']}.", ""]
        if not run["results"]:
            lines += ["No certified seats to score yet.", ""]
            continue
        lines += [
            "| Assumption | Seats | MAE (share) | Brier | Log score | 90% coverage | Winner accuracy |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
        for assumption, entry in run["results"].items():
            m = entry["overall"]
            lines.append(
                f"| {assumption} | {m['n']} | {m['mae_vote_share']:.4f} | {m['brier']:.4f} | "
                f"{m['log_score']:.4f} | {m['coverage_90']:.3f} | {m['winner_accuracy']:.3f} |"
            )
        chamber = run["failure_condition"]["status"]
        lines += ["", f"Chamber-level failure condition: `{chamber}`.", ""]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--as-of", required=True, help="UTC date; only certifications observed by then count")
    ap.add_argument("--ledger-dir", type=Path, default=None, help="default: the production ledger")
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = ap.parse_args(argv)
    card = build(as_of=args.as_of, ledger_dir=args.ledger_dir)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    base = args.out_dir / f"scorecard_asof_{args.as_of}"
    for suffix, text in (
        (".json", json.dumps(card, indent=2, default=str) + "\n"),
        (".md", to_markdown(card)),
    ):
        with base.with_suffix(suffix).open("x") as handle:  # never overwrite a scorecard
            handle.write(text)
    print(to_markdown(card).split("##")[0])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

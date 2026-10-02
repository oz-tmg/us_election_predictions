"""Seal a forecast before the event, so the evaluation afterwards means something.

A backtest tells you how a model would have done on elections whose answers were already
in the training corpus' neighbourhood. It cannot tell you how the model does on an election
nobody has seen. The only way to buy that evidence is to write the prediction down first,
in a form nobody can quietly revise, and then score it with rules that were also fixed
first.

This module writes that artefact. Three design decisions make it worth more than a
timestamped guess:

**Every assumption in the band is registered, and all of them are scored.** The national
environment is unidentified (see ``models.baseline.national_environment``), so the
projection is a sweep over an assumed shrinkage factor rather than a point. Registering the
sweep and then, after the election, reporting whichever shrinkage turned out closest would
be the garden of forking paths with extra steps. So the evaluation plan below commits to
scoring **all five** and reporting all five, and separately scores the *band* as a single
falsifiable claim.

**The known defects are declared in advance.** A model's failures are only informative if
you said what you expected to go wrong before you knew. The ``declared_defects`` block
lists them — 173 seats on a crude fallback, a party crosswalk two seats short, renomination
assumed for everyone — so a post-election post-mortem cannot be a creative-writing exercise.

**A pre-declared failure condition.** If the realised seat count falls outside the 90%
interval under *every* assumption in the band, the model's uncertainty was too narrow. That
is written here, before the fact, rather than negotiated afterwards.

The payload carries a SHA-256 of its own prediction block. The commit that adds the file is
the timestamp; the hash is the tamper evidence.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import date
from pathlib import Path

import pandas as pd

SCHEMA_VERSION = "1.0"

SEAT_COLUMNS = [
    "assumption",
    "office",
    "geography_id",
    "state_po",
    "district_num",
    "mean_dem_share",
    "sigma",
    "dem_win_prob",
    "source",
    "boundary_confidence",
    "litigation_risk",
]

# Fixed before the event. Changing any of these after 2026-11-03 voids the exercise.
EVALUATION_PLAN = {
    "scored_on": (
        "2026-11-03 certified returns, once available from the states "
        "(not calls, not unofficial counts)"
    ),
    "unit": "congressional district (House), state (Senate)",
    "basis": "two-party Democratic vote share; uncontested races handled as in the backtest, never as 100-0",
    "every_assumption_is_scored": (
        "All five shrinkage assumptions are scored and all five reported. Selecting the "
        "best-performing one after the fact is forbidden and would void this registration."
    ),
    "per_seat_metrics": [
        "Brier score on dem_win_prob",
        "log score on dem_win_prob",
        "expected calibration error and a reliability curve over the same 10 bins as the backtest",
        "mean absolute error on mean_dem_share",
        "90% and 95% interval coverage from mean_dem_share +/- z * sigma",
    ],
    "chamber_metrics": [
        "absolute error on mean Democratic seat count",
        "whether the realised seat count fell inside the 90% simulation interval",
        "whether the band's directional claim held (House favoured Democratic at every assumption)",
    ],
    "comparators_fixed_in_advance": [
        "naive persistence: each seat repeats its own 2024 two-party share",
        "state-lean fallback applied to ALL seats, not just the 173 redrawn ones",
        "the backtest's own leave-one-cycle-out House MAE of 0.078694 as the in-sample reference",
    ],
    "failure_condition": (
        "If the realised Democratic seat count falls outside the 90% interval under every "
        "assumption in the band, the model's stated uncertainty was too narrow. This is a "
        "failure of the forecast, not of the band, and is to be reported as such."
    ),
    "split_evaluation_required": (
        "Per-seat metrics must be reported separately for the 262 seats projected from the "
        "model and the 173 projected from the state-lean fallback. A single pooled number "
        "would hide which half of the chamber the model actually knows anything about."
    ),
}


def _git_head() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=10, check=True
        )
        return out.stdout.strip()
    except (subprocess.SubprocessError, OSError):
        return None


def _digest(obj: object) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()


def build(
    *,
    election_date: str,
    band: pd.DataFrame,
    seats: pd.DataFrame,
    environment: dict,
    house_coverage: dict,
    senate_coverage: dict,
    conclusions: list[str],
    declared_defects: list[str],
    data_snapshots: dict,
) -> dict:
    """Assemble the sealed payload. Pure: writes nothing."""
    predictions = {
        "band": band.to_dict(orient="records"),
        "seats": seats[SEAT_COLUMNS].to_dict(orient="records"),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "registered_on": date.today().isoformat(),
        "election_date": election_date,
        "git_commit_at_registration": _git_head(),
        "status": "PRE-REGISTERED FORECAST -- NOT PUBLISHED AS A FORECAST",
        "what_this_is": (
            "A prediction sealed before the event so that the post-election evaluation is "
            "out-of-sample. It is not a published forecast and carries no editorial claim; "
            "see blog/posts/05-the-forecast-i-am-not-publishing.md."
        ),
        "national_environment": environment,
        "conclusions": conclusions,
        "declared_defects": declared_defects,
        "evaluation_plan": EVALUATION_PLAN,
        "coverage": {"house": house_coverage, "senate": senate_coverage},
        "data_snapshots": data_snapshots,
        "predictions": predictions,
        "predictions_sha256": _digest(predictions),
    }


def write(payload: dict, reports_dir: str | Path) -> tuple[Path, Path]:
    """Write the sealed JSON and a human-readable sibling. Refuses to overwrite."""
    reports = Path(reports_dir)
    stem = f"preregistration_{payload['election_date']}"
    json_path, md_path = reports / f"{stem}.json", reports / f"{stem}.md"
    for path in (json_path, md_path):
        if path.exists():
            raise FileExistsError(
                f"{path} already exists. A pre-registration is sealed by definition -- "
                "delete it deliberately and explain why in the commit, or write a new one "
                "under a different election_date."
            )
    json_path.write_text(json.dumps(payload, indent=2, default=str))
    md_path.write_text(render_markdown(payload))
    return json_path, md_path


def _md_table(df: pd.DataFrame) -> str:
    """Markdown table without pulling in tabulate (CLAUDE.md §7: keep the stack boring)."""
    cols = [str(c) for c in df.columns]
    rows = [[("" if pd.isna(v) else str(v)) for v in rec] for rec in df.to_numpy()]
    widths = [max(len(c), *(len(r[i]) for r in rows)) if rows else len(c) for i, c in enumerate(cols)]
    head = "| " + " | ".join(c.ljust(w) for c, w in zip(cols, widths, strict=True)) + " |"
    rule = "|" + "|".join("-" * (w + 2) for w in widths) + "|"
    body = ["| " + " | ".join(v.ljust(w) for v, w in zip(r, widths, strict=True)) + " |" for r in rows]
    return "\n".join([head, rule, *body])


def _counts_table(series: pd.Series, label: str) -> str:
    counts = series.value_counts()
    return _md_table(pd.DataFrame({label: counts.index.astype(str), "seats": counts.to_numpy()}))


def render_markdown(payload: dict) -> str:
    band = pd.DataFrame(payload["predictions"]["band"])
    seats = pd.DataFrame(payload["predictions"]["seats"])
    house = seats[seats["office"] == "us_house"]
    one = house[house["assumption"] == house["assumption"].iloc[0]]
    lines = [
        f"# Pre-registered 2026 projection — sealed {payload['registered_on']}",
        "",
        f"> **{payload['status']}**",
        f"> Election date: {payload['election_date']} · "
        f"commit `{(payload['git_commit_at_registration'] or 'unknown')[:12]}` · "
        f"predictions SHA-256 `{payload['predictions_sha256'][:16]}…`",
        "",
        payload["what_this_is"],
        "",
        "## The claim",
        "",
        "The national environment is **unidentified**, so this is a sweep over an assumed",
        "shrinkage factor, not a point forecast. Every row below is registered and every row",
        "will be scored. Picking the best one afterwards would void the exercise.",
        "",
        _md_table(band.drop(columns=["assumption"], errors="ignore")),
        "",
    ]
    lines += [f"- {c}" for c in payload["conclusions"]]
    lines += [
        "",
        "## What I expect to be wrong",
        "",
        "Declared before the event. A post-mortem that discovers these afterwards proves nothing.",
        "",
    ]
    lines += [f"{i}. {d}" for i, d in enumerate(payload["declared_defects"], 1)]
    lines += [
        "",
        "## Composition of the registered House forecast",
        "",
        _counts_table(one["source"], "prior source"),
        "",
        _counts_table(one["boundary_confidence"], "boundary confidence"),
        "",
        "## How this will be scored",
        "",
        f"**Scored on:** {payload['evaluation_plan']['scored_on']}",
        "",
        f"**Every assumption is scored.** {payload['evaluation_plan']['every_assumption_is_scored']}",
        "",
        "**Per-seat:** " + "; ".join(payload["evaluation_plan"]["per_seat_metrics"]) + ".",
        "",
        "**Chamber:** " + "; ".join(payload["evaluation_plan"]["chamber_metrics"]) + ".",
        "",
        "**Comparators, fixed now:**",
        "",
    ]
    lines += [f"- {c}" for c in payload["evaluation_plan"]["comparators_fixed_in_advance"]]
    lines += [
        "",
        f"**Split evaluation.** {payload['evaluation_plan']['split_evaluation_required']}",
        "",
        f"**Pre-declared failure condition.** {payload['evaluation_plan']['failure_condition']}",
        "",
        "## Provenance",
        "",
        "| Source | Snapshot |",
        "|---|---|",
    ]
    lines += [f"| {k} | {v} |" for k, v in payload["data_snapshots"].items()]
    lines += [
        "",
        f"Per-seat predictions: {len(seats):,} rows across "
        f"{seats['assumption'].nunique()} assumptions, in the JSON sibling and in "
        f"`preregistration_{payload['election_date']}_seats.csv`.",
        "",
        "---",
        "",
        "*Nonpartisan. This models probability and uncertainty, not a preferred outcome. "
        "Historical returns are certified; everything here is modelled and labelled as such.*",
    ]
    return "\n".join(lines) + "\n"

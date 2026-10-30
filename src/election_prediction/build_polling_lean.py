"""Reproduce a separate, never automatically promoted polling-lean experiment."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from .data import candidate_polls, polling_archive
from .data.manifest import sha256_file
from .evaluation.score_preregistration import load_registration, verify_seal
from .polling import lean
from .reporting.model_cards import ModelCard, render_model_card


def _markdown(report: dict) -> str:
    covered_2024 = {row["office"] for row in report.get("input_cycle_coverage", []) if row["cycle"] == 2024}
    coverage_note = (
        "- 2024 fixed-window coverage: "
        + "; ".join(
            f"{label} {'included' if office in covered_2024 else 'absent'}"
            for office, label in (("us_house", "House"), ("us_senate", "Senate"))
        )
        + "."
    )
    lines = [
        "# Polling-Lean Research",
        "",
        f"Review date: {report['review_date']}. Owner: Alex Oswald.",
        "Research only. No estimator promoted, no 2026 race-poll forecast, no change to the September seal.",
        "",
        "## Data",
        "",
        f"Ratings archive: {report['intake']['input_rows']:,} rows; research panel: "
        f"{report['window']['eligible_poll_rows']:,} eligible poll questions; "
        f"{report['window'].get('eligible_races', 0):,} race-cycles in the fixed window.",
        "Senate: lagged presidential state lean. House: separately labeled lagged House proxy,",
        "not presidential district lean. Publication and historical input vintages are unverified.",
        "Source: FiveThirtyEight, CC BY 4.0; certified outcome reconciliation: registered MEDSL returns.",
        "",
        "## Equal-Cycle Held-Out Results",
        "",
        "All errors use two-party Democratic vote-share fractions; 0.01 is one share point.",
        "| Office | Pipeline | Cycles | MAE | Brier | Log Loss | 90% Coverage |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for office, models in report["evaluation"]["summary"].items():
        for name, segments in models.items():
            segment = segments["all"]
            m = segment["equal_cycle_metrics"]
            lines.append(
                f"| {office} | {name} | {segment['n_cycles']} | {m['mae']:.4f} | "
                f"{m['brier']:.4f} | {m['log_loss']:.4f} | {m['coverage_90']:.3f} |"
            )
    lines.extend(
        [
            "",
            "By-cycle, competitive-only, lean-band calibration, raw and post-blend slopes,",
            "whole-cycle bootstrap uncertainty, exclusions and gates are in `study.json`.",
            "The full-history diagnostic is not held-out performance. Shared-error simulation",
            "uses one slope draw per election, never independent state corrections.",
            "",
            "## Remaining Gates",
            "",
        ]
    )
    for office, gate in report["evaluation"]["gates"].items():
        lines.append(f"- {office}: " + "; ".join(gate["reasons"]) + ".")
    lines.extend(
        [
            coverage_note,
            "- Publication availability and historical ballot identities remain unverified.",
            "- Historical House presidential lean on each election's boundaries is unavailable.",
            "- Fundamentals/roster/map inputs are not independently archived forecast-date snapshots.",
            "- No reviewed 2026 race polls: a numerical 2026 adjustment is withheld.",
            "- Polled-seat simulations cannot establish complete chamber calibration/control.",
            "",
            "Manual file request and source links: `docs/polling-lean-downloads.md`.",
            "Specification: `docs/polling-lean-experiment.md`. No article coefficient copied.",
        ]
    )
    return "\n".join(lines) + "\n"


def _model_card(report: dict) -> str:
    metrics: dict[str, str | int | float] = {}
    for office, models in report["evaluation"]["summary"].items():
        for pipeline, segments in models.items():
            for name, value in segments["all"]["equal_cycle_metrics"].items():
                metrics[f"{office}/{pipeline}/{name}"] = round(value, 5)
    return render_model_card(
        ModelCard(
            name="polling_lean_residual_experiment",
            version="v1-archive-research" if report.get("candidate_intake") else "v0-research",
            office_geography="U.S. Senate/state and House/district; separate office fits",
            model_type="Cycle-demeaned controlled regression; whole-cycle bootstrap; correlated simulation",
            target="Actual minus predicted Democratic two-party vote-share fraction",
            training_cycles="Earlier-cycle-only folds; exact office/cycle coverage in study.json",
            sources=[
                "FiveThirtyEight CC BY 4.0 archives; exact input and source-manifest hashes in study.json",
                "Registered MEDSL certified returns; archived October 22 chronological benchmark outputs",
            ],
            features=[
                "Lagged presidential state lean (Senate); labeled lagged House proxy (House)",
                "Cycle intercepts and weighted pollster/sponsor/mode/horizon exposure controls",
                "Raw polling average, precision fundamentals blend, post-blend lean residual adjustment",
            ],
            exclusions=[
                "Independent/same-party, unresolved RCV/Louisiana rounds and non-November elections",
                "Ambiguous structural race keys, unreconciled certified shares and missing priors",
                "No respondent/voter/donor records; no retrospective pollster ratings as predictors",
            ],
            assumptions=[
                "Fixed seven-day field-date horizon; candidate field midpoint versus ratings median proxy",
                "Candidate field-end/database-entry exclusions; missing publication dates are not inferred",
                "Equal cycle/race fitting weights; bootstrap whole elections, not independent polls",
                "Same national/regional/unit shocks and one shared uncertain lean coefficient per election",
                "Precision blend assumes independent signal errors; asserted correlation split retained",
            ],
            failure_modes=[
                "Retrospective archive selection and incomplete historical publication evidence",
                "House proxy differs from presidential district lean; reset-map cycles absent",
                "Historical fundamentals/map/roster vintages are not verified real-time inputs",
                "Bootstrap coefficient uncertainty does not identify future-cycle slope heterogeneity",
                "Small number of cycles and selective race coverage; no full-chamber validation",
            ],
            intended_use=(
                "Internal retrospective research only. No promotion, no 2026 numerical polling correction, "
                "no change to September forecast. Review candidate-poll downloads and vintage gates first."
            ),
            metrics=metrics,
            privacy_tier=0,
            owner="Alex Oswald",
            review_date=report["review_date"],
        )
    )


def build(
    *,
    archive: Path,
    output: Path,
    review_date: str,
    design: lean.Design | None = None,
    candidate_archives: list[Path] | None = None,
) -> dict:
    if output.exists():
        raise FileExistsError("preserve the prior study; choose a new output directory")
    design = design or lean.Design()
    pd.Timestamp(review_date)  # Validate the explicit project-calendar review date.
    polling_archive.verify_registered_archive(archive)
    candidate_archives = candidate_archives or []
    if len({p.resolve() for p in candidate_archives}) != len(candidate_archives):
        raise ValueError("duplicate candidate archive path")
    for path in candidate_archives:
        polling_archive.verify_registered_archive(path)
    seal_files = sorted(Path("reports").glob("preregistration_2026-11-03*"))
    before = {str(p): sha256_file(p) for p in seal_files}
    verify_seal(load_registration("reports/preregistration_2026-11-03.json"))
    predictions = {
        office: Path(f"reports/refresh_2026-10-22/chronological_{office}_predictions.csv")
        for office in ("house", "senate")
    }
    paths = [
        archive,
        Path("data/gold/race_results.parquet"),
        Path("data/gold/presidential_panel.parquet"),
        Path("data/gold/house_panel.parquet"),
        *predictions.values(),
        *candidate_archives,
        *[
            p.with_suffix(".provenance.json")
            for p in candidate_archives
            if p.with_suffix(".provenance.json").exists()
        ],
    ]
    inputs = {str(path): sha256_file(path) for path in paths}
    priors = pd.concat([pd.read_csv(p) for p in predictions.values()], ignore_index=True)
    polls, intake = polling_archive.prepare_ratings(
        pd.read_csv(archive),
        races=pd.read_parquet(paths[1]),
        presidential=pd.read_parquet(paths[2]),
        fundamentals=priors,
        house_panel=pd.read_parquet(paths[3]),
    )
    candidate_intake = None
    if candidate_archives:
        candidates, candidate_intake = candidate_polls.prepare_candidates(
            [candidate_polls.read_candidate_file(p) for p in candidate_archives],
            races=pd.read_parquet(paths[1]),
            presidential=pd.read_parquet(paths[2]),
            fundamentals=priors,
            house_panel=pd.read_parquet(paths[3]),
        )
        polls, replaced = candidate_polls.replace_overlapping_cycles(
            polls, candidates, candidate_intake["replacement_office_cycles"]
        )
        candidate_intake["ratings_questions_replaced"] = replaced
    races, window = lean.aggregate_races(polls, design)
    if races.empty:
        raise ValueError("no eligible races; inspect source coverage and feature joins")
    evaluated, evaluation = lean.evaluate(races, design)
    after = {str(p): sha256_file(p) for p in seal_files}
    if before != after:
        raise RuntimeError("sealed forecast changed during experiment")
    if inputs != {str(p): sha256_file(p) for p in paths}:
        raise RuntimeError("research inputs changed during experiment")
    source_files = [
        Path(__file__),
        Path(polling_archive.__file__),
        Path(lean.__file__),
        Path(candidate_polls.__file__),
    ]
    archive_paths = {p.resolve() for p in [archive, *candidate_archives]}
    report = {
        "review_date": review_date,
        "created_at": datetime.now(UTC).isoformat(),
        "design": asdict(design),
        "intake": intake,
        "candidate_intake": candidate_intake,
        "input_cycle_coverage": races.groupby(["office", "cycle"])
        .size()
        .reset_index(name="races")
        .to_dict("records"),
        "window": window,
        "evaluation": evaluation,
        "inputs_sha256": inputs,
        "implementation_sha256": {str(p): sha256_file(p) for p in source_files},
        "seal_hashes": after,
        "seal_unchanged": True,
        "source_manifests": [
            {"path": str(path), "sha256": sha256_file(path), "metadata": json.loads(path.read_text())}
            for path in Path("data/manifests").glob("538_race_poll_history*__*.json")
            if Path(json.loads(path.read_text())["raw_path"]).resolve() in archive_paths
        ],
        "candidate_provenance": [
            json.loads(p.with_suffix(".provenance.json").read_text())
            for p in candidate_archives
            if p.with_suffix(".provenance.json").exists()
        ],
        "manual_file_inventory": polling_archive.inspect_local_archives(
            archive.parent, supplied=candidate_archives
        ),
        "attribution": {
            "publisher": "FiveThirtyEight",
            "license": "CC BY 4.0",
            "url": polling_archive.RATINGS_URL,
            "transformations": "D/R general screening, certified reconciliation, fixed horizon, "
            "lagged features, weighted race aggregation and chronological residual calibration",
        },
    }
    output.mkdir(parents=True, exist_ok=False)
    panel_columns = [
        *sorted(lean.REQUIRED),
        *[
            c
            for c in ("field_start", "field_end", "database_created_at", "source_kind", "source_files")
            if c in polls
        ],
    ]
    polls[panel_columns].to_csv(output / "poll_questions.csv", index=False)
    races.to_csv(output / "race_averages.csv", index=False)
    evaluated.to_csv(output / "held_out_predictions.csv", index=False)
    with (output / "study.json").open("x") as handle:
        json.dump(report, handle, indent=2, default=str, allow_nan=False)
    (output / "README.md").write_text(_markdown(report))
    (output / "model_card.md").write_text(_model_card(report))
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    acquire = commands.add_parser("acquire", help="download registered public publisher archives")
    acquire.add_argument("--directory", type=Path, required=True)
    acquire.add_argument("--candidate-files", action="store_true")
    acquire.add_argument("--report", type=Path, required=True)
    preserve = commands.add_parser("preserve-candidate", help="import an unmodified user archive")
    preserve.add_argument("--file", type=Path, required=True)
    preserve.add_argument("--archive-url", required=True)
    study = commands.add_parser("study", help="run the fixed retrospective study without changing forecasts")
    study.add_argument("--archive", type=Path, required=True)
    study.add_argument("--out", type=Path, required=True)
    study.add_argument("--review-date", required=True)
    study.add_argument("--candidate-archive", type=Path, action="append", default=[])
    args = parser.parse_args(argv)
    if args.command == "preserve-candidate":
        print(
            json.dumps(
                candidate_polls.preserve_manual_file(args.file, archive_url=args.archive_url), indent=2
            )
        )
        return 0
    if args.command == "acquire":
        if args.report.exists():
            raise FileExistsError("preserve the earlier acquisition report")
        attempts = polling_archive.download_archives(
            args.directory, include_candidate_files=args.candidate_files
        )
        args.report.parent.mkdir(parents=True, exist_ok=True)
        with args.report.open("x") as handle:
            json.dump({"checked_at": datetime.now(UTC).isoformat(), "attempts": attempts}, handle, indent=2)
        print(json.dumps(attempts, indent=2))
        return 0 if all(a["status"] == "acquired_unreviewed" for a in attempts) else 2
    report = build(
        archive=args.archive,
        output=args.out,
        review_date=args.review_date,
        candidate_archives=args.candidate_archive,
    )
    print(
        json.dumps(
            {
                "output": str(args.out),
                "eligible_races": report["window"]["eligible_races"],
                "gates": report["evaluation"]["gates"],
                "seal_unchanged": True,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

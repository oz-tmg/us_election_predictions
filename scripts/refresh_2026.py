#!/usr/bin/env python
"""Rebuild cached live features, chronological evaluations and a dated comparison to the seal."""

from __future__ import annotations

import argparse
import contextlib
import importlib.metadata
import io
import json
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, "src")

from project_2026 import main as project  # noqa: E402

from election_prediction.data.manifest import SourceManifest, sha256_file  # noqa: E402
from election_prediction.data.privacy import PrivacyTier  # noqa: E402
from election_prediction.evaluation import chronological, score_preregistration  # noqa: E402
from election_prediction.features import fundamentals, plan_versions  # noqa: E402
from election_prediction.models import error_structure, simulation  # noqa: E402
from election_prediction.models.baseline import house, presidential, senate  # noqa: E402


def snapshot_compilations(stamp: str) -> dict:
    senate_paths = sorted(
        p
        for p in Path("data/reference").glob("senate_roster_*.csv")
        if p.stem.removeprefix("senate_roster_") <= stamp
    )
    senate_filename = senate_paths[-1].name if senate_paths else f"senate_roster_{stamp}.csv"
    sources = {
        senate_filename: (
            "senate_current_roster",
            "U.S. Senate",
            "https://www.senate.gov/senators/",
        ),
        f"house_roster_{stamp}.csv": (
            "house_current_roster",
            "Clerk of the U.S. House",
            "https://clerk.house.gov/xml/lists/MemberData.xml",
        ),
        "senate_specials_2026.csv": (
            "fec_election_schedule_2026",
            "FEC / Ohio Secretary of State",
            "https://www.fec.gov/documents/5910/2026pdates.pdf",
        ),
        "candidacy_2026.csv": (
            "candidate_candidacy_announcements_2026",
            "State election authorities / cited official announcements and reporting",
            "source_url per compiled row",
        ),
        "special_elections_2025_2026.csv": (
            "special_elections_compiled",
            "State election authorities / MEDSL",
            "source_url and baseline_source per compiled row",
        ),
    }
    provenance = {}
    for filename, (source_id, owner, url) in sources.items():
        original = Path("data/reference") / filename
        if not original.is_file():
            continue
        checksum = sha256_file(original)
        raw = Path(f"data/raw/source={source_id}/snapshot={stamp}/sha256={checksum}") / filename
        raw.parent.mkdir(parents=True, exist_ok=True)
        if raw.exists() and sha256_file(raw) != sha256_file(original):
            raise ValueError(f"immutable compilation snapshot already exists: {raw}")
        if not raw.exists():
            shutil.copyfile(original, raw)
        manifest = SourceManifest.for_snapshot(
            raw_path=raw,
            source_id=f"{source_id}_{checksum[:12]}",
            dataset_name=filename,
            source_owner=owner,
            source_url=url,
            privacy_tier=PrivacyTier.PUBLIC_AGGREGATE,
            license_or_terms=(
                "Public election facts; cite source URLs and retrieval dates. No reporting prose reproduced."
            ),
            permitted_use="Nonpartisan aggregate research and reproducible reporting.",
            prohibited_use="No contact fields, advocacy targeting or claims of unverified nomination.",
            office_coverage=["us_senate", "us_house"],
            geography_coverage=["state", "district"],
            election_cycle="2026",
            owner="Alex Oswald (data steward)",
            acquisition_method="manual_compilation",
            required_attribution=owner,
            file_format="csv",
        )
        manifest.validation_status = "passed"
        manifest.row_count = len(pd.read_csv(original, comment="#"))
        manifest.write()
        provenance[str(original)] = {"sha256": sha256_file(original), "snapshot": str(raw)}
    return provenance


def rebuild_and_evaluate(output: Path) -> tuple[dict, dict, dict]:
    gold = Path("data/gold")
    races = pd.read_parquet(gold / "race_results.parquet")
    returns = pd.read_parquet("data/silver/election_returns.parquet")
    acs = pd.read_parquet(gold / "acs_state_features.parquet")
    pres = fundamentals.build_presidential_panel(races, acs)
    hpanel = house.build_house_panel(races, returns, plans=plan_versions.PlanVersions.load())
    spanel = senate.build_senate_panel(races, returns)
    for name, panel in [("presidential", pres), ("house", hpanel), ("senate", spanel)]:
        panel.to_parquet(gold / f"{name}_panel.parquet", index=False)
    chronological_senate = chronological.lag_senate_presidential_reference(spanel, pres)
    specs = {
        "presidential": (pres, presidential.DEFAULT_FEATURES, "lag_dem_share"),
        "house": (hpanel, house.DEFAULT_FEATURES, house.NAIVE_FEATURE),
        "senate": (chronological_senate, senate.DEFAULT_FEATURES, senate.NAIVE_FEATURE),
    }
    evaluation, correlations = {}, {}
    for office, (panel, features, naive) in specs.items():
        preds, metrics = chronological.backtest(panel, features=features, naive_feature=naive)
        preds.to_csv(output / f"chronological_{office}_predictions.csv", index=False)
        evaluation[office] = metrics
        if office == "presidential" and metrics.get("n"):
            wins = metrics["metrics"]["mae_vote_share"] < metrics["naive_mae"]
            metrics["release_gate"] = {
                "beats_persistence": wins,
                "selected_benchmark": "OLS" if wins else "persistence",
                "reason": "Compare chronologically before promoting the more complex presidential model",
            }
        if office != "presidential":
            correlations[office] = error_structure.evaluate(
                preds, expected_units=435 if office == "house" else None
            )
    # Senate specification gate (2026-10-29): every candidate is scored on the same
    # expanding-window backtest and promoted only if it beats the baseline there.
    spec_evaluations = {}
    for name, features in senate.SPECIFICATIONS.items():
        preds, metrics = chronological.backtest(
            chronological_senate, features=features, naive_feature=senate.NAIVE_FEATURE
        )
        preds.to_csv(output / f"chronological_senate_{name}_predictions.csv", index=False)
        spec_evaluations[name] = {
            "mae": metrics["metrics"]["mae_vote_share"],
            "open_seat_mae": senate.open_seat_mae(preds),
            "coverage_90": metrics["metrics"]["coverage_90"],
            "n": metrics["n"],
            "n_open_seats": int(preds["open_seat"].fillna(False).astype(bool).sum()),
        }
    senate_selection = senate.select_specification(spec_evaluations)
    return evaluation, correlations, senate_selection


def refresh_special_baselines(output: Path) -> list[dict]:
    """Refresh only validated same-map baselines; never replace election results."""
    path = Path("data/reference/special_elections_2025_2026.csv")
    baseline_path = Path("data/gold/cd_presidential_baseline_2024.parquet")
    compiled = pd.read_csv(path, comment="#", dtype={"district": str})
    compiled["baseline_two_party_votes"] = compiled["baseline_two_party_votes"].astype(float)
    baseline = pd.read_parquet(baseline_path).set_index(["state_po", "district_num"])
    changes = []
    for index, row in compiled.iterrows():
        if row["office"] != "us_house" or row["baseline_cycle"] != 2024:
            continue
        key = (row["state_po"], int(row["district"]))
        if key not in baseline.index:
            continue
        new = baseline.loc[key]
        quality = str(new["baseline_quality"])
        changes.append(
            {
                "special_id": row["special_id"],
                "old_share": float(row["baseline_dem_share"]),
                "rebuilt_share": float(new["baseline_dem_share"]),
                "quality": quality,
                "share_updated": quality == "ok",
            }
        )
        if quality == "ok":
            compiled.loc[index, "baseline_dem_share"] = new["baseline_dem_share"]
            compiled.loc[index, "baseline_two_party_votes"] = new["two_party_votes"]
            compiled.loc[index, "baseline_source"] = (
                f"{baseline_path} sha256={sha256_file(baseline_path)}; validated same 2024 geography"
            )
        else:
            # A proportionally duplicated source cannot support a turnout ratio.
            compiled.loc[index, "baseline_two_party_votes"] = float("nan")
    headers = "\n".join(line for line in path.read_text().splitlines() if line.startswith("#"))
    path.write_text(headers + "\n" + compiled.to_csv(index=False))
    (output / "special_baseline_refresh.json").write_text(json.dumps(changes, indent=2))
    return changes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", default=date.today().isoformat())
    args = parser.parse_args(argv)
    stamp = date.fromisoformat(args.as_of).isoformat()
    output = Path("reports") / f"refresh_{stamp}"
    output.mkdir(parents=True, exist_ok=True)
    registration_path = Path("reports/preregistration_2026-11-03.json")
    sealed_files = list(Path("reports").glob("preregistration_2026-11-03.*"))
    sealed_files.append(Path("reports/preregistration_2026-11-03_seats.csv"))
    before = {str(p): sha256_file(p) for p in sealed_files}
    registration = score_preregistration.load_registration(registration_path)
    score_preregistration.verify_seal(registration)
    provenance = snapshot_compilations(stamp)
    baseline_changes = refresh_special_baselines(output)
    provenance.update(snapshot_compilations(stamp))
    inputs = [
        Path("data/silver/election_returns.parquet"),
        Path("data/gold/race_results.parquet"),
        Path("data/gold/acs_state_features.parquet"),
        Path("data/reference/house_plan_versions.csv"),
        Path("data/reference/special_elections_2025_2026.csv"),
        Path("data/gold/cd_presidential_baseline_2024.parquet"),
        Path("data/gold/race_universe_2026.parquet"),
        Path("data/reference/transferred_priors_2026.csv"),
    ]
    optional = Path("data/gold/incumbent_filings_2026.parquet")
    if optional.is_file():
        inputs.append(optional)
    provenance.update({str(p): {"sha256": sha256_file(p)} for p in inputs})
    evaluation, correlations, senate_selection = rebuild_and_evaluate(output)
    (output / "chronological_evaluation.json").write_text(json.dumps(evaluation, indent=2))
    (output / "senate_specification_gate.json").write_text(json.dumps(senate_selection, indent=2))
    (output / "correlation_evaluation.json").write_text(json.dumps(correlations, indent=2))
    text = io.StringIO()
    with contextlib.redirect_stdout(text):
        payload = project(
            as_of=stamp,
            reports_dir=output,
            correlation_params=simulation.CorrelationParams(**correlations["house"]["selected_parameters"]),
            senate_correlation_params=simulation.CorrelationParams(
                **correlations["senate"]["selected_parameters"]
            ),
            senate_features=senate_selection["features"],
        )
    (output / "projection_2026.txt").write_text(text.getvalue())
    current = pd.DataFrame(payload["seats"])
    current.to_csv(output / "projection_seats.csv", index=False)
    old_seats = pd.DataFrame(registration["predictions"]["seats"])
    diff = current.merge(
        old_seats,
        on=["geography_id", "office", "assumption"],
        how="outer",
        suffixes=("_current", "_sealed"),
        indicator=True,
        validate="one_to_one",
    )
    diff["mean_share_change"] = diff["mean_dem_share_current"] - diff["mean_dem_share_sealed"]
    diff["probability_change"] = diff["dem_win_prob_current"] - diff["dem_win_prob_sealed"]
    diff.to_csv(output / "seat_changes_vs_seal.csv", index=False)
    old_band = pd.DataFrame(registration["predictions"]["band"])
    band = pd.DataFrame(payload["band_results"]).merge(
        old_band, on="assumption", suffixes=("_current", "_sealed")
    )
    band.to_csv(output / "band_changes_vs_seal.csv", index=False)
    races = pd.read_parquet("data/gold/race_results.parquet")
    h24 = races[races.office.eq("us_house") & races.cycle.eq(2024)]
    contested = h24[~h24.uncontested_flag]
    definitions = {
        "all_races_ratio_of_two_party_votes": float(
            h24.dem_votes.sum() / (h24.dem_votes.sum() + h24.rep_votes.sum())
        ),
        "contested_ratio_of_two_party_votes": float(
            contested.dem_votes.sum() / (contested.dem_votes.sum() + contested.rep_votes.sum())
        ),
        "contested_total_vote_weighted_model_input": float(
            (contested.two_party_dem_share * contested.total_votes).sum() / contested.total_votes.sum()
        ),
    }
    after = {str(p): sha256_file(p) for p in sealed_files}
    if before != after:
        raise RuntimeError("sealed registration files changed during the refresh")
    summary = {
        "as_of": stamp,
        "python_version": sys.version,
        "package_versions": {
            name: importlib.metadata.version(name)
            for name in (
                "pandas",
                "numpy",
                "pyarrow",
                "geopandas",
                "pypdf",
                "openpyxl",
                "beautifulsoup4",
                "lxml",
            )
        },
        "build_spec_sha256": sha256_file("pyproject.toml"),
        "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "code_sha256": {
            str(path): sha256_file(path)
            for root in (Path("src/election_prediction"), Path("scripts"))
            for path in sorted(root.rglob("*.py"))
        },
        "guidance_sha256": {
            name: sha256_file(name)
            for name in ("PROJECT_CONTEXT.md", "AGENTS.md", "CLAUDE.md", "COMPANY_CONTEXT.md")
        },
        "working_tree_changes": subprocess.check_output(["git", "diff", "--stat"], text=True),
        "input_provenance": provenance,
        "sealed_files_sha256": after,
        "seal_preserved": True,
        "national_baseline_definitions": definitions,
        "senate_composition": payload["senate_composition"],
        "candidacy_coverage": payload["candidacy_coverage"],
        "house_coverage": payload["house_coverage"],
        "transfer_provenance": payload["transfer_provenance"],
        "special_baseline_changes": baseline_changes,
        "chronological_evaluation": evaluation,
        "senate_specification_gate": senate_selection,
        "correlations": correlations,
        "diagnostics": {
            path.name: {"path": str(path), "sha256": sha256_file(path)}
            for path in [
                output / "economic_cross_check.json",
                output / "generic_ballot_cross_check.json",
                output / "full_chamber_evaluation.json",
                output / "ballot_coverage.json",
                output / "special_source_refresh.json",
                output / "transfers/audit.json",
            ]
            if path.is_file()
        },
    }
    (output / "refresh_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    lines = [
        f"# 2026 Forecast Refresh - {stamp}",
        "",
        "Internal model scenarios; no live forecast published. "
        "The original registration is preserved and remains the scored holdout.",
        "",
        "## Changes",
        "",
        "| Shrinkage | House mean: sealed -> current | House P(D): sealed -> current | "
        "Senate P(D): sealed -> current |",
        "|---:|---:|---:|---:|",
    ]
    for row in band.to_dict(orient="records"):
        lines.append(
            f"| {row['shrinkage_current']:.2f} | "
            f"{row['house_mean_seats_sealed']:.1f} -> {row['house_mean_seats_current']:.1f} | "
            f"{row['house_p_dem_sealed']:.3f} -> {row['house_p_dem_current']:.3f} | "
            f"{row['sen_p_dem_sealed']:.3f} -> {row['sen_p_dem_current']:.3f} |"
        )
    lines += [
        "",
        "## Coverage and limitations",
        "",
        "```json\n" + json.dumps(payload["senate_composition"], indent=2) + "\n```",
        "",
        f"Candidacy evidence: {payload['candidacy_coverage']}. Missing evidence remains an assumption.",
        f"House prior sources: {payload['house_coverage']['seats_by_source']}.",
        "Each prior's national reference now matches its source election. "
        "The previous run incorrectly subtracted the 2022 national input from 2024 priors.",
        "The sealed 33-race Senate universe is unchanged; this new run includes FL/OH specials "
        "and uses current official holders/caucuses.",
        "Historical ACS is still a single vintage: excluded from the chronological benchmark. "
        "Historical candidate availability is reconstructed, not an archived as-of input.",
        "",
        "## National baseline definitions",
        "",
        "```json\n" + json.dumps(definitions, indent=2) + "\n```",
        "",
        "The October 11 findings compared the all-race aggregate (0.4869) with the model's "
        "contested-race, total-vote-weighted input (0.4974). These are different quantities; "
        "the latter is labelled as the model input rather than an aggregate two-party national vote.",
        "",
        "## Chronological evaluation",
        "",
        "| Office | Cycles | MAE | Persistence MAE | 90% coverage |",
        "|---|---:|---:|---:|---:|",
    ]
    for office, metrics in evaluation.items():
        if metrics.get("n"):
            m = metrics["metrics"]
            lines.append(
                f"| {office} | {metrics['n_cycles']} | {m['mae_vote_share']:.4f} | "
                f"{metrics['naive_mae']:.4f} | {m['coverage_90']:.3f} |"
            )
    lines += [
        "",
        "## Senate specification gate",
        "",
        f"Selected: `{senate_selection['selected']}`. " + " ".join(senate_selection["reasons"]),
        "",
        "| Specification | MAE | Open-seat MAE | 90% coverage | n (open) |",
        "|---|---:|---:|---:|---:|",
    ]
    for name, ev in senate_selection["evaluations"].items():
        open_mae = "n/a" if ev["open_seat_mae"] is None else f"{ev['open_seat_mae']:.4f}"
        lines.append(
            f"| {name} | {ev['mae']:.4f} | {open_mae} | {ev['coverage_90']:.3f} | "
            f"{ev['n']} ({ev['n_open_seats']}) |"
        )
    lines += ["", "## Correlated error", ""]
    for office, result in correlations.items():
        lines += [
            f"{office}: {result['selection_reason']}. "
            f"Selected variance shares: {result['selected_parameters']}.",
            f"Held-out interval evaluation: {result['summary']}. Universe: {result['evaluation_universe']}.",
            "",
        ]
    lines += [
        "## Experimental cross-checks",
        "",
        "Economic, polling and full-chamber diagnostics are linked in `refresh_summary.json`. "
        "They are not precision-blended into this band and do not authorize changing the seal. "
        "Their model cards describe failed promotion gates and incomplete source coverage.",
        "",
        "## Operational follow-up",
        "",
        "See `docs/refresh-2026-status.md`, `docs/results-2026-runbook.md` and the dated model card "
        "for source gaps, candidacy limits, release gates and the macroeconomic cross-check specification.",
        "Source freshness is per row, not the report date. See `special_source_refresh.json` "
        "for any newly reverified counts and exclusions; other retrieval dates remain unchanged. "
        "Economic and polling cross-checks remain separate, unpromoted diagnostics.",
        "",
        "## Reproduction",
        "",
        f"`python scripts/refresh_2026.py --as-of {stamp}`",
        "Requires registered cached live inputs/P0 and CD-baseline builds, not just an empty checkout.",
        "",
        "Full input checksums, source snapshots, model evaluations and seal verification "
        "are in `refresh_summary.json`. Per-seat and band differences are adjacent CSV files.",
    ]
    (output / "README.md").write_text("\n".join(lines) + "\n")
    print(f"Refreshed projection and comparison -> {output / 'README.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

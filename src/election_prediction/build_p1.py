"""End-to-end P1 baseline build (``ep-build-p1``).

Runs the P0 foundation, then the P1 baseline forecasting stack, all reproducibly:

    P0 (returns + geography + race table)
      -> ACS features (live or synthetic)
      -> presidential fundamentals panel (lagged vote + national env + demographics)
      -> leave-one-cycle-out backtest + calibration evaluation
      -> correlated presidential simulation (win probs + EC distribution)
      -> House district partisanship score + correlated seat/chamber simulation
      -> model cards + a forecast backtest report

Historical backtest only — no live forecast is published (PROJECT_CONTEXT §4). Outputs
land in ``reports/`` and ``data/gold/``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

from .config import load_dotenv
from .data import acquire, acs, source_validation
from .data.manifest import SourceManifest
from .data.privacy import PrivacyTier
from .evaluation import forecast_eval
from .features import fundamentals
from .geography import reference as geography_reference
from .geography import tiger
from .models import simulation
from .models.baseline import house_partisanship, presidential
from .pipelines_cli import build as build_p0
from .reporting.model_cards import write_forecast_report, write_presidential_model_card


def _write_public_manifest(
    *,
    raw_path: Path,
    manifests_dir: Path,
    source_id: str,
    dataset_name: str,
    source_url: str,
    geography_coverage: list[str],
    election_cycle: str,
    file_format: str,
    row_count: int,
    unique_key: list[str],
    known_caveats: str = "",
) -> Path:
    manifest = SourceManifest.for_snapshot(
        raw_path=raw_path,
        source_id=source_id,
        dataset_name=dataset_name,
        source_owner="U.S. Census Bureau",
        source_url=source_url,
        privacy_tier=PrivacyTier.PUBLIC_AGGREGATE,
        license_or_terms="Public domain (U.S. Census Bureau); cite table/layer and vintage.",
        permitted_use="Public nonpartisan research and aggregate reporting with citation.",
        prohibited_use="Do not misrepresent estimates as certified election results.",
        office_coverage=["all"],
        geography_coverage=geography_coverage,
        election_cycle=election_cycle,
        owner="project-owner (data steward)",
        file_format=file_format,
        required_attribution="U.S. Census Bureau.",
        known_caveats=known_caveats,
    )
    manifest.validation_status = "passed"
    manifest.row_count = row_count
    manifest.unique_key = unique_key
    return manifest.write(manifests_dir)


def _acs_features(
    base: Path,
    *,
    allow_network: bool,
    require_live: bool = False,
    vintage: int = acs.DEFAULT_ACS_VINTAGE,
) -> tuple[pd.DataFrame, str]:
    """Return validated ACS features and acquisition mode."""
    if allow_network:
        try:
            raw_path = acs.download_acs_states(vintage, base / "data/raw")
            raw = acs.parse_acs_json(raw_path)
            features = acs.standardize_acs(raw, vintage=vintage, source_id=f"census_acs5_state_{vintage}")
            checks = acs.validate_acs_features(features)
            if not checks["ok"]:
                raise acquire.InvalidResponse(f"ACS validation failed: {checks}")
            _write_public_manifest(
                raw_path=raw_path,
                manifests_dir=base / "data/manifests",
                source_id=f"census_acs5_state_{vintage}",
                dataset_name=f"ACS {vintage} 5-Year State Estimates",
                source_url=f"{acs.CENSUS_API}/{vintage}/acs/acs5",
                geography_coverage=["state"],
                election_cycle=str(vintage),
                file_format="json",
                row_count=len(features),
                unique_key=["geoid"],
                known_caveats="ACS estimates carry sampling uncertainty; margins of error matter.",
            )
            return features, "live"
        except acquire.CredentialRequired as e:
            print(f"\n  ! {e.instructions()}\n")
            if require_live:
                raise
        except acquire.AcquisitionError as e:
            print(f"  ! {e}")
            if require_live:
                raise

    if require_live:
        raise acquire.AcquisitionError("--require-live was set but ACS could not be acquired.")

    raw = acs.build_synthetic_acs(vintage)
    features = acs.standardize_acs(raw, vintage=vintage, source_id=f"census_acs5_state_{vintage}_synthetic")
    checks = acs.validate_acs_features(features)
    if not checks["ok"]:
        raise acquire.InvalidResponse(f"Synthetic ACS validation failed: {checks}")
    return features, "synthetic"


def _tiger_boundaries(
    base: Path,
    *,
    allow_network: bool,
    require_live: bool = False,
    vintage: int = tiger.DEFAULT_TIGER_VINTAGE,
) -> dict:
    """Acquire, validate, and persist TIGER state/county/CD boundaries."""
    raw_dir = base / "data/raw"
    silver_dir = base / "data/silver"
    manifests_dir = base / "data/manifests"
    outputs = {layer: silver_dir / f"tiger_{layer}_{vintage}.parquet" for layer in ("state", "county", "cd")}

    if allow_network:
        try:
            state_shp = tiger.download_tiger(vintage, "state", raw_dir)
            county_shp = tiger.download_tiger(vintage, "county", raw_dir)
            target_fips = [state.fips for state in geography_reference.STATES.values()]
            cd_shps = tiger.download_tiger_cd(
                vintage,
                raw_dir,
                state_fips=target_fips,
                require_all=True,
            )
            layer_shps = {
                "state": {"us": state_shp},
                "county": {"us": county_shp},
                "cd": cd_shps,
            }
            checks = {}
            for layer, keyed_paths in layer_shps.items():
                gdf = tiger.to_geoparquet_many(list(keyed_paths.values()), outputs[layer])
                checks[layer] = tiger.validate_boundaries(gdf)
                if not checks[layer]["ok"]:
                    raise acquire.InvalidResponse(
                        f"TIGER {layer} geometry/GEOID validation failed: {checks[layer]}"
                    )
                inventory = tiger.write_inventory(vintage, layer, keyed_paths, raw_dir)
                congress = tiger.congress_for_vintage(vintage) if layer == "cd" else ""
                _write_public_manifest(
                    raw_path=inventory,
                    manifests_dir=manifests_dir,
                    source_id=(
                        f"census_tiger_{congress}_{vintage}"
                        if layer == "cd"
                        else f"census_tiger_{layer}_{vintage}"
                    ),
                    dataset_name=f"TIGER/Line {vintage} {layer.upper()} Boundaries",
                    source_url=(
                        f"{tiger.TIGER_BASE}/TIGER{vintage}/"
                        f"{'CD' if layer == 'cd' else tiger.NATIONAL_LAYERS[layer]}"
                    ),
                    geography_coverage=["congressional_district" if layer == "cd" else layer],
                    election_cycle=str(vintage),
                    file_format="json",
                    row_count=len(gdf),
                    unique_key=["GEOID"],
                    known_caveats=(
                        "Congressional districts are distributed as one archive per state; "
                        "the raw inventory records every archive checksum."
                        if layer == "cd"
                        else "Boundary vintage must match the analysis cycle."
                    ),
                )
            return {"mode": "live", "checks": checks, "outputs": outputs}
        except (acquire.AcquisitionError, OSError, ValueError) as exc:
            print(f"  ! TIGER acquisition failed: {exc}")
            if require_live:
                if isinstance(exc, acquire.AcquisitionError):
                    raise
                raise acquire.AcquisitionError(f"TIGER acquisition failed: {exc}") from exc

    if require_live:
        raise acquire.AcquisitionError("--require-live was set but TIGER could not be acquired.")

    checks = {}
    for layer, output in outputs.items():
        gdf = tiger.build_synthetic_boundaries(layer)
        gdf.to_parquet(output)
        checks[layer] = tiger.validate_boundaries(gdf)
        if not checks[layer]["ok"]:
            raise acquire.InvalidResponse(f"Synthetic TIGER {layer} validation failed: {checks[layer]}")
    return {"mode": "synthetic", "checks": checks, "outputs": outputs}


def build(base: Path, *, allow_network: bool = True, require_live: bool = False) -> dict:
    base = Path(base)
    p0 = build_p0(base, allow_network=allow_network, require_live=require_live)
    race_table = p0["race_table"]
    gold_dir = base / "data/gold"
    reports_dir = base / "reports"
    gold_dir.mkdir(parents=True, exist_ok=True)

    acs_features, acs_mode = _acs_features(base, allow_network=allow_network, require_live=require_live)
    acs_features.to_parquet(gold_dir / "acs_state_features.parquet", index=False)
    tiger_result = _tiger_boundaries(base, allow_network=allow_network, require_live=require_live)
    data_modes = {
        **p0["modes"],
        "census_acs": acs_mode,
        "census_tiger": tiger_result["mode"],
    }

    source_checks = {"status": "skipped", "reason": "live Senate and ACS required"}
    if p0["modes"].get("us_senate") in {"live", "manual"} and acs_mode == "live":
        source_checks = source_validation.validate_live_sources(p0["returns"], acs_features)
        source_validation.write_report(source_checks, reports_dir / "source_validation_report.md")
        if require_live and not source_checks["ok"]:
            raise acquire.InvalidResponse(
                f"Authoritative Senate/ACS source validation failed: {source_checks}"
            )

    # ---- presidential fundamentals baseline (P1-001) --------------------
    panel = fundamentals.build_presidential_panel(race_table, acs_features)
    panel.to_parquet(gold_dir / "presidential_panel.parquet", index=False)

    feats_base = ["lag_dem_share", "national_dem_share"]
    feats_demo = feats_base + ["college_share"]
    preds_base, m_base = presidential.backtest_leave_one_cycle_out(panel, feats_base)
    preds_demo, m_demo = presidential.backtest_leave_one_cycle_out(panel, feats_demo)

    eval_base = forecast_eval.evaluate_backtest(preds_base) if len(preds_base) else {}
    eval_demo = forecast_eval.evaluate_backtest(preds_demo) if len(preds_demo) else {}

    # ---- correlated presidential simulation (P1-005) --------------------
    # Simulate the most recent backtested cycle using its held-out predictions.
    pres_sim = {}
    if len(preds_demo):
        latest = preds_demo[preds_demo["cycle"] == preds_demo["cycle"].max()]
        pres_sim = simulation.simulate_presidential(latest)

    # ---- House partisanship + seat simulation (P1-002, P1-005) ----------
    house_input = fundamentals.build_house_partisanship_input(race_table)
    score = house_partisanship.build_partisanship_score(house_input)
    score.to_parquet(gold_dir / "house_partisanship_score.parquet", index=False)

    house_sim = {}
    if len(score):
        import numpy as np

        from .geography import reference as ref

        means = score["mean_dem_share"].to_numpy()
        sigmas = np.full(len(score), 0.05)  # baseline district-level uncertainty
        regions = [ref.by_postal(s).census_region for s in score["state_po"]]
        sim = simulation.simulate_shares(means, sigmas, regions, n_sims=10_000)
        house_sim = simulation.seat_distribution(sim, score["state_po"].tolist())

    # ---- reports --------------------------------------------------------
    results = {
        "presidential": {
            "baseline_backtest": m_base,
            "demographics_backtest": m_demo,
            "baseline_eval": eval_base,
            "demographics_eval": eval_demo,
            "simulation": _jsonable(pres_sim),
        },
        "house": {"n_districts_scored": int(len(score)), "seat_simulation": house_sim},
        "data_mode": data_modes,
        "tiger": tiger_result["checks"],
        "source_validation": source_checks,
    }
    any_synthetic = any(m == "synthetic" for m in data_modes.values())
    write_presidential_model_card(results, reports_dir, synthetic=any_synthetic)
    report_path = write_forecast_report(results, reports_dir, synthetic=any_synthetic)
    (reports_dir / "p1_results.json").write_text(json.dumps(_jsonable(results), indent=2))

    print("\n=== P1 baseline summary ===")
    print(
        f"  Presidential MAE (lag+national): {m_base.get('mae'):.4f} "
        f"| +college: {m_demo.get('mae'):.4f} | naive persistence: "
        f"{m_base.get('naive_persistence_mae'):.4f}"
    )
    if eval_demo:
        print(
            f"  Win-prob Brier: {eval_demo['brier']:.4f} | log score: "
            f"{eval_demo['log_score']:.4f} | ECE: {eval_demo['ece']:.4f} | "
            f"90% coverage: {eval_demo['coverage_90']:.3f}"
        )
    if pres_sim:
        ec = pres_sim["electoral_college"]
        print(
            f"  Sim (latest cycle) mean Dem EV: {ec['mean_dem_ev']:.0f} "
            f"| P(Dem EC majority): {ec['p_dem_majority']:.2f}"
        )
    if house_sim:
        print(
            f"  House sim mean Dem seats: {house_sim['mean_dem_seats']:.0f}/"
            f"{house_sim['n_units']} | P(Dem control): {house_sim['p_dem_control']:.2f}"
        )
    print(f"  Reports -> {report_path}")
    return results


def _jsonable(obj):
    """Convert DataFrames/np types in a nested dict to JSON-friendly forms."""
    import numpy as np

    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, pd.DataFrame):
        return obj.to_dict("records")
    if isinstance(obj, (np.floating, np.integer)):
        return obj.item()
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build the P1 baseline forecasting stack.")
    ap.add_argument("--base", default=".")
    ap.add_argument("--offline", action="store_true", help="use synthetic fixtures (no network)")
    ap.add_argument(
        "--require-live",
        action="store_true",
        help="fail instead of falling back to synthetic fixtures "
        "(use for any run whose numbers will be published)",
    )
    args = ap.parse_args(argv)
    if args.offline and args.require_live:
        ap.error("--offline and --require-live are mutually exclusive")
    if loaded := load_dotenv(Path(args.base) / ".env"):
        print(f"Loaded {len(loaded)} local settings from .env: {', '.join(sorted(loaded))}", flush=True)
    try:
        build(Path(args.base), allow_network=not args.offline, require_live=args.require_live)
    except acquire.AcquisitionError as e:
        print(f"\nP1 build FAILED — could not acquire real data:\n  {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

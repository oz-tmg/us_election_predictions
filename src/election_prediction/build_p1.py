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
from pathlib import Path

import pandas as pd

from .data import acs
from .evaluation import forecast_eval
from .features import fundamentals
from .models import simulation
from .models.baseline import house_partisanship, presidential
from .pipelines_cli import build as build_p0
from .reporting.model_cards import write_forecast_report, write_presidential_model_card


def _acs_features(base: Path, *, allow_network: bool, vintage: int = 2020) -> pd.DataFrame:
    if allow_network:
        try:
            raw_path = acs.download_acs_states(vintage, base / "data/raw")
            raw = acs.parse_acs_json(raw_path)
            return acs.standardize_acs(raw, vintage=vintage, source_id=f"census_acs5_state_{vintage}")
        except RuntimeError as e:
            print(f"  ! {e}")
    raw = acs.build_synthetic_acs(vintage)
    return acs.standardize_acs(raw, vintage=vintage,
                               source_id=f"census_acs5_state_{vintage}_synthetic")


def build(base: Path, *, allow_network: bool = True) -> dict:
    base = Path(base)
    p0 = build_p0(base, allow_network=allow_network)
    race_table = p0["race_table"]
    gold_dir = base / "data/gold"
    reports_dir = base / "reports"
    gold_dir.mkdir(parents=True, exist_ok=True)

    acs_features = _acs_features(base, allow_network=allow_network)
    acs_features.to_parquet(gold_dir / "acs_state_features.parquet", index=False)

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
            "baseline_backtest": m_base, "demographics_backtest": m_demo,
            "baseline_eval": eval_base, "demographics_eval": eval_demo,
            "simulation": _jsonable(pres_sim),
        },
        "house": {"n_districts_scored": int(len(score)), "seat_simulation": house_sim},
        "data_mode": p0["modes"],
    }
    write_presidential_model_card(results, reports_dir, synthetic=any(
        m == "synthetic" for m in p0["modes"].values()))
    report_path = write_forecast_report(results, reports_dir, synthetic=any(
        m == "synthetic" for m in p0["modes"].values()))
    (reports_dir / "p1_results.json").write_text(json.dumps(_jsonable(results), indent=2))

    print("\n=== P1 baseline summary ===")
    print(f"  Presidential MAE (lag+national): {m_base.get('mae'):.4f} "
          f"| +college: {m_demo.get('mae'):.4f} | naive persistence: "
          f"{m_base.get('naive_persistence_mae'):.4f}")
    if eval_demo:
        print(f"  Win-prob Brier: {eval_demo['brier']:.4f} | log score: "
              f"{eval_demo['log_score']:.4f} | ECE: {eval_demo['ece']:.4f} | "
              f"90% coverage: {eval_demo['coverage_90']:.3f}")
    if pres_sim:
        ec = pres_sim["electoral_college"]
        print(f"  Sim (latest cycle) mean Dem EV: {ec['mean_dem_ev']:.0f} "
              f"| P(Dem EC majority): {ec['p_dem_majority']:.2f}")
    if house_sim:
        print(f"  House sim mean Dem seats: {house_sim['mean_dem_seats']:.0f}/"
              f"{house_sim['n_units']} | P(Dem control): {house_sim['p_dem_control']:.2f}")
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
    args = ap.parse_args(argv)
    build(Path(args.base), allow_network=not args.offline)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

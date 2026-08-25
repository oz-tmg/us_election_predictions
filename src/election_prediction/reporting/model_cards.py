"""Model cards and the forecast backtest report.

Every model publishes a model card (CLAUDE.md §6, docs/methodology.md "Minimum Model
Card"): name/version, office+geography, training cycles, sources+snapshots, target,
features, exclusions, assumptions, failure modes, privacy tier, backtest + calibration
results, owner, review date. The forecast report summarizes the backtest honestly, with
historical-vs-modeled labelling and close-races-look-close framing.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path


def _synthetic_banner(synthetic: bool) -> str:
    if not synthetic:
        return ""
    return (
        "> ⚠️ **SYNTHETIC DATA.** This run used a fictional fixture matching the MEDSL "
        "schema because live data access was unavailable. Numbers below are illustrative "
        "of the *pipeline*, not real electoral estimates. Re-run with real snapshots to "
        "publish.\n\n"
    )


def write_presidential_model_card(results: dict, reports_dir: str | Path, *, synthetic: bool = False) -> Path:
    pres = results["presidential"]
    m = pres.get("demographics_backtest", {})
    ev = pres.get("demographics_eval", {})
    out_dir = Path(reports_dir) / "model_cards"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "presidential_fundamentals_v0.md"

    def g(d, k, fmt="{:.4f}"):
        v = d.get(k)
        return fmt.format(v) if isinstance(v, (int, float)) else "n/a"

    lines = [
        "# Model Card — Presidential Fundamentals Baseline v0",
        "",
        _synthetic_banner(synthetic).rstrip(),
        "",
        "## Identity",
        "",
        "- **Name / version:** presidential_fundamentals · v0",
        "- **Office / geography:** U.S. President · state (two-party Democratic vote share)",
        "- **Type:** transparent fundamentals baseline (polls-free), OLS",
        "- **Privacy tier:** 0 (public aggregate)",
        f"- **Owner:** project-owner (data steward) · **Review date:** {date.today().isoformat()}",
        "",
        "## Data",
        "",
        "- **Sources:** MEDSL president returns (state, two-party basis); Census ACS 5-year "
        "state demographics. Snapshot dates recorded in `data/manifests/`.",
        f"- **Training cycles:** backtested leave-one-cycle-out (n={m.get('n', 'n/a')} state-cycles).",
        "- **Target:** state two-party Democratic vote share.",
        "- **Features:** previous-cycle state share (F-002), national environment, college share (F-006).",
        "",
        "## Assumptions & exclusions",
        "",
        "- Two-party share basis; third-party votes excluded from the target (CLAUDE.md §6).",
        "- Like-for-like geography; states with no prior-cycle lag are excluded from training.",
        "- Linear, additive effects; no polling signal (baseline by design).",
        "",
        "## Backtest (leave-one-cycle-out)",
        "",
        f"- **MAE (vote share):** {g(m, 'mae')}  ·  **RMSE:** {g(m, 'rmse')}",
        f"- **Naive persistence MAE:** {g(m, 'naive_persistence_mae')} (baseline the model must beat)",
        f"- **Winner accuracy:** {g(m, 'winner_accuracy', '{:.3f}')}",
        f"- **Brier (win prob):** {g(ev, 'brier')}  ·  **Log score:** {g(ev, 'log_score')}",
        f"- **ECE (calibration):** {g(ev, 'ece')}  ·  **90% interval coverage:** "
        f"{g(ev, 'coverage_90', '{:.3f}')}",
        "",
        "## Failure modes",
        "",
        "- Correlated national polling/environment misses (mitigated by the correlated "
        "simulation layer, not by this point model).",
        "- Redistricting / boundary changes do not affect state-level presidential, but do "
        "affect the House score built alongside it.",
        "- Realignment cycles where past vote is a poor guide.",
        "",
        "## Intended use",
        "",
        "Transparent prior and evaluation benchmark. Not a published live forecast; historical "
        "backtest only (PROJECT_CONTEXT §4).",
        "",
    ]
    path.write_text("\n".join(x for x in lines if x is not None))
    return path


def write_forecast_report(results: dict, reports_dir: str | Path, *, synthetic: bool = False) -> Path:
    pres = results["presidential"]
    m_base = pres.get("baseline_backtest", {})
    m_demo = pres.get("demographics_backtest", {})
    ev = pres.get("demographics_eval", {})
    sim = pres.get("simulation", {})
    house = results.get("house", {})
    hs = house.get("seat_simulation", {})

    out = Path(reports_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "forecast_backtest_report.md"

    def f(d, k, fmt="{:.4f}"):
        v = d.get(k)
        return fmt.format(v) if isinstance(v, (int, float)) else "n/a"

    lines = [
        "# Forecast Backtest Report — P1 Baselines",
        "",
        f"_Generated: {date.today().isoformat()}_",
        "",
        _synthetic_banner(synthetic).rstrip(),
        "",
        "> Historical backtest only — no live forecast is published. Vote share and win "
        "probability are reported separately; close races are meant to look close.",
        "",
        "## Presidential fundamentals (state two-party Dem share)",
        "",
        "| Model | MAE | RMSE | Winner acc. |",
        "|---|---:|---:|---:|",
        f"| Naive persistence (prev cycle) | {f(m_base, 'naive_persistence_mae')} | — | — |",
        f"| Baseline (lag + national) | {f(m_base, 'mae')} | {f(m_base, 'rmse')} | "
        f"{f(m_base, 'winner_accuracy', '{:.3f}')} |",
        f"| + demographics (college share) | {f(m_demo, 'mae')} | {f(m_demo, 'rmse')} | "
        f"{f(m_demo, 'winner_accuracy', '{:.3f}')} |",
        "",
        "### Calibration (win probability, + demographics model)",
        "",
        f"- Brier score: **{f(ev, 'brier')}** · Log score: **{f(ev, 'log_score')}** · "
        f"ECE: **{f(ev, 'ece')}**",
        f"- Interval coverage — 90%: {f(ev, 'coverage_90', '{:.3f}')} · "
        f"95%: {f(ev, 'coverage_95', '{:.3f}')} (target ≈ nominal level)",
        "",
    ]

    cc = ev.get("calibration_curve") or []
    if cc:
        lines += [
            "### Reliability curve",
            "",
            "| Pred bin | n | mean pred | observed |",
            "|---|---:|---:|---:|",
        ]
        for r in cc:
            lines.append(
                f"| {r['bin_low']:.1f}–{r['bin_high']:.1f} | {r['n']} | "
                f"{r['mean_pred']:.3f} | {r['observed_freq']:.3f} |"
            )
        lines.append("")

    if sim:
        ec = sim.get("electoral_college", {})
        lines += [
            "## Correlated presidential simulation (latest backtested cycle)",
            "",
            "States are simulated with shared national + regional error (never independent).",
            "",
            f"- Mean Democratic electoral votes: **{f(ec, 'mean_dem_ev', '{:.0f}')}** "
            f"(90% range {f(ec, 'ev_5th', '{:.0f}')}–{f(ec, 'ev_95th', '{:.0f}')})",
            f"- P(Democratic EC majority ≥270): **{f(ec, 'p_dem_majority', '{:.2f}')}**",
            "",
        ]

    if hs:
        lines += [
            "## House correlated seat simulation",
            "",
            f"- Districts scored: {house.get('n_districts_scored', 'n/a')}",
            f"- Mean Democratic seats (of {hs.get('n_units', 'n/a')} simulated): "
            f"**{f(hs, 'mean_dem_seats', '{:.0f}')}** "
            f"(90% range {f(hs, 'seats_5th', '{:.0f}')}–{f(hs, 'seats_95th', '{:.0f}')})",
            f"- P(Democratic control): **{f(hs, 'p_dem_control', '{:.2f}')}**",
            "",
        ]

    lines += [
        "## Reading these numbers",
        "",
        "The baseline must beat naive persistence on MAE and stay calibrated (ECE near 0, "
        "coverage near nominal) before any complex model ships (CLAUDE.md §2 rule 5). The "
        "simulation converts vote-share uncertainty into seat/EC probabilities using correlated "
        "error, so a national miss moves many states together.",
        "",
        "See `reports/model_cards/` for the model card and `data/manifests/` for data lineage.",
        "",
    ]
    path.write_text("\n".join(x for x in lines if x is not None))
    return path

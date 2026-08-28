"""Model cards and the forecast backtest report.

Every model publishes a model card (CLAUDE.md §6, docs/methodology.md "Minimum Model
Card"): name/version, office+geography, training cycles, sources+snapshots, target,
features, exclusions, assumptions, failure modes, privacy tier, backtest + calibration
results, owner, review date. The forecast report summarizes the backtest honestly, with
historical-vs-modeled labelling and close-races-look-close framing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import pandas as pd


def _synthetic_banner(synthetic: bool) -> str:
    if not synthetic:
        return ""
    return (
        "> ⚠️ **SYNTHETIC DATA.** This run used a fictional fixture matching the MEDSL "
        "schema because live data access was unavailable. Numbers below are illustrative "
        "of the *pipeline*, not real electoral estimates. Re-run with real snapshots to "
        "publish.\n\n"
    )


@dataclass(frozen=True)
class ModelCard:
    """Reusable minimum model-card contract for every forecasting component."""

    name: str
    version: str
    office_geography: str
    model_type: str
    target: str
    training_cycles: str
    sources: list[str]
    features: list[str]
    exclusions: list[str]
    assumptions: list[str]
    failure_modes: list[str]
    intended_use: str
    metrics: dict[str, str | int | float] = field(default_factory=dict)
    privacy_tier: int = 0
    owner: str = "project-owner (data steward)"
    review_date: str = field(default_factory=lambda: date.today().isoformat())


def render_model_card(card: ModelCard, *, synthetic: bool = False) -> str:
    """Render a standardized Markdown model card with the required audit fields."""

    def bullets(values: list[str]) -> list[str]:
        return [f"- {value}" for value in values] or ["- None documented."]

    lines = [
        f"# Model Card — {card.name} {card.version}",
        "",
        _synthetic_banner(synthetic).rstrip(),
        "",
        "## Identity",
        "",
        f"- **Name / version:** {card.name} · {card.version}",
        f"- **Office / geography:** {card.office_geography}",
        f"- **Type:** {card.model_type}",
        f"- **Privacy tier:** {card.privacy_tier}",
        f"- **Owner:** {card.owner} · **Review date:** {card.review_date}",
        "",
        "## Data and target",
        "",
        f"- **Training/evaluation cycles:** {card.training_cycles}",
        f"- **Target:** {card.target}",
        "- **Sources:**",
        *[f"  - {source}" for source in card.sources],
        "",
        "## Features",
        "",
        *bullets(card.features),
        "",
        "## Exclusions",
        "",
        *bullets(card.exclusions),
        "",
        "## Assumptions",
        "",
        *bullets(card.assumptions),
        "",
        "## Evaluation",
        "",
    ]
    if card.metrics:
        lines.extend(f"- **{name}:** {value}" for name, value in card.metrics.items())
    else:
        lines.append("- Not yet outcome-evaluated; treat as a transparent baseline component.")
    lines.extend(
        [
            "",
            "## Failure modes",
            "",
            *bullets(card.failure_modes),
            "",
            "## Intended use",
            "",
            card.intended_use,
            "",
        ]
    )
    return "\n".join(lines)


def write_model_card(
    card: ModelCard,
    reports_dir: str | Path,
    *,
    filename: str,
    synthetic: bool = False,
) -> Path:
    out_dir = Path(reports_dir) / "model_cards"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / filename
    path.write_text(render_model_card(card, synthetic=synthetic))
    return path


def write_polling_model_card(results: dict, reports_dir: str | Path, *, synthetic: bool = False) -> Path:
    polling = results["polling"]
    card = ModelCard(
        name="polling_average",
        version="v0",
        office_geography="U.S. President · state (two-party Democratic vote share)",
        model_type="transparent weighted average + precision blend with fundamentals",
        target="State two-party Democratic vote share and simulated win probability.",
        training_cycles=str(polling.get("cycle", "n/a")),
        sources=[
            "Public pollster toplines supplied through the governed poll schema; "
            "row-level source URLs retained.",
            "MEDSL presidential returns and Census ACS fundamentals prior; snapshots in data/manifests/.",
        ],
        features=[
            "Exponential field-date decay (21-day half-life by default).",
            "Square-root sample-size weighting and LV/RV/adult population weights.",
            "Optional externally supplied Democratic house-effect adjustment; v0 does not estimate ratings.",
            "Fundamentals prior blended by inverse variance with a non-zero uncertainty floor.",
        ],
        exclusions=[
            "Respondent microdata and all personal/contact fields.",
            "Polls with invalid dates, samples, geography, source URLs, or vote-share ranges.",
            "Third-party/undecided allocation beyond conversion to reported D/R two-party share.",
        ],
        assumptions=[
            "Published toplines and metadata accurately describe the survey.",
            "The supplied house-effect value is independently governed and expressed as Democratic share.",
            "The precision blend is a transparent baseline, not a claim that polling and "
            "fundamentals errors are independent.",
            "Correlated national and regional simulation errors remain after averaging.",
        ],
        failure_modes=[
            "Correlated polling miss, nonresponse bias, or late movement shared across states.",
            "Sparse state polling lets one pollster or sponsor dominate despite explicit weighting.",
            "Mode/population labels are coarse quality proxies, not learned causal corrections.",
            "Synthetic fixture runs are pipeline tests and cannot support public forecasts.",
        ],
        intended_use=(
            "Auditable polling baseline and input to historical/scenario simulation. "
            "Publish only after real toplines, source licenses, and held-out calibration "
            "are reviewed. Never use it for person-level targeting."
        ),
        metrics={
            "Polls": polling.get("n_polls", "n/a"),
            "States/geographies averaged": polling.get("n_averages", "n/a"),
            "Mean effective polls": f"{polling.get('mean_effective_polls', float('nan')):.2f}",
            "Outcome calibration": "pending held-out real-poll backtest",
        },
    )
    return write_model_card(card, reports_dir, filename="polling_average_v0.md", synthetic=synthetic)


def write_polling_forecast_report(results: dict, reports_dir: str | Path, *, synthetic: bool = False) -> Path:
    """Write poll-average, blended-state, and correlated simulation outputs."""
    polling = results["polling"]
    sim = results["simulation"]
    ec = sim["electoral_college"]
    units = sim["unit_distributions"]
    if isinstance(units, list):
        units = pd.DataFrame(units)
    closest = units.assign(distance=(units["dem_win_prob"] - 0.5).abs()).sort_values("distance").head(12)
    path = Path(reports_dir) / "polling_forecast_report.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Polling + Fundamentals Scenario Report — P2 Baseline",
        "",
        f"_Generated: {date.today().isoformat()}_",
        "",
        _synthetic_banner(synthetic).rstrip(),
        "",
        "> Vote share, uncertainty, and win probability are separate outputs. This is a "
        "historical/scenario pipeline, not a deterministic race call.",
        "",
        "## Polling average",
        "",
        f"- Poll rows: **{polling['n_polls']}**",
        f"- State/geography averages: **{polling['n_averages']}**",
        f"- Mean effective polls per average: **{polling['mean_effective_polls']:.2f}**",
        f"- Data mode: **{results['data_mode']['polls']}**",
        "",
        "## Correlated Electoral College simulation",
        "",
        "Shared national and regional errors move states together; states are never simulated independently.",
        "",
        f"- Mean Democratic EV: **{ec['mean_dem_ev']:.0f}** "
        f"(90% range {ec['ev_5th']:.0f}–{ec['ev_95th']:.0f})",
        f"- P(Democratic EC majority ≥270): **{ec['p_dem_majority']:.3f}**",
        "",
        "## Closest state distributions",
        "",
        "| State | Mean D share | 90% share interval | P(D win) | Mean leader |",
        "|---|---:|---:|---:|:---:|",
    ]
    for row in closest.itertuples():
        lines.append(
            f"| {row.unit} | {row.mean_dem_share:.3f} | "
            f"{row.dem_share_5th:.3f}–{row.dem_share_95th:.3f} | "
            f"{row.dem_win_prob:.3f} | {row.mean_leader} |"
        )
    lines.extend(
        [
            "",
            "## Limitations",
            "",
            "The v0 average uses transparent fixed weights and supplied house-effect placeholders. "
            "It has not yet estimated pollster effects or completed a held-out real-poll backtest. "
            "See `reports/model_cards/polling_average_v0.md` before interpreting outputs.",
            "",
        ]
    )
    path.write_text("\n".join(lines))
    return path


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

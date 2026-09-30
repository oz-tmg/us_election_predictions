"""Figures for the public blog series (`blog/posts/`).

Every figure is built from a committed artefact of a real build — `reports/p1_results.json`
(P1 backtest, generated 2026-09-01), `reports/national_environment_2026-09-15.json`
(NE-001 band), and `reports/data_quality_report.md` counts — so a reader can trace any
number in a post back to the run that produced it (CLAUDE.md §8).

Nothing here imports the modelling layer except `models.simulation`, which figure 4 calls
directly to re-run the published House seat simulation under two correlation structures.
No figure recomputes a model; they render what the build already wrote.

Design follows one validated categorical palette (blue / orange / aqua), light surface.
Every figure carries period, geographic unit, source and snapshot date in its subtitle or
footer, and labels historical backtest vs. modelled projection (CLAUDE.md §6).

Run:  python blog/figures/make_figures.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"

# --- palette (validated: worst all-pairs CVD ΔE 9.2, normal-vision 24.0, light mode) ---
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"
S1 = "#2a78d6"  # blue   — slot 1
S2 = "#eb6834"  # orange — slot 2
S3 = "#1baf7a"  # aqua   — slot 3 (sub-3:1 on light: always direct-labelled)
CRITICAL = "#d03b3b"

Z90 = 1.6448536269514722

plt.rcParams.update(
    {
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "font.family": "sans-serif",
        "font.sans-serif": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
        "font.size": 10,
        "text.color": INK,
        "axes.labelcolor": INK_2,
        "axes.edgecolor": BASELINE,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "axes.grid": True,
        "grid.color": GRID,
        "grid.linewidth": 0.7,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "figure.dpi": 160,
    }
)

PCT = FuncFormatter(lambda v, _: f"{v:.0%}")


def _frame(ax: plt.Axes) -> None:
    ax.set_axisbelow(True)
    ax.tick_params(length=0)


def _canvas(
    width: float,
    plot_height: float,
    *,
    title: str,
    subtitle: str,
    footer: str,
    ncols: int = 1,
    left: float = 0.10,
    right: float = 0.985,
    xlabel_in: float = 0.58,
    wspace: float = 0.30,
    sharey: bool = False,
    panel_titles_in: float = 0.0,
):
    """A figure whose title, plot and footer occupy reserved, non-overlapping bands.

    Sizes are reasoned in inches and converted to figure fractions, so a caption of a
    different length moves the plot rather than colliding with it. ``plot_height`` is the
    height of the drawing area alone; title and footer are added on top of it.
    """
    title_in = 0.52 + 0.185 * (subtitle.count("\n") + 1) + panel_titles_in
    footer_in = 0.20 + 0.155 * (footer.count("\n") + 1) + xlabel_in
    height = plot_height + title_in + footer_in

    fig, axes = plt.subplots(1, ncols, figsize=(width, height), sharey=sharey)
    fig.subplots_adjust(
        top=1 - title_in / height,
        bottom=footer_in / height,
        left=left,
        right=right,
        wspace=wspace,
    )
    fig.text(0.012, 1 - 0.30 / height, title, ha="left", va="top", fontsize=13.5, fontweight="bold", color=INK)
    fig.text(0.012, 1 - 0.62 / height, subtitle, ha="left", va="top", fontsize=9.5, color=INK_2)
    fig.text(0.012, 0.10 / height, footer, ha="left", va="bottom", fontsize=7.8, color=MUTED)
    return fig, axes


def _save(fig: plt.Figure, name: str) -> None:
    path = OUT / name
    fig.savefig(path)
    plt.close(fig)
    print(f"wrote {path.relative_to(ROOT)}")


def load_p1() -> dict:
    return json.loads((REPORTS / "p1_results.json").read_text())


def load_band() -> dict:
    """Newest committed band. Dated filenames are the audit trail; the figure tracks head."""
    files = sorted(REPORTS.glob("national_environment_*.json"))
    if not files:
        raise FileNotFoundError("no reports/national_environment_*.json; run scripts/project_2026.py")
    return json.loads(files[-1].read_text())


# --------------------------------------------------------------------------------------
# Figure 1 — did the baseline beat the dumbest thing that could work?
# --------------------------------------------------------------------------------------
def fig01_mae(p1: dict) -> None:
    rows = [
        ("President\n(state)", p1["presidential"]["demographics_backtest"]),
        ("U.S. House\n(district)", p1["house"]["backtest"]),
        ("U.S. Senate\n(state)", p1["senate"]["backtest"]),
    ]
    labels = [r[0] for r in rows]
    naive = [r[1]["naive_persistence_mae"] for r in rows]
    model = [r[1]["mae"] for r in rows]
    n = [r[1]["n"] for r in rows]

    y = np.arange(len(rows))[::-1]
    h = 0.33
    fig, ax = _canvas(
        7.8,
        2.9,
        left=0.135,
        title="All three baselines beat doing nothing — by a little",
        subtitle="Leave-one-cycle-out backtest. “Naive persistence” repeats the geography’s own previous result\n"
        "(for the Senate, its last presidential vote). That margin is the entire case for the model.",
        footer="Historical backtest, not a forecast · unit: state (president, Senate), congressional district (House) · cycles 1976–2024\n"
        "Source: MIT Election Data & Science Lab certified returns; U.S. Census ACS 5-year (vintage 2023). Snapshot 2026-09-01.",
    )
    _frame(ax)
    ax.barh(y + h / 2 + 0.01, naive, height=h, color=MUTED, label="Naive persistence", zorder=3)
    ax.barh(y - h / 2 - 0.01, model, height=h, color=S1, label="Transparent baseline", zorder=3)

    for yi, v in zip(y, naive, strict=True):
        ax.text(v + 0.0016, yi + h / 2 + 0.01, f"{v:.4f}", va="center", fontsize=9, color=INK_2)
    for yi, v in zip(y, model, strict=True):
        ax.text(v + 0.0016, yi - h / 2 - 0.01, f"{v:.4f}", va="center", fontsize=9, fontweight="bold", color=INK)
    ax.set_yticks(y, [f"{lab}\nn = {nn:,}" for lab, nn in zip(labels, n, strict=True)], fontsize=9.4, color=INK_2)
    ax.set_xlim(0, 0.116)
    ax.set_xlabel("Mean absolute error, two-party Democratic vote share  (lower is better)")
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.02f}"))
    ax.grid(axis="y", visible=False)
    ax.legend(frameon=False, loc="upper right", fontsize=9, labelcolor=INK_2)
    _save(fig, "fig-01-baseline-vs-naive.png")


# --------------------------------------------------------------------------------------
# Figure 2 — reliability: does "70%" happen 70% of the time?
# --------------------------------------------------------------------------------------
def fig02_reliability(p1: dict) -> None:
    series = [
        ("President", p1["presidential"]["demographics_eval"], S1, "o"),
        ("U.S. House", p1["house"]["evaluation"], S2, "s"),
        ("U.S. Senate", p1["senate"]["evaluation"], S3, "D"),
    ]
    # Three near-identical curves overplot badly, so they are faceted rather than layered.
    fig, axes = _canvas(
        9.6,
        3.3,
        ncols=3,
        sharey=True,
        left=0.072,
        wspace=0.13,
        panel_titles_in=0.34,
        title="The reliability curve is where a forecast stops being an opinion",
        subtitle="Each marker is a probability bin; marker area is proportional to the number of races in it. On the\n"
        "dashed line a stated probability means what it says. Above it, too timid. Below it, too bold.",
        footer="Historical backtest, leave-one-cycle-out · unit: state (president, Senate), congressional district (House) · cycles 1976–2024\n"
        "Uncertainty: the middle bins are thin (19–160 races for president and Senate), so the centre of each curve is the least trustworthy part.\n"
        "Annotation marks each office’s largest deviation among bins holding at least 20 races. Source: MEDSL certified returns. Snapshot 2026-09-01.",
    )
    for ax, (name, ev, colour, _marker) in zip(axes, series, strict=True):
        _frame(ax)
        ax.plot([0, 1], [0, 1], color=BASELINE, lw=1.3, ls=(0, (4, 3)), zorder=2)
        curve = ev["calibration_curve"]
        x = np.array([c["mean_pred"] for c in curve])
        yv = np.array([c["observed_freq"] for c in curve])
        nn = np.array([c["n"] for c in curve], float)
        ax.plot(x, yv, color=colour, lw=2.0, zorder=4)
        ax.scatter(
            x, yv, s=14 + 110 * np.sqrt(nn / nn.max()), color=colour, edgecolor=SURFACE, linewidth=1.3, zorder=5
        )

        eligible = nn >= 20
        k = int(np.argmax(np.where(eligible, np.abs(yv - x), -1)))
        over = yv[k] < x[k]
        ax.annotate(
            f"{'too bold' if over else 'too timid'}\nsaid {x[k]:.0%}, happened {yv[k]:.0%}\n(n = {nn[k]:,.0f})",
            xy=(x[k], yv[k]),
            xytext=(0.05, 0.955),
            textcoords="axes fraction",
            ha="left",
            va="top",
            fontsize=8.1,
            color=INK_2,
            arrowprops={"arrowstyle": "-", "color": MUTED, "lw": 0.9},
        )

        ax.set_xlim(-0.03, 1.03)
        ax.set_ylim(-0.03, 1.03)
        ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
        ax.xaxis.set_major_formatter(PCT)
        ax.yaxis.set_major_formatter(PCT)
        ax.set_title(f"{name}  ·  ECE {ev['ece']:.3f}", fontsize=10, color=INK, fontweight="bold", pad=9)
        ax.set_xlabel("Forecast win probability")
    axes[0].set_ylabel("Share actually won")
    _save(fig, "fig-02-reliability-curve.png")


# --------------------------------------------------------------------------------------
# Figure 3 — interval coverage against its own promise
# --------------------------------------------------------------------------------------
def fig03_coverage(p1: dict) -> None:
    offices = [
        ("President", p1["presidential"]["demographics_eval"], S1),
        ("U.S. House", p1["house"]["evaluation"], S2),
        ("U.S. Senate", p1["senate"]["evaluation"], S3),
    ]
    fig, axes = _canvas(
        8.6,
        2.6,
        ncols=2,
        sharey=True,
        left=0.105,
        wspace=0.16,
        panel_titles_in=0.40,
        title="Coverage: the interval’s own promise, audited",
        subtitle="A 90% interval should contain the truth 90% of the time. Left of the dashed line the model is\n"
        "overconfident; right of it, needlessly vague. Both are errors — only one of them embarrasses you.",
        footer="Historical backtest, leave-one-cycle-out · cycles 1976–2024 · unit: state / congressional district\n"
        "Source: MIT Election Data & Science Lab certified returns. Snapshot 2026-09-01.",
    )
    for ax, (key, nominal, panel) in zip(
        axes, [("coverage_90", 0.90, "90% interval"), ("coverage_95", 0.95, "95% interval")], strict=True
    ):
        _frame(ax)
        ax.axvline(nominal, color=BASELINE, lw=1.4, ls=(0, (4, 3)), zorder=2)
        y = np.arange(len(offices))[::-1]
        for yi, (_name, ev, colour) in zip(y, offices, strict=True):
            v = ev[key]
            ax.plot([nominal, v], [yi, yi], color=colour, lw=2.0, zorder=3)
            ax.scatter([v], [yi], s=95, color=colour, edgecolor=SURFACE, linewidth=1.6, zorder=4)
            off = 0.005 if v >= nominal else -0.005
            ax.text(
                v + off,
                yi + 0.17,
                f"{v:.1%}",
                fontsize=9,
                color=INK,
                fontweight="bold",
                ha="left" if v >= nominal else "right",
            )
        ax.set_yticks(y, [o[0] for o in offices], fontsize=9.6, color=INK_2)
        ax.set_ylim(-0.55, 2.62)
        ax.set_xlim(0.815, 0.975)
        ax.set_xticks([0.85, 0.90, 0.95])
        ax.set_title(f"{panel} — promised {nominal:.0%}", fontsize=10, color=INK, fontweight="bold", pad=10)
        ax.xaxis.set_major_formatter(PCT)
        ax.grid(axis="y", visible=False)
    _save(fig, "fig-03-interval-coverage.png")


# --------------------------------------------------------------------------------------
# Figure 4 — the same means, two correlation structures
# --------------------------------------------------------------------------------------
def fig04_correlation(p1: dict) -> dict:
    """Re-run the published 435-seat House simulation with and without shared error.

    Means are the fitted district means from the published run. Per-seat sigma is
    recovered from that run's own 5th/95th percentiles (marginal sigma is unchanged by
    the correlation structure), which reproduces the run's two documented regimes: the
    model seats at ~0.113 and the widened partisanship-prior seats at ~0.223. Seats whose
    interval hit a 0/1 bound are assigned the model sigma; they are safe seats where
    sigma barely moves a seat count. Only the correlation structure differs between the
    two histograms.
    """
    sys.path.insert(0, str(ROOT / "src"))
    from election_prediction.geography import reference as ref
    from election_prediction.models.simulation import CorrelationParams, seat_distribution, simulate_shares

    units = p1["house"]["unit_distributions"]
    ids = [u["unit"] for u in units]
    means = np.array([u["mean_dem_share"] for u in units])
    lo = np.array([u["dem_share_5th"] for u in units])
    hi = np.array([u["dem_share_95th"] for u in units])

    sigma = (hi - lo) / (2 * Z90)
    clipped = (lo <= 1e-9) | (hi >= 1 - 1e-9)
    model_sigma = float(np.median(sigma[~clipped & (sigma < 0.17)]))
    sigma[clipped] = model_sigma

    # unit ids are canonical geography keys, e.g. "state:01|district:cong_03"
    regions = [ref.by_fips(u.split("|")[0].split(":")[1]).census_region for u in ids]

    corr = simulate_shares(means, sigma, regions, n_sims=20_000, params=CorrelationParams(), seed=7)
    indep = simulate_shares(
        means, sigma, regions, n_sims=20_000, params=CorrelationParams(0.0, 0.0, 1.0), seed=7
    )
    d_corr = seat_distribution(corr, ids, total_seats=435)
    d_indep = seat_distribution(indep, ids, total_seats=435)

    seats_corr = (corr > 0.5).sum(axis=1)
    seats_indep = (indep > 0.5).sum(axis=1)

    fig, ax = _canvas(
        8.6,
        4.1,
        left=0.065,
        title="One modelling choice, two completely different forecasts",
        subtitle="Identical district means, identical per-seat uncertainty. The only difference is whether a national\n"
        "miss is allowed to move every district at once. The narrow one is the model that sounds confident.",
        footer="Re-simulation of the published 2024 backtest seat universe (435 seats, 2022 plan era) · 20,000 draws · seed 7\n"
        "Uncertainty: per-seat sigma recovered from the published run’s own intervals; only the correlation structure differs.\n"
        "Source: MIT Election Data & Science Lab certified returns; blog/figures/make_figures.py. Snapshot 2026-09-01.",
    )
    _frame(ax)
    bins = np.arange(90, 344, 4)
    ax.hist(
        seats_corr,
        bins=bins,
        color=S1,
        alpha=0.9,
        label=f"Correlated error, as published — 90% range {d_corr['seats_5th']:.0f}–{d_corr['seats_95th']:.0f} seats",
        zorder=3,
    )
    ax.hist(
        seats_indep,
        bins=bins,
        color=S2,
        alpha=0.9,
        label=f"Independent error — 90% range {d_indep['seats_5th']:.0f}–{d_indep['seats_95th']:.0f} seats",
        zorder=4,
    )
    top = ax.get_ylim()[1]
    ax.set_ylim(0, top * 1.46)
    ax.set_xlim(90, 344)
    ax.axvline(217.5, color=CRITICAL, lw=1.6, zorder=5)
    ax.text(214, top * 1.03, "218 = control", fontsize=8.6, color=CRITICAL, va="bottom", ha="right")

    ax.annotate(
        f"Independent errors\nmean {d_indep['mean_dem_seats']:.0f} seats · 90% range only "
        f"{d_indep['seats_95th'] - d_indep['seats_5th']:.0f} seats wide\nP(control) = {d_indep['p_dem_control']:.0%}",
        xy=(226, top * 0.34),
        xytext=(258, top * 0.74),
        fontsize=8.7,
        color=INK_2,
        arrowprops={"arrowstyle": "-", "color": MUTED, "lw": 0.9},
    )
    ax.annotate(
        f"Same means, shared shocks\nmean {d_corr['mean_dem_seats']:.0f} seats · 90% range spans "
        f"{d_corr['seats_95th'] - d_corr['seats_5th']:.0f} seats\nP(control) = {d_corr['p_dem_control']:.0%}",
        xy=(140, top * 0.10),
        xytext=(99, top * 0.52),
        fontsize=8.7,
        color=INK_2,
        arrowprops={"arrowstyle": "-", "color": MUTED, "lw": 0.9},
    )

    ax.set_xlabel("Simulated Democratic seats, 435-seat House")
    ax.set_ylabel("Simulations (of 20,000)")
    ax.set_yticks([])
    ax.legend(frameon=False, loc="upper left", fontsize=8.8, labelcolor=INK_2)
    ax.grid(axis="y", visible=False)
    _save(fig, "fig-04-correlated-vs-independent.png")
    return {"correlated": d_corr, "independent": d_indep, "model_sigma": model_sigma}


# --------------------------------------------------------------------------------------
# Figure 5 — the parameter that isn't there
# --------------------------------------------------------------------------------------
def fig05_swing_ratio(p1: dict) -> None:
    eras = p1["national_swing"]["by_plan_era"]
    pooled = p1["national_swing"]["pooled"]
    x = np.arange(len(eras))
    fig, ax = _canvas(
        8.2,
        4.0,
        left=0.085,
        panel_titles_in=0.16,
        title="Five estimates, one void — and the void is the current cycle",
        subtitle="How far a district moves when the nation moves a point. Wobbly but estimable for fifty years, then\n"
        "the 2022 maps arrive with a single observable swing and the estimate ceases to exist. Not zero. Absent.",
        footer="Estimated within redistricting eras on certified returns, uncontested races excluded · unit: congressional district\n"
        "Uncertainty: pooled R² is 0.082 — national swing explains only a small share of district movement, which is itself the finding.\n"
        "Source: MIT Election Data & Science Lab certified returns, cycles 1976–2024. Snapshot 2026-09-01.",
    )
    _frame(ax)
    ax.axhline(1.0, color=BASELINE, lw=1.4, ls=(0, (4, 3)), zorder=2)
    ax.text(len(eras) - 0.42, 1.006, "uniform swing = 1.0", fontsize=8.4, color=MUTED, va="bottom", ha="right")

    for xi, era in zip(x, eras, strict=True):
        ok = era["status"] == "ok"
        if ok:
            r = era["swing_ratio"]
            ax.plot([xi, xi], [1.0, r], color=S1, lw=2.0, zorder=3)
            ax.scatter([xi], [r], s=110, color=S1, edgecolor=SURFACE, linewidth=1.7, zorder=4)
            ax.text(xi, r + (0.035 if r >= 1 else -0.055), f"{r:.2f}", ha="center", fontsize=9.2, color=INK, fontweight="bold")
        else:
            ax.scatter([xi], [1.0], s=115, facecolor=SURFACE, edgecolor=CRITICAL, linewidth=1.8, zorder=4)
            ax.annotate(
                "unidentified\nonly one swing\nobservable (2022 to 2024)",
                xy=(xi, 1.0),
                xytext=(xi - 0.05, 0.70),
                fontsize=8.6,
                color=CRITICAL,
                ha="center",
                arrowprops={"arrowstyle": "-", "color": CRITICAL, "lw": 0.9},
            )
        ax.text(xi, 0.622, f"n = {era['n']:,}", ha="center", fontsize=8.2, color=MUTED)

    ax.set_xticks(x, [f"{e['plan_era']}s\nmaps" for e in eras], fontsize=9.4, color=INK_2)
    ax.set_ylim(0.58, 1.32)
    ax.set_ylabel("Swing ratio (district swing per point of national swing)")
    ax.set_xlim(-0.6, len(eras) - 0.4)
    ax.grid(axis="x", visible=False)
    ax.text(
        0.012,
        0.975,
        f"Pooled across all eras: {pooled['swing_ratio']:.3f}   ·   R² = {pooled['r_squared']:.3f}   ·   "
        f"residual sd = {pooled['residual_sigma']:.3f}",
        transform=ax.transAxes,
        va="top",
        fontsize=8.6,
        color=INK_2,
    )
    _save(fig, "fig-05-swing-ratio-by-era.png")


# --------------------------------------------------------------------------------------
# Figure 6 — the band, and the chamber it cannot resolve
# --------------------------------------------------------------------------------------
def fig06_band(band: dict) -> None:
    rows = band["band_results"]
    shr = np.array([r["shrinkage"] for r in rows])
    hp = np.array([r["house_p_dem"] for r in rows])
    sp = np.array([r["sen_p_dem"] for r in rows])
    hm = np.array([r["house_mean_seats"] for r in rows])
    h5 = np.array([r["house_5th"] for r in rows])
    h95 = np.array([r["house_95th"] for r in rows])

    fig, (ax1, ax2) = _canvas(
        9.4,
        3.6,
        ncols=2,
        left=0.075,
        wspace=0.26,
        panel_titles_in=0.34,
        title="A band, not a number — because the number is an assumption",
        subtitle="Special elections say the environment moved; nothing in the data says how much of that carries into a\n"
        "general election. So the x-axis is an assumption we sweep, not a parameter we fitted. Read the whole line.",
        footer="Modelled projection for 2026-11-03, NOT published as a forecast · n = 8 compiled special elections, 2025-04-01 to 2026-06-16\n"
        "Uncertainty: shrinkage is an assumption with no historical calibration; plotted standard errors cover sampling across specials only.\n"
        "All 435 House seats carry boundary_confidence = unverified. Source: compiled specials + MEDSL certified returns. Snapshot 2026-09-30.",
    )
    _frame(ax1)
    ax1.axhline(0.5, color=BASELINE, lw=1.4, ls=(0, (4, 3)), zorder=2)
    ax1.text(1.02, 0.505, "coin flip", fontsize=8.2, color=MUTED, va="bottom", ha="right")
    ax1.plot(shr, hp, color=S1, lw=2.2, marker="o", ms=7.5, mec=SURFACE, mew=1.5, zorder=4, label="House")
    ax1.plot(shr, sp, color=S2, lw=2.2, marker="s", ms=7.5, mec=SURFACE, mew=1.5, zorder=4, label="Senate")
    ax1.text(0.60, 0.695, "House", color=S1, fontsize=10, fontweight="bold")
    ax1.text(0.60, 0.345, "Senate", color=S2, fontsize=10, fontweight="bold")
    ax1.fill_between(shr, 0.5, sp, where=sp < 0.5, color=S2, alpha=0.10, zorder=1)
    ax1.set_ylim(0.20, 0.86)
    ax1.set_xlim(0.18, 1.07)
    ax1.yaxis.set_major_formatter(PCT)
    ax1.set_ylabel("P(Democratic chamber control)")
    ax1.set_xlabel("Assumed shrinkage factor")
    ax1.set_title("One chamber answers, one refuses", fontsize=10, color=INK_2, pad=9)
    ax1.legend(frameon=False, loc="upper left", fontsize=8.8, labelcolor=INK_2)

    _frame(ax2)
    ax2.fill_between(shr, h5, h95, color=S1, alpha=0.16, zorder=2, label="90% simulation range")
    ax2.plot(shr, hm, color=S1, lw=2.2, marker="o", ms=7.5, mec=SURFACE, mew=1.5, zorder=4, label="Mean seats")
    ax2.axhline(217.5, color=CRITICAL, lw=1.6, zorder=3)
    ax2.text(1.05, 221, "218 = control", fontsize=8.4, color=CRITICAL, ha="right")
    ax2.set_ylim(100, 390)
    ax2.set_xlim(0.18, 1.07)
    ax2.set_ylabel("Democratic seats, 435-seat House")
    ax2.set_xlabel("Assumed shrinkage factor")
    ax2.set_title("The seat range never stops straddling 218", fontsize=10, color=INK_2, pad=9)
    ax2.legend(frameon=False, loc="lower right", fontsize=8.8, labelcolor=INK_2)
    _save(fig, "fig-06-shrinkage-band.png")


# --------------------------------------------------------------------------------------
# Figure 7 — the 34 races we threw away, and what it cost
# --------------------------------------------------------------------------------------
def fig07_quarantine() -> None:
    # Counts as published in reports/data_quality_report.md (snapshot 2026-09-01).
    reasons = [
        ("Candidate votes exceed the reported total", 28),
        ("Rounding / transcription (≤10 votes)", 3),
        ("Candidate votes fall below the total", 2),
        ("Multi-round contest suspected (~2× total)", 1),
    ]
    labels = [r[0] for r in reasons]
    vals = [r[1] for r in reasons]
    y = np.arange(len(reasons))[::-1]

    fig, ax = _canvas(
        8.4,
        2.5,
        left=0.335,
        title="Thirty-four races that do not add up",
        subtitle="Races where the candidates’ votes and the jurisdiction’s own reported total disagree. Excluded\n"
        "uniformly, kept on disk with a reason — not silently repaired, and not dropped from the seat count.",
        footer="Historical certified returns · unit: race · cycles 1976–2024 · reason labels are descriptive, not adjudicated\n"
        "Source: MIT Election Data & Science Lab; reports/data_quality_report.md. Snapshot 2026-09-01.",
    )
    _frame(ax)
    ax.barh(y, vals, height=0.62, color=S1, zorder=3)
    for yi, v in zip(y, vals, strict=True):
        ax.text(v + 0.42, yi, str(v), va="center", fontsize=9.6, fontweight="bold", color=INK)
    ax.set_yticks(y, labels, fontsize=9.2, color=INK_2)
    ax.set_xlim(0, 33)
    ax.set_xlabel("Races quarantined")
    ax.grid(axis="y", visible=False)
    ax.text(
        0.995,
        0.06,
        "34 of 12,392 races (0.27%)\nRefitting with them included moves\npresidential MAE by +0.000089",
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=8.8,
        color=INK_2,
    )
    _save(fig, "fig-07-quarantine.png")


def main() -> int:
    p1 = load_p1()
    band = load_band()
    fig01_mae(p1)
    fig02_reliability(p1)
    fig03_coverage(p1)
    sim = fig04_correlation(p1)
    fig05_swing_ratio(p1)
    fig06_band(band)
    fig07_quarantine()
    print("\nfigure 4 numbers (for the post body):")
    print(json.dumps(sim, indent=2, default=float))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

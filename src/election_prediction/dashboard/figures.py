"""Plotly figure builders. Pure functions of bundle tables; no I/O, no modelling.

Colour has one job per chart. Probability and two-party share use a red–grey–blue
diverging scale whose grey midpoint is "even", so a close race *looks* close (CLAUDE.md
§2.3); nothing is painted a solid "called" colour. Charts with a single measure use
neutral ink so party hues never carry an unrelated meaning. "No contest" and "uncontested"
use a darker grey than the diverging midpoint and say so in the hover and the legend.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Chrome and ink (light surface).
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
NO_CONTEST = "#b4b3ab"
FONT = 'system-ui, -apple-system, "Segoe UI", sans-serif'

# Diverging: Republican pole (0) – neutral grey (0.5) – Democratic pole (1).
DIVERGING = [
    [0.0, "#8f1f22"],
    [0.2, "#e34948"],
    [0.4, "#f3b7b4"],
    [0.5, "#f0efec"],
    [0.6, "#b7d3f6"],
    [0.8, "#2a78d6"],
    [1.0, "#184f95"],
]

Z_90 = 1.6448536269514722  # two-sided 90% normal interval
FALLBACK_SOURCES = {"fallback_state_lean"}


def _base_layout(fig: go.Figure, *, height: int = 420) -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=48, r=24, t=16, b=40),
        paper_bgcolor=SURFACE,
        plot_bgcolor=SURFACE,
        font=dict(family=FONT, color=INK_2, size=13),
        hoverlabel=dict(bgcolor="white", font=dict(family=FONT, color=INK)),
        showlegend=False,
    )
    fig.update_xaxes(gridcolor=GRID, linecolor=AXIS, zeroline=False, tickfont=dict(color=MUTED))
    fig.update_yaxes(gridcolor=GRID, linecolor=AXIS, zeroline=False, tickfont=dict(color=MUTED))
    return fig


def _pct(x: float) -> str:
    return "—" if pd.isna(x) else f"{100 * x:.0f}%"


def interval_90(mean: pd.Series, sigma: pd.Series) -> tuple[pd.Series, pd.Series]:
    """The seat's own marginal 90% interval on two-party share, clipped to [0, 1]."""
    return (mean - Z_90 * sigma).clip(0, 1), (mean + Z_90 * sigma).clip(0, 1)


def _colorbar(title: str, tickvals: list[float], ticktext: list[str]) -> dict[str, Any]:
    # Horizontal, under the map: a vertical bar takes a third of a phone's width.
    return dict(
        title=dict(text=title, side="top", font=dict(color=INK_2, size=12)),
        tickvals=tickvals,
        ticktext=ticktext,
        tickfont=dict(color=MUTED, size=11),
        orientation="h",
        x=0.5,
        xanchor="center",
        y=-0.02,
        yanchor="top",
        len=0.7,
        thickness=10,
        outlinewidth=0,
    )


def _prob_colorbar(title: str) -> dict[str, Any]:
    return _colorbar(title, [0, 0.25, 0.5, 0.75, 1], ["R 100%", "R 75%", "Even", "D 75%", "D 100%"])


def _us_geo(fig: go.Figure) -> go.Figure:
    fig.update_geos(
        scope="usa",
        bgcolor=SURFACE,
        showlakes=False,
        showland=True,
        landcolor=NO_CONTEST,
        subunitcolor=SURFACE,
    )
    fig.update_layout(margin=dict(l=0, r=0, t=28, b=64))
    return fig


def _no_contest_note(fig: go.Figure, text: str) -> None:
    fig.add_annotation(
        text=f"<span style='color:{NO_CONTEST}'>■</span> {text}",
        x=0.0,
        y=1.0,
        yanchor="bottom",
        xref="paper",
        yref="paper",
        showarrow=False,
        font=dict(color=INK_2, size=12),
        xanchor="left",
    )


def senate_map(seats: pd.DataFrame) -> go.Figure:
    """One assumption's Senate contests, coloured by P(Democratic win)."""
    s = seats[seats["office"] == "us_senate"].copy()
    lo, hi = interval_90(s["mean_dem_share"], s["sigma"])
    s["hover"] = [
        f"<b>{st}</b><br>P(Democratic win) {_pct(p)}<br>"
        f"Two-party Dem share {_pct(m)} (90%: {_pct(a)}–{_pct(b)})"
        for st, p, m, a, b in zip(s["state_po"], s["dem_win_prob"], s["mean_dem_share"], lo, hi, strict=True)
    ]
    # Two contests in one state (a special beside a regular race) share one shape; the map
    # shows the closer race and the hover says there is another.
    s["closeness"] = (s["dem_win_prob"] - 0.5).abs()
    counts = s.groupby("state_po")["geography_id"].transform("size")
    s.loc[counts > 1, "hover"] += "<br><i>Two contests in this state — see Races</i>"
    s = s.sort_values("closeness").drop_duplicates("state_po")

    fig = go.Figure(
        go.Choropleth(
            locations=s["state_po"],
            locationmode="USA-states",
            z=s["dem_win_prob"],
            zmin=0,
            zmax=1,
            colorscale=DIVERGING,
            marker_line_color=SURFACE,
            marker_line_width=1,
            text=s["hover"],
            hovertemplate="%{text}<extra></extra>",
            colorbar=_prob_colorbar("P(Democratic win)"),
        )
    )
    _us_geo(_base_layout(fig, height=460))
    _no_contest_note(fig, "No Senate contest this cycle")
    return fig


def history_map(results: pd.DataFrame, office: str, cycle: int) -> go.Figure:
    """Certified two-party Democratic share by state for one office and cycle."""
    r = results[
        (results["office"] == office)
        & (results["cycle"] == cycle)
        & (results["race_type"] == "gen")
        & (results["geography_id"].str.count(r"\|") == 0)
    ].copy()
    contested = r[~r["uncontested_flag"].astype(bool)]
    uncontested = r[r["uncontested_flag"].astype(bool)]
    fig = go.Figure(
        go.Choropleth(
            locations=contested["state_po"],
            locationmode="USA-states",
            z=contested["two_party_dem_share"],
            zmin=0.25,
            zmax=0.75,
            colorscale=DIVERGING,
            marker_line_color=SURFACE,
            marker_line_width=1,
            customdata=np.stack(
                [
                    contested["winner_party"].str.title(),
                    contested["certified_flag"].map({True: "Certified", False: "Not marked certified"}),
                ],
                axis=-1,
            )
            if len(contested)
            else None,
            hovertemplate=(
                "<b>%{location}</b><br>Two-party Dem share %{z:.1%}<br>"
                "Winner: %{customdata[0]}<br>%{customdata[1]}<extra></extra>"
            ),
            colorbar=_colorbar("Two-party Dem share", [0.25, 0.5, 0.75], ["≤25%", "50%", "≥75%"]),
        )
    )
    if len(uncontested):
        fig.add_trace(
            go.Choropleth(
                locations=uncontested["state_po"],
                locationmode="USA-states",
                z=np.zeros(len(uncontested)),
                colorscale=[[0, NO_CONTEST], [1, NO_CONTEST]],
                showscale=False,
                marker_line_color=SURFACE,
                customdata=uncontested["winner_party"].str.title(),
                hovertemplate=(
                    "<b>%{location}</b><br>Uncontested — no two-party share<br>"
                    "Winner: %{customdata}<extra></extra>"
                ),
            )
        )
    _us_geo(_base_layout(fig, height=460))
    _no_contest_note(fig, "No contest, or uncontested (never shown as 100–0)")
    return fig


def house_strip(seats: pd.DataFrame) -> go.Figure:
    """All House seats ordered by P(Democratic win). Hollow markers are state-lean fallbacks."""
    h = seats[seats["office"] == "us_house"].sort_values("dem_win_prob", ascending=False).copy()
    h["rank"] = np.arange(1, len(h) + 1)
    lo, hi = interval_90(h["mean_dem_share"], h["sigma"])
    h["label"] = h["state_po"] + "-" + h["district_num"].fillna(0).astype(int).astype(str).str.zfill(2)
    h["hover"] = [
        f"<b>{lab}</b><br>P(Democratic win) {_pct(p)}<br>"
        f"Two-party Dem share {_pct(m)} (90%: {_pct(a)}–{_pct(b)})<br>"
        f"Prior: {src.replace('_', ' ')} · boundaries {bc}"
        for lab, p, m, a, b, src, bc in zip(
            h["label"],
            h["dem_win_prob"],
            h["mean_dem_share"],
            lo,
            hi,
            h["source"],
            h["boundary_confidence"].fillna("n/a"),
            strict=True,
        )
    ]
    fallback = h["source"].isin(FALLBACK_SOURCES)
    fig = go.Figure()
    for mask, symbol in ((~fallback, "circle"), (fallback, "circle-open")):
        part = h[mask]
        fig.add_trace(
            go.Scatter(
                x=part["rank"],
                y=part["dem_win_prob"],
                mode="markers",
                marker=dict(
                    symbol=symbol,
                    size=8,
                    color=part["dem_win_prob"],
                    colorscale=DIVERGING,
                    cmin=0,
                    cmax=1,
                    line=dict(width=1.5, color=part["dem_win_prob"] if symbol == "circle-open" else SURFACE),
                ),
                text=part["hover"],
                hovertemplate="%{text}<extra></extra>",
            )
        )
    fig.add_hline(y=0.5, line=dict(color=AXIS, width=1, dash="dot"))
    fig.add_vline(x=218, line=dict(color=AXIS, width=1))
    fig.add_annotation(
        x=218,
        y=1.04,
        yref="y",
        text="218th seat",
        showarrow=False,
        font=dict(color=MUTED, size=11),
        xanchor="left",
    )
    _base_layout(fig, height=380)
    fig.update_xaxes(
        title=dict(text="Seats, ordered by P(Democratic win)", font=dict(color=INK_2)), range=[0, len(h) + 5]
    )
    fig.update_yaxes(
        title=dict(text="P(Democratic win)", font=dict(color=INK_2)), range=[-0.03, 1.08], tickformat=".0%"
    )
    return fig


def _shrinkage_axis(band: Sequence[Mapping[str, Any]]) -> list[str]:
    return [str(b["shrinkage"]) for b in band]


def house_band_chart(band: Sequence[Mapping[str, Any]]) -> go.Figure:
    """Mean Democratic House seats with the simulation's 5th–95th percentile, per assumption."""
    x = _shrinkage_axis(band)
    mean = [b["house_mean_seats"] for b in band]
    lo = [b["house_5th"] for b in band]
    hi = [b["house_95th"] for b in band]
    fig = go.Figure(
        go.Scatter(
            x=x,
            y=mean,
            mode="markers",
            marker=dict(size=10, color=INK_2),
            error_y=dict(
                type="data",
                symmetric=False,
                array=[h - m for h, m in zip(hi, mean, strict=True)],
                arrayminus=[m - lo_ for m, lo_ in zip(mean, lo, strict=True)],
                color=INK_2,
                thickness=2,
                width=6,
            ),
            customdata=np.stack([lo, hi], axis=-1),
            hovertemplate=(
                "Shrinkage %{x}<br>Mean %{y:.0f} Democratic seats<br>"
                "5th–95th: %{customdata[0]:.0f}–%{customdata[1]:.0f}<extra></extra>"
            ),
        )
    )
    fig.add_hline(
        y=218,
        line=dict(color=AXIS, width=1, dash="dot"),
        annotation_text="218 for control",
        annotation_font_color=MUTED,
    )
    _base_layout(fig, height=360)
    fig.update_xaxes(type="category", title=dict(text="Shrinkage assumption", font=dict(color=INK_2)))
    fig.update_yaxes(title=dict(text="Democratic House seats", font=dict(color=INK_2)), range=[0, 435])
    return fig


def control_chart(band: Sequence[Mapping[str, Any]]) -> go.Figure:
    """P(Democratic control) per assumption: House and Senate as small multiples."""
    x = _shrinkage_axis(band)
    fig = make_subplots(
        rows=1, cols=2, subplot_titles=("House", "Senate"), shared_yaxes=True, horizontal_spacing=0.08
    )
    for col, key in ((1, "house_p_dem"), (2, "sen_p_dem")):
        y = [b.get(key) for b in band]
        fig.add_trace(
            go.Scatter(
                x=x,
                y=y,
                mode="lines+markers",
                line=dict(color=INK_2, width=2),
                marker=dict(size=8, color=INK_2),
                hovertemplate="Shrinkage %{x}<br>P(Democratic control) %{y:.0%}<extra></extra>",
            ),
            row=1,
            col=col,
        )
        fig.add_hline(y=0.5, line=dict(color=AXIS, width=1, dash="dot"), row=1, col=col)
    _base_layout(fig, height=320)
    fig.update_xaxes(type="category", title=dict(text="Shrinkage assumption", font=dict(color=INK_2)))
    fig.update_yaxes(range=[0, 1], tickformat=".0%")
    fig.update_yaxes(title=dict(text="P(Democratic control)", font=dict(color=INK_2)), row=1, col=1)
    fig.update_annotations(font=dict(color=INK, size=13))
    return fig


OFFICE_TITLES = {
    "president": "President (state)",
    "us_house": "House (district)",
    "us_senate": "Senate (state)",
}


def calibration_chart(offices: Mapping[str, Mapping[str, Any]]) -> go.Figure:
    """Reliability curves, one panel per office. On the diagonal = calibrated."""
    names = list(offices)
    fig = make_subplots(
        rows=1,
        cols=len(names),
        shared_yaxes=True,
        horizontal_spacing=0.06,
        subplot_titles=[OFFICE_TITLES.get(n, n) for n in names],
    )
    for i, name in enumerate(names, start=1):
        curve = [b for b in offices[name]["calibration_curve"] if b.get("n")]
        fig.add_trace(
            go.Scatter(
                x=[0, 1], y=[0, 1], mode="lines", hoverinfo="skip", line=dict(color=AXIS, width=1, dash="dot")
            ),
            row=1,
            col=i,
        )
        fig.add_trace(
            go.Scatter(
                x=[b["mean_pred"] for b in curve],
                y=[b["observed_freq"] for b in curve],
                mode="lines+markers",
                line=dict(color=INK_2, width=2),
                marker=dict(size=8, color=INK_2),
                customdata=[b["n"] for b in curve],
                hovertemplate=("Predicted %{x:.0%}<br>Observed %{y:.0%}<br>n = %{customdata}<extra></extra>"),
            ),
            row=1,
            col=i,
        )
    _base_layout(fig, height=340)
    fig.update_xaxes(
        range=[0, 1], tickformat=".0%", title=dict(text="Predicted P(Dem win)", font=dict(color=INK_2))
    )
    fig.update_yaxes(range=[0, 1], tickformat=".0%")
    fig.update_yaxes(title=dict(text="Observed frequency", font=dict(color=INK_2)), row=1, col=1)
    fig.update_annotations(font=dict(color=INK, size=13))
    return fig


# --- Texas page -------------------------------------------------------------------------

# Run styles for comparing projections: ink weight and dash carry identity, not hue, so a
# party colour never stands in for a run.
RUN_STYLES = {
    "latest": dict(color=INK, width=2.5, dash="solid"),
    "scenario": dict(color=INK, width=2, dash="dash"),
    "previous": dict(color=MUTED, width=2, dash="solid"),
    "seal": dict(color=MUTED, width=2, dash="dot"),
}
POLL_BAND = "rgba(137, 135, 129, 0.16)"


def senate_runs_chart(
    runs: Sequence[tuple[str, str, pd.DataFrame]],
    state_po: str,
    poll: Mapping[str, float] | None = None,
) -> go.Figure:
    """One state's Senate mean share across the assumption band, for several runs.

    ``runs`` is ``(label, style, seats)`` with ``style`` a key of ``RUN_STYLES``. ``poll``
    (``poll_mean_dem_share``, ``poll_sigma``) is drawn as a shaded band: a cross-check
    beside the runs, not an input to them.
    """
    fig = go.Figure()
    if poll:
        lo = poll["poll_mean_dem_share"] - poll["poll_sigma"]
        hi = poll["poll_mean_dem_share"] + poll["poll_sigma"]
        fig.add_hrect(y0=lo, y1=hi, fillcolor=POLL_BAND, line_width=0, layer="below")
        fig.add_hline(
            y=poll["poll_mean_dem_share"],
            line=dict(color=MUTED, width=1, dash="dashdot"),
            annotation_text=f"Poll average {poll['poll_mean_dem_share']:.1%} ±{poll['poll_sigma']:.1%} "
            "(cross-check, not blended)",
            annotation_position="top left",
            annotation_font=dict(color=INK_2, size=11),
        )
    for label, style, seats in runs:
        s = seats[(seats["office"] == "us_senate") & (seats["state_po"] == state_po)].copy()
        s["shrinkage"] = s["assumption"].str.removeprefix("shrinkage=")
        lo, hi = interval_90(s["mean_dem_share"], s["sigma"])
        fig.add_trace(
            go.Scatter(
                x=s["shrinkage"],
                y=s["mean_dem_share"],
                mode="lines+markers",
                name=label,
                line=RUN_STYLES[style],
                marker=dict(size=8, color=RUN_STYLES[style]["color"]),
                customdata=np.stack([s["dem_win_prob"], lo, hi], axis=-1),
                hovertemplate=(
                    f"<b>{label}</b><br>Shrinkage %{{x}}<br>Dem two-party share %{{y:.1%}} "
                    "(90%: %{customdata[1]:.1%}–%{customdata[2]:.1%})<br>"
                    "P(Democratic win) %{customdata[0]:.0%}<extra></extra>"
                ),
            )
        )
    fig.add_hline(y=0.5, line=dict(color=AXIS, width=1, dash="dot"))
    _base_layout(fig, height=400)
    fig.update_layout(
        showlegend=True,
        legend=dict(orientation="h", x=0, y=1.12, font=dict(color=INK_2, size=12)),
        margin=dict(l=48, r=24, t=56, b=40),
    )
    fig.update_xaxes(type="category", title=dict(text="Shrinkage assumption", font=dict(color=INK_2)))
    fig.update_yaxes(title=dict(text="Two-party Dem share", font=dict(color=INK_2)), tickformat=".0%")
    return fig


def polls_chart(
    polls: pd.DataFrame,
    office: str,
    *,
    average: Mapping[str, float] | None = None,
    history: Mapping[int, float] | None = None,
) -> go.Figure:
    """Each compiled poll at its field end date; hollow markers are registered-voter polls."""
    p = polls[polls["office"] == office].copy()
    p["field_end"] = pd.to_datetime(p["field_end"])
    fig = go.Figure()
    for population, symbol in (("LV", "circle"), ("RV", "circle-open")):
        part = p[p["population"] == population]
        if part.empty:
            continue
        fig.add_trace(
            go.Scatter(
                x=part["field_end"],
                y=part["two_party_dem_share"],
                mode="markers",
                name="Likely voters" if population == "LV" else "Registered voters",
                marker=dict(symbol=symbol, size=10, color=INK_2, line=dict(width=1.5, color=INK_2)),
                customdata=np.stack(
                    [part["pollster"], part["sample_size"], part["dem_pct"], part["rep_pct"]], axis=-1
                ),
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>Field end %{x|%b %d}<br>"
                    "Dem %{customdata[2]}% · Rep %{customdata[3]}% (two-party %{y:.1%})<br>"
                    "n = %{customdata[1]}<extra></extra>"
                ),
            )
        )
    if average:
        fig.add_hline(
            y=average["poll_mean_dem_share"],
            line=dict(color=INK, width=1.5, dash="dashdot"),
            annotation_text=f"Average {average['poll_mean_dem_share']:.1%}",
            annotation_position="bottom right",
            annotation_font=dict(color=INK_2, size=11),
        )
    for cycle, share in sorted((history or {}).items()):
        fig.add_hline(
            y=share,
            line=dict(color=MUTED, width=1, dash="dot"),
            annotation_text=f"{cycle} result {share:.1%}",
            annotation_position="top left",
            annotation_font=dict(color=MUTED, size=11),
        )
    fig.add_hline(y=0.5, line=dict(color=AXIS, width=1, dash="dot"))
    _base_layout(fig, height=340)
    fig.update_layout(
        showlegend=True,
        legend=dict(orientation="h", x=0, y=1.14, font=dict(color=INK_2)),
        margin=dict(l=48, r=24, t=48, b=40),
    )
    fig.update_yaxes(
        title=dict(text="Two-party Dem share", font=dict(color=INK_2)), tickformat=".0%", range=[0.40, 0.58]
    )
    return fig


def region_history_chart(history: pd.DataFrame) -> go.Figure:
    """Small multiples, one panel per region; office carried by marker shape, not colour."""
    regions = list(dict.fromkeys(history["region"]))
    cols = 3
    rows = -(-len(regions) // cols)
    fig = make_subplots(
        rows=rows,
        cols=cols,
        subplot_titles=regions,
        shared_yaxes=True,
        vertical_spacing=0.16,
        horizontal_spacing=0.05,
    )
    for i, region in enumerate(regions):
        r, c = divmod(i, cols)
        part = history[history["region"] == region]
        for office, symbol in (("president", "circle"), ("governor", "diamond")):
            o = part[part["office"] == office].sort_values("cycle")
            fig.add_trace(
                go.Scatter(
                    x=o["cycle"],
                    y=o["two_party_dem_share"],
                    mode="lines+markers",
                    name=office.title(),
                    legendgroup=office,
                    showlegend=i == 0,
                    line=dict(color=INK_2 if office == "president" else MUTED, width=2),
                    marker=dict(symbol=symbol, size=9, color=INK_2 if office == "president" else MUTED),
                    hovertemplate=f"<b>{region}</b><br>{office.title()} %{{x}}: %{{y:.1%}}<extra></extra>",
                ),
                row=r + 1,
                col=c + 1,
            )
        fig.add_hline(y=0.5, line=dict(color=AXIS, width=1, dash="dot"), row=r + 1, col=c + 1)
    _base_layout(fig, height=260 * rows + 40)
    fig.update_layout(
        showlegend=True,
        legend=dict(orientation="h", x=0, y=0.99, yanchor="top", yref="container", font=dict(color=INK_2)),
        margin=dict(l=48, r=24, t=96, b=32),
    )
    fig.update_xaxes(tickvals=[2018, 2020, 2022, 2024])
    fig.update_yaxes(tickformat=".0%")
    fig.update_annotations(font=dict(color=INK, size=12))
    return fig

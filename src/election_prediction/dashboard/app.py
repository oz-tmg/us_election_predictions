"""The Plotly Dash app, built for one audience at a time.

``create_app(Tier.PUBLIC, ...)`` builds the public site: historical certified results and
the method note, from the public store only. It is never handed a vault store, so no code
path in that process can serve a vault number.

``create_app(Tier.VAULT, ...)`` builds the vault: projections, scenarios, the sealed
pre-registration and diagnostics, behind Cloudflare Access verification on every request
(``access.py``).

Every chart is wrapped in ``chart_card`` with the CLAUDE.md §6 footer — period, unit,
source, snapshot, uncertainty and a plain-language summary — and every projection page
carries its run's status line, so modelled numbers never appear unlabelled.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import flask
import pandas as pd
from dash import Dash, Input, Output, dash_table, dcc, html

from election_prediction.dashboard import figures
from election_prediction.dashboard.access import AccessDenied, AccessVerifier
from election_prediction.dashboard.bundle import RunKind, RunManifest, Tier
from election_prediction.dashboard.store import BundleStore

# dash_table ships without type information for its generated components.
DataTable: Any = dash_table.DataTable  # type: ignore[attr-defined]

ASSETS = Path(__file__).parent / "assets"
PROJECTION_KINDS = {RunKind.PREREGISTRATION, RunKind.REFRESH, RunKind.SCENARIO}
OPEN_PATHS = {"/healthz"}


@dataclass(frozen=True)
class Caption:
    period: str
    unit: str
    source: str
    snapshot: str
    uncertainty: str
    summary: str


def chart_card(title: str, graph: Any, caption: Caption) -> html.Section:
    return html.Section(
        className="card",
        children=[
            html.H3(title),
            html.P(caption.summary, className="summary"),
            graph,
            html.Dl(
                className="caption",
                children=[
                    item
                    for label, value in (
                        ("Period", caption.period),
                        ("Unit", caption.unit),
                        ("Source", caption.source),
                        ("Snapshot", caption.snapshot),
                        ("Uncertainty", caption.uncertainty),
                    )
                    for item in (html.Dt(label), html.Dd(value))
                ],
            ),
        ],
    )


def _graph(fig: Any, graph_id: str) -> dcc.Graph:
    return dcc.Graph(id=graph_id, figure=fig, config={"displaylogo": False, "responsive": True})


def _status_banner(m: RunManifest) -> html.Div:
    return html.Div(
        className=f"status status-{m.kind.value}",
        children=[
            html.Strong(m.status_label),
            html.Span(f" · {m.title} · run {m.run_id}"),
        ],
    )


def _sources_text(m: RunManifest) -> str:
    commit = (m.source_git_commit or "unknown")[:12]
    return f"{', '.join(sorted(m.sources)) or 'n/a'} (build commit {commit})"


def _caveats(m: RunManifest) -> html.Details:
    return html.Details(
        className="caveats",
        children=[
            html.Summary(f"Caveats and declared defects ({len(m.caveats)})"),
            html.Ul([html.Li(c) for c in m.caveats]),
        ],
    )


def _split_text(split: dict[str, float] | None) -> str:
    if not split:
        return "unreported"
    return "/".join(f"{100 * split[k]:.0f}" for k in ("national", "regional", "state") if k in split)


def _coverage_only(summary: str, conclusions: Sequence[str]) -> str:
    """The manifest summary opens with the conclusions; the overview already lists them."""
    for c in conclusions:
        summary = summary.replace(c, "")
    return summary.strip()


# --- pages ------------------------------------------------------------------------------


def _empty(text: str) -> html.Div:
    return html.Div(className="empty", children=text)


def page_history(store: BundleStore, office: str, cycle: int | None) -> list[Any]:
    runs = [m for m in store.runs() if m.kind is RunKind.HISTORICAL]
    if not runs:
        return [_empty("No historical results have been exported yet.")]
    m = runs[0]
    results = store.table(m.run_id, "results")
    cycles = sorted(results.loc[results["office"] == office, "cycle"].unique())
    # Senate cycles are biennial, presidential quadrennial: snap to the latest held cycle.
    held = [int(c) for c in cycles if cycle is None or c <= cycle]
    cycle = held[-1] if held else int(cycles[0])
    office_name = {"president": "Presidential", "us_senate": "Senate"}[office]
    caption = Caption(
        period=f"{cycle} general election",
        unit="State",
        source="MIT Election Data and Science Lab certified returns; " + _sources_text(m),
        snapshot=m.as_of,
        uncertainty="Certified counts; no modelled uncertainty. Third-party votes excluded.",
        summary=(
            f"{office_name} two-party Democratic share by state in {cycle}. Grey states "
            "had no contest that year or an uncontested race."
        ),
    )
    return [
        html.Div(className="status status-historical", children=html.Strong(m.status_label)),
        chart_card(
            f"{office_name} results, {cycle}",
            _graph(figures.history_map(results, office, cycle), "history-map"),
            caption,
        ),
    ]


def _projection_frame(
    store: BundleStore, run_id: str, assumption: str
) -> tuple[RunManifest, pd.DataFrame, dict[str, Any]]:
    m = store.manifest(run_id)
    seats = store.table(run_id, "seats")
    band = store.document(run_id, "band")
    return m, seats[seats["assumption"] == assumption], band


def page_overview(store: BundleStore, run_id: str, assumption: str) -> list[Any]:
    m, _, band = _projection_frame(store, run_id, assumption)
    br = band["band_results"]
    corr = band.get("correlation_parameters") or {}
    ne = band["national_environment"]
    return [
        _status_banner(m),
        html.Section(
            className="card",
            children=[
                html.H3("What this run says"),
                html.Ul([html.Li(c) for c in band["conclusions"]]),
                html.P(_coverage_only(m.summary, band["conclusions"]), className="summary"),
                _caveats(m),
            ],
        ),
        chart_card(
            "House seats across the assumption band",
            _graph(figures.house_band_chart(br), "band-chart"),
            Caption(
                period="2026 general election (November 3)",
                unit="U.S. House, national seat total",
                source=_sources_text(m),
                snapshot=m.as_of,
                uncertainty=(
                    "Bars span the correlated simulation's 5th–95th percentile; the "
                    "shrinkage assumption is swept, not estimated."
                ),
                summary=(
                    "Each point is one shrinkage assumption. The spread across points is "
                    "assumption uncertainty; the bars are simulation uncertainty within one."
                ),
            ),
        ),
        chart_card(
            "Chamber control across the assumption band",
            _graph(figures.control_chart(br), "control-chart"),
            Caption(
                period="2026 general election (November 3)",
                unit="Chamber",
                source=_sources_text(m),
                snapshot=m.as_of,
                uncertainty=(
                    f"Correlated error split {_split_text(corr.get('house'))} "
                    "(national/regional/state), asserted, not estimated."
                ),
                summary=(
                    "Probability of Democratic control at each assumption. Where the line "
                    "crosses 50%, the band cannot resolve the chamber."
                ),
            ),
        ),
        html.Section(
            className="card",
            children=[
                html.H3("National environment"),
                html.P(
                    f"Estimator: {ne.get('estimator')} · status: {ne.get('status')} · "
                    f"identified: {ne.get('identified')}",
                    className="summary",
                ),
                DataTable(
                    data=[
                        {
                            "Assumption": b["assumption"],
                            "National two-party Dem share": f"{b['national_dem_share']:.3f}",
                            "Std. error": f"{b['share_std_error']:.4f}",
                        }
                        for b in ne.get("band") or []
                    ],
                    style_as_list_view=True,
                    style_cell={"fontFamily": figures.FONT, "padding": "6px"},
                ),
            ],
        ),
    ]


def page_map(store: BundleStore, run_id: str, assumption: str) -> list[Any]:
    m, seats, _ = _projection_frame(store, run_id, assumption)
    common = dict(period="2026 general election (November 3)", source=_sources_text(m), snapshot=m.as_of)
    n_fallback = int((seats["office"].eq("us_house") & seats["source"].isin(figures.FALLBACK_SOURCES)).sum())
    return [
        _status_banner(m),
        chart_card(
            f"Senate contests · {assumption}",
            _graph(figures.senate_map(seats), "senate-map"),
            Caption(
                unit="State",
                uncertainty="Hover shows each contest's 90% interval on two-party share.",
                summary="Colour is the probability of a Democratic win; grey-white means close to even.",
                **common,
            ),
        ),
        chart_card(
            f"House seats · {assumption}",
            _graph(figures.house_strip(seats), "house-strip"),
            Caption(
                unit="Congressional district (2026 lines)",
                uncertainty=(
                    "Ordering shows per-seat probabilities only; chamber odds come "
                    "from the correlated simulation, not from counting dots."
                ),
                summary=(
                    f"All 435 seats, most Democratic-leaning first. {n_fallback} hollow "
                    "markers sit on redrawn lines with only a state-lean prior and are "
                    "the least informed seats."
                ),
                **common,
            ),
        ),
    ]


def races_table(seats: pd.DataFrame) -> pd.DataFrame:
    lo, hi = figures.interval_90(seats["mean_dem_share"], seats["sigma"])
    district = seats["district_num"].fillna(0).astype(int).astype(str).str.zfill(2)
    out = pd.DataFrame(
        {
            "Office": seats["office"].map({"us_house": "House", "us_senate": "Senate"}),
            "Race": seats["state_po"].where(
                seats["office"] == "us_senate", seats["state_po"] + "-" + district
            ),
            "P(Dem win)": seats["dem_win_prob"].round(3),
            "Dem two-party share": seats["mean_dem_share"].round(3),
            "90% low": lo.round(3),
            "90% high": hi.round(3),
            "Prior": seats["source"].str.replace("_", " "),
            "Boundaries": seats["boundary_confidence"].fillna("n/a"),
            "Litigation": seats["litigation_risk"].fillna("n/a"),
        }
    )
    return out.sort_values(["Office", "P(Dem win)"], ascending=[False, False])


def page_races(store: BundleStore, run_id: str, assumption: str) -> list[Any]:
    m, seats, _ = _projection_frame(store, run_id, assumption)
    table = races_table(seats)
    return [
        _status_banner(m),
        html.Section(
            className="card",
            children=[
                html.H3(f"Every race · {assumption}"),
                html.P(
                    "Filter any column (e.g. type TX in Race, or >0.4 in P(Dem win)). The 90% "
                    "interval is each race's own marginal interval on two-party share.",
                    className="summary",
                ),
                DataTable(
                    id="races-table",
                    data=table.to_dict("records"),
                    columns=[{"name": c, "id": c} for c in table.columns],
                    filter_action="native",
                    sort_action="native",
                    page_size=25,
                    style_as_list_view=True,
                    style_cell={"fontFamily": figures.FONT, "padding": "6px", "textAlign": "left"},
                    style_header={"fontWeight": "600"},
                ),
                html.P(f"Snapshot {m.as_of} · {_sources_text(m)}", className="footnote"),
            ],
        ),
    ]


def page_diagnostics(store: BundleStore) -> list[Any]:
    runs = [m for m in store.runs() if m.kind is RunKind.BACKTEST]
    if not runs:
        return [_empty("No backtest has been exported yet.")]
    m = runs[0]
    offices = store.document(m.run_id, "diagnostics")["offices"]
    rows = [
        {
            "Office": figures.OFFICE_TITLES.get(o, o),
            "n": d["n"],
            "MAE (share)": round(d["mae_vote_share"], 4),
            "Naive persistence MAE": round(d["naive_persistence_mae"], 4),
            "Brier": round(d["brier"], 4),
            "Log score": round(d["log_score"], 4),
            "ECE": round(d["ece"], 4),
            "90% coverage": round(d["coverage_90"], 3),
            "95% coverage": round(d["coverage_95"], 3),
        }
        for o, d in offices.items()
    ]
    return [
        _status_banner(m),
        html.Section(
            className="card",
            children=[
                html.H3("Backtest scores"),
                html.P(
                    "Lower MAE, Brier and log score are better; coverage should sit near its "
                    "nominal 90% / 95%. Every office is compared with naive persistence.",
                    className="summary",
                ),
                DataTable(
                    data=rows,
                    style_as_list_view=True,
                    style_cell={"fontFamily": figures.FONT, "padding": "6px"},
                ),
                _caveats(m),
            ],
        ),
        chart_card(
            "Calibration (reliability curves)",
            _graph(figures.calibration_chart(offices), "calibration-chart"),
            Caption(
                period="Held-out cycles, 1976–2024",
                unit="State (president, Senate); district (House)",
                source=_sources_text(m),
                snapshot=m.as_of,
                uncertainty="Bins with few races (see n in hover) are noisy.",
                summary="Points on the dotted diagonal mean predicted probabilities came "
                "true as often as stated.",
            ),
        ),
    ]


def page_runs(stores: Sequence[BundleStore]) -> list[Any]:
    rows = [
        {
            "Run": m.run_id,
            "Status": m.status_label,
            "As of": m.as_of,
            "Audience": m.tier.value,
            "Build commit": (m.source_git_commit or "")[:12],
            "Exporter commit": (m.exporter_git_commit or "")[:12],
            "Sources": "; ".join(f"{k} sha256:{v[:12]}" for k, v in sorted(m.sources.items())),
        }
        for s in stores
        for m in s.runs()
    ]
    return [
        html.Section(
            className="card",
            children=[
                html.H3("Run registry"),
                html.P(
                    "Every bundle the dashboard can show, with the commit and input hashes it was "
                    "built from.",
                    className="summary",
                ),
                DataTable(
                    data=rows,
                    style_as_list_view=True,
                    page_size=25,
                    style_cell={
                        "fontFamily": figures.FONT,
                        "padding": "6px",
                        "textAlign": "left",
                        "whiteSpace": "normal",
                    },
                ),
            ],
        )
    ]


ABOUT = dcc.Markdown(
    """
### About

A nonpartisan, reproducible, calibration-first look at U.S. elections by
[Savepoint Analytics](https://www.alexoswald.ca). Every number on this site is rebuilt from
public, licensed data by code, and every chart states its period, unit, source, snapshot
date and uncertainty.

**Certified, unofficial and modelled numbers are labelled distinctly.** Modelled 2026
numbers are not published here: the 2026 projection is held, and its pre-registered
prediction will be scored against certified returns after November 3.

Results: MIT Election Data and Science Lab, *U.S. President 1976–2024*, *U.S. Senate
1976–2024* (Harvard Dataverse).
""",
    className="card",
)


# --- app --------------------------------------------------------------------------------


def _install_access(server: flask.Flask, verifier: AccessVerifier | None) -> None:
    @server.before_request
    def _require_access() -> flask.Response | None:
        if flask.request.path in OPEN_PATHS or verifier is None:
            return None
        try:
            claims = verifier.verify_request(flask.request.headers, flask.request.cookies)
        except AccessDenied:
            return flask.Response("Forbidden", status=403, mimetype="text/plain")
        flask.g.viewer = claims.get("email")
        return None


def _install_headers(server: flask.Flask, tier: Tier, frame_ancestors: str) -> None:
    @server.after_request
    def _headers(resp: flask.Response) -> flask.Response:
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        ancestors = "'none'" if tier is Tier.VAULT else frame_ancestors
        resp.headers["Content-Security-Policy"] = f"frame-ancestors {ancestors}"
        if tier is Tier.VAULT:
            resp.headers["Cache-Control"] = "private, no-store"
            resp.headers["X-Robots-Tag"] = "noindex, nofollow"
        return resp


def create_app(
    tier: Tier,
    public_store: BundleStore,
    vault_store: BundleStore | None = None,
    *,
    verifier: AccessVerifier | None = None,
    insecure_local: bool = False,
    frame_ancestors: str = "'self' https://www.alexoswald.ca https://alexoswald.ca",
) -> Dash:
    tier = Tier(tier)
    if public_store.tier is not Tier.PUBLIC:
        raise ValueError("public_store must be a public-tier store")
    if tier is Tier.PUBLIC and vault_store is not None:
        raise ValueError("the public app is never given a vault store")
    if tier is Tier.VAULT:
        if vault_store is None or vault_store.tier is not Tier.VAULT:
            raise ValueError("the vault app needs a vault-tier store")
        if verifier is None and not insecure_local:
            raise ValueError("the vault app needs an Access verifier (or insecure_local for dev)")

    server = flask.Flask(__name__)

    @server.get("/healthz")
    def _health() -> str:
        return "ok"

    _install_access(server, verifier if tier is Tier.VAULT else None)
    _install_headers(server, tier, frame_ancestors)

    title = "US Elections · Savepoint Analytics" + (" · Vault" if tier is Tier.VAULT else "")
    # Dash accepts a Flask instance as ``server``; its type hint does not say so.
    app = Dash(
        __name__,
        server=server,  # type: ignore[arg-type]
        title=title,
        assets_folder=str(ASSETS),
        suppress_callback_exceptions=True,
    )

    if tier is Tier.PUBLIC:
        nav = [("/", "Results history"), ("/about", "About")]
    else:
        nav = [
            ("/", "Chambers"),
            ("/map", "Map"),
            ("/races", "Races"),
            ("/diagnostics", "Diagnostics"),
            ("/history", "Results history"),
            ("/runs", "Runs"),
            ("/about", "About"),
        ]

    projection_runs = [m for m in vault_store.runs() if m.kind in PROJECTION_KINDS] if vault_store else []
    controls: list[Any] = []
    if tier is Tier.VAULT:
        controls = [
            html.Label("Run", htmlFor="run-select"),
            dcc.Dropdown(
                id="run-select",
                options=[{"label": f"{m.as_of} · {m.title}", "value": m.run_id} for m in projection_runs],
                value=projection_runs[0].run_id if projection_runs else None,
                clearable=False,
            ),
            html.Label("Assumption", htmlFor="assumption-select"),
            dcc.RadioItems(id="assumption-select", inline=True),
        ]
    history_controls = [
        dcc.RadioItems(
            id="history-office",
            inline=True,
            value="president",
            options=[{"label": "President", "value": "president"}, {"label": "Senate", "value": "us_senate"}],
        ),
        dcc.Slider(
            id="history-cycle",
            min=1976,
            max=2024,
            step=2,
            value=2024,
            marks={y: str(y) for y in range(1976, 2025, 8)},
        ),
    ]

    app.layout = html.Div(
        className=f"app tier-{tier.value}",
        children=[
            dcc.Location(id="url"),
            html.Header(
                className="topbar",
                children=[
                    html.Div(
                        className="brand",
                        children=[
                            html.A("US Elections", href="/"),
                            html.Span("Vault — private, not for redistribution", className="vault-tag")
                            if tier is Tier.VAULT
                            else None,
                        ],
                    ),
                    html.Nav([dcc.Link(label, href=href) for href, label in nav]),
                ],
            ),
            html.Div(id="controls", className="controls", children=controls),
            html.Div(id="history-controls", className="controls", children=history_controls),
            html.Main(id="page"),
            html.Footer(
                "Savepoint Analytics · nonpartisan, reproducible election analysis · "
                "certified, unofficial and modelled numbers are labelled distinctly"
            ),
        ],
    )

    if tier is Tier.VAULT:

        @app.callback(
            Output("assumption-select", "options"),
            Output("assumption-select", "value"),
            Input("run-select", "value"),
        )
        def _assumptions(run_id: str | None) -> tuple[list[dict[str, str]], str | None]:
            if not run_id or vault_store is None:
                return [], None
            band = vault_store.document(run_id, "band")["band_results"]
            names = [b["assumption"] for b in band]
            options = [{"label": n.replace("shrinkage=", "shrinkage "), "value": n} for n in names]
            return options, names[len(names) // 2]

    @app.callback(
        Output("page", "children"),
        Output("controls", "style"),
        Output("history-controls", "style"),
        Input("url", "pathname"),
        Input("history-office", "value"),
        Input("history-cycle", "value"),
        Input("run-select", "value") if tier is Tier.VAULT else Input("url", "search"),
        Input("assumption-select", "value") if tier is Tier.VAULT else Input("url", "hash"),
    )
    def _route(path: str | None, office: str, cycle: int, run_id: Any, assumption: Any):
        hide: dict[str, str] = {"display": "none"}
        show: dict[str, str] = {}
        path = path or "/"
        is_history = path == "/history" or (tier is Tier.PUBLIC and path == "/")
        if is_history:
            return page_history(public_store, office, cycle), hide, show
        if path == "/about":
            return [ABOUT], hide, hide
        if tier is Tier.PUBLIC or vault_store is None:
            return [_empty("Page not found.")], hide, hide
        if path == "/diagnostics":
            return page_diagnostics(vault_store), hide, hide
        if path == "/runs":
            return page_runs([public_store, vault_store]), hide, hide
        if not run_id or not assumption:
            return [_empty("No projection runs have been exported yet.")], show, hide
        pages = {"/": page_overview, "/map": page_map, "/races": page_races}
        if path not in pages:
            return [_empty("Page not found.")], hide, hide
        return pages[path](vault_store, run_id, assumption), show, hide

    return app

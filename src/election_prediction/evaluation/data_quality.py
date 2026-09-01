"""Data-quality report (P0-009).

Renders missingness, duplicate keys, vote-total reconciliation, and stale-source
flags for the loaded data, as both a machine-readable dict and a Markdown report.
Makes gaps visible before anything is modeled (PROJECT_CONTEXT.md §17.5).
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd

STALE_AFTER_DAYS = 400  # a per-cycle source older than this is flagged for refresh

# Share of races whose candidate votes may disagree with the source's reported total
# before the build fails. Real certified returns carry a small number of genuine
# source-side discrepancies (amended counts, omitted scattering write-ins), and the
# ingestion playbook's quality gate is "source totals reconcile **or caveats
# documented**" — so mismatches are always listed, and only an unusual *rate* fails.
RECONCILIATION_TOLERANCE_PCT = 0.5


def _missingness(df: pd.DataFrame) -> pd.DataFrame:
    miss = df.isna().mean().sort_values(ascending=False)
    return (miss[miss > 0] * 100).round(2).rename("pct_missing").to_frame()


def _snapshot_age_days(snapshot_date: str) -> int | None:
    try:
        d = datetime.fromisoformat(str(snapshot_date)[:10]).date()
    except ValueError:
        return None
    return (date.today() - d).days


def build_quality_report(
    returns: pd.DataFrame,
    race_table: pd.DataFrame,
    geography: pd.DataFrame,
    *,
    data_modes: dict | None = None,
    transform_stats: dict | None = None,
    quarantine_stats: dict | None = None,
) -> dict:
    """Compute the data-quality metrics dict for the loaded P0 tables.

    ``data_modes`` records how each source was acquired (live / manual / synthetic) and
    ``transform_stats`` what standardization dropped or merged, and ``quarantine_stats``
    which races were excluded for failing reconciliation — all auditable from the
    published report rather than only from logs.
    """
    report: dict = {"generated_at": datetime.now(UTC).isoformat(timespec="seconds")}
    report["data_modes"] = data_modes or {}
    report["transform_stats"] = transform_stats or {}
    report["quarantine"] = quarantine_stats or {}

    # --- coverage ---------------------------------------------------------
    report["coverage"] = {
        "returns_rows": int(len(returns)),
        "races": int(returns["race_id"].nunique()),
        "cycles": sorted(int(c) for c in returns["cycle"].unique()),
        "offices": sorted(returns["office"].unique().tolist()),
        "states": int(returns["state_po"].nunique()),
        "geography_rows": int(len(geography)),
    }

    # --- missingness ------------------------------------------------------
    report["missingness_pct"] = _missingness(returns)["pct_missing"].to_dict()

    # --- duplicate keys ---------------------------------------------------
    report["duplicate_keys"] = {
        # Same natural key as the silver gate: the party line is part of it, because
        # MEDSL records unnamed aggregate minor-party votes as several rows per race.
        "returns_race_candidate_party": int(returns.duplicated(["race_id", "candidate", "party"]).sum()),
        "race_table_race_id": int(race_table.duplicated(["race_id"]).sum()),
        "geography_geography_id": int(geography.duplicated(["geography_id"]).sum()),
    }

    # --- vote-total reconciliation ---------------------------------------
    agg = returns.groupby("race_id").agg(sum_cand=("candidatevotes", "sum"), reported=("totalvotes", "max"))
    checkable = agg[agg["reported"] > 0]
    mismatches = checkable[checkable["sum_cand"] != checkable["reported"]]
    mismatch_pct = round(100 * len(mismatches) / len(checkable), 3) if len(checkable) else 0.0
    report["vote_reconciliation"] = {
        "races_checked": int(len(checkable)),
        "races_mismatched": int(len(mismatches)),
        "mismatch_pct": mismatch_pct,
        "tolerance_pct": RECONCILIATION_TOLERANCE_PCT,
        "within_tolerance": mismatch_pct <= RECONCILIATION_TOLERANCE_PCT,
        "example_mismatches": mismatches.head(5).reset_index().to_dict("records"),
    }

    # --- contest flags ----------------------------------------------------
    report["contests"] = {
        "uncontested_races": int(race_table["uncontested_flag"].sum()),
        "uncontested_pct": round(100 * race_table["uncontested_flag"].mean(), 2) if len(race_table) else 0.0,
        "uncertified_races": int((~race_table["certified_flag"]).sum()),
    }

    # --- source freshness -------------------------------------------------
    freshness = []
    for src, g in returns.groupby("source_id"):
        snap = g["snapshot_date"].iloc[0]
        age = _snapshot_age_days(snap)
        freshness.append(
            {
                "source_id": src,
                "snapshot_date": snap,
                "age_days": age,
                "stale": (age is not None and age > STALE_AFTER_DAYS),
            }
        )
    report["source_freshness"] = freshness

    report["overall_ok"] = (
        sum(report["duplicate_keys"].values()) == 0 and report["vote_reconciliation"]["within_tolerance"]
    )
    return report


def render_markdown(report: dict) -> str:
    """Render the quality report dict as a Markdown document."""
    c = report["coverage"]
    lines = [
        "# Data-Quality Report — P0 Foundation",
        "",
        f"_Generated: {report['generated_at']}Z_",
        "",
        "> Scope: loaded MEDSL federal returns (silver), model-ready race table (gold),",
        "> and the canonical geography spine. Nonpartisan; historical/certified returns.",
        "",
    ]

    modes = report.get("data_modes") or {}
    if modes:
        synthetic = [k for k, v in modes.items() if v == "synthetic"]
        if synthetic:
            lines += [
                "> ⚠️ **SYNTHETIC DATA IN THIS RUN.** Sources acquired as synthetic "
                f"fixtures: {', '.join(sorted(synthetic))}. Numbers below describe the "
                "*pipeline*, not real elections.",
                "",
            ]
        lines += ["## Acquisition mode", ""]
        for source, mode in sorted(modes.items()):
            label = {
                "live": "live download",
                "manual": "verified manual download",
                "synthetic": "SYNTHETIC fixture",
            }.get(mode, mode)
            lines.append(f"- `{source}`: {label}")
        lines.append("")

    lines += [
        "## Coverage",
        "",
        f"- Returns rows: **{c['returns_rows']:,}**",
        f"- Distinct races: **{c['races']:,}**",
        f"- Cycles: {', '.join(map(str, c['cycles']))}",
        f"- Offices: {', '.join(c['offices'])}",
        f"- States covered: {c['states']}",
        f"- Geography spine rows: {c['geography_rows']:,}",
        "",
        "## Duplicate keys",
        "",
    ]
    for k, v in report["duplicate_keys"].items():
        flag = "OK" if v == 0 else "**FAIL**"
        lines.append(f"- `{k}`: {v} {flag}")

    vr = report["vote_reconciliation"]
    lines += [
        "",
        "## Vote-total reconciliation",
        "",
        f"- Races checked (totalvotes populated): {vr['races_checked']:,}",
        f"- Races where candidate sum ≠ reported total: **{vr['races_mismatched']}** "
        f"({vr.get('mismatch_pct', 0)}%, tolerance {vr.get('tolerance_pct', 0)}%)",
    ]

    q = report.get("quarantine") or {}
    if q.get("quarantined_races"):
        lines += [
            "",
            "## Quarantined races (excluded from the modeling layer)",
            "",
            f"- Races excluded: **{q['quarantined_races']}** of {q['races_total']:,} ({q['pct_of_races']}%)",
            "",
            "These races' candidate votes do not sum to the jurisdiction's reported total. "
            "The causes are heterogeneous and state-specific, so they are excluded uniformly "
            "and retained at `data/silver/quarantined_races.csv` with a reason, rather than "
            "corrected by cause-specific rules (CLAUDE.md §6). The reason labels below are "
            "descriptive: confirming why any given race fails requires the state's certified "
            "return, not an inference from the discrepancy.",
            "",
        ]
        for reason, n in q.get("by_reason", {}).items():
            lines.append(f"- {n} — {reason}")

    ts = report.get("transform_stats") or {}
    if ts:
        lines += [
            "",
            "## Standardization decisions",
            "",
            "What the raw → silver transform dropped or merged, per source:",
            "",
        ]
        for source, stats in sorted(ts.items()):
            detail = ", ".join(f"{k.replace('_', ' ')}: {v:,}" for k, v in stats.items())
            lines.append(f"- `{source}` — {detail}")
        lines += [
            "",
            "Primaries and other non-general stages are excluded so comparisons stay "
            "like-for-like; fusion-voting lines are summed per candidate so a candidate's "
            "own vote is not split across party lines.",
        ]

    ct = report["contests"]
    lines += [
        "",
        "## Contest flags",
        "",
        f"- Uncontested races: {ct['uncontested_races']} ({ct['uncontested_pct']}%) "
        "— handled explicitly, never as 100–0 truth (CLAUDE.md §6).",
        f"- Uncertified races: {ct['uncertified_races']}",
        "",
        "## Missingness (columns with any nulls)",
        "",
    ]
    miss = report["missingness_pct"]
    if miss:
        for col, pct in miss.items():
            lines.append(f"- `{col}`: {pct}%")
    else:
        lines.append("- None.")

    lines += ["", "## Source freshness", ""]
    for f in report["source_freshness"]:
        flag = "STALE" if f["stale"] else "fresh"
        lines.append(f"- `{f['source_id']}` — snapshot {f['snapshot_date']} ({f['age_days']} days, {flag})")

    lines += [
        "",
        "## Overall",
        "",
        f"**{'PASS' if report['overall_ok'] else 'ATTENTION NEEDED'}** — "
        "keys unique and vote totals reconcile."
        if report["overall_ok"]
        else "**ATTENTION NEEDED** — see failed checks above.",
        "",
    ]
    return "\n".join(lines)


def write_report(report: dict, out_dir: str | Path = "reports") -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "data_quality_report.md"
    path.write_text(render_markdown(report))
    return path

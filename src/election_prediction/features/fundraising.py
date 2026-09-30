"""F-004: candidate fundraising as a race-level feature, from FEC candidate totals.

Encoded as a **ratio between the parties, not raw dollars.** Nominal dollars are not
comparable across a 1980-2026 span: inflation, the 2002 BCRA soft-money ban, and the rise
of independent expenditures all shift the level without shifting the balance. A ratio is
scale-free, and its logit form is symmetric -- a 2:1 Democratic advantage and a 2:1
Republican one are equal and opposite.

**Fundraising is endogenous, and the direction of the bias is known.** Money flows toward
races that are already close and toward candidates already expected to win, so a
fundraising feature partly *measures* the outcome rather than predicting it. It must
therefore be tested strictly against the current baseline (CLAUDE.md §2, rule 5): a small
in-sample improvement is the expected signature of endogeneity, not of a better model.

Two data conditions constrain what this can honestly claim, both measured here rather
than assumed:

* **``coverage_end_date`` is per candidate, not per race.** It is the end of that
  candidate's last filed report, so one race can compare a Democrat's receipts through
  December against a Republican's through September. That is not a like-for-like ratio, so
  :func:`build_fundraising` records both windows and flags a race whose sides are
  misaligned beyond ``MAX_COVERAGE_GAP_DAYS``.
* **The endpoint offers no pre-election cutoff.** ``max_coverage_end_date`` is accepted and
  silently ignored by ``/candidates/totals/`` (verified: identical result sets with and
  without it), so a historical total runs past election day and includes post-election
  receipts -- which winners collect to retire debt. That leaks the outcome into a
  predictive feature, and it leaks in the worst direction: it inflates *backtest*
  performance while a live cycle, whose filings are necessarily pre-election, gets no such
  help. Rows affected carry ``post_election_coverage``, and a backtest that does not
  exclude them is not measuring prediction.
"""

from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

from .candidate_crosswalk import DEMOCRAT, REPUBLICAN, normalize_party

FUNDRAISING_COLUMNS = [
    "cycle",
    "office",
    "state_po",
    "district_num",
    "dem_receipts",
    "rep_receipts",
    "dem_candidates",
    "rep_candidates",
    "dem_top_candidate_id",
    "rep_top_candidate_id",
    "dem_top_receipts",
    "rep_top_receipts",
    "dem_receipt_share",
    "log_receipt_ratio",
    "dem_coverage_end",
    "rep_coverage_end",
    "coverage_gap_days",
    "coverage_aligned",
    "post_election_coverage",
    "usable",
    "unusable_reason",
]

# Smoothing in dollars, applied to both sides of the ratio. Without it a race where one
# party raised nothing gives an infinite log ratio, and a race where one raised $200 gives
# an implausibly large finite one. $10,000 is roughly the floor of a real congressional
# campaign, so it caps the ratio at a magnitude the data can actually support.
RECEIPTS_SMOOTHING = 10_000.0

# Beyond this, the two parties' reporting windows are not measuring the same period.
MAX_COVERAGE_GAP_DAYS = 45


def election_day(cycle: int) -> dt.date:
    """First Tuesday after the first Monday in November — the federal general."""
    d = dt.date(int(cycle), 11, 1)
    # The first Monday, then the day after.
    d += dt.timedelta(days=(0 - d.weekday()) % 7)
    return d + dt.timedelta(days=1)


def _top(group: pd.DataFrame) -> tuple[object, float]:
    """The party's largest fundraiser, as the nominee proxy.

    The totals endpoint lists every filer, including primary losers, so summing a party's
    receipts overstates what the general-election nominee actually raised -- most in a
    contested primary. The top fundraiser is the closest available proxy for the nominee
    without primary results, and it is only a proxy: the best-funded primary candidate is
    not always the winner. ``dem_candidates``/``rep_candidates`` and the party sums are kept
    alongside so the substitution stays auditable rather than invisible.
    """
    if not len(group):
        return pd.NA, 0.0
    row = group.loc[group["receipts"].idxmax()]
    return row["candidate_id"], float(row["receipts"])


def build_fundraising(totals: pd.DataFrame) -> pd.DataFrame:
    """One row per seat-cycle from a parsed ``/candidates/totals/`` frame."""
    df = totals.copy()
    df["receipts"] = pd.to_numeric(df["receipts"], errors="coerce").fillna(0.0)
    df["party"] = df["fec_party"].map(normalize_party)
    df["cycle"] = pd.to_numeric(df.get("election_year", df.get("cycle")), errors="coerce")
    df["coverage_end"] = pd.to_datetime(df.get("coverage_end_date"), errors="coerce")
    # Senate seats have no district; keeping it null stops a state's two classes being
    # distinguished by a meaningless 00.
    df.loc[df["office"] == "us_senate", "district_num"] = np.nan

    records = []
    keys = ["cycle", "office", "state_po", "district_num"]
    for key, seat in df.groupby(keys, dropna=False):
        cycle, office, state_po, district_num = key
        dem = seat[seat["party"] == DEMOCRAT]
        rep = seat[seat["party"] == REPUBLICAN]
        dem_id, dem_top = _top(dem)
        rep_id, rep_top = _top(rep)

        # The top-fundraiser proxy is the modelled quantity; the party sums are diagnostic.
        d, r = dem_top, rep_top
        share = (d + RECEIPTS_SMOOTHING) / (d + r + 2 * RECEIPTS_SMOOTHING)

        dem_end = dem.loc[dem["candidate_id"] == dem_id, "coverage_end"].max() if len(dem) else pd.NaT
        rep_end = rep.loc[rep["candidate_id"] == rep_id, "coverage_end"].max() if len(rep) else pd.NaT
        gap = abs((dem_end - rep_end).days) if pd.notna(dem_end) and pd.notna(rep_end) else None
        eday = election_day(int(cycle)) if pd.notna(cycle) else None
        post = bool(
            eday is not None
            and (
                (pd.notna(dem_end) and dem_end.date() > eday) or (pd.notna(rep_end) and rep_end.date() > eday)
            )
        )

        reasons = []
        if not len(dem) or not len(rep):
            reasons.append("one major party has no filer; a ratio is undefined")
        if d <= 0 or r <= 0:
            reasons.append("a party's nominee proxy raised nothing")
        if gap is None:
            reasons.append("a coverage window is missing")
        elif gap > MAX_COVERAGE_GAP_DAYS:
            reasons.append(f"coverage windows differ by {gap} days")

        records.append(
            {
                "cycle": cycle,
                "office": office,
                "state_po": state_po,
                "district_num": district_num,
                "dem_receipts": float(dem["receipts"].sum()),
                "rep_receipts": float(rep["receipts"].sum()),
                "dem_candidates": int(len(dem)),
                "rep_candidates": int(len(rep)),
                "dem_top_candidate_id": dem_id,
                "rep_top_candidate_id": rep_id,
                "dem_top_receipts": d,
                "rep_top_receipts": r,
                "dem_receipt_share": float(share),
                "log_receipt_ratio": float(np.log((d + RECEIPTS_SMOOTHING) / (r + RECEIPTS_SMOOTHING))),
                "dem_coverage_end": dem_end,
                "rep_coverage_end": rep_end,
                "coverage_gap_days": gap,
                "coverage_aligned": bool(gap is not None and gap <= MAX_COVERAGE_GAP_DAYS),
                "post_election_coverage": post,
                "usable": not reasons,
                "unusable_reason": "; ".join(reasons),
            }
        )

    out = pd.DataFrame(records, columns=FUNDRAISING_COLUMNS)
    return out.sort_values(keys).reset_index(drop=True)


def validate_fundraising(df: pd.DataFrame) -> dict:
    """Gates on a built fundraising table."""
    checks: dict[str, object] = {}
    missing = [c for c in FUNDRAISING_COLUMNS if c not in df.columns]
    checks["schema.required_columns"] = not missing
    checks["schema.missing"] = missing
    if missing:
        checks["ok"] = False
        return checks

    checks["rows"] = int(len(df))
    keys = ["cycle", "office", "state_po", "district_num"]
    checks["keys.one_row_per_seat"] = int(df.duplicated(subset=keys).sum()) == 0
    checks["receipts.nonnegative"] = bool(
        (df[["dem_receipts", "rep_receipts", "dem_top_receipts", "rep_top_receipts"]] >= 0).all().all()
    )
    # The proxy cannot exceed the party sum it was drawn from.
    checks["receipts.top_within_party_total"] = bool(
        (df["dem_top_receipts"] <= df["dem_receipts"] + 1e-6).all()
        and (df["rep_top_receipts"] <= df["rep_receipts"] + 1e-6).all()
    )
    checks["share.in_unit_interval"] = bool(df["dem_receipt_share"].between(0, 1).all())
    # Smoothing exists precisely so this cannot happen; if it does, it was bypassed.
    checks["ratio.finite"] = bool(np.isfinite(df["log_receipt_ratio"]).all())
    # An unusable row must say why, or it is indistinguishable from a bug.
    blank = df["unusable_reason"].fillna("").astype(str).str.strip() == ""
    checks["provenance.unusable_reason_given"] = int((~df["usable"] & blank).sum()) == 0
    checks["coverage.rows_post_election"] = int(df["post_election_coverage"].sum())
    checks["coverage.rows_misaligned"] = int((~df["coverage_aligned"]).sum())
    checks["usable_rows"] = int(df["usable"].sum())

    checks["ok"] = all(v for v in checks.values() if isinstance(v, bool))
    return checks


def fundraising_summary(df: pd.DataFrame) -> dict:
    """Coverage and distribution, with the caveats the feature must travel with."""
    usable = df[df["usable"]]
    return {
        "rows": int(len(df)),
        "usable_rows": int(len(usable)),
        "usable_share": (len(usable) / len(df)) if len(df) else float("nan"),
        "cycles": sorted({int(c) for c in df["cycle"].dropna().unique()}),
        "unusable_reasons": (df.loc[~df["usable"], "unusable_reason"].value_counts().head(10).to_dict()),
        "post_election_coverage_rows": int(df["post_election_coverage"].sum()),
        "misaligned_coverage_rows": int((~df["coverage_aligned"]).sum()),
        "log_ratio_quantiles": (
            usable["log_receipt_ratio"].quantile([0.05, 0.25, 0.5, 0.75, 0.95]).round(3).to_dict()
            if len(usable)
            else {}
        ),
        "caveats": [
            "Fundraising is endogenous: money follows expected closeness and expected "
            "winners, so this feature partly measures the outcome. Test it strictly.",
            "The nominee is proxied by each party's top fundraiser; primary results are "
            "not available, and the best-funded primary candidate is not always the winner.",
            "coverage_end_date is per candidate, so the two sides of a ratio can cover "
            "different periods; misaligned rows are marked unusable.",
            "/candidates/totals/ offers no pre-election cutoff, so historical totals "
            "include post-election receipts. Backtests must exclude post_election_coverage "
            "rows or they are not measuring prediction.",
        ],
    }

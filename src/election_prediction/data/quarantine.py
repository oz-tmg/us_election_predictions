"""Quarantine for races whose reported votes do not reconcile.

Real MEDSL returns contain a small number of races where the candidate votes do not
sum to the jurisdiction's reported total. The causes are heterogeneous and
state-specific — Louisiana's all-party primary and a handful of court-ordered
Texas runoffs put two rounds under one ``GEN`` stage, New York's 2024 files carry a
``BLANK`` ballot row that its total excludes while its 2022 files include it — so
there is no single corrective rule. Patching each cause separately is where quiet
bias enters a returns table.

The project's rule (CLAUDE.md §6: uncontested and irregular races get a documented
imputation/exclusion plus a sensitivity test, never a silent fix) is applied here as
a uniform exclusion: races that fail reconciliation are separated out, retained on
disk with a reason, reported in the data-quality report, and measured for their
effect on model error. Everything that reconciles is used as-is.

The failing condition is deliberately identical to the ``votes.reconcile_to_total``
gate in :mod:`.validation`, so the gate cannot disagree with what was quarantined.
"""

from __future__ import annotations

import pandas as pd

QUARANTINE_COLUMNS = [
    "race_id",
    "cycle",
    "office",
    "state_po",
    "district_num",
    "sum_candidatevotes",
    "reported_totalvotes",
    "difference",
    "pct_of_total",
    "reason",
]


def _classify(diff: float, pct: float) -> str:
    """Describe the shape of a mismatch without asserting an unverified cause.

    These labels group the failures for the data-quality report. They are
    descriptive only — confirming *why* a given race fails needs the state's
    certified return, not an inference from the discrepancy.
    """
    if abs(diff) <= 10:
        return "rounding_or_transcription (<=10 votes)"
    if pct >= 40:
        return "multi_round_contest_suspected (candidate sum ~2x total)"
    if diff > 0:
        return "candidate_sum_exceeds_total"
    return "candidate_sum_below_total"


def find_reconciliation_failures(returns: pd.DataFrame) -> pd.DataFrame:
    """Return one row per race whose candidate votes do not match the reported total.

    Races with no reported total are *not* failures — they are the unopposed-race
    sentinel handled in :func:`.medsl._mask_unreported_races` and are left alone.
    """
    agg = returns.groupby("race_id").agg(
        sum_candidatevotes=("candidatevotes", "sum"),
        reported_totalvotes=("totalvotes", "max"),
        cycle=("cycle", "first"),
        office=("office", "first"),
        state_po=("state_po", "first"),
        district_num=("district_num", "first"),
    )
    checked = agg[agg["reported_totalvotes"] > 0].copy()
    failures = checked[checked["sum_candidatevotes"] != checked["reported_totalvotes"]].copy()
    if failures.empty:
        return pd.DataFrame(columns=QUARANTINE_COLUMNS)

    failures["difference"] = failures["sum_candidatevotes"] - failures["reported_totalvotes"]
    failures["pct_of_total"] = (failures["difference"].abs() / failures["reported_totalvotes"] * 100).round(3)
    failures["reason"] = [
        _classify(float(d), float(p))
        for d, p in zip(failures["difference"], failures["pct_of_total"], strict=True)
    ]
    return failures.reset_index()[QUARANTINE_COLUMNS].sort_values(["pct_of_total"], ascending=False)


def split_quarantine(returns: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Split silver returns into (retained, quarantined_rows, quarantine_manifest)."""
    manifest = find_reconciliation_failures(returns)
    bad_ids = set(manifest["race_id"]) if not manifest.empty else set()
    mask = returns["race_id"].isin(bad_ids)
    return returns[~mask].reset_index(drop=True), returns[mask].reset_index(drop=True), manifest


def summarize(manifest: pd.DataFrame, *, races_total: int) -> dict:
    """Compact stats for the data-quality report and the build log."""
    if manifest.empty:
        return {"quarantined_races": 0, "races_total": races_total, "pct_of_races": 0.0, "by_reason": {}}
    return {
        "quarantined_races": int(len(manifest)),
        "races_total": int(races_total),
        "pct_of_races": round(len(manifest) / races_total * 100, 3) if races_total else 0.0,
        "by_reason": manifest["reason"].value_counts().to_dict(),
        "by_office": manifest["office"].value_counts().to_dict(),
    }

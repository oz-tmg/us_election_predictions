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

**Corrected 2026-10-07.** The rule was exact equality against ``totalvotes``, and that
excluded 32 House races and 2 presidential races, 27 of which were not defective at all.
MEDSL carries blank, void, over- and under-vote ballots as pseudo-candidate rows, and
whether its ``totalvotes`` counts them **varies by state and year** with nothing in the data
saying which convention was used. All 26 of New York's 2024 House races were excluded because
their totals omit BLANK and VOID; the District of Columbia's 2024 presidential return was
excluded because its total omits OVERVOTES and UNDERVOTES; New York's 2024 presidential total
*includes* both. The cost was not abstract: with no 2024 House result for New York, the
House model fell back to 2022 — the state's Republican peak — and mispriced 26 seats of the
sealed 2026 forecast, four of them below 50% Democratic in seats Democrats had just won
(``reports/preregistration_2026-11-03_findings.md`` F-2).

So a race is now reconciled if it matches its reported total under *either* convention,
within a de-minimis allowance. That keeps the uniform-exclusion principle — no
cause-specific patching, no imputation, nothing silently corrected — while not condemning a
race for a bookkeeping choice its publisher never declared. Four House races still fail, and
all four are structurally wrong rather than conventionally different: Louisiana's 2002
all-party primary, the two court-ordered Texas 2006 re-runs, and Maine's 2018 ranked-choice
count.
"""

from __future__ import annotations

import pandas as pd

#: Rows that are not votes for anybody: blank ballots, void ballots, over- and
#: under-votes, exhausted ranked ballots, and administrative counts. MEDSL carries them as
#: pseudo-candidates, and **whether its ``totalvotes`` includes them varies by state and by
#: year**, which is the whole problem. New York's 2024 House files exclude them from the
#: total (BLANK + VOID is exactly the 6-10% gap on all 26 districts); the District of
#: Columbia's 2024 presidential file excludes OVERVOTES + UNDERVOTES, exactly its 2,535-vote
#: gap; New York's 2024 presidential file *includes* UNDERVOTES and VOID. Nothing in the data
#: says which convention a given race used.
#:
#: Note ``SCATTERING`` and ``WRITE-IN`` are deliberately absent: those are votes somebody
#: cast for somebody, and MEDSL's totals include them.
NON_VOTE_LABELS = frozenset(
    {
        "BLANK",
        "BLANKS",
        "BLANK VOTES",
        "VOID",
        "SPOILED",
        "OVERVOTES",
        "OVER VOTES",
        "UNDERVOTES",
        "UNDER VOTES",
        "EXHAUSTED",
        "BALLOTS CAST",
        "REGISTERED VOTERS",
    }
)

#: A race reconciles if it lands within this of its reported total under *either*
#: convention. Absolute floor for transcription noise; relative floor for a residual too
#: small to carry signal. New York's 2024 presidential return is 874 votes out of 8,381,429
#: — 0.0104% — which no row accounts for and which cannot move a vote share.
#:
#: Both floors are deliberately far below the structural failures this gate exists to
#: catch: Louisiana 2002's all-party primary is 93.4% out, the two court-ordered Texas 2006
#: re-runs are 83.6% and 56.9%, and Maine 2018's ranked-choice first-versus-final round is
#: 2.07%. Those four are the only House races that still fail, which is the intended result.
RECONCILIATION_ABS_TOLERANCE = 10.0
RECONCILIATION_PCT_TOLERANCE = 0.001

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


def unreconciled_races(returns: pd.DataFrame) -> tuple[list[str], int]:
    """``(race_ids that do not reconcile under either convention, races checked)``.

    The single definition of "reconciles", shared with ``validation`` so the gate and the
    quarantine cannot drift apart. They did drift: exact equality in the validator excluded
    32 races the quarantine had already been corrected to accept, and the build failed on
    its own corrected data.
    """
    ids = find_reconciliation_failures(returns)
    checked = 0
    if {"race_id", "totalvotes"}.issubset(returns.columns):
        totals = returns.groupby("race_id")["totalvotes"].max()
        checked = int((totals > 0).sum())
    return (ids["race_id"].tolist() if not ids.empty else []), checked


def find_reconciliation_failures(returns: pd.DataFrame) -> pd.DataFrame:
    """Return one row per race whose candidate votes do not match the reported total.

    Races with no reported total are *not* failures — they are the unopposed-race
    sentinel handled in :func:`.medsl._mask_unreported_races` and are left alone.
    """
    df = returns.copy()
    label = df.get("candidate", pd.Series("", index=df.index)).fillna("").astype(str).str.upper().str.strip()
    df["_is_vote"] = ~label.isin(NON_VOTE_LABELS)
    df["_vote_only"] = df["candidatevotes"].where(df["_is_vote"], 0)

    # Reconciliation needs only race_id, candidatevotes, totalvotes and candidate. The rest
    # is reporting metadata, and it is optional so that this predicate can be shared with
    # `validation` without forcing every caller to carry a full silver schema.
    spec = {
        "sum_candidatevotes": ("candidatevotes", "sum"),
        "sum_votes_only": ("_vote_only", "sum"),
        "reported_totalvotes": ("totalvotes", "max"),
    }
    for col in ("cycle", "office", "state_po", "district_num"):
        if col in df.columns:
            spec[col] = (col, "first")
    agg = df.groupby("race_id").agg(**spec)
    for col in ("cycle", "office", "state_po", "district_num"):
        if col not in agg.columns:
            agg[col] = pd.NA
    checked = agg[agg["reported_totalvotes"] > 0].copy()

    # The source's convention is not recorded, so try both and take the better. A race is a
    # failure only if it cannot be reconciled *either* way -- which leaves exactly the races
    # whose totals are structurally wrong rather than conventionally different.
    gap_all = (checked["sum_candidatevotes"] - checked["reported_totalvotes"]).abs()
    gap_votes = (checked["sum_votes_only"] - checked["reported_totalvotes"]).abs()
    best = pd.concat([gap_all, gap_votes], axis=1).min(axis=1)
    allowed = pd.concat(
        [
            pd.Series(RECONCILIATION_ABS_TOLERANCE, index=checked.index),
            RECONCILIATION_PCT_TOLERANCE * checked["reported_totalvotes"],
        ],
        axis=1,
    ).max(axis=1)

    failures = checked[best > allowed].copy()
    if failures.empty:
        return pd.DataFrame(columns=QUARANTINE_COLUMNS)

    # Report the signed gap under whichever convention came closer, so the reason label
    # describes the failure that actually survived.
    closer_is_votes = gap_votes.loc[failures.index] < gap_all.loc[failures.index]
    failures["difference"] = (failures["sum_candidatevotes"] - failures["reported_totalvotes"]).where(
        ~closer_is_votes, failures["sum_votes_only"] - failures["reported_totalvotes"]
    )
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

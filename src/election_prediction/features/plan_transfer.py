"""Old-to-new vote transfer: place a prior on boundaries it was not measured on (RD-003).

Nine states vote in November 2026 under a different congressional map than they used in
2024, so 173 seats have no usable prior: their district number survived, their territory
did not. Until something fills that gap those seats fall back to their state's presidential
lean with an inflated sigma (``models.baseline.projection``), which is honest and crude.

This module is what replaces the crude part. The chain is:

    precinct results  --(areal/population weight)-->  census block  --(BAF)-->  new district

and every link loses something. A precinct split by a new district line has to have its
votes divided; the division is a guess weighted by block population, not a count. Blocks
whose assignment cannot be resolved drop out. Precincts that cannot be geocoded to blocks
drop out. The output is therefore never "the district's 2024 vote" — it is an estimate with
three distinct ways of being wrong.

**The three confidence components are reported separately and never collapsed into one
score.** That is a deliberate constraint from ``docs/redistricting-change-plan.md``, and it
matters because they fail differently:

* ``unsplit_share`` — the fraction of the new district's transferred vote that came from
  precincts lying entirely inside it. High means little splitting was needed.
* ``old_district_majority_share`` — the fraction contributed by precincts that were in a
  single old district. Low means the new seat is a blend of several old ones, so its prior
  inherits several different incumbency and candidate effects.
* ``geocoded_share`` — the fraction of the old vote that could be placed at all. Low means
  the transfer is extrapolating from a subset.

A district can score well on one and badly on another, and a single collapsed number would
hide exactly that. A consumer deciding whether to trust a transferred prior needs all three.

**The sigma for a transferred prior is measured, not assumed.** ``backtest_transfer``
compares transferred priors against what actually happened in a cycle where both the old
and new maps are observed — Virginia 2020 → 2022 is the first — against two comparators:
no prior at all, and the state-lean fallback the projection uses today. The residual spread
from that backtest is what ``projection`` should be handed as ``transfer_sigma``. Until
that number exists, this module will not pretend to have one.

Nothing here runs against an unregistered source: see ``REQUIRED_SOURCES`` and
``docs/dataset-registry.md`` § "RD-003 geographic-reconciliation sources".
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

# Registered 2026-09-30 in docs/dataset-registry.md. A transfer that cannot name its
# sources is not reproducible, so the gate is in code rather than in a comment.
REQUIRED_SOURCES = ("census_pl94171_2020", "census_baf_2020", "rdh_precinct_boundaries")

CONFIDENCE_COMPONENTS = ("unsplit_share", "old_district_majority_share", "geocoded_share")

TRANSFER_COLUMNS = [
    "state_po",
    "new_district",
    "transferred_dem_share",
    "transferred_weight",
    *CONFIDENCE_COMPONENTS,
    "n_source_precincts",
    "n_source_old_districts",
]


class UnregisteredSourceError(ValueError):
    """A transfer was attempted against a source that is not in the dataset registry."""


class TransferSigmaUnmeasured(ValueError):
    """A transferred prior was requested before the backtest measured its uncertainty."""


def assert_sources_registered(sources: dict[str, str]) -> None:
    """Every required source must be present and carry a registry status.

    The point is not the string check — it is that acquiring geographic data for this
    project is gated on a licence review (RDH's terms are noncommercial, nonpartisan and
    explicitly anti-gerrymandering), and a pipeline that can silently run without one is a
    governance hole regardless of what the docs say.
    """
    missing = [s for s in REQUIRED_SOURCES if not sources.get(s)]
    if missing:
        raise UnregisteredSourceError(
            f"sources {missing} are not registered. See docs/dataset-registry.md "
            "§ 'RD-003 geographic-reconciliation sources' and register them with licence, "
            "permitted use, privacy tier and attribution before running a transfer."
        )


@dataclass(frozen=True)
class TransferInputs:
    """The three tables a transfer needs, already conformed to block level.

    ``blocks``     : block_id, state_po, vap (or pop) — from P.L. 94-171
    ``assignments``: block_id, new_district          — from the BAF for the NEW plan
    ``precincts``  : precinct_id, block_id, state_po, old_district, dem_votes, rep_votes
                     — precinct results already apportioned to blocks by the caller's
                       geocoding step, which is where the areal/population weighting lives
    """

    blocks: pd.DataFrame
    assignments: pd.DataFrame
    precincts: pd.DataFrame


def transfer(inputs: TransferInputs, *, sources: dict[str, str]) -> pd.DataFrame:
    """Place old precinct results onto new districts, carrying three confidence components.

    Returns one row per new district. ``transferred_dem_share`` is a two-party share, on the
    same basis as everything else in the stack (CLAUDE.md §6).
    """
    assert_sources_registered(sources)

    blocks, assign, prec = inputs.blocks, inputs.assignments, inputs.precincts
    for frame, cols in (
        (blocks, {"block_id", "state_po"}),
        (assign, {"block_id", "new_district"}),
        (prec, {"precinct_id", "block_id", "old_district", "dem_votes", "rep_votes"}),
    ):
        missing = cols - set(frame.columns)
        if missing:
            raise ValueError(f"transfer input is missing column(s) {sorted(missing)}")

    weight_col = "vap" if "vap" in blocks.columns else "pop"
    if weight_col not in blocks.columns:
        raise ValueError("blocks must carry 'vap' (preferred) or 'pop' as the allocation weight")

    # ---- geocoded share: what fraction of the old vote can be placed at all? -------------
    placed = prec.merge(assign, on="block_id", how="left")
    placed["two_party"] = placed["dem_votes"].astype(float) + placed["rep_votes"].astype(float)
    total_vote = placed.groupby("state_po", dropna=False)["two_party"].sum()
    resolved = placed[placed["new_district"].notna()].copy()
    geocoded = resolved.groupby("state_po")["two_party"].sum() / total_vote

    if not len(resolved):
        return pd.DataFrame(columns=TRANSFER_COLUMNS)

    # ---- splitting: a precinct touching >1 new district had to be divided ----------------
    per_precinct_districts = resolved.groupby("precinct_id")["new_district"].nunique()
    resolved["precinct_is_split"] = resolved["precinct_id"].map(per_precinct_districts) > 1

    out = []
    for (state, new_d), grp in resolved.groupby(["state_po", "new_district"]):
        two_party = grp["two_party"].sum()
        dem = grp["dem_votes"].astype(float).sum()
        unsplit = grp.loc[~grp["precinct_is_split"], "two_party"].sum()

        by_old = grp.groupby("old_district")["two_party"].sum()
        majority = float(by_old.max() / two_party) if two_party > 0 else float("nan")

        out.append(
            {
                "state_po": state,
                "new_district": new_d,
                "transferred_dem_share": float(dem / two_party) if two_party > 0 else float("nan"),
                "transferred_weight": float(two_party),
                "unsplit_share": float(unsplit / two_party) if two_party > 0 else float("nan"),
                "old_district_majority_share": majority,
                "geocoded_share": float(geocoded.get(state, float("nan"))),
                "n_source_precincts": int(grp["precinct_id"].nunique()),
                "n_source_old_districts": int(by_old.size),
            }
        )
    return pd.DataFrame(out)[TRANSFER_COLUMNS].sort_values(["state_po", "new_district"]).reset_index(
        drop=True
    )


def backtest_transfer(
    transferred: pd.DataFrame, actual: pd.DataFrame, *, state_lean_fallback: pd.DataFrame
) -> dict:
    """Score a transfer against what actually happened, versus two fixed comparators.

    ``actual`` needs ``state_po``, ``new_district``, ``actual_dem_share``. The comparators
    are the ones the plan names: **no prior at all** (the chamber mean, i.e. what you get
    with no district information) and **the state-lean fallback** the projection uses today.
    A transfer that cannot beat the fallback is not worth its complexity.

    The returned ``transfer_sigma`` is the residual standard deviation — the number
    ``projection.project_house`` should be handed. It is measured here and nowhere else.
    """
    merged = transferred.merge(actual, on=["state_po", "new_district"], how="inner")
    if not len(merged):
        raise ValueError("no overlap between transferred priors and actual results")
    merged = merged.merge(state_lean_fallback, on=["state_po"], how="left")

    err = merged["transferred_dem_share"] - merged["actual_dem_share"]
    no_prior_err = merged["actual_dem_share"].mean() - merged["actual_dem_share"]
    fallback_err = merged["state_pres_lean_share"] - merged["actual_dem_share"]

    def mae(x: pd.Series) -> float:
        return float(np.abs(x).mean())

    return {
        "n_districts": int(len(merged)),
        "transfer_mae": mae(err),
        "no_prior_mae": mae(no_prior_err),
        "state_lean_fallback_mae": mae(fallback_err),
        "beats_no_prior": bool(mae(err) < mae(no_prior_err)),
        "beats_fallback": bool(mae(err) < mae(fallback_err)),
        # The measured quantity. Hand this to projection as transfer_sigma; never a default.
        "transfer_sigma": float(err.std(ddof=1)) if len(merged) > 1 else float("nan"),
        "confidence_components": {
            c: {"min": float(merged[c].min()), "median": float(merged[c].median())}
            for c in CONFIDENCE_COMPONENTS
            if c in merged.columns
        },
    }


def transfer_sigma_from_backtest(backtest: dict) -> float:
    """Pull the measured sigma out, refusing an unmeasured or useless one.

    A transferred prior that does not beat the state-lean fallback must not be used: the
    projection already has the fallback, and swapping it for something worse while calling
    it a transfer would be a regression wearing a better name.
    """
    sigma = backtest.get("transfer_sigma")
    if sigma is None or not np.isfinite(sigma):
        raise TransferSigmaUnmeasured(
            "transfer_sigma is unmeasured. Run backtest_transfer on a cycle where both maps "
            "are observed (Virginia 2020->2022 is the registered first case) before any "
            "transferred prior reaches a projection."
        )
    if not backtest.get("beats_fallback"):
        raise TransferSigmaUnmeasured(
            f"the transfer does not beat the state-lean fallback "
            f"({backtest['transfer_mae']:.4f} vs {backtest['state_lean_fallback_mae']:.4f}). "
            "Using it would be a regression; keep the fallback and improve the transfer."
        )
    return float(sigma)

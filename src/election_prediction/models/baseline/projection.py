"""Forward projection of a live cycle from fitted baselines (House and Senate, 2026).

Everything else in the baseline stack is retrospective: it fits and scores on cycles whose
results are known. This module runs the same fitted models *forward* onto a cycle that has
not happened, which needs three inputs the backtest gets for free:

* **The seat roster** — from ``race_universe_<cycle>.parquet`` (P0-001), not from returns.
* **The national environment** — the backtest conditions on the true contemporaneous
  value, which a live cycle does not have. For 2026 it comes from special-election
  overperformance (``data/special_elections.implied_national_dem_share``), and it is the
  single largest source of error in the projection: the House model's coefficient on
  ``national_dem_share`` is +0.884, so a 1-point error in the national call moves nearly
  every district by 0.9 points.
* **Incumbency** — from the seat roster's ``incumbent_party``, under the assumption that
  the sitting member both runs and is renominated. ``features.filings`` now verifies the
  first half of that from FEC filings (``incumbent_status = "filed"``); the second half is
  still unverified, because renomination needs primary results and FEC does not publish
  them. Projections therefore keep ``incumbency_assumed`` so a consumer cannot mistake the
  assumption for a finding, and ``filings_summary`` reports how much of the roster the
  filing evidence covers.

* **District boundaries** — a House seat's prior is its last result *on the same
  territory*. ``plan_era`` assumes one map per decade, and several states use a different
  congressional map in 2026 than in 2024, so the roster's ``boundary_confidence`` decides
  whether the old-number prior may be used at all (RD-002,
  ``docs/redistricting-change-plan.md``):

  ============  ======================================  ======================  ===========
  confidence    prior                                   ``source``              sigma
  ============  ======================================  ======================  ===========
  unchanged     last result under the same plan         ``model``               residual
  redrawn       transferred share, if Track C built it  ``model_transferred``   widened
  redrawn       otherwise: state presidential lean      ``fallback_state_lean`` widened
  pending       as redrawn (in-effect plan)             as redrawn              as redrawn
  unverified    **refused** unless ``allow_unverified``  ``model_unverified``    residual
  ============  ======================================  ======================  ===========

  The fallback is honest about what is known: a redrawn district with no transferred prior
  is, to the model, a seat whose only known geography is its state, so it gets the state's
  lean and a sigma widened by the within-state dispersion of district leans — a measured
  quantity the caller supplies, not a factor invented here. The state lean is on the
  presidential basis while the model's ``district_lean`` is on the House basis; that
  mismatch is accepted for a fallback and is one reason its sigma is wide.

The Senate model takes **no national-environment feature** (its terms are state
presidential lean, incumbency, and the midterm penalty), so the specials estimate does not
reach it through the model. Applying it there requires an explicit uniform-swing scenario,
which ``project_senate`` exposes as ``uniform_swing`` rather than smuggling in.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .house import DEFAULT_SIGMA, NON_VOTING_JURISDICTIONS, OLSModel

PROJECTION_COLUMNS = [
    "geography_id",
    "state_po",
    "district_num",
    "office",
    "mean_dem_share",
    "sigma",
    "source",
    "boundary_confidence",
    "incumbent_party",
    "incumbency_assumed",
]

# ``boundary_confidence`` vocabulary, written by ``features.race_universe`` and, once the
# plan-version register exists (RD-001), by ``features.plan_versions``. Anything else is an
# error, not a fifth category.
BOUNDARY_UNCHANGED = "unchanged"
BOUNDARY_REDRAWN = "redrawn"
BOUNDARY_PENDING = "pending"
BOUNDARY_UNVERIFIED = "unverified"
BOUNDARY_CONFIDENCE_VALUES = frozenset(
    {BOUNDARY_UNCHANGED, BOUNDARY_REDRAWN, BOUNDARY_PENDING, BOUNDARY_UNVERIFIED}
)

# Where Track C (RD-003) will write a prior placed on the *new* boundaries. Named here, on
# the consumer, for the same reason as ``RESOLVED_PARTY_COLUMN``: the producer imports the
# name rather than both sides spelling it independently.
TRANSFERRED_PRIOR_COLUMN = "transferred_dem_share"


class UnverifiedBoundaryError(ValueError):
    """A House seat's boundaries are unverified and the caller did not opt in."""


# P0-003 replaced the hand-kept ``INCUMBENT_PARTY_OVERRIDES`` table that used to live here.
# The one entry it held -- Cynthia Lummis, labelled OTHER in the 2026 roster because
# Wyoming's 2020 Senate returns carry a null party for every candidate -- is now resolved
# from the FEC roster, which records her as ``REP``. Any seat whose party the returns cannot
# supply is filled the same way, so the table has nothing left to hold.
#
# ``filings.resolve_incumbent_status`` writes this column from
# ``filings.resolved_incumbent_party``; ``_incumbency_terms`` prefers it when present and
# falls back to the raw ``incumbent_party`` otherwise, so a projection still runs before
# the FEC layer is built. The producer and this constant must agree on the name --
# ``test_filings`` pins that, because a silent mismatch would leave the fallback running
# forever while every unit test still passed.
RESOLVED_PARTY_COLUMN = "incumbent_party_resolved"

# Senators elected as independents who caucus with the Democrats. Two-party vote share
# cannot see them -- Sanders's 2024 race records a Democratic share of 0.000 and King's
# 0.238 -- so counting Senate control from returns alone hands both seats to Republicans
# and understates Democratic holdovers by two.
INDEPENDENT_DEM_CAUCUS = frozenset({("ME", 2024), ("VT", 2024)})


def _incumbency_terms(universe: pd.DataFrame) -> pd.DataFrame:
    out = universe.copy()
    party = out["incumbent_party"].fillna("").astype(str).str.upper()
    if RESOLVED_PARTY_COLUMN in out.columns:
        # A resolved label only ever *fills* a gap -- it never overwrites a party the
        # returns already state -- so preferring it cannot silently reclassify a seat.
        resolved = out[RESOLVED_PARTY_COLUMN].fillna("").astype(str).str.upper()
        party = party.where(party.isin(["DEMOCRAT", "REPUBLICAN"]), resolved)
    # An open seat is one with no identified incumbent; both indicators go to zero, which
    # is exactly how the fitted models encode it.
    out["incumbent_dem"] = (party == "DEMOCRAT").astype(float)
    out["incumbent_rep"] = (party == "REPUBLICAN").astype(float)
    return out


def _lean_coefficient(model: OLSModel) -> float:
    """The fitted weight on ``district_lean`` — how far a lean error moves the prediction."""
    if model.coef_ is None or "district_lean" not in model.features:
        return 1.0
    # ``coef_[0]`` is the intercept; features follow in order.
    return float(model.coef_[1 + model.features.index("district_lean")])


def _route_boundaries(seats: pd.DataFrame, *, allow_unverified: bool) -> pd.Series:
    """Validate ``boundary_confidence`` and refuse unverified seats unless opted in."""
    if "boundary_confidence" not in seats.columns:
        conf = pd.Series(BOUNDARY_UNVERIFIED, index=seats.index)
    else:
        conf = seats["boundary_confidence"].fillna(BOUNDARY_UNVERIFIED).astype(str)
    bad = sorted(set(conf) - BOUNDARY_CONFIDENCE_VALUES)
    if bad:
        raise ValueError(
            f"unknown boundary_confidence value(s) {bad}; expected {sorted(BOUNDARY_CONFIDENCE_VALUES)}"
        )
    n_unverified = int((conf == BOUNDARY_UNVERIFIED).sum())
    if n_unverified and not allow_unverified:
        raise UnverifiedBoundaryError(
            f"{n_unverified} House seat(s) have unverified boundaries. Compile the plan-version "
            "register (RD-001) or pass allow_unverified=True to project them as unchanged -- "
            "an assumption the report must then state."
        )
    return conf


def project_house(
    universe: pd.DataFrame,
    model: OLSModel,
    *,
    national_dem_share: float,
    lagged_national_dem_share: float,
    resid_sigma: float | None = None,
    pres_reference: pd.DataFrame | None = None,
    fallback_lean_sd: float | None = None,
    transfer_sigma: float | None = None,
    allow_unverified: bool = False,
) -> tuple[pd.DataFrame, dict]:
    """Project every House seat on the ballot from a prior result and a national environment.

    ``lagged_national_dem_share`` is the national share the *prior* cycle's district
    results are measured against, matching how ``district_lean`` is constructed in
    training — the lean must not contain information from the cycle being predicted.

    Which prior a seat gets is decided by its ``boundary_confidence`` (module docstring).
    Redrawn seats need ``pres_reference`` (``state_po``, ``state_pres_lean``) and
    ``fallback_lean_sd`` — the within-state dispersion of district leans, measured from
    the training panel — or, if Track C has supplied ``transferred_dem_share``,
    ``transfer_sigma``. None of these has a default: a redrawn seat with no stated
    uncertainty is a silent assumption, which is what this routing exists to prevent.
    """
    seats = universe[
        (universe["office"] == "us_house") & (~universe["state_po"].isin(NON_VOTING_JURISDICTIONS))
    ].copy()
    seats = _incumbency_terms(seats)
    conf = _route_boundaries(seats, allow_unverified=allow_unverified)
    seats["boundary_confidence"] = conf
    seats["national_dem_share"] = float(national_dem_share)
    sigma = float(resid_sigma) if resid_sigma else DEFAULT_SIGMA

    old_prior = pd.to_numeric(seats["prior_dem_share"], errors="coerce")
    redrawn = conf.isin([BOUNDARY_REDRAWN, BOUNDARY_PENDING])

    # ---- transferred prior (Track C), when present ----------------------------------
    transferred = pd.Series(np.nan, index=seats.index, dtype=float)
    if TRANSFERRED_PRIOR_COLUMN in seats.columns:
        transferred = pd.to_numeric(seats[TRANSFERRED_PRIOR_COLUMN], errors="coerce")
    has_transfer = redrawn & transferred.notna()
    if has_transfer.any() and transfer_sigma is None:
        raise ValueError(
            "transferred priors present but transfer_sigma not given; state the transfer uncertainty"
        )

    # ---- state-lean fallback for redrawn seats without a transfer -------------------
    needs_fallback = redrawn & ~has_transfer
    state_lean = pd.Series(np.nan, index=seats.index, dtype=float)
    if needs_fallback.any():
        if pres_reference is None or fallback_lean_sd is None:
            raise ValueError(
                f"{int(needs_fallback.sum())} redrawn seat(s) have no transferred prior; "
                "pres_reference and fallback_lean_sd are required for the state-lean fallback"
            )
        ref = pres_reference[["state_po", "state_pres_lean"]].drop_duplicates("state_po")
        state_lean = seats[["state_po"]].merge(ref, on="state_po", how="left")["state_pres_lean"].to_numpy()
        state_lean = pd.Series(state_lean, index=seats.index, dtype=float)
        missing = needs_fallback & state_lean.isna()
        if missing.any():
            raise ValueError(
                f"no state_pres_lean for redrawn seats in {sorted(seats.loc[missing, 'state_po'].unique())}"
            )

    # ---- the lean each seat is projected from --------------------------------------
    # The old-number prior is *discarded* for redrawn seats, not merely overridden: a
    # redrawn district's last result is a fact about different territory.
    lean = old_prior - lagged_national_dem_share
    lean = lean.where(~redrawn, np.nan)
    lean = lean.where(~has_transfer, transferred - lagged_national_dem_share)
    lean = lean.where(~needs_fallback, state_lean)
    seats["district_lean"] = lean

    usable = seats["district_lean"].notna()
    seats.loc[usable, "mean_dem_share"] = model.predict(seats[usable])

    source = np.select(
        [~usable, has_transfer, needs_fallback, conf == BOUNDARY_UNVERIFIED],
        ["no_prior_result", "model_transferred", "fallback_state_lean", "model_unverified"],
        default="model",
    )
    seats["source"] = source

    # A widened sigma adds the lean's uncertainty, scaled by how hard the model leans on
    # it, in quadrature with the residual. Both inputs are measured, neither is a factor.
    beta = _lean_coefficient(model)
    fallback_sigma = (
        math.hypot(sigma, beta * float(fallback_lean_sd)) if fallback_lean_sd is not None else float("nan")
    )
    transferred_sigma = (
        math.hypot(sigma, beta * float(transfer_sigma)) if transfer_sigma is not None else float("nan")
    )
    seats["sigma"] = np.select(
        [has_transfer, needs_fallback], [transferred_sigma, fallback_sigma], default=sigma
    )
    seats["incumbency_assumed"] = True
    out = seats.dropna(subset=["mean_dem_share"]).reindex(columns=PROJECTION_COLUMNS).reset_index(drop=True)

    coverage = {
        "seats_projected": int(len(out)),
        "seats_in_roster": int(len(seats)),
        "seats_without_prior": int((~usable).sum()),
        "seats_by_boundary_confidence": conf.value_counts().sort_index().to_dict(),
        "seats_by_source": pd.Series(source).value_counts().sort_index().to_dict(),
        "redrawn_states": sorted(seats.loc[redrawn, "state_po"].unique().tolist()),
        "national_dem_share": float(national_dem_share),
        "resid_sigma": sigma,
        "fallback_lean_sd": None if fallback_lean_sd is None else float(fallback_lean_sd),
        "fallback_sigma": None if math.isnan(fallback_sigma) else fallback_sigma,
        "boundaries_assumed_unchanged": int((conf == BOUNDARY_UNVERIFIED).sum()),
        "incumbency_verified": False,
    }
    return out, coverage


def project_senate(
    universe: pd.DataFrame,
    model: OLSModel,
    pres_reference: pd.DataFrame,
    *,
    midterm_penalty: float,
    resid_sigma: float | None = None,
    uniform_swing: float = 0.0,
) -> tuple[pd.DataFrame, dict]:
    """Project the Senate seats on the ballot from state presidential lean and incumbency.

    ``pres_reference`` supplies ``state_pres_lean`` per state from the most recent
    presidential cycle. ``midterm_penalty`` is +1 when a Republican holds the White House
    and -1 when a Democrat does, matching the fitted sign convention.

    ``uniform_swing`` is a **scenario** knob in two-party share points, added after
    prediction. The Senate model has no national-environment term, so this is the only way
    a specials-derived environment can reach it, and keeping it separate from the model
    prediction is deliberate: it is an assumption laid on top, not an estimate.
    """
    seats = universe[universe["office"] == "us_senate"].copy()
    seats = _incumbency_terms(seats)
    seats = seats.merge(pres_reference[["state_po", "state_pres_lean"]], on="state_po", how="left")
    seats["midterm_penalty"] = float(midterm_penalty)

    usable = seats["state_pres_lean"].notna()
    seats.loc[usable, "mean_dem_share"] = model.predict(seats[usable])
    seats["mean_dem_share"] = seats["mean_dem_share"] + float(uniform_swing)
    seats["source"] = np.where(usable, "model", "no_pres_reference")

    sigma = float(resid_sigma) if resid_sigma else DEFAULT_SIGMA
    seats["sigma"] = sigma
    seats["incumbency_assumed"] = True
    seats["district_num"] = np.nan
    seats["boundary_confidence"] = "n/a"  # statewide; no boundary risk
    out = seats.dropna(subset=["mean_dem_share"]).reindex(columns=PROJECTION_COLUMNS).reset_index(drop=True)

    coverage = {
        "seats_projected": int(len(out)),
        "seats_in_roster": int(len(seats)),
        "midterm_penalty": float(midterm_penalty),
        "uniform_swing": float(uniform_swing),
        "resid_sigma": sigma,
        "incumbency_verified": False,
    }
    return out, coverage

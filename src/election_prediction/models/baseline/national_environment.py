"""National-environment estimator contract (NE-001).

The House baseline's largest coefficient is on ``national_dem_share`` (+0.884), and the
backtest conditions on its *true* value. A live cycle has to get it from somewhere, and
every candidate source is a different kind of thing: special-election overperformance is
an association with the environment whose shrinkage factor cannot be identified from one
cycle; a generic-ballot average is a measurement of it (blocked on NE-000); economic
fundamentals are a 13-cycle regression (NE-004). This module is the one shape they all
return into, so a projection consumes a contract rather than a particular estimator's
DataFrame — and so a band cannot be collapsed to a point by the first caller in a hurry.

The field that does the work is ``identified``. It is ``False`` whenever a free parameter
was assumed rather than estimated, and for the specials band it is ``False`` **by
construction**: :func:`validate` refuses a specials-derived estimate that claims otherwise,
in the same spirit as ``filings.validate_filings`` refusing to emit ``nominated``.

A projection may be produced from:

* a **band** — the estimator sweeps its unidentified parameter and every row carries the
  assumption that generated it, so the consumer must iterate and report the sweep;
* an **identified point** — a measured estimate with a backtest behind it;
* a **scenario** — an explicit, labelled ``point`` that is unidentified because it *is*
  the assumption. It is allowed because it cannot be mistaken for a finding.

It may **not** be produced from an unidentified point that is not a scenario. That is the
case where a number with no support would silently become the forecast, and
:func:`projectable` raises on it.

See ``docs/national-environment-plan.md`` Track A.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import pandas as pd

from ...data import special_elections as se

ESTIMATORS = frozenset({"specials_band", "generic_ballot", "fundamentals", "scenario"})
STATUSES = frozenset({"band", "point", "unavailable"})

# Estimators that are unidentified by construction: a validator refuses any estimate from
# them that claims ``identified = True``, whatever a caller passed.
UNIDENTIFIED_BY_CONSTRUCTION = frozenset({"specials_band", "scenario"})

BAND_COLUMNS = ["assumption", "national_dem_share", "share_std_error"]


class ContractError(ValueError):
    """An estimate violates the national-environment contract."""


@dataclass
class NationalEnvironment:
    """One national two-party Democratic share estimate, or a band of them."""

    estimator: str
    status: str
    national_dem_share: float | None
    band: pd.DataFrame | None
    identified: bool
    assumptions: list[str] = field(default_factory=list)
    caveats: list[str] = field(default_factory=list)
    provenance: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """JSON-serialisable form; the band becomes a list of row records."""
        return {
            "estimator": self.estimator,
            "status": self.status,
            "national_dem_share": self.national_dem_share,
            "band": None if self.band is None else self.band.to_dict(orient="records"),
            "identified": self.identified,
            "assumptions": list(self.assumptions),
            "caveats": list(self.caveats),
            "provenance": dict(self.provenance),
        }


def validate(est: NationalEnvironment) -> NationalEnvironment:
    """Enforce the contract; raise :class:`ContractError` rather than return a report.

    A malformed estimate must not reach a projection, so this fails loudly instead of
    handing back an ``ok`` flag a caller could ignore.
    """
    if est.estimator not in ESTIMATORS:
        raise ContractError(f"unknown estimator {est.estimator!r}; expected one of {sorted(ESTIMATORS)}")
    if est.status not in STATUSES:
        raise ContractError(f"unknown status {est.status!r}; expected one of {sorted(STATUSES)}")

    if est.estimator in UNIDENTIFIED_BY_CONSTRUCTION and est.identified:
        raise ContractError(
            f"{est.estimator} is unidentified by construction and cannot claim identified=True; "
            "its free parameter was assumed, not estimated"
        )

    if est.status == "band":
        if est.national_dem_share is not None:
            raise ContractError("a band carries no single national_dem_share; the sweep is the output")
        if est.band is None or len(est.band) == 0:
            raise ContractError("status='band' requires a non-empty band")
        missing = [c for c in BAND_COLUMNS if c not in est.band.columns]
        if missing:
            raise ContractError(f"band is missing columns {missing}")
        blank = est.band["assumption"].astype(str).str.strip() == ""
        if est.band["assumption"].isna().any() or blank.any():
            raise ContractError("every band row must carry the assumption that generated it")
        if est.identified:
            raise ContractError("a band is by definition unidentified; identified must be False")
    elif est.status == "point":
        if est.national_dem_share is None:
            raise ContractError("status='point' requires national_dem_share")
        if est.band is not None:
            raise ContractError("a point estimate carries no band")
        if not est.identified and not est.assumptions:
            raise ContractError("an unidentified point must name the assumption it rests on")
    else:  # unavailable
        if est.national_dem_share is not None or est.band is not None:
            raise ContractError("status='unavailable' carries neither a share nor a band")
    return est


def projectable(est: NationalEnvironment) -> pd.DataFrame:
    """The rows a projection may iterate over — or a refusal.

    Returns one row per assumption for a band, one row for an identified point or a
    scenario, and raises for anything else. This is the acceptance criterion in the plan:
    *a projection cannot be produced from an unidentified estimator without the band.*
    """
    validate(est)
    if est.status == "unavailable":
        raise ContractError(f"{est.estimator} is unavailable: {'; '.join(est.caveats) or 'no estimate'}")
    if est.status == "band":
        return est.band.copy().reset_index(drop=True)
    if est.identified or est.estimator == "scenario":
        return pd.DataFrame(
            [
                {
                    "assumption": "; ".join(est.assumptions) if est.assumptions else "identified point",
                    "national_dem_share": float(est.national_dem_share),
                    "share_std_error": est.provenance.get("share_std_error", float("nan")),
                }
            ]
        )
    raise ContractError(
        f"{est.estimator} returned an unidentified point; project from its band or state a scenario"
    )


# ---- estimators -----------------------------------------------------------------------


def from_specials(
    estimate: dict,
    *,
    baseline_national_dem_share: float,
    factors: tuple[float, ...] = se.SHRINKAGE_SENSITIVITY,
    snapshot_date: date | str | None = None,
) -> NationalEnvironment:
    """The specials overperformance mean, swept across the shrinkage band.

    ``estimate`` is a ``special_elections.national_environment_estimate`` result. The
    shrinkage factor is the unidentified parameter, so the output is a band: one row per
    factor, each labelled with the factor that produced it. ``identified`` is ``False``
    and :func:`validate` keeps it that way.
    """
    if estimate.get("status") != "ok":
        return NationalEnvironment(
            estimator="specials_band",
            status="unavailable",
            national_dem_share=None,
            band=None,
            identified=False,
            caveats=[str(estimate.get("reason", "no estimate"))],
            provenance={"source_id": "special_elections_compiled", "n": int(estimate.get("n", 0))},
        )

    rows = []
    caveats: list[str] = []
    for f in factors:
        implied = se.implied_national_dem_share(
            estimate, baseline_national_dem_share=baseline_national_dem_share, shrinkage=f
        )
        rows.append(
            {
                "assumption": f"shrinkage={f:g}",
                "shrinkage": float(f),
                "applied_margin_swing": implied["applied_margin_swing"],
                "national_dem_share": implied["national_dem_share"],
                "share_std_error": implied["share_std_error"],
            }
        )
        caveats = list(implied["caveats"])

    return NationalEnvironment(
        estimator="specials_band",
        status="band",
        national_dem_share=None,
        band=pd.DataFrame(rows),
        identified=False,
        assumptions=[
            f"shrinkage factor swept over {list(factors)}; it is an assumption, not an estimate",
            "the specials swing is measured against presidential baselines and applied to a House basis",
        ],
        caveats=list(estimate.get("caveats", [])) + caveats,
        provenance={
            "source_id": "special_elections_compiled",
            "snapshot_date": str(snapshot_date) if snapshot_date is not None else None,
            "n": int(estimate["n"]),
            "date_range": estimate.get("date_range"),
            "mean_overperformance": float(estimate["mean_overperformance"]),
            "std_error": float(estimate.get("std_error", float("nan"))),
            "baseline_national_dem_share": float(baseline_national_dem_share),
        },
    )


def scenario(national_dem_share: float, *, label: str) -> NationalEnvironment:
    """An explicit what-if. Unidentified by definition, and labelled so it cannot pass as one."""
    return NationalEnvironment(
        estimator="scenario",
        status="point",
        national_dem_share=float(national_dem_share),
        band=None,
        identified=False,
        assumptions=[f"scenario: {label}"],
        provenance={"source_id": "scenario"},
    )


# ---- band-level conclusions ------------------------------------------------------------


def control_conclusion(band_results: pd.DataFrame, *, chamber: str, p_column: str) -> str:
    """State what the band says about one chamber's control, as a sentence.

    ``band_results`` has one row per assumption with the simulated probability of
    Democratic control in ``p_column`` and the assumption label in ``assumption``. The
    sentence distinguishes the case the plan treats as a finding (the conclusion holds at
    every assumption) from the case that would falsify Track A (control flips inside the
    band), so a reader is never left to infer it from a table.
    """
    if band_results.empty:
        return f"{chamber}: no band results."
    p = band_results[p_column].astype(float)
    labels = band_results["assumption"].astype(str)
    lo, hi = float(p.min()), float(p.max())
    if lo > 0.5:
        return f"{chamber}: Democrats favored at every assumption in the band (P(control) {lo:.3f}–{hi:.3f})."
    if hi < 0.5:
        return (
            f"{chamber}: Republicans favored at every assumption in the band "
            f"(P(Dem control) {lo:.3f}–{hi:.3f})."
        )
    crossing = labels[p >= 0.5].tolist()
    return (
        f"{chamber}: control depends on the assumption -- Democrats favored only at "
        f"{', '.join(crossing)} (P(Dem control) {lo:.3f}–{hi:.3f}). The band cannot resolve this "
        "chamber; narrowing it (NE-002) or an identified estimator (NE-003) would."
    )

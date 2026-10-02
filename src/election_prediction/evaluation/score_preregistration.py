"""Grade a sealed forecast against what actually happened — written before the outcome.

``reporting.preregistration`` fixed the scoring rules in prose. Prose is not executable, and
the gap between the two is where a forecast quietly gets graded on a curve. Writing this
module after election day would mean every judgement inside it — which seats count, when
"certified" starts, what to do with a race still being recounted — was made by someone who
had already seen the answer. That is the same garden of forking paths the registration
exists to close, moved one month downstream.

So the ambiguities the plan left open are resolved **here and now**, before any result
exists. Each one is a decision that could flatter or damn the forecast, and each is settled
in the only state where that choice is honest — ignorance:

1. **When is it scored?** The caller must pass ``as_of``. A seat with no certified result by
   that date is **excluded and counted** in ``unscored``, never silently dropped. Some states
   certify in a week, some take a month, Georgia and Louisiana can run to a December runoff.
   Reporting the as-of date and the unscored count alongside every metric is what stops the
   scoring date becoming a free parameter.
2. **Uncontested seats?** Scored, **and** reported separately, **and** reported again with
   them excluded. Both numbers, always, so neither can be chosen afterwards. The backtest
   excluded them from fitting because an unopposed candidate measures ballot access rather
   than preference; here we *did* make a prediction, so refusing to score it would be
   marking our own homework.
3. **A map moved after sealing?** Thirty seats sit in states with live litigation. If a
   court changes a map after the registration date, the prediction describes districts that
   no longer exist. Those seats are **void**: excluded, counted, and requiring a stated
   source. Void is not a silent drop and not a failure — it is a seat the test cannot reach.
4. **Retirements and primary losses?** Scored normally, with **no carve-out**. The forecast
   assumed renomination for everyone and declared that as a defect. Excusing it afterwards
   would convert a declared weakness into a free pass.
5. **A third party wins?** Two-party share is still defined, so the share metrics stand; the
   Democratic-win indicator is 0. The forecast was wrong about the winner and is scored as
   wrong.

Every metric is computed through ``evaluation.forecast_eval`` — the same functions the
backtest used. A holdout scored by different machinery than the backtest is not comparable
to it, and comparability is the entire point.

The seal is verified before anything is scored. A registration whose hash does not match
its own predictions is not evidence of anything.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from ..reporting import preregistration as prereg
from . import forecast_eval as fe

ACTUAL_COLUMNS = ["geography_id", "office", "actual_dem_share", "certified_on"]
# Optional on the actual-results frame. When absent, the "excluded" variant equals the
# "included" one rather than silently dropping rows -- the asymmetry would be invisible.
OPTIONAL_ACTUAL_COLUMNS = ["uncontested", "naive_prior_dem_share", "state_lean_share"]

# Pre-specified splits. Every metric below is reported for each of these groups as well as
# overall, because a pooled number hides which part of the chamber the model understood.
SPLITS = ("source", "boundary_confidence")


class SealBroken(ValueError):
    """The registration's stored digest does not match its own predictions."""


@dataclass(frozen=True)
class ScoringInputs:
    """Everything the scorer needs, with nothing left to decide at scoring time."""

    registration: dict
    actual: pd.DataFrame
    as_of: str
    void_geographies: dict[str, str]  # geography_id -> source for why the map moved


def verify_seal(registration: dict) -> None:
    """Recompute the digest. A registration that cannot prove it is unmodified is not evidence."""
    stored = registration.get("predictions_sha256")
    recomputed = prereg._digest(registration["predictions"])
    if stored != recomputed:
        raise SealBroken(
            f"predictions_sha256 {stored!r} does not match the predictions it covers "
            f"({recomputed!r}). The registration has been modified since sealing and cannot "
            "be scored as a holdout."
        )


def _prepare(inputs: ScoringInputs) -> tuple[pd.DataFrame, dict]:
    """Join predictions to outcomes and apply the four pre-specified exclusions."""
    verify_seal(inputs.registration)

    preds = pd.DataFrame(inputs.registration["predictions"]["seats"])
    actual = inputs.actual.copy()
    missing = set(ACTUAL_COLUMNS) - set(actual.columns)
    if missing:
        raise ValueError(f"actual results are missing column(s) {sorted(missing)}")

    merged = preds.merge(actual, on=["geography_id", "office"], how="left")

    as_of = pd.Timestamp(inputs.as_of)
    certified = pd.to_datetime(merged["certified_on"], errors="coerce")

    merged["is_void"] = merged["geography_id"].isin(inputs.void_geographies)
    merged["is_uncertified"] = certified.isna() | (certified > as_of)
    merged["is_scored"] = ~merged["is_void"] & ~merged["is_uncertified"] & merged["actual_dem_share"].notna()

    n_assumptions = max(merged["assumption"].nunique(), 1)
    audit = {
        "as_of": inputs.as_of,
        "seats_registered": int(len(merged) / n_assumptions),
        "scored": int(merged["is_scored"].sum() / n_assumptions),
        "unscored_not_certified": int(merged["is_uncertified"].sum() / n_assumptions),
        "void_map_changed_after_sealing": int(merged["is_void"].sum() / n_assumptions),
        "void_sources": dict(inputs.void_geographies),
        "no_carve_out_for": "retirements, primary losses, candidate quality -- scored as predicted",
    }
    return merged, audit


def _metrics(frame: pd.DataFrame) -> dict:
    """The registered metric set, through the same code path as the backtest."""
    if not len(frame):
        return {"n": 0}
    prob = frame["dem_win_prob"].to_numpy(float)
    outcome = (frame["actual_dem_share"].to_numpy(float) > 0.5).astype(float)
    mean = frame["mean_dem_share"].to_numpy(float)
    sigma = frame["sigma"].to_numpy(float)
    actual = frame["actual_dem_share"].to_numpy(float)
    return {
        "n": int(len(frame)),
        "brier": fe.brier_score(prob, outcome),
        "log_score": fe.log_score(prob, outcome),
        "ece": fe.expected_calibration_error(prob, outcome),
        "mae_vote_share": float(np.abs(mean - actual).mean()),
        "coverage_90": fe.interval_coverage(mean, sigma, actual, level=0.90),
        "coverage_95": fe.interval_coverage(mean, sigma, actual, level=0.95),
        "calibration_curve": fe.calibration_curve(prob, outcome).to_dict(orient="records"),
        "winner_accuracy": float(((prob > 0.5).astype(float) == outcome).mean()),
    }


def _comparators(frame: pd.DataFrame) -> dict:
    """The three comparators fixed at registration time. No others are added afterwards."""
    if not len(frame):
        return {}
    actual = frame["actual_dem_share"].to_numpy(float)
    out = {}
    if "naive_prior_dem_share" in frame.columns:
        naive = frame["naive_prior_dem_share"].to_numpy(float)
        ok = ~np.isnan(naive)
        out["naive_persistence_mae"] = float(np.abs(naive[ok] - actual[ok]).mean()) if ok.any() else None
    if "state_lean_share" in frame.columns:
        lean = frame["state_lean_share"].to_numpy(float)
        ok = ~np.isnan(lean)
        out["state_lean_all_seats_mae"] = float(np.abs(lean[ok] - actual[ok]).mean()) if ok.any() else None
    out["backtest_reference_house_mae"] = 0.078694
    return out


def score(inputs: ScoringInputs) -> dict:
    """Grade every registered assumption. None is singled out, now or ever."""
    merged, audit = _prepare(inputs)
    scored = merged[merged["is_scored"]]

    plan = inputs.registration.get("evaluation_plan", {})
    results = {}
    for assumption, grp in scored.groupby("assumption", sort=False):
        house = grp[grp["office"] == "us_house"]
        entry = {
            "overall": _metrics(grp),
            "by_office": {o: _metrics(g) for o, g in grp.groupby("office")},
            "comparators": _comparators(grp),
            "uncontested": {
                "included": _metrics(house),
                "excluded": _metrics(house[~house.get("uncontested", pd.Series(False, index=house.index))]),
            },
        }
        for split in SPLITS:
            if split in house.columns:
                entry[f"house_by_{split}"] = {str(k): _metrics(g) for k, g in house.groupby(split)}
        results[assumption] = entry

    return {
        "registration": {
            "election_date": inputs.registration["election_date"],
            "registered_on": inputs.registration["registered_on"],
            "predictions_sha256": inputs.registration["predictions_sha256"],
            "seal_verified": True,
        },
        "audit": audit,
        "declared_defects": inputs.registration.get("declared_defects", []),
        "every_assumption_scored": sorted(results),
        "results": results,
        "chamber": _chamber(inputs.registration, scored),
        "failure_condition": _failure_condition(inputs.registration, scored, plan),
    }


def _chamber(registration: dict, scored: pd.DataFrame) -> dict:
    """Seat-count error and whether the realised count fell inside each 90% interval."""
    band = {r["assumption"]: r for r in registration["predictions"]["band"]}
    house = scored[scored["office"] == "us_house"]
    if not len(house):
        return {}
    one = house[house["assumption"] == house["assumption"].iloc[0]]
    realised = int((one["actual_dem_share"] > 0.5).sum())
    out = {"realised_dem_seats_among_scored": realised, "scored_seats": int(len(one))}
    for a, row in band.items():
        lo, hi = row.get("house_5th"), row.get("house_95th")
        out[a] = {
            "predicted_mean_seats": row.get("house_mean_seats"),
            "absolute_error": None
            if row.get("house_mean_seats") is None
            else abs(float(row["house_mean_seats"]) - realised),
            "inside_90_interval": None if lo is None else bool(lo <= realised <= hi),
        }
    return out


def _failure_condition(registration: dict, scored: pd.DataFrame, plan: dict) -> dict:
    """The condition declared before the event: outside the 90% interval under EVERY assumption."""
    chamber = _chamber(registration, scored)
    checks = [v["inside_90_interval"] for k, v in chamber.items() if isinstance(v, dict)]
    known = [c for c in checks if c is not None]
    return {
        "declared": plan.get("failure_condition"),
        "assumptions_whose_interval_contained_the_truth": int(sum(bool(c) for c in known)),
        "assumptions_checked": len(known),
        "triggered": bool(known) and not any(known),
    }


def load_registration(path: str | Path) -> dict:
    return json.loads(Path(path).read_text())

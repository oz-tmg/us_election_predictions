"""National generic-ballot diagnostics; insufficient archives never imply zero house effects."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from ..models.baseline.national_environment import NationalEnvironment
from .average import average_polls
from .schema import validate_polls


def house_effects(polls: pd.DataFrame, targets: pd.DataFrame, *, cycle: int) -> pd.DataFrame:
    """Shrink pollster departures from each cycle's common error, using earlier cycles only.

    Fixed October 20 cutoff and preceding 60-day window. Five pseudo-polls of zero
    effect, at least five observed polls and two cycles per pollster are pre-specified.
    Common election error is not mislabeled a pollster effect.
    """
    frame = polls[polls.cycle.lt(cycle)].copy()
    cutoff = pd.to_datetime(frame.cycle.astype(str) + "-10-20")
    frame = frame[frame.published_on.le(cutoff) & frame.field_end.ge(cutoff - pd.Timedelta(days=60))]
    frame = frame.merge(targets[["cycle", "actual_dem_share"]], on="cycle", validate="many_to_one")
    frame["error"] = frame.two_party_dem_share - frame.actual_dem_share
    frame["centered"] = frame.error - frame.groupby("cycle").error.transform("mean")
    rows: list[dict[str, Any]] = []
    for pollster, group in frame.groupby("pollster"):
        identified = len(group) >= 5 and group.cycle.nunique() >= 2
        rows.append(
            {
                "pollster": pollster,
                "n_polls": len(group),
                "n_cycles": group.cycle.nunique(),
                "identified": identified,
                "house_effect_dem": float(group.centered.sum() / (len(group) + 5)) if identified else 0.0,
            }
        )
    return pd.DataFrame(rows, columns=["pollster", "n_polls", "n_cycles", "identified", "house_effect_dem"])


def historical_topline_check(toplines: pd.DataFrame, targets: pd.DataFrame) -> dict:
    """Retrospective published-average diagnostic, not an archived real-time backtest."""
    frame = toplines.copy()
    frame["date"] = pd.to_datetime(frame.modeldate, format="%m/%d/%Y")
    rows: list[dict[str, Any]] = []
    for cycle in sorted(targets.cycle.unique()):
        cutoff = pd.Timestamp(f"{cycle}-10-20")
        eligible = frame[frame.date.le(cutoff) & frame.date.ge(cutoff - pd.Timedelta(days=7))]
        if eligible.empty:
            continue
        row = eligible.sort_values("date").iloc[-1]
        target = targets[targets.cycle.eq(cycle)].iloc[0]
        share = float(row.dem_estimate / (row.dem_estimate + row.rep_estimate))
        rows.append(
            {
                "cycle": int(cycle),
                "cutoff": str(cutoff.date()),
                "average_date": str(row.date.date()),
                "prediction": share,
                "actual": float(target.actual_dem_share),
                "publisher_timestamp": str(row.timestamp),
            }
        )
    errors = np.array([float(r["prediction"]) - float(r["actual"]) for r in rows])
    return {
        "n_cycles": len(rows),
        "predictions": rows,
        "mae": float(np.abs(errors).mean()) if len(errors) else None,
        "rmse": float(np.sqrt((errors**2).mean())) if len(errors) else None,
        "real_time_vintage_verified": False,
        "promotion_eligible": False,
        "limitation": "Publisher averages rebuilt in 2020; no pollster samples or verified as-of archive",
    }


def estimate(polls: pd.DataFrame, *, as_of: str, historical: dict) -> NationalEnvironment:
    if not validate_polls(polls)["ok"]:
        raise ValueError("generic-ballot input failed poll validation")
    if not polls.office.eq("us_house_generic").all() or not polls.geography_id.eq("nation:us").all():
        raise ValueError("generic estimator accepts national House ballot polls only")
    recent = polls[
        polls.field_end.ge(pd.Timestamp(as_of) - pd.Timedelta(days=60))
        & polls.field_end.le(pd.Timestamp(as_of))
        & polls.published_on.le(pd.Timestamp(as_of))
    ]
    if recent.empty:
        return NationalEnvironment(
            "generic_ballot", "unavailable", None, None, False, caveats=["No public poll within 60 days"]
        )
    floor = max(0.025, historical.get("rmse") or 0.025)
    average = average_polls(recent, reference_date=as_of, poll_error_floor=floor).iloc[0]
    return NationalEnvironment(
        "generic_ballot",
        "point",
        float(average.poll_mean_dem_share),
        None,
        False,
        assumptions=["21-day half-life; square-root sample weights; LV/RV population weights"],
        caveats=[
            "Thin hand-compiled source coverage; not a comprehensive polling census",
            "House effects unidentified: no validated multi-cycle poll-level archive",
            "Retrospective publisher-average check cannot establish real-time calibration",
            "National intended vote is not a calibrated win probability or chamber forecast",
        ],
        provenance={
            **average.to_dict(),
            "promotion_eligible": False,
            "historical_check": historical,
            "house_effect_status": "unidentified",
        },
    )

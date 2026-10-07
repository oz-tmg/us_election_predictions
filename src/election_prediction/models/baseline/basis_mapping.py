"""Presidential district share -> House district share, with a measured residual (RD-003).

``features/plan_transfer`` places a **presidential** two-party share on new district
boundaries. ``projection.project_house`` consumes ``transferred_dem_share`` by differencing
it against the national *House* share, exactly as it treats a prior House result:

    lean = transferred_dem_share - lagged_national_dem_share

So handing the transfer's output over raw is a **basis error**, not a precision one: a
district's presidential lean would be read as its House lean. Presidential and House shares
differ systematically — incumbency, candidate quality, uncontested seats, and split-ticket
voting all live in the gap — and across 744 contested district-cycles in 2020 and 2024 they
differ by a mean absolute **0.0349**, against the transfer's own geography error of 0.0159.

This module closes that gap, and it is the second half of ``docs/redistricting-change-plan.md``
Track C option 2: "map it to a House-basis lean through the fitted presidential-to-House
relationship, with that mapping's residual added to the seat's sigma."

**Both sides are measured as leans, not levels.** The mapping is fitted on

    house_lean  = house_dem_share - national_house_dem_share
    pres_lean   = pres_dem_share  - national_pres_dem_share

so the national environment of the fitting cycle cancels out and the projection keeps
modelling the environment separately. Fitting on levels would bake one cycle's national
result into every future transfer.

**What the residual contains, and why that is the right thing for a redrawn seat.** The fit
absorbs *average* incumbency but cannot know who will run on new territory, so the residual
carries the per-seat incumbency and candidate-quality spread. For a seat whose boundaries
changed that is honest: the incumbent's advantage on ground they have never represented is
genuinely unknown, and a transferred prior should not pretend otherwise.

The sigma handed to ``project_house`` is therefore

    hypot(transfer geography sigma, mapping residual sigma)

because the two errors are independent — one is where the votes were, the other is how
presidential votes translate into House votes. ``project_house`` then adds the model's own
residual, scaled by its lean coefficient, so this value is the uncertainty on the *lean*
and is not comparable to a seat sigma.

**Measured 2026-10-07**, fitted on 744 contested district-cycles across 2020 and 2024:

    intercept          +0.0063
    slope               1.1435
    residual sd         0.0723
    leave-one-cycle-out 0.0726   <- matches in-sample, so the relationship transfers
    MAE                 0.0361

**And this is the finding that matters: the basis mapping, not the transfer, is now the
binding constraint.** Virginia's transfer places votes to within a 0.0159 geography error,
and converting the result to a House basis costs 0.0723 — four and a half times as much. The
end-to-end effect on a redrawn seat is therefore modest: sigma falls from the state-lean
fallback's 0.1450 to roughly 0.134, still above the 0.1121 of a seat with a real prior
result. That ordering is correct — a transferred estimate should beat a statewide guess and
lose to an actual district result — but anyone expecting RD-003 to collapse the 173-seat
uncertainty should read the numbers above first. It narrows it by about 8%, not by half.

That also makes ``docs/redistricting-change-plan.md`` Track C's rejected option 1 —
transferring the **House** vote directly and skipping this conversion — worth revisiting
rather than settled. It was rejected for carrying old incumbency onto new territory, which
is a real cost; 0.0713 is the price of avoiding it, and nobody has measured whether the
incumbency contamination is worse than that.

----

**The specification is wrong for the task, and applying it makes the forecast worse.**
Measured 2026-10-07 on both backtest states, scoring the transfer against certified 2022
House results with and without this map applied:

    Virginia        raw 0.0312 MAE, sigma 0.0185   mapped 0.0420 MAE, sigma 0.0277
    North Carolina  raw 0.0310 MAE, sigma 0.0461   mapped 0.0461 MAE, sigma 0.0533

The map hurts, consistently, on both states. The reason is a cycle mismatch that the
leave-one-cycle-out check could not see because both its cycles have the same flaw: the map
is fitted on **presidential-year** House results (2020 and 2024) and the forecast applies it
to a **midterm** (2022 in the backtest, 2026 in production). Presidential and House votes
relate differently on-cycle than off-cycle — coattails compress the gap in a presidential
year — so a slope of 1.14 measured in 2020 and 2024 over-amplifies a midterm lean.

The correct specification is **lagged**: presidential cycle *Y* to House cycle *Y+2*, which
is the actual prediction task. There is exactly one observable pair for it — 2020
presidential to 2022 House — because MEDSL's precinct series starts in 2018 and so no 2016
CD baseline can be built. One pair can be fitted or it can be validated, not both, and an
in-sample conversion handed to a live forecast is the false precision this stack exists to
avoid.

**So this map is not wired into the projection.** It stays because it is measured, because
it quantifies the presidential-to-House gap honestly, and because it documents why the
obvious correction is not available. What ``project_house`` is handed instead is the **raw
transferred presidential share with the sigma measured from the raw backtest**, and that is
defensible for a reason worth stating: the projection differences the prior against
``lagged_national_dem_share``, so the national *level* difference between presidential and
House vote is already absorbed, and what remains is the slope, which the backtest sigma
measures directly against real outcomes. The pipeline that was scored is the pipeline that
runs.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

#: Presidential cycles with a built CD baseline. A mapping cycle needs both a presidential
#: baseline *and* House results on the same district lines, which is why it is presidential
#: years only: a midterm has no presidential vote to map from.
PRESIDENTIAL_CYCLES = (2016, 2020, 2024)

MAPPING_COLUMNS = ["cycle", "state_po", "district_num", "pres_lean", "house_lean", "pres_reference"]


class BasisMappingUnfitted(ValueError):
    """A transferred prior was converted before the presidential-to-House map was fitted."""


@dataclass(frozen=True)
class BasisMap:
    """A fitted presidential-lean -> House-lean map and its measured residual.

    The fitted ``slope`` is **1.14**, not below 1. That is the opposite of what one might
    expect from the usual story that incumbency pulls safe seats back toward
    competitiveness, and it survives on held-out cycles, so it is a property of the data
    rather than of the fit: among *contested* seats, House leans are **amplified** relative
    to presidential ones. Uncontested races are excluded from the panel (CLAUDE.md §6), and
    excluding them removes exactly the safe seats where compression would show up, leaving
    contested seats where an entrenched member outruns their party's presidential nominee.
    """

    intercept: float
    slope: float
    residual_sd: float
    n: int
    cycles: tuple[int, ...]
    mae: float
    #: Leave-one-cycle-out residual sd, when more than one cycle is available. ``None`` with
    #: a single cycle, and that is reported rather than papered over with an in-sample number.
    loco_residual_sd: float | None = None
    diagnostics: dict = field(default_factory=dict)

    def house_lean(self, pres_lean: pd.Series | np.ndarray) -> np.ndarray:
        """The House lean a given presidential lean implies."""
        return self.intercept + self.slope * np.asarray(pres_lean, dtype=float)

    def combined_sigma(self, transfer_sigma: float) -> float:
        """Geography error and basis error in quadrature — they are independent."""
        return float(np.hypot(float(transfer_sigma), self.residual_sd))

    def to_dict(self) -> dict:
        return {
            "intercept": round(self.intercept, 6),
            "slope": round(self.slope, 6),
            "residual_sd": round(self.residual_sd, 6),
            "loco_residual_sd": None if self.loco_residual_sd is None else round(self.loco_residual_sd, 6),
            "mae": round(self.mae, 6),
            "n_districts": self.n,
            "cycles": list(self.cycles),
            **self.diagnostics,
        }


def build_mapping_panel(house_panel: pd.DataFrame, cd_baselines: dict[int, pd.DataFrame]) -> pd.DataFrame:
    """One row per district-cycle where both a House result and a presidential baseline exist.

    ``cd_baselines`` maps cycle -> the gold CD presidential baseline for that cycle. Rows
    whose baseline is flagged anything other than ``ok`` are dropped: a mapping fitted on a
    baseline that failed its own reconciliation would be measuring the defect.
    """
    frames = []
    for cycle, baseline in cd_baselines.items():
        if baseline is None or not len(baseline):
            continue
        b = baseline.copy()
        if "baseline_quality" in b.columns:
            b = b[b["baseline_quality"] == "ok"]
        b = b[["state_po", "district_num", "baseline_dem_share"]].dropna()
        b["district_num"] = b["district_num"].astype(int)

        h = house_panel[house_panel["cycle"] == cycle]
        if not len(h):
            continue
        h = h[["state_po", "district_num", "two_party_dem_share", "national_dem_share", "uncontested_flag"]]
        h = h.dropna(subset=["two_party_dem_share", "national_dem_share"]).copy()
        h["district_num"] = h["district_num"].astype(int)

        # Uncontested House races are not a measurement of partisanship (CLAUDE.md §6) and
        # would drag the slope toward zero wherever one party simply did not run.
        if "uncontested_flag" in h.columns:
            h = h[~h["uncontested_flag"].astype(bool)]

        merged = h.merge(b, on=["state_po", "district_num"], how="inner")
        if not len(merged):
            continue
        # The reference is the **unweighted mean across the districts in the panel**, not
        # the vote-weighted national presidential share. Either removes the national level;
        # what matters is that fit time and apply time use the *same* definition, so the
        # value is recorded and `to_house_basis` demands it explicitly rather than letting a
        # caller pass the true national share and silently shift every lean.
        national_pres = float(merged["baseline_dem_share"].mean())
        merged["cycle"] = cycle
        merged["pres_reference"] = national_pres
        merged["pres_lean"] = merged["baseline_dem_share"] - national_pres
        merged["house_lean"] = merged["two_party_dem_share"] - merged["national_dem_share"]
        frames.append(merged[MAPPING_COLUMNS])

    if not frames:
        return pd.DataFrame(columns=MAPPING_COLUMNS)
    return pd.concat(frames, ignore_index=True)


def _ols(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    design = np.column_stack([np.ones_like(x), x])
    coef, *_ = np.linalg.lstsq(design, y, rcond=None)
    return float(coef[0]), float(coef[1])


def fit(panel: pd.DataFrame, *, min_districts: int = 100) -> BasisMap:
    """Fit the map, and refuse to return one that rests on too little.

    ``min_districts`` is a floor, not a target. A map fitted on a handful of districts would
    hand ``project_house`` a residual that understates its own uncertainty, which is the
    failure mode this whole routing exists to prevent.
    """
    panel = panel.dropna(subset=["pres_lean", "house_lean"])
    if len(panel) < min_districts:
        raise BasisMappingUnfitted(
            f"only {len(panel)} district-cycles available; need at least {min_districts}. "
            "Build the CD presidential baselines first (ep-build-cd-baselines)."
        )
    x = panel["pres_lean"].to_numpy(float)
    y = panel["house_lean"].to_numpy(float)
    intercept, slope = _ols(x, y)
    resid = y - (intercept + slope * x)
    cycles = tuple(sorted(panel["cycle"].unique().astype(int).tolist()))

    # Leave one cycle out. With two cycles this is a real held-out test of whether the
    # relationship transfers across elections, which is the thing a 2026 forecast needs.
    loco = None
    if len(cycles) > 1:
        errs = []
        for held in cycles:
            tr, te = panel[panel["cycle"] != held], panel[panel["cycle"] == held]
            if len(tr) < min_districts or not len(te):
                continue
            a, b = _ols(tr["pres_lean"].to_numpy(float), tr["house_lean"].to_numpy(float))
            errs.append(te["house_lean"].to_numpy(float) - (a + b * te["pres_lean"].to_numpy(float)))
        if errs:
            loco = float(np.std(np.concatenate(errs), ddof=1))

    return BasisMap(
        intercept=intercept,
        slope=slope,
        residual_sd=float(np.std(resid, ddof=2)),
        n=int(len(panel)),
        cycles=cycles,
        mae=float(np.abs(resid).mean()),
        loco_residual_sd=loco,
        diagnostics={
            "raw_pres_vs_house_mae": round(float(np.abs(y - x).mean()), 6),
            # The reference each cycle's leans were taken against. `to_house_basis` must be
            # given one of these, not the vote-weighted national share.
            "pres_reference_by_cycle": (
                {
                    int(c): round(float(v), 6)
                    for c, v in panel.groupby("cycle")["pres_reference"].first().items()
                }
                if "pres_reference" in panel.columns
                else {}
            ),
            "districts_per_cycle": {int(c): int((panel["cycle"] == c).sum()) for c in cycles},
        },
    )


def to_house_basis(
    transferred_pres_share: pd.Series,
    *,
    basis_map: BasisMap,
    national_pres_share: float,
    lagged_national_house_share: float,
) -> pd.Series:
    """Convert a transferred presidential share into the House-basis share ``project_house`` wants.

    ``national_pres_share`` must be ``basis_map.diagnostics["pres_reference_by_cycle"][cycle]``
    for the cycle the *transfer* came from — the unweighted district mean the fit used, **not**
    the vote-weighted national presidential share, which would shift every lean — and
    ``lagged_national_house_share`` the national House share the projection differences
    against. Passing the wrong one is the error this signature exists to make visible.
    """
    pres_lean = pd.to_numeric(transferred_pres_share, errors="coerce") - national_pres_share
    return pd.Series(
        lagged_national_house_share + basis_map.house_lean(pres_lean),
        index=transferred_pres_share.index,
        dtype=float,
    )

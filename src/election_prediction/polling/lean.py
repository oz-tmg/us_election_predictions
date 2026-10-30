"""Unpromoted lean-conditioned calibration with whole-election validation.

Fractions throughout: positive lean and positive actual-minus-predicted error favor
Democrats. Controls absorb cycle, pollster, sponsor, mode and horizon associations;
they do not establish why an association exists or correct selective poll publication.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..evaluation import forecast_eval
from ..geography.reference import by_postal
from ..models.simulation import CorrelationParams

GATES = ["publication_verified", "field_end_verified", "geography_verified", "fundamentals_vintage_verified"]
REQUIRED = {
    "question_id",
    "poll_id",
    "race_id",
    "cycle",
    "office",
    "state_po",
    "poll_date",
    "election_date",
    "pollster",
    "sponsor_partisan",
    "mode",
    "sample_size",
    "poll_dem_share",
    "actual_dem_share",
    "actual_dem_win",
    "lean",
    "lean_reference_cycle",
    "pred_dem_share",
    "resid_sigma",
    "train_through",
    "lean_basis",
    *GATES,
}
PIPELINES = ("polls_only", "fundamentals_blend", "lean_adjusted_blend")


@dataclass(frozen=True)
class Design:
    horizon_days: int = 7
    lookback_days: int = 21
    half_life_days: float = 21.0
    poll_error_floor: float = 0.025
    blend_error_floor: float = 0.02
    min_training_cycles: int = 4
    bootstrap_draws: int = 200
    n_sims: int = 5000
    seed: int = 23

    def __post_init__(self) -> None:
        if self.horizon_days < 0 or self.lookback_days < 1 or self.half_life_days <= 0:
            raise ValueError("invalid fixed horizon/decay")
        if min(self.poll_error_floor, self.blend_error_floor) <= 0:
            raise ValueError("uncertainty floors must be positive")
        if self.min_training_cycles < 4 or self.bootstrap_draws < 20 or self.n_sims < 100:
            raise ValueError("need four training cycles, >=20 bootstrap draws and >=100 simulations")


def validate_panel(polls: pd.DataFrame) -> pd.DataFrame:
    if not REQUIRED.issubset(polls):
        raise ValueError(f"research panel missing columns: {sorted(REQUIRED - set(polls))}")
    out = polls.copy()
    if out.empty:
        return out
    for date in ("poll_date", "election_date"):
        out[date] = pd.to_datetime(out[date], errors="raise")
        if out[date].isna().any():
            raise ValueError(f"missing {date}")
    numbers = [
        "cycle",
        "sample_size",
        "poll_dem_share",
        "actual_dem_share",
        "actual_dem_win",
        "lean",
        "lean_reference_cycle",
        "pred_dem_share",
        "resid_sigma",
        "train_through",
    ]
    if out[numbers].isna().any().any() or not np.isfinite(out[numbers].to_numpy(float)).all():
        raise ValueError("missing/nonfinite research quantities")
    if not out.office.isin(["us_house", "us_senate"]).all():
        raise ValueError("House/Senate only; do not pool governor or presidential polls")
    if (
        not out[["poll_dem_share", "actual_dem_share", "pred_dem_share"]].ge(0).all().all()
        or not out[["poll_dem_share", "actual_dem_share", "pred_dem_share"]].le(1).all().all()
    ):
        raise ValueError("shares must be fractions, not margins or percentages")
    if not out.lean.between(-0.5, 0.5).all() or not out.actual_dem_win.isin([0, 1]).all():
        raise ValueError("invalid lean or outcome")
    if (out.sample_size <= 0).any() or (out.resid_sigma <= 0).any():
        raise ValueError("positive sample sizes and out-of-sample prior sigmas required")
    if not out.lean_reference_cycle.lt(out.cycle).all() or not out.train_through.lt(out.cycle).all():
        raise ValueError("lean and fundamentals must use strictly earlier elections")
    if out.question_id.duplicated().any():
        raise ValueError("duplicate question ID")
    for column in GATES:
        if not out[column].map(lambda x: isinstance(x, (bool, np.bool_))).all():
            raise ValueError(f"{column} must contain explicit booleans")
    for gate, date in (("publication_verified", "published_on"), ("field_end_verified", "field_end")):
        if out[gate].any() and date not in out:
            raise ValueError(f"{gate} needs actual {date} evidence, not just a boolean")
        if date in out:
            out[date] = pd.to_datetime(out[date], errors="raise")
            if out.loc[out[gate], date].isna().any():
                raise ValueError(f"verified {date} cannot be missing")
    for column in ("question_id", "race_id", "poll_id", "pollster", "sponsor_partisan", "mode", "state_po"):
        if out[column].isna().any() or out[column].astype(str).str.strip().eq("").any():
            raise ValueError(f"missing {column}")
    static = [
        "cycle",
        "office",
        "state_po",
        "election_date",
        "actual_dem_share",
        "actual_dem_win",
        "lean",
        "lean_reference_cycle",
        "pred_dem_share",
        "resid_sigma",
        "train_through",
        "lean_basis",
    ]
    if out.groupby("race_id")[static].nunique(dropna=False).gt(1).any().any():
        raise ValueError("conflicting race metadata or outcomes")
    return out


def aggregate_races(polls: pd.DataFrame, design: Design) -> tuple[pd.DataFrame, dict]:
    frame = validate_panel(polls)
    if frame.empty:
        return pd.DataFrame(), {"input_poll_rows": 0, "eligible_poll_rows": 0}
    frame["days_to_election"] = (frame.election_date - frame.poll_date).dt.total_seconds() / 86400
    in_window = frame.days_to_election.between(
        design.horizon_days, design.horizon_days + design.lookback_days
    )
    cutoff = frame.election_date - pd.Timedelta(days=design.horizon_days)
    known_late = pd.Series(False, index=frame.index)
    late_dates = {}
    for date in ("published_on", "field_end", "database_created_at"):
        if date in frame:
            values = pd.to_datetime(frame[date], errors="raise")
            late_dates[date] = values.notna() & values.gt(cutoff)
            known_late |= late_dates[date]
    late_publication_or_field_end = late_dates.get("published_on", pd.Series(False, index=frame.index)) | (
        late_dates.get("field_end", pd.Series(False, index=frame.index))
    )
    in_window &= ~known_late
    frame = frame[in_window].copy()
    # Multiple questions from one survey must not gain influence by duplication.
    variants = frame.groupby(["race_id", "poll_id"]).question_id.transform("count")
    age = frame.days_to_election - design.horizon_days
    frame["weight"] = np.exp(-np.log(2) * age / design.half_life_days) * np.sqrt(frame.sample_size) / variants
    controls = pd.get_dummies(frame[["pollster", "sponsor_partisan", "mode"]], dtype=float)
    controls.columns = [f"control:{name}" for name in controls.columns]
    controls["control:horizon"] = frame.days_to_election / 21.0
    frame = pd.concat([frame, controls], axis=1)
    rows = []
    for _, group in frame.groupby("race_id", sort=True):
        normalized = group.weight / group.weight.sum()
        first = group.iloc[0]
        row = {
            c: first[c]
            for c in [
                "race_id",
                "cycle",
                "office",
                "state_po",
                "election_date",
                "actual_dem_share",
                "actual_dem_win",
                "lean",
                "lean_reference_cycle",
                "pred_dem_share",
                "resid_sigma",
                "train_through",
                "lean_basis",
            ]
        }
        row.update({gate: bool(group[gate].all()) for gate in GATES})
        mean = float((normalized * group.poll_dem_share).sum())
        variance = float((normalized * (group.poll_dem_share - mean) ** 2).sum())
        # Divide variants' sampling precision too: repeated questions are not independent samples.
        per_survey = (
            group.assign(normalized=normalized)
            .groupby("poll_id")
            .agg(total_weight=("normalized", "sum"), sample=("sample_size", "max"))
        )
        sampling = float((per_survey.total_weight**2 / per_survey["sample"]).sum() * mean * (1 - mean))
        sigma = float(np.sqrt(variance + sampling + design.poll_error_floor**2))
        prior_precision = float(first.resid_sigma) ** -2
        poll_precision = sigma**-2
        poll_weight = poll_precision / (prior_precision + poll_precision)
        row.update(
            {
                "poll_mean": mean,
                "poll_sigma": sigma,
                "poll_weight": poll_weight,
                "blend_mean": poll_weight * mean + (1 - poll_weight) * float(first.pred_dem_share),
                "blend_sigma": max(design.blend_error_floor, (prior_precision + poll_precision) ** -0.5),
                "n_polls": int(group.poll_id.nunique()),
                "n_questions": len(group),
            }
        )
        row.update({c: float((group[c] * normalized).sum()) for c in controls.columns})
        rows.append(row)
    return pd.DataFrame(rows), {
        "input_poll_rows": len(polls),
        "eligible_poll_rows": len(frame),
        "outside_fixed_window": int((~in_window).sum()),
        "known_publication_or_field_end_after_cutoff": int(late_publication_or_field_end.sum()),
        "known_database_entry_after_cutoff": int(
            late_dates.get("database_created_at", pd.Series(dtype=bool)).sum()
        ),
        "any_known_availability_date_after_cutoff": int(known_late.sum()),
        "availability_exclusions_include_database_entry": "database_created_at" in frame,
        "eligible_races": len(rows),
        "availability": "Median-date window is retrospective unless field-end/publication evidence verified",
    }


def fit_slope(races: pd.DataFrame, *, prediction_column: str, design: Design) -> dict:
    """Equal-cycle/race weighted, cycle-demeaned fit; bootstrap entire elections."""
    if races.office.nunique() > 1:
        raise ValueError("fit each office separately")
    if races.race_id.duplicated().any():
        raise ValueError("one aggregated row required per race; polls must not masquerade as races")
    cycles = sorted(races.cycle.unique())
    if len(cycles) < design.min_training_cycles:
        return {"status": "insufficient_history", "n_cycles": len(cycles)}
    # Future-only categories are not fitted. Tiny ridge regularizes redundant nuisance dummies,
    # not the lean coefficient; no retrospective pollster ratings enter this matrix.
    controls = [c for c in races if c.startswith("control:") and races[c].abs().sum() > 0]
    x = races[["lean", *controls]].astype(float)
    y = races.actual_dem_share - races[prediction_column]
    x = x - x.groupby(races.cycle).transform("mean")
    y = y - y.groupby(races.cycle).transform("mean")
    blocks = []
    for cycle in cycles:
        mask = races.cycle.eq(cycle)
        xx, yy = x.loc[mask].to_numpy(), y.loc[mask].to_numpy()
        blocks.append((xx.T @ xx / len(xx), xx.T @ yy / len(xx)))
    grams = np.stack([b[0] for b in blocks])
    products = np.stack([b[1] for b in blocks])
    penalty = np.eye(x.shape[1]) * 1e-5
    penalty[0, 0] = 0

    def solve(counts: np.ndarray) -> float | None:
        gram = np.einsum("c,cij->ij", counts, grams)
        product = counts @ products
        nuisance = gram[1:, 1:] + penalty[1:, 1:]
        information = gram[0, 0] - gram[0, 1:] @ np.linalg.solve(nuisance, gram[1:, 0])
        if information < 1e-7:
            return None
        return float(np.linalg.solve(gram + penalty, product)[0])

    beta = solve(np.ones(len(cycles)))
    if beta is None:
        return {"status": "lean_unidentified_after_controls", "n_cycles": len(cycles)}
    rng = np.random.default_rng(design.seed)
    slopes = []
    for _ in range(design.bootstrap_draws):
        counts = rng.multinomial(len(cycles), np.full(len(cycles), 1 / len(cycles)))
        value = solve(counts)
        if value is not None:
            slopes.append(value)
    if len(slopes) < design.bootstrap_draws * 0.8:
        return {"status": "bootstrap_identification_failed", "n_cycles": len(cycles)}
    # Center the empirical uncertainty at the original fit, not the bootstrap's random mean.
    draws = np.asarray(slopes) - np.mean(slopes) + beta
    return {
        "status": "estimated_research_only",
        "n_cycles": len(cycles),
        "n_races": len(races),
        "train_through": int(max(cycles)),
        "slope": beta,
        "slope_draws": draws.tolist(),
        "slope_interval_90": np.quantile(draws, [0.05, 0.95]).tolist(),
        "error_definition": "actual minus prediction; Democratic two-party share fractions",
        "fit": (
            "equal cycle; equal race; within-cycle centered; pollster/sponsor/mode/horizon exposure controls"
        ),
        "uncertainty": "whole-cycle pairs bootstrap; no independent-poll standard errors",
        "nuisance_ridge": 1e-5,
        "n_controls": len(controls),
    }


def simulate_with_lean(
    races: pd.DataFrame,
    *,
    mean: np.ndarray,
    sigma: np.ndarray,
    design: Design,
    slope_draws: np.ndarray | None = None,
) -> np.ndarray:
    """One slope draw per election, shared across all races, plus existing shared errors."""
    mean, sigma = np.asarray(mean, float), np.asarray(sigma, float)
    if mean.shape != (len(races),) or sigma.shape != (len(races),):
        raise ValueError("one mean and sigma required per race")
    if not np.isfinite(mean).all() or not np.isfinite(sigma).all() or (sigma < 0).any():
        raise ValueError("finite means and nonnegative sigmas required")
    rng = np.random.default_rng(design.seed)
    params = CorrelationParams().normalized()
    regions = [by_postal(s).census_region for s in races.state_po]
    mapping = {r: i for i, r in enumerate(sorted(set(regions)))}
    national = rng.standard_normal((design.n_sims, 1))
    regional = rng.standard_normal((design.n_sims, len(mapping)))[:, [mapping[r] for r in regions]]
    unit = rng.standard_normal((design.n_sims, len(races)))
    error = (
        np.sqrt(params.national) * national
        + np.sqrt(params.regional) * regional
        + np.sqrt(params.state) * unit
    )
    draws = mean[None, :] + sigma[None, :] * error
    if slope_draws is not None:
        slopes = np.asarray(slope_draws, float)
        if slopes.ndim != 1 or not len(slopes) or not np.isfinite(slopes).all():
            raise ValueError("finite bootstrap slope draws required")
        slope_rng = np.random.default_rng(design.seed + 1)
        beta = slope_rng.choice(slopes, size=(design.n_sims, 1))
        draws += beta * races.lean.to_numpy()[None, :]
    return np.clip(draws, 0, 1)


def _metrics(group: pd.DataFrame) -> dict:
    actual = group.actual_dem_share.to_numpy()
    outcome = group.actual_dem_win.to_numpy()
    prob = group.dem_win_prob.to_numpy()
    return {
        "n": len(group),
        "mae": float(np.abs(group.prediction - actual).mean()),
        "bias_actual_minus_prediction": float((actual - group.prediction).mean()),
        "brier": forecast_eval.brier_score(prob, outcome),
        "log_loss": forecast_eval.log_score(prob, outcome),
        "coverage_90": float(((actual >= group.low) & (actual <= group.high)).mean()),
        "calibration": forecast_eval.calibration_curve(prob, outcome).to_dict("records"),
    }


def summarize(predictions: pd.DataFrame) -> dict:
    summaries: dict[str, dict] = {}
    if predictions.empty:
        return summaries
    for (office, pipeline), group in predictions.groupby(["office", "pipeline"]):
        slices = {"all": group, "competitive_unadjusted": group[group.competitive]}
        for label, subset in group.groupby("lean_band", observed=True):
            slices[f"lean:{label}"] = subset
        results: dict[str, dict] = {}
        for label, subset in slices.items():
            if subset.empty:
                results[label] = {"n": 0, "n_cycles": 0}
                continue
            folds = [{"cycle": int(c), **_metrics(g)} for c, g in subset.groupby("cycle")]
            results[label] = {
                "n": len(subset),
                "n_cycles": len(folds),
                "equal_cycle_metrics": {
                    name: float(np.mean([f[name] for f in folds]))
                    for name in ("mae", "brier", "log_loss", "coverage_90", "bias_actual_minus_prediction")
                },
                "by_cycle": folds,
            }
        summaries.setdefault(office, {})[pipeline] = results
    return summaries


def evaluate(races: pd.DataFrame, design: Design) -> tuple[pd.DataFrame, dict]:
    predictions, folds, diagnostics = [], [], {}
    for office, panel in races.groupby("office"):
        diagnostics[office] = {
            "raw_poll_error": fit_slope(panel, prediction_column="poll_mean", design=design),
            "after_fundamentals_blend": fit_slope(panel, prediction_column="blend_mean", design=design),
        }
        for cycle, test in panel.groupby("cycle"):
            train = panel[panel.cycle.lt(cycle)]
            fit = fit_slope(train, prediction_column="blend_mean", design=design)
            if fit["status"] != "estimated_research_only":
                folds.append({"office": office, "cycle": int(cycle), **fit})
                continue
            folds.append({"office": office, "cycle": int(cycle), **fit})
            for pipeline in PIPELINES:
                raw = pipeline == "polls_only"
                mean = test["poll_mean" if raw else "blend_mean"].to_numpy(float)
                sigma = test["poll_sigma" if raw else "blend_sigma"].to_numpy(float)
                slope = np.asarray(fit["slope_draws"]) if pipeline == "lean_adjusted_blend" else None
                draws = simulate_with_lean(test, mean=mean, sigma=sigma, design=design, slope_draws=slope)
                out = test[
                    [
                        "race_id",
                        "cycle",
                        "office",
                        "state_po",
                        "actual_dem_share",
                        "actual_dem_win",
                        "lean",
                        "lean_basis",
                        *GATES,
                    ]
                ].copy()
                out["pipeline"] = pipeline
                out["prediction"] = np.clip(
                    mean + (fit["slope"] * test.lean.to_numpy() if slope is not None else 0), 0, 1
                )
                out["dem_win_prob"] = (draws > 0.5).mean(axis=0)
                out["low"], out["high"] = np.quantile(draws, [0.05, 0.95], axis=0)
                out["competitive"] = test.poll_mean.sub(0.5).abs().le(0.05)
                out["lean_band"] = np.select(
                    [test.lean.lt(-0.05), test.lean.gt(0.05)], ["republican", "democratic"], default="mixed"
                )
                out["train_through"] = fit["train_through"]
                predictions.append(out)
    output = pd.concat(predictions, ignore_index=True) if predictions else pd.DataFrame()
    summary = summarize(output)
    gates = {}
    for office, models in summary.items():
        improvement = True
        reasons = []
        for segment in ("all", "competitive_unadjusted"):
            base = models["fundamentals_blend"][segment]
            corrected = models["lean_adjusted_blend"][segment]
            enough = corrected["n_cycles"] >= 4
            better = enough and all(
                corrected["equal_cycle_metrics"][m] < base["equal_cycle_metrics"][m]
                for m in ("mae", "brier", "log_loss")
            )
            covered = enough and corrected["equal_cycle_metrics"]["coverage_90"] >= 0.85
            improvement &= better and covered
            if not (better and covered):
                reasons.append(f"{segment}: insufficient cycles, scores not all improved, or coverage < .85")
        office_rows = races[races.office.eq(office)]
        vintage = all(bool(office_rows[c].all()) for c in GATES)
        if not vintage:
            reasons.append("publication/field-end, district geography or fundamentals vintage is unverified")
        if office_rows.lean_basis.str.contains("proxy").any():
            vintage = False
            reasons.append("House proxy cannot establish presidential-district lean correction")
        gates[office] = {
            "metrics_gate_passed": bool(improvement),
            "vintage_gate_passed": vintage,
            "review_candidate": bool(improvement and vintage),
            "promoted": False,
            "reasons": reasons or ["manual scientific review required; no automatic deployment"],
        }
    return output, {
        "status": "evaluated_retrospective_research" if len(output) else "insufficient_history",
        "diagnostics_all_history_not_a_holdout": diagnostics,
        "chronological_folds": folds,
        "summary": summary,
        "gates": gates,
        "promoted": False,
        "chamber_control_probability": None,
        "chamber_limitation": "Only polled eligible seats; not a complete chamber or caucus reconstruction",
        "simulation": "asserted national/regional/unit split; one shared bootstrap lean slope per election",
        "uncertainty_limitations": [
            "Bootstrap slopes describe coefficient uncertainty, not identified future-cycle slope dispersion",
            "Precision blend assumes independent fundamentals/poll signals; coverage must be tested",
            "National/regional correlation split remains asserted, not newly estimated from these polls",
        ],
        "coverage_by_office_cycle": [
            {
                "office": office,
                "cycle": int(cycle),
                "races": len(group),
                "states": sorted(group.state_po.unique().tolist()),
            }
            for (office, cycle), group in races.groupby(["office", "cycle"])
        ],
        "2026_polling_correction": None,
        "2026_status": "blocked: no reviewed 2026 House/Senate race polls; sealed forecast unchanged",
    }

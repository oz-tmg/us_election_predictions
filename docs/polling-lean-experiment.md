# Polling Error Conditional on Partisan Lean

Owner: Alex Oswald. Specification fixed October 23, 2026, before fitting the new
experiment. Research only; the September 30 forecast remains the scored holdout.

The hypothesis was suggested by an article that already examined historical elections.
Fixing this implementation before its first fit does not make those historical cycles
independent prospective confirmation of the hypothesis. Chronological parameter fitting
reduces lookahead but cannot undo that hypothesis-selection history. Preserve the original
2026 holdout; do not retrofit its registration to validate this new experiment.

## Question and Units

Does a geographic partisan-lean term improve forecasts beyond an ordinary polling
average and beyond the same average blended with fundamentals? All quantities use
Democratic two-party vote-share fractions, not D-minus-R margins. Error is actual
minus predicted share; lean is positive toward Democrats. No article coefficient is
copied into the model. Vote-share corrections are not probability-point corrections.

## Fixed Evaluation Design

- House and Senate fitted separately. Ordinary D/R general elections only; explicitly
  exclude independent/same-party, primary, runoff, ranked-choice and unresolved rounds.
- Seven-day horizon; median poll field date at or before that cutoff, within the
  preceding 21 days. A median date is NOT proof that fieldwork/publication was complete.
  Publication and field-end timestamps are required for real-time promotion.
- Three comparisons: raw polling average, fundamentals blend, and that blend with a
  lean term learned from earlier cycles' blend residuals. The last comparison corrects
  residual error after blending rather than stacking a raw-poll correction twice.
- Every fold trains strictly on earlier elections, with at least four training cycles.
  Each cycle receives equal total fitting weight, each race equal weight within cycle,
  and polls divide their race's weight. Repeated surveys do not create extra races.
- Fit a cycle-intercept-controlled lean slope, with weighted pollster, sponsor, mode
  and horizon exposure controls on each race average. Resample entire cycles for slope
  uncertainty; no IID-poll confidence claims. A tiny fixed nuisance-only ridge of 1e-5
  resolves redundant dummy columns; the lean term is unpenalized. Controls are nuisance
  adjustments for the diagnostic, not retrospective ratings. This does not estimate
  future-election heterogeneity of the slope, only uncertainty in its mean coefficient.
- Fundamentals must be out-of-sample earlier-cycle forecasts. Lagged presidential lean
  must predate the target election. House geography must be verified on the target map;
  any previous-House-share proxy is reported separately and is promotion-ineligible.
- Report equal-cycle MAE, Brier, log loss, calibration and 90% coverage overall, by lean
  band, and for races within five share points of 50% in the UNADJUSTED forecast. Never
  choose the competitive subset using eventual outcomes or the preferred correction.
- Simulate the same national/regional shocks for all three comparisons. Draw one lean
  slope per simulated election, shared across races; do not draw it independently by
  state. Retain uncertainty even if a coefficient's estimated mean is near zero.
- A promotion candidate needs at least four held-out cycles, lower MAE/Brier/log loss
  than the blend both overall and in the fixed competitive subset, 90% coverage >= .85,
  and all source, geography, publication and fundamentals-vintage gates. No automatic
  deployment: passing metrics creates a review candidate, not a promoted estimator.

## Current Operational Boundary

The ratings archive is outcome-selected and retrospectively curated. Its medians and
embedded results are suitable for a labeled diagnostic, not an exact replay of what a
forecaster knew. The experiment must list exclusions, missing joins and coverage rather
than silently substituting statewide lean for a House district. Independent/caucus and
RCV forecasts remain separate work. Sparse polled seats cannot establish full-chamber
calibration; chamber summaries must identify the polled subset and withhold control
probabilities. No numerical 2026 polling correction is possible without reviewed 2026
House/Senate race polls. Generic-ballot polls cannot substitute for them.

The current House feature join has no usable within-era lag in 2002, 2012 or 2022;
those reset-map cycles are explicitly missing rather than carried across boundaries.
The ratings-only study's accepted House history ends in 2020. The October 25 candidate
archive extension can add 2024 House polling; Senate polling still ends in 2022 because
the supplied current Senate file is a November 2021 capture. Different coverage sets
prevent interpreting a House/Senate difference as causal.

## October 25 Candidate Archive Extension

The evaluation horizon, controls, training rule, uncertainty, seed and promotion gates
are unchanged. The source adapter now admits checked D/R question pairs from the four
manual downloads. It handles both party-column schemas, collapses identical repeated
answer rows, rejects conflicting metadata/answers and explicitly hypothetical matchups,
and requires positive reported samples and plausible percentages. Targets come only
from unambiguous structural joins to registered certified returns; no archived actual
outcomes are invented for a topline-only file. Candidate identities/ballots are still
not independently verified as-of historical cutoffs.

The publisher's field start/end supply a midpoint proxy rather than an actual median
interview date. Both field-end and database-entry date must be no later than the fixed
seven-day cutoff. Database `created_at` does not prove publication; its timezone is
unestablished, so the date is used only for a conservative exclusion, never a verified
publication flag. Same-day entry cannot establish an intraday forecast's availability.
Archive captures after an election likewise cannot establish historical availability.

Candidate-covered office-cycles replace all ratings questions for those office-cycles,
including ratings questions absent/rejected in the candidate archive. Earlier ratings
cycles remain explicitly retrospective. This avoids duplication and using poorer date
metadata to re-admit a question excluded by known field/entry dates. The new source mix
changes coverage and averaging, so changes from the earlier study are not attributable
solely to the lean correction. It is another research analysis, not new prospective
confirmation and not a forecast update.

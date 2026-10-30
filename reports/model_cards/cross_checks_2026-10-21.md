# Experimental Cross-Checks: October 21, 2026

Owner/reviewer: Alex Oswald. Version: 2026-10-21. Public aggregate research only.
No general-election results, restricted records, targeting or causal claims. None of
these diagnostics replaces or alters the September 30 sealed forecast.

## Economic Fundamentals

- Target: incumbent-president-party share of all House two-party votes, converted to
  Democratic share after fitting. Not the projection's contested, total-vote-weighted
  national feature, and not a chamber-control probability.
- Sources: BEA real disposable income per capita `A229RX0`; BLS `UNRATE` and `CPIAUCSL`,
  via FRED/ALFRED, registered before acquisition. Exact October 20 real-time start/end;
  same-vintage latest monthly observation and year-earlier observation. Observation,
  information-set and retrieval dates differ. Exact release date is unknown in clipped
  responses and is not invented. No revised historical backfills.
- Fixed specification: 12-month log real-income growth, incumbent president on ballot
  and consecutive party terms. Unemployment change and log inflation are separate
  alternatives. OLS; expanding window with at least six prior cycles.
- Income: eight historical vintaged cycles (2010-2024), two held-out cycles. MAE 0.0331
  versus persistence 0.0151 and midterm-only 0.0154. Nominal 90% coverage is 0/2.
  Its negative income coefficient is unstable evidence, not an economic claim.
- Unemployment: 17 held-out cycles, MAE 0.0218 versus midterm-only 0.0188;
  90% coverage 0.765. Earlier income vintages unavailable; missing stays missing.
- Current income diagnostic: Democratic share 0.5291, sigma 0.0332. Unidentified,
  non-calibrated midterm cross-check, never precision-blended into specials. Eligibility
  requires eight held-out cycles, coverage >=0.85 and beating both benchmarks.
  No specification passes. Details: `economic_cross_check.json` in the dated report.

## Generic Ballot

- Target: national intended two-party House vote, not actual turnout or win probability.
  Hand-compiled original releases: Marist, September 14-15 (1,280 RV; released September
  23), and Emerson, September 21-22 (1,000 LV; released September 24). Publication and
  completed fieldwork must precede cutoff. No new YouGov or respondent data collection.
- Existing weights: 21-day half-life, square-root sample size, LV/RV population weights.
  Diagnostic Democratic share 0.5605, sigma 0.0279. Two month-old surveys are not a
  comprehensive polling census; that sigma cannot cover all turnout or model bias.
- Eleven October 20 publisher-average reconstructions (1996-2016): MAE 0.0216,
  RMSE 0.0256. Publisher timestamps are September 2020: explicitly NOT a verified
  real-time archive or poll-level backtest. Malformed DataHub CSV quarantined; no bad
  lines skipped to manufacture usable samples.
  Attribution: [FiveThirtyEight generic-ballot data](https://github.com/fivethirtyeight/data/tree/master/congress-generic-ballot),
  CC BY 4.0; transformed to fixed-cutoff two-party shares and compared with MEDSL outcomes.
- Earlier-cycle, within-cycle-centered, partially pooled pollster-effect code is tested.
  No validated multi-cycle poll-level archive exists to fit it. Zero adjustment means
  unidentified, not measured absence of house effects. Not promoted; the environment
  contract refuses this unidentified point as a live forecast.

## Complete-House Diagnostic

- Require exactly 435 unique voting districts and explicit major-party winners; no
  missing seat dropped while claiming a complete chamber. Earlier-cycle training only;
  missing district lags use lagged state-presidential fallbacks with wider uncertainty.
  One-sided availability is reconstructed from final returns, not archived ballots.
- Shared error is fitted on earlier out-of-sample residuals. Compare correlated 5,000-draw
  seat intervals and control Brier/log-loss with the asserted variance split.
- Five complete held-out chamber folds survive (2014, 2016, 2020, 2022, 2024).
  Missing-share seats remain wider fallbacks; the canonical winner table removes ballot
  dispositions such as ME-02's exhausted-ballot pile from actual winners. Both splits
  cover 5/5 results; estimated mean interval score is 97.6 versus 192.2, control Brier
  0.0481 versus 0.0904. This is promising retrospective evidence, not verified real-time
  calibration: ballot availability and map vintages remain reconstructed, with few
  independent cycles. Missing/duplicate and independent/caucus cycles are omitted.
  Historical 100-seat Senate class/holdover/caucus rosters are absent. Not promoted.
- Presidential chronological OLS MAE 0.0467 loses to persistence 0.0321. Persistence
  remains the release benchmark; do not advertise the OLS as an improvement.
  See `full_chamber_evaluation.json` and `chronological_evaluation.json`. These are
  retrospective diagnostics, not validation of live-model chamber probabilities.

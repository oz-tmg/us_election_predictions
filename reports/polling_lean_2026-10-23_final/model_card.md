# Model Card — polling_lean_residual_experiment v0-research



## Identity

- **Name / version:** polling_lean_residual_experiment · v0-research
- **Office / geography:** U.S. Senate/state and House/district; separate office fits
- **Type:** Cycle-demeaned controlled regression; whole-cycle bootstrap; correlated simulation
- **Privacy tier:** 0
- **Owner:** Alex Oswald · **Review date:** 2026-10-23

## Data and target

- **Training/evaluation cycles:** Senate 1998-2022; House available same-era lags 1998-2020; earlier-cycle-only folds
- **Target:** Actual minus predicted Democratic two-party vote-share fraction
- **Sources:**
  - FiveThirtyEight CC BY 4.0 ratings CSV; exact input and source-manifest hashes in study.json
  - Registered MEDSL certified returns; archived October 22 chronological benchmark outputs

## Features

- Lagged presidential state lean (Senate); labeled lagged House proxy (House)
- Cycle intercepts and weighted pollster/sponsor/mode/horizon exposure controls
- Raw polling average, precision fundamentals blend, post-blend lean residual adjustment

## Exclusions

- Independent/same-party, unresolved RCV/Louisiana rounds and non-November elections
- Ambiguous structural race keys, unreconciled certified shares and missing priors
- No respondent/voter/donor records; no retrospective pollster ratings as predictors

## Assumptions

- Fixed seven-day median-date horizon; missing publication dates are not inferred
- Equal cycle/race fitting weights; bootstrap whole elections, not independent polls
- Same national/regional/unit shocks and one shared uncertain lean coefficient per election
- Precision blend assumes independent signal errors; asserted correlation split retained

## Evaluation

- **us_house/fundamentals_blend/mae:** 0.0333
- **us_house/fundamentals_blend/brier:** 0.13013
- **us_house/fundamentals_blend/log_loss:** 0.49141
- **us_house/fundamentals_blend/coverage_90:** 0.82719
- **us_house/fundamentals_blend/bias_actual_minus_prediction:** -0.01214
- **us_house/lean_adjusted_blend/mae:** 0.034
- **us_house/lean_adjusted_blend/brier:** 0.13427
- **us_house/lean_adjusted_blend/log_loss:** 0.50203
- **us_house/lean_adjusted_blend/coverage_90:** 0.8167
- **us_house/lean_adjusted_blend/bias_actual_minus_prediction:** -0.01377
- **us_house/polls_only/mae:** 0.03519
- **us_house/polls_only/brier:** 0.13346
- **us_house/polls_only/log_loss:** 0.49962
- **us_house/polls_only/coverage_90:** 0.82118
- **us_house/polls_only/bias_actual_minus_prediction:** -0.01255
- **us_senate/fundamentals_blend/mae:** 0.02392
- **us_senate/fundamentals_blend/brier:** 0.05119
- **us_senate/fundamentals_blend/log_loss:** 0.16599
- **us_senate/fundamentals_blend/coverage_90:** 0.925
- **us_senate/fundamentals_blend/bias_actual_minus_prediction:** -0.00418
- **us_senate/lean_adjusted_blend/mae:** 0.02263
- **us_senate/lean_adjusted_blend/brier:** 0.04905
- **us_senate/lean_adjusted_blend/log_loss:** 0.15864
- **us_senate/lean_adjusted_blend/coverage_90:** 0.94438
- **us_senate/lean_adjusted_blend/bias_actual_minus_prediction:** -0.00177
- **us_senate/polls_only/mae:** 0.02418
- **us_senate/polls_only/brier:** 0.05403
- **us_senate/polls_only/log_loss:** 0.17823
- **us_senate/polls_only/coverage_90:** 0.92378
- **us_senate/polls_only/bias_actual_minus_prediction:** -0.00455

## Failure modes

- Retrospective archive selection and incomplete historical publication evidence
- House proxy differs from presidential district lean; reset-map cycles absent
- Historical fundamentals/map/roster vintages are not verified real-time inputs
- Bootstrap coefficient uncertainty does not identify future-cycle slope heterogeneity
- Small number of cycles and selective race coverage; no full-chamber validation

## Intended use

Internal retrospective research only. No promotion, no 2026 numerical polling correction, no change to September forecast. Review candidate-poll downloads and vintage gates first.

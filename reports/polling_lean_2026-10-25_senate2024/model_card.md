# Model Card — polling_lean_residual_experiment v1-archive-research



## Identity

- **Name / version:** polling_lean_residual_experiment · v1-archive-research
- **Office / geography:** U.S. Senate/state and House/district; separate office fits
- **Type:** Cycle-demeaned controlled regression; whole-cycle bootstrap; correlated simulation
- **Privacy tier:** 0
- **Owner:** Alex Oswald · **Review date:** 2026-10-25

## Data and target

- **Training/evaluation cycles:** Earlier-cycle-only folds; exact office/cycle coverage in study.json
- **Target:** Actual minus predicted Democratic two-party vote-share fraction
- **Sources:**
  - FiveThirtyEight CC BY 4.0 archives; exact input and source-manifest hashes in study.json
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

- Fixed seven-day field-date horizon; candidate field midpoint versus ratings median proxy
- Candidate field-end/database-entry exclusions; missing publication dates are not inferred
- Equal cycle/race fitting weights; bootstrap whole elections, not independent polls
- Same national/regional/unit shocks and one shared uncertain lean coefficient per election
- Precision blend assumes independent signal errors; asserted correlation split retained

## Evaluation

- **us_house/fundamentals_blend/mae:** 0.03215
- **us_house/fundamentals_blend/brier:** 0.12951
- **us_house/fundamentals_blend/log_loss:** 0.47453
- **us_house/fundamentals_blend/coverage_90:** 0.85415
- **us_house/fundamentals_blend/bias_actual_minus_prediction:** -0.0119
- **us_house/lean_adjusted_blend/mae:** 0.03272
- **us_house/lean_adjusted_blend/brier:** 0.13313
- **us_house/lean_adjusted_blend/log_loss:** 0.48389
- **us_house/lean_adjusted_blend/coverage_90:** 0.84515
- **us_house/lean_adjusted_blend/bias_actual_minus_prediction:** -0.01323
- **us_house/polls_only/mae:** 0.03399
- **us_house/polls_only/brier:** 0.13333
- **us_house/polls_only/log_loss:** 0.48348
- **us_house/polls_only/coverage_90:** 0.84119
- **us_house/polls_only/bias_actual_minus_prediction:** -0.01278
- **us_senate/fundamentals_blend/mae:** 0.024
- **us_senate/fundamentals_blend/brier:** 0.05203
- **us_senate/fundamentals_blend/log_loss:** 0.16921
- **us_senate/fundamentals_blend/coverage_90:** 0.91651
- **us_senate/fundamentals_blend/bias_actual_minus_prediction:** -0.00528
- **us_senate/lean_adjusted_blend/mae:** 0.02255
- **us_senate/lean_adjusted_blend/brier:** 0.04933
- **us_senate/lean_adjusted_blend/log_loss:** 0.16026
- **us_senate/lean_adjusted_blend/coverage_90:** 0.9353
- **us_senate/lean_adjusted_blend/bias_actual_minus_prediction:** -0.00312
- **us_senate/polls_only/mae:** 0.02445
- **us_senate/polls_only/brier:** 0.05417
- **us_senate/polls_only/log_loss:** 0.17969
- **us_senate/polls_only/coverage_90:** 0.9213
- **us_senate/polls_only/bias_actual_minus_prediction:** -0.00541

## Failure modes

- Retrospective archive selection and incomplete historical publication evidence
- House proxy differs from presidential district lean; reset-map cycles absent
- Historical fundamentals/map/roster vintages are not verified real-time inputs
- Bootstrap coefficient uncertainty does not identify future-cycle slope heterogeneity
- Small number of cycles and selective race coverage; no full-chamber validation

## Intended use

Internal retrospective research only. No promotion, no 2026 numerical polling correction, no change to September forecast. Review candidate-poll downloads and vintage gates first.

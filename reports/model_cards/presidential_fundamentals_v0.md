# Model Card — Presidential Fundamentals Baseline v0

> ⚠️ **SYNTHETIC DATA.** This run used a fictional fixture matching the MEDSL schema because live data access was unavailable. Numbers below are illustrative of the *pipeline*, not real electoral estimates. Re-run with real snapshots to publish.

## Identity

- **Name / version:** presidential_fundamentals · v0
- **Office / geography:** U.S. President · state (two-party Democratic vote share)
- **Type:** transparent fundamentals baseline (polls-free), OLS
- **Privacy tier:** 0 (public aggregate)
- **Owner:** project-owner (data steward) · **Review date:** 2026-07-08

## Data

- **Sources:** MEDSL president returns (state, two-party basis); Census ACS 5-year state demographics. Snapshot dates recorded in `data/manifests/`.
- **Training cycles:** backtested leave-one-cycle-out (n=204 state-cycles).
- **Target:** state two-party Democratic vote share.
- **Features:** previous-cycle state share (F-002), national environment, college share (F-006).

## Assumptions & exclusions

- Two-party share basis; third-party votes excluded from the target (CLAUDE.md §6).
- Like-for-like geography; states with no prior-cycle lag are excluded from training.
- Linear, additive effects; no polling signal (baseline by design).

## Backtest (leave-one-cycle-out)

- **MAE (vote share):** 0.0248  ·  **RMSE:** 0.0311
- **Naive persistence MAE:** 0.0265 (baseline the model must beat)
- **Winner accuracy:** 0.931
- **Brier (win prob):** 0.0548  ·  **Log score:** 0.1770
- **ECE (calibration):** 0.0439  ·  **90% interval coverage:** 0.863

## Failure modes

- Correlated national polling/environment misses (mitigated by the correlated simulation layer, not by this point model).
- Redistricting / boundary changes do not affect state-level presidential, but do affect the House score built alongside it.
- Realignment cycles where past vote is a poor guide.

## Intended use

Transparent prior and evaluation benchmark. Not a published live forecast; historical backtest only (PROJECT_CONTEXT §4).

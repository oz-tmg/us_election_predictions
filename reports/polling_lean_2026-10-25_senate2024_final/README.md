# Polling-Lean Research

Review date: 2026-10-25. Owner: Alex Oswald.
Research only. No estimator promoted, no 2026 race-poll forecast, no change to the September seal.

## Data

Ratings archive: 20,466 rows; research panel: 2,979 eligible poll questions; 918 race-cycles in the fixed window.
Senate: lagged presidential state lean. House: separately labeled lagged House proxy,
not presidential district lean. Publication and historical input vintages are unverified.
Source: FiveThirtyEight, CC BY 4.0; certified outcome reconciliation: registered MEDSL returns.

## Equal-Cycle Held-Out Results

All errors use two-party Democratic vote-share fractions; 0.01 is one share point.
| Office | Pipeline | Cycles | MAE | Brier | Log Loss | 90% Coverage |
|---|---|---:|---:|---:|---:|---:|
| us_house | fundamentals_blend | 7 | 0.0322 | 0.1295 | 0.4745 | 0.854 |
| us_house | lean_adjusted_blend | 7 | 0.0327 | 0.1331 | 0.4839 | 0.845 |
| us_house | polls_only | 7 | 0.0340 | 0.1333 | 0.4835 | 0.841 |
| us_senate | fundamentals_blend | 10 | 0.0240 | 0.0520 | 0.1692 | 0.917 |
| us_senate | lean_adjusted_blend | 10 | 0.0225 | 0.0493 | 0.1603 | 0.935 |
| us_senate | polls_only | 10 | 0.0244 | 0.0542 | 0.1797 | 0.921 |

By-cycle, competitive-only, lean-band calibration, raw and post-blend slopes,
whole-cycle bootstrap uncertainty, exclusions and gates are in `study.json`.
The full-history diagnostic is not held-out performance. Shared-error simulation
uses one slope draw per election, never independent state corrections.

## Remaining Gates

- us_house: all: insufficient cycles, scores not all improved, or coverage < .85; competitive_unadjusted: insufficient cycles, scores not all improved, or coverage < .85; publication/field-end, district geography or fundamentals vintage is unverified; House proxy cannot establish presidential-district lean correction.
- us_senate: publication/field-end, district geography or fundamentals vintage is unverified.
- 2024 fixed-window coverage: House included; Senate included.
- Publication availability and historical ballot identities remain unverified.
- Historical House presidential lean on each election's boundaries is unavailable.
- Fundamentals/roster/map inputs are not independently archived forecast-date snapshots.
- No reviewed 2026 race polls: a numerical 2026 adjustment is withheld.
- Polled-seat simulations cannot establish complete chamber calibration/control.

Manual file request and source links: `docs/polling-lean-downloads.md`.
Specification: `docs/polling-lean-experiment.md`. No article coefficient copied.

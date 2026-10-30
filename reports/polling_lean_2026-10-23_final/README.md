# Polling-Lean Research

Review date: 2026-10-23. Owner: Alex Oswald.
Research only. No estimator promoted, no 2026 race-poll forecast, no change to the September seal.

## Data

Ratings archive: 20,466 rows; 2,916 eligible poll questions; 867 race-cycles in the fixed window.
Senate: lagged presidential state lean. House: separately labeled lagged House proxy,
not presidential district lean. Publication and historical input vintages are unverified.
Source: FiveThirtyEight, CC BY 4.0; certified outcome reconciliation: registered MEDSL returns.

## Equal-Cycle Held-Out Results

All errors use two-party Democratic vote-share fractions; 0.01 is one share point.
| Office | Pipeline | Cycles | MAE | Brier | Log Loss | 90% Coverage |
|---|---|---:|---:|---:|---:|---:|
| us_house | fundamentals_blend | 6 | 0.0333 | 0.1301 | 0.4914 | 0.827 |
| us_house | lean_adjusted_blend | 6 | 0.0340 | 0.1343 | 0.5020 | 0.817 |
| us_house | polls_only | 6 | 0.0352 | 0.1335 | 0.4996 | 0.821 |
| us_senate | fundamentals_blend | 9 | 0.0239 | 0.0512 | 0.1660 | 0.925 |
| us_senate | lean_adjusted_blend | 9 | 0.0226 | 0.0491 | 0.1586 | 0.944 |
| us_senate | polls_only | 9 | 0.0242 | 0.0540 | 0.1782 | 0.924 |

By-cycle, competitive-only, lean-band calibration, raw and post-blend slopes,
whole-cycle bootstrap uncertainty, exclusions and gates are in `study.json`.
The full-history diagnostic is not held-out performance. Shared-error simulation
uses one slope draw per election, never independent state corrections.

## Remaining Gates

- us_house: all: insufficient cycles, scores not all improved, or coverage < .85; competitive_unadjusted: insufficient cycles, scores not all improved, or coverage < .85; publication/field-end, district geography or fundamentals vintage is unverified; House proxy cannot establish presidential-district lean correction.
- us_senate: publication/field-end, district geography or fundamentals vintage is unverified.
- 2024 congressional poll coverage is absent from the ratings archive.
- Candidate-poll CSV intake and field/publication/round review remain necessary.
- Historical House presidential lean on each election's boundaries is unavailable.
- Fundamentals/roster/map inputs are not independently archived forecast-date snapshots.
- No reviewed 2026 race polls: a numerical 2026 adjustment is withheld.
- Polled-seat simulations cannot establish complete chamber calibration/control.

Manual file request and source links: `docs/polling-lean-downloads.md`.
Specification: `docs/polling-lean-experiment.md`. No article coefficient copied.

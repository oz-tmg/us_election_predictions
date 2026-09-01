# Forecast Backtest Report — P1 Baselines

_Generated: 2026-08-31_



> Historical backtest only — no live forecast is published. Vote share and win probability are reported separately; close races are meant to look close.

## Presidential fundamentals (state two-party Dem share)

| Model | MAE | RMSE | Winner acc. |
|---|---:|---:|---:|
| Naive persistence (prev cycle) | 0.0422 | — | — |
| Baseline (lag + national) | 0.0415 | 0.0533 | 0.859 |
| + demographics (college share) | 0.0367 | 0.0489 | 0.875 |

### Calibration (win probability, + demographics model)

- Brier score: **0.0939** · Log score: **0.3179** · ECE: **0.0411**
- Interval coverage — 90%: 0.849 · 95%: 0.905 (target ≈ nominal level)

### Reliability curve

| Pred bin | n | mean pred | observed |
|---|---:|---:|---:|
| 0.0–0.1 | 236 | 0.022 | 0.064 |
| 0.1–0.2 | 45 | 0.144 | 0.044 |
| 0.2–0.3 | 41 | 0.250 | 0.171 |
| 0.3–0.4 | 28 | 0.359 | 0.393 |
| 0.4–0.5 | 27 | 0.453 | 0.370 |
| 0.5–0.6 | 19 | 0.543 | 0.526 |
| 0.6–0.7 | 28 | 0.648 | 0.679 |
| 0.7–0.8 | 27 | 0.747 | 0.741 |
| 0.8–0.9 | 38 | 0.851 | 0.921 |
| 0.9–1.0 | 121 | 0.973 | 0.975 |

## Correlated presidential simulation (latest backtested cycle)

States are simulated with shared national + regional error (never independent).

- Mean Democratic electoral votes: **237** (90% range 140–365)
- P(Democratic EC majority ≥270): **0.30**

## House correlated seat simulation

- Districts scored: 505
- Mean Democratic seats (of 505 simulated): **267** (90% range 202–342)
- P(Democratic control): **0.61**

## Senate fundamentals (statewide two-party Dem share)

| Model | MAE | RMSE | Winner acc. |
|---|---:|---:|---:|
| Naive (state's last presidential vote) | 0.1031 | — | — |
| Baseline (presidential lean + incumbency + midterm) | 0.0853 | 0.1295 | 0.801 |

- Brier: **0.1480** · Log score: 0.4599 · ECE: 0.0759
- Interval coverage — 90%: 0.928 · 95%: 0.943

Governor is not covered: MEDSL's gubernatorial returns are a separate dataset this project has not ingested yet.

## Incumbency (F-001, derived)

MEDSL carries no incumbency flag, so it is derived by matching the prior seat-holder against the current candidate roster — six years back for Senate, and never across a redistricting boundary.

| Office | Races w/ usable prior | Incumbent running | Open seat | Incumbent win rate |
|---|---:|---:|---:|---:|
| us_house | 8,203 | 0.793 | 0.207 | 0.956 |
| us_senate | 728 | 0.637 | 0.363 | 0.901 |

## National environment → district swing (P1-004)

`district_swing = alpha + beta * national_swing`, estimated on certified returns within redistricting eras, excluding uncontested races.

- Swing ratio **beta = 1.043** (uniform-swing null = 1.0; deviation +0.043)
- Unexplained district-specific swing (residual sd): **0.1205**
- R²: 0.082 on 7,277 district-cycles

| Plan era | n | Swing ratio | Residual sd | R² |
|---:|---:|---:|---:|---:|
| 1972 | 739 | 0.756 | 0.1283 | 0.007 |
| 1982 | 1,458 | 0.798 | 0.1275 | 0.032 |
| 1992 | 1,539 | 1.188 | 0.1195 | 0.070 |
| 2002 | 1,563 | 1.105 | 0.1253 | 0.171 |
| 2012 | 1,598 | 0.993 | 0.1106 | 0.069 |
| 2022 | 380 | unidentified | — | — |

A generic-ballot poll is a *forecast of next cycle's national swing* and is an input to this relationship, not part of estimating it — so no poll data is needed here and none is assumed. The low R² is the finding: national swing explains only a small share of district-level movement, and the residual sd above is what keeps a seat simulation from being overconfident.

## Quarantine sensitivity

34 races were excluded for failing vote-total reconciliation (see the data-quality report). Refitting the same baseline with them included:

| Presidential baseline | MAE | n |
|---|---:|---:|
| Excluding quarantined races (published) | 0.0367 | 610 |
| Including quarantined races | 0.0368 | 612 |

Difference: **+0.000089** two-party share. A near-zero delta means the exclusion is not doing hidden work; a large one would mean the excluded races carry signal and the exclusion needs revisiting.

## Reading these numbers

The baseline must beat naive persistence on MAE and stay calibrated (ECE near 0, coverage near nominal) before any complex model ships (CLAUDE.md §2 rule 5). The simulation converts vote-share uncertainty into seat/EC probabilities using correlated error, so a national miss moves many states together.

See `reports/model_cards/` for the model card and `data/manifests/` for data lineage.

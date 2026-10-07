# Forecast Backtest Report — P1 Baselines

_Generated: 2026-10-07_



> Historical backtest only — no live forecast is published. Vote share and win probability are reported separately; close races are meant to look close.

## Presidential fundamentals (state two-party Dem share)

| Model | MAE | RMSE | Winner acc. |
|---|---:|---:|---:|
| Naive persistence (prev cycle) | 0.0421 | — | — |
| Baseline (lag + national) | 0.0417 | 0.0534 | 0.858 |
| + demographics (college share) | 0.0368 | 0.0489 | 0.876 |

### Calibration (win probability, + demographics model)

- Brier score: **0.0938** · Log score: **0.3177** · ECE: **0.0456**
- Interval coverage — 90%: 0.851 · 95%: 0.905 (target ≈ nominal level)

### Reliability curve

| Pred bin | n | mean pred | observed |
|---|---:|---:|---:|
| 0.0–0.1 | 235 | 0.022 | 0.064 |
| 0.1–0.2 | 47 | 0.143 | 0.064 |
| 0.2–0.3 | 41 | 0.252 | 0.146 |
| 0.3–0.4 | 26 | 0.360 | 0.423 |
| 0.4–0.5 | 28 | 0.451 | 0.357 |
| 0.5–0.6 | 22 | 0.548 | 0.500 |
| 0.6–0.7 | 26 | 0.653 | 0.692 |
| 0.7–0.8 | 27 | 0.750 | 0.778 |
| 0.8–0.9 | 38 | 0.852 | 0.921 |
| 0.9–1.0 | 122 | 0.974 | 0.975 |

## Correlated presidential simulation (latest backtested cycle)

States are simulated with shared national + regional error (never independent).

- Mean Democratic electoral votes: **275** (90% range 174–403)
- P(Democratic EC majority ≥270): **0.48**

## House district fundamentals (district two-party Dem share)

| Model | MAE | RMSE | Winner acc. |
|---|---:|---:|---:|
| Naive (district's previous result) | 0.0905 | — | — |
| Baseline (lagged lean + national env. + incumbency) | 0.0785 | 0.1125 | 0.929 |

- Brier: **0.0611** · Log score: 0.2289 · ECE: 0.0479 · 90% coverage: 0.902

Uncontested districts are excluded from fitting and scoring — a race with no opponent measures ballot access, not district preference — but they keep their seats in the simulation below. The national environment is contemporaneous, so this measures district accuracy *given* a correct national call; forecasting that national number is P1-004's job.

## House correlated seat simulation

- Seat universe (2024, plan era 2022): **435 of 435** voting seats (complete)
- Seats from the model: 394 (90.6%); carried on a partisanship prior with widened uncertainty: 41; on the most recent result: 0

Districts whose returns were quarantined or that ran unopposed still hold seats, so they are carried on a fallback rather than dropped — a chamber simulated on fewer than 435 seats would understate uncertainty and misstate control. Non-voting delegates (DC and the territories) are excluded.

- Mean Democratic seats: **219** (90% range 117–326)
- P(Democratic control): **0.49**

## Senate fundamentals (statewide two-party Dem share)

| Model | MAE | RMSE | Winner acc. |
|---|---:|---:|---:|
| Naive (state's last presidential vote) | 0.1031 | — | — |
| Baseline (presidential lean + incumbency + midterm) | 0.0852 | 0.1294 | 0.801 |

- Brier: **0.1479** · Log score: 0.4597 · ECE: 0.0758
- Interval coverage — 90%: 0.928 · 95%: 0.943

Governor is not covered. MEDSL publishes no multi-decade gubernatorial series; its returns sit in a 2016 state-level file and 2018-2024 precinct-level per-state files that need aggregating (see the dataset registry).

## Incumbency (F-001, derived)

MEDSL carries no incumbency flag, so it is derived by matching the prior seat-holder against the current candidate roster — six years back for Senate, and never across a redistricting boundary.

| Office | Races w/ usable prior | Incumbent running | Open seat | Incumbent win rate |
|---|---:|---:|---:|---:|
| us_house | 8,207 | 0.793 | 0.207 | 0.956 |
| us_senate | 728 | 0.637 | 0.363 | 0.901 |

## National environment → district swing (P1-004)

`district_swing = alpha + beta * national_swing`, estimated on certified returns within redistricting eras, excluding uncontested races.

- Swing ratio **beta = 1.039** (uniform-swing null = 1.0; deviation +0.039)
- Unexplained district-specific swing (residual sd): **0.1204**
- R²: 0.082 on 7,308 district-cycles

| Plan era | n | Swing ratio | Residual sd | R² |
|---:|---:|---:|---:|---:|
| 1972 | 739 | 0.756 | 0.1283 | 0.007 |
| 1982 | 1,458 | 0.798 | 0.1275 | 0.032 |
| 1992 | 1,539 | 1.188 | 0.1195 | 0.070 |
| 2002 | 1,564 | 1.105 | 0.1252 | 0.171 |
| 2012 | 1,601 | 0.983 | 0.1105 | 0.069 |
| 2022 | 407 | unidentified | — | — |

A generic-ballot poll is a *forecast of next cycle's national swing* and is an input to this relationship, not part of estimating it — so no poll data is needed here and none is assumed. The low R² is the finding: national swing explains only a small share of district-level movement, and the residual sd above is what keeps a seat simulation from being overconfident.

## Prospective race universe — 2026 (P0-001)

Everything above is a backtest. This is the forward-looking scaffold: which seats are on the ballot and who holds them now.

- Election date: **2026-11-03**
- Seats on the ballot: **468** (435 House, 33 Senate)
- House chamber complete: True · incumbent identified for 468 seats · prior available for 468
- ⚠️ Holder's party unresolved for **1** seat(s) — the source leaves the party field null for some contests, so the seat would otherwise be counted as third-party. Closing this is backlog item P0-003.

**This is not a candidate list.** The following are not derivable from returns and are left explicitly unknown rather than guessed:

- candidate filings / who is actually running (needs fec_api — registered, key required)
- retirements, primary outcomes, party switches
- appointed incumbents filling a vacancy
- governor (returns not ingested; MEDSL splits them by year and geography level)
- special elections (off-schedule by definition)
- primary outcomes and renomination (boundary_confidence is sourced; candidacy is not)

## Quarantine sensitivity

2 races were excluded for failing vote-total reconciliation (see the data-quality report). Refitting the same baseline with them included:

| Presidential baseline | MAE | n |
|---|---:|---:|
| Excluding quarantined races (published) | 0.0368 | 612 |
| Including quarantined races | 0.0368 | 612 |

Difference: **+0.000000** two-party share. A near-zero delta means the exclusion is not doing hidden work; a large one would mean the excluded races carry signal and the exclusion needs revisiting.

## Reading these numbers

The baseline must beat naive persistence on MAE and stay calibrated (ECE near 0, coverage near nominal) before any complex model ships (CLAUDE.md §2 rule 5). The simulation converts vote-share uncertainty into seat/EC probabilities using correlated error, so a national miss moves many states together.

See `reports/model_cards/` for the model card and `data/manifests/` for data lineage.

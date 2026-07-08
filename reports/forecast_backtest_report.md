# Forecast Backtest Report — P1 Baselines

_Generated: 2026-07-08_

> ⚠️ **SYNTHETIC DATA.** This run used a fictional fixture matching the MEDSL schema because live data access was unavailable. Numbers below are illustrative of the *pipeline*, not real electoral estimates. Re-run with real snapshots to publish.

> Historical backtest only — no live forecast is published. Vote share and win probability are reported separately; close races are meant to look close.

## Presidential fundamentals (state two-party Dem share)

| Model | MAE | RMSE | Winner acc. |
|---|---:|---:|---:|
| Naive persistence (prev cycle) | 0.0265 | — | — |
| Baseline (lag + national) | 0.0260 | 0.0322 | 0.936 |
| + demographics (college share) | 0.0248 | 0.0311 | 0.931 |

### Calibration (win probability, + demographics model)

- Brier score: **0.0548** · Log score: **0.1770** · ECE: **0.0439**
- Interval coverage — 90%: 0.863 · 95%: 0.926 (target ≈ nominal level)

### Reliability curve

| Pred bin | n | mean pred | observed |
|---|---:|---:|---:|
| 0.0–0.1 | 81 | 0.007 | 0.000 |
| 0.1–0.2 | 10 | 0.145 | 0.100 |
| 0.2–0.3 | 9 | 0.242 | 0.222 |
| 0.3–0.4 | 8 | 0.358 | 0.125 |
| 0.4–0.5 | 4 | 0.460 | 0.500 |
| 0.5–0.6 | 5 | 0.539 | 0.800 |
| 0.6–0.7 | 3 | 0.633 | 0.333 |
| 0.7–0.8 | 8 | 0.747 | 0.875 |
| 0.8–0.9 | 4 | 0.858 | 0.500 |
| 0.9–1.0 | 72 | 0.987 | 0.972 |

## Correlated presidential simulation (latest backtested cycle)

States are simulated with shared national + regional error (never independent).

- Mean Democratic electoral votes: **264** (90% range 199–357)
- P(Democratic EC majority ≥270): **0.40**

## House correlated seat simulation

- Districts scored: 172
- Mean Democratic seats (of 172 simulated): **80** (90% range 45–119)
- P(Democratic control): **0.38**

## Reading these numbers

The baseline must beat naive persistence on MAE and stay calibrated (ECE near 0, coverage near nominal) before any complex model ships (CLAUDE.md §2 rule 5). The simulation converts vote-share uncertainty into seat/EC probabilities using correlated error, so a national miss moves many states together.

See `reports/model_cards/` for the model card and `data/manifests/` for data lineage.

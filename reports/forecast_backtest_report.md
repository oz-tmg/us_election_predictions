# Forecast Backtest Report — P1 Baselines

_Generated: 2026-08-03_

> ⚠️ **SYNTHETIC DATA.** This run used a fictional fixture matching the MEDSL schema because live data access was unavailable. Numbers below are illustrative of the *pipeline*, not real electoral estimates. Re-run with real snapshots to publish.

> Historical backtest only — no live forecast is published. Vote share and win probability are reported separately; close races are meant to look close.

## Presidential fundamentals (state two-party Dem share)

| Model | MAE | RMSE | Winner acc. |
|---|---:|---:|---:|
| Naive persistence (prev cycle) | 0.0265 | — | — |
| Baseline (lag + national) | 0.0260 | 0.0322 | 0.936 |
| + demographics (college share) | 0.0254 | 0.0316 | 0.936 |

### Calibration (win probability, + demographics model)

- Brier score: **0.0480** · Log score: **0.1678** · ECE: **0.0429**
- Interval coverage — 90%: 0.868 · 95%: 0.912 (target ≈ nominal level)

### Reliability curve

| Pred bin | n | mean pred | observed |
|---|---:|---:|---:|
| 0.0–0.1 | 83 | 0.010 | 0.000 |
| 0.1–0.2 | 14 | 0.149 | 0.143 |
| 0.2–0.3 | 6 | 0.230 | 0.000 |
| 0.3–0.4 | 6 | 0.366 | 0.167 |
| 0.4–0.5 | 4 | 0.459 | 0.750 |
| 0.5–0.6 | 4 | 0.542 | 0.500 |
| 0.6–0.7 | 4 | 0.670 | 1.000 |
| 0.7–0.8 | 5 | 0.734 | 0.800 |
| 0.8–0.9 | 6 | 0.855 | 0.667 |
| 0.9–1.0 | 72 | 0.988 | 0.972 |

## Correlated presidential simulation (latest backtested cycle)

States are simulated with shared national + regional error (never independent).

- Mean Democratic electoral votes: **261** (90% range 202–360)
- P(Democratic EC majority ≥270): **0.36**

## House correlated seat simulation

- Districts scored: 172
- Mean Democratic seats (of 172 simulated): **80** (90% range 46–118)
- P(Democratic control): **0.38**

## Reading these numbers

The baseline must beat naive persistence on MAE and stay calibrated (ECE near 0, coverage near nominal) before any complex model ships (CLAUDE.md §2 rule 5). The simulation converts vote-share uncertainty into seat/EC probabilities using correlated error, so a national miss moves many states together.

See `reports/model_cards/` for the model card and `data/manifests/` for data lineage.

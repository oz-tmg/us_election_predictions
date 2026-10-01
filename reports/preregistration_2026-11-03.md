# Pre-registered 2026 projection — sealed 2026-09-30

> **PRE-REGISTERED FORECAST -- NOT PUBLISHED AS A FORECAST**
> Election date: 2026-11-03 · commit `9e4e512e6ede` · predictions SHA-256 `4de09ecf82f218ee…`

A prediction sealed before the event so that the post-election evaluation is out-of-sample. It is not a published forecast and carries no editorial claim; see blog/posts/05-the-forecast-i-am-not-publishing.md.

## The claim

The national environment is **unidentified**, so this is a sweep over an assumed
shrinkage factor, not a point forecast. Every row below is registered and every row
will be scored. Picking the best one afterwards would void the exercise.

| shrinkage | nat_share | house_mean_seats | house_5th | house_95th | house_p_dem | sen_dem_seats_up | sen_mean_total | sen_p_dem |
|-----------|-----------|------------------|-----------|------------|-------------|------------------|----------------|-----------|
| 0.25      | 0.5157    | 228.2            | 117.0     | 352.0      | 0.536       | 15.8             | 47.8           | 0.272     |
| 0.33      | 0.5232    | 233.1            | 122.0     | 357.0      | 0.562       | 16.3             | 48.3           | 0.298     |
| 0.5       | 0.5392    | 243.6            | 132.0     | 368.0      | 0.62        | 17.2             | 49.2           | 0.357     |
| 0.75      | 0.5626    | 259.3            | 148.0     | 383.0      | 0.701       | 18.7             | 50.7           | 0.45      |
| 1.0       | 0.5861    | 275.1            | 162.0     | 395.0      | 0.77        | 20.1             | 52.1           | 0.545     |

- House: Democrats favored at every assumption in the band (P(control) 0.536–0.770).
- Senate: control depends on the assumption -- Democrats favored only at shrinkage=1 (P(Dem control) 0.272–0.545). The band cannot resolve this chamber; narrowing it (NE-002) or an identified estimator (NE-003) would.

## What I expect to be wrong

Declared before the event. A post-mortem that discovers these afterwards proves nothing.

1. 173 House seats have no prior on their 2026 boundaries. They use their state's presidential lean with sigma 0.1450 against a modelled 0.1121. RD-003's vote transfer is unbuilt, so these seats are the least informed part of the chamber and should show visibly worse per-seat scores.
2. The derived Democratic Senate caucus is 45 of 100, two short of the actual 47. The candidate/party crosswalk (P0-003) cannot resolve every member's affiliation from two-party share, so Senate Democratic seats are likely understated by about two.
3. Renomination is assumed for every sitting member. 458 have a 2026 FEC filing and 10 were not found; primaries are not compiled at all, so retirements and primary defeats are invisible to this forecast.
4. The national environment is unidentified. The shrinkage factor is an assumption swept over, not an estimate, and no historical calibration for it exists yet (NE-002 open).
5. Maps in AL, LA, MO, TN are under live litigation and could move before election day. The register records the plan in effect at the snapshot date; a late court order would invalidate those seats' boundaries.
6. The simulation's correlated-error split (45/25/30 national/regional/state) is asserted, not estimated from residuals. Chamber-level interval width is sensitive to it.

## Composition of the registered House forecast

| prior source        | seats |
|---------------------|-------|
| model               | 262   |
| fallback_state_lean | 173   |

| boundary confidence | seats |
|---------------------|-------|
| unchanged           | 262   |
| redrawn             | 173   |

## How this will be scored

**Scored on:** 2026-11-03 certified returns, once available from the states (not calls, not unofficial counts)

**Every assumption is scored.** All five shrinkage assumptions are scored and all five reported. Selecting the best-performing one after the fact is forbidden and would void this registration.

**Per-seat:** Brier score on dem_win_prob; log score on dem_win_prob; expected calibration error and a reliability curve over the same 10 bins as the backtest; mean absolute error on mean_dem_share; 90% and 95% interval coverage from mean_dem_share +/- z * sigma.

**Chamber:** absolute error on mean Democratic seat count; whether the realised seat count fell inside the 90% simulation interval; whether the band's directional claim held (House favoured Democratic at every assumption).

**Comparators, fixed now:**

- naive persistence: each seat repeats its own 2024 two-party share
- state-lean fallback applied to ALL seats, not just the 173 redrawn ones
- the backtest's own leave-one-cycle-out House MAE of 0.078694 as the in-sample reference

**Split evaluation.** Per-seat metrics must be reported separately for the 262 seats projected from the model and the 173 projected from the state-lean fallback. A single pooled number would hide which half of the chamber the model actually knows anything about.

**Pre-declared failure condition.** If the realised Democratic seat count falls outside the 90% interval under every assumption in the band, the model's stated uncertainty was too narrow. This is a failure of the forecast, not of the band, and is to be reported as such.

## Provenance

| Source | Snapshot |
|---|---|
| MEDSL certified returns | 2026-09-30 (cycles 1976-2024) |
| Census ACS 5-year | vintage 2023 |
| FEC filings | 2026-09-15 |
| plan-version register (RD-001) | verified 2026-09-30 |
| compiled special elections | 11 rows compiled through 2026-07-28; 8 used after same-party and seat double-count gating |

Per-seat predictions: 2,340 rows across 5 assumptions, in the JSON sibling and in `preregistration_2026-11-03_seats.csv`.

---

*Nonpartisan. This models probability and uncertainty, not a preferred outcome. Historical returns are certified; everything here is modelled and labelled as such.*

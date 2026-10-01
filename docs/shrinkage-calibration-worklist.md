# Shrinkage Calibration: Compilation Worklist (NE-002)

_Machinery built 2026-09-30 (`models/baseline/shrinkage_calibration.py`, 16 tests). **No
pairs are compiled yet.** `band_from_pairs` returns `status = "insufficient"` until they
are, and refuses to produce a sweep rather than inventing one._

## Why this is the cheapest open item

The 2026 projection sweeps the shrinkage factor over 0.25–1.00 because nothing identifies
it. That sweep is wide enough that **the Senate band straddles a coin flip** — P(Dem
control) 0.272 to 0.545 — so the band cannot resolve the chamber at all. The House is
favoured across the whole sweep, so narrowing it there changes confidence but not the
verdict.

Narrowing the sweep is therefore the one change that could resolve the Senate without new
modelling, new data sources, or new licence reviews. It needs four numbers, each with a
source.

## What a pair is

For each cycle where both halves are observable, the realised shrinkage is

```
realised_shrinkage = general_margin_swing / specials_overperformance
```

- **`specials_overperformance`** — the mean overperformance of that cycle's special
  elections against their districts' presidential baselines. Must be computed through
  `special_elections.compute_overperformance`, the *same* path the live estimate uses.
  A bound measured a different way than the quantity it constrains is not a bound.
- **`general_margin_swing`** — the national House two-party margin swing from the prior
  general to the following one, from certified MEDSL returns already in `data/silver/`.

## The four pairs

| `pair_id` | Specials from | General | Notes |
|---|---|---|---|
| `2017_2018` | 2017 cycle specials | 2018 midterm | The richest specials cycle of the four. |
| `2019_2020` | 2019 cycle specials | 2020 presidential | Presidential-year general; see the pooling caveat. |
| `2021_2022` | 2021 cycle specials | 2022 midterm | Straddles the 2022 redistricting boundary — the *general* is on new maps while the *specials* ran on old ones. Record it; flag it in `notes`. |
| `2023_2024` | 2023 cycle specials | 2024 presidential | Most recent; closest in composition to the live estimate. |

Fewer than three compiled pairs yields `insufficient` by design. Three yields a bound with
the missing pair named in its caveats.

## Rules for compilation

These mirror the plan-version register, which exists because recall is not a source:

1. **Every row carries `source_url`, `retrieved_on`, `verified_by`.** The validator rejects
   a blank in any of them. An uncited pair is a lead, not a fact.
2. **Specials overperformance goes through the existing code path.** Do not hand-average.
   Compile the specials to `data/reference/special_elections_<cycle>.csv` in the existing
   schema and run `compute_overperformance`, so the same gating (same-party rounds, seat
   double-counting) applies as to the live estimate.
3. **General swing comes from certified returns**, not from a news summary.
4. **Record the chamber.** House only for the first pass; a Senate pair would mix two very
   different seat universes.

## Known caveats to carry into the bound

The module already states these; they are repeated here so the compiler knows what the
numbers will and will not support.

- **Four observations is a bound, never a fit.** The output is the observed min and max,
  not a confidence interval — four points cannot support a distributional claim. A future
  cycle can land outside the range and nothing here rules that out.
- **Midterm and presidential cycles are pooled.** The relationship plausibly differs
  between them, and with four pairs it cannot be split without losing the bound entirely.
  If a fifth and sixth pair ever exist, split them.
- **2021→2022 crosses a redistricting boundary.** The general ran on new maps; the specials
  did not. That is a real distortion in one of only four observations.
- **Selection bias is inherited, not fixed.** Specials happen where vacancies happen, in
  every cycle. The bound carries every caveat the live estimate does.

## Done when

`band_from_pairs` returns `status = "bound"` over at least three sourced pairs; the
projection's sweep is driven by `ShrinkageBound.as_factors()` instead of the hardcoded
`SHRINKAGE_SENSITIVITY` default; and the Senate band is re-reported to show whether a
narrower sweep resolves the chamber or demonstrates that it cannot be resolved. Either
answer is a result.

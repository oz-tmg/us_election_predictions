# Shrinkage Calibration: Compilation Worklist (NE-002)

_Machinery built 2026-09-30 (`models/baseline/shrinkage_calibration.py`, 19 tests).
**Half of each pair is now compiled**; the specials half is the remaining human task.
`data/reference/shrinkage_calibration_pairs.csv` carries four rows, and
`calibration_pairs` refuses them with "not yet compiled" rather than inventing a bound._

## ⛔ BLOCKER found 2026-10-01: the specials half is not derivable from this repo

Investigated before compiling. **MEDSL's House file contains 30 special-election rows in
total, all from 2006.** For cycles 2016–2024 it contains none:

```
special flag on us_house rows:  {False: 31971, True: 30}
special races by cycle >= 2016: NONE
```

So `specials_overperformance` cannot be computed from certified returns already on disk. It
requires external compilation, and each row needs two sourced numbers, not one:

1. **The special's result** — dem/rep/other votes, with `source_url` and `retrieved_on`.
2. **`baseline_dem_share`** — that district's presidential two-party share, which is what
   overperformance is measured against. The repo computes this only for **2024**
   (`data/gold/cd_presidential_baseline_2024.parquet`, built by `features/cd_baseline.py`
   from MEDSL precinct files). A 2017–18 special needs a **2016** baseline; a 2021–22
   special needs **2020**. Neither exists here.

That is a genuine multi-day data task, not a gap I can close by computing harder. **Three
paths, and the choice is the project owner's:**

| Path | What it costs | What it risks |
|---|---|---|
| **A. Hand-compile externally** | Compile each cycle's specials plus a cited presidential baseline per district (The Downballot / Split Ticket publish these; registered as `downballot_split_ticket`, cite per row) | Slow, and the baselines come from a Tier-B secondary source rather than our own precinct arithmetic |
| **B. Extend `cd_baseline.py` to 2016 and 2020** | Ingest the 2016 (and confirm 2020) MEDSL precinct files and compute baselines ourselves | Engineering I can do, but it only solves half — the special results still need external compilation |
| **C. Change the baseline definition** | Use each district's prior *House* result instead of its presidential share | **Breaks comparability.** The live 2026 estimate uses a presidential baseline; a bound measured against a different quantity does not constrain it. The worklist's own rule forbids this |

Recommendation: **B then A.** Doing B first means the baselines are ours, computed the same
way for every cycle, and the hand-compilation is then only the special results. C should not
be taken — it would produce a number that looks like a bound and is not one.

### B attempted 2026-10-01 — and it does not reach far enough back

`build_cd_baselines` is now a real build (`ep-build-cd-baselines --vintage YYYY`) rather
than an ad-hoc call, and the national 2020 and 2024 tables replace a gold file that covered
8 states. But **2016 cannot be built from any registered source**, which changes what A can
cover.

MEDSL's per-state precinct series (`medsl_precinct_by_state`) runs **2018, 2020, 2022,
2024**. 2016 is not in it. A separate row, `mit_precinct_project`, is MEDSL's older precinct
project and may cover 2016 with uneven state coverage — it is `identified`, unacquired, and
would need its own registration and profiling before use.

There is a second constraint that bites even where a baseline exists. A 2020 precinct file
assigns precincts to districts from its own `us_house` rows, so a 2020 build is on
**2012-era lines by construction**. A special held in 2022 or later sits on 2022-era lines
and needs 2020 presidential vote *re-aggregated onto those lines* — which is RD-003's vote
transfer, not this build.

Putting both together, in-house baselines support:

| Pair | Baseline needed | Available in-house? |
|---|---|---|
| `2017_2018` | 2016 presidential, 2012-era lines | ❌ no 2016 precinct source registered |
| `2019_2020` | 2016 presidential, 2012-era lines | ❌ same |
| `2021_2022` | 2020 presidential — 2012-era lines for 2021 specials, 2022-era for 2022 specials | ⚠️ partial: 2021 specials only |
| `2023_2024` | 2020 presidential, 2022-era lines | ❌ needs RD-003 transfer |

**So B does not unblock the historical pairs.** Path A for 2017–2020 would have to take its
baselines from a cited third-party tracker (`downballot_split_ticket`, Tier B, cite per
row) — which is the thing B was meant to avoid, and is a defensible choice only if it is
labelled as such on every affected row.

### What the national 2020 run actually found

Running it nationally for the first time surfaced a bug that had been sitting in
`cd_baseline.py` unexercised, because the only previous run covered 8 states:

**Minnesota and North Dakota came out at 0.000 Democratic.** MEDSL's precinct files carry
each state's own party name in `party_detailed` — `DEMOCRATIC FARMER LABOR` in Minnesota,
`DEMOCRATIC-NPL` in North Dakota — and simplify both to `OTHER`. The module matched
`party_simplified == "DEMOCRAT"` literally, so 1.7 million Biden votes in Minnesota counted
as third-party. The state-level MEDSL file has no such problem, so nothing upstream caught
it. Fixed; both now reconcile to four decimals.

**The worse problem was that the build called this a success.** It counted files and rows
and never checked whether the numbers were right. `ep-build-cd-baselines` now reconciles
every state's CD aggregate against its certified state-level two-party share and marks
anything more than a point off as `fails_reconciliation` — flagged, not dropped, because a
short table invites a silent join while a flagged one forces a decision. A state missing
from the certified panel fails too: unknown must never read as fine.

Result for 2020: **42 of 49 states reconcile** (360 districts `ok`, 9 `under_covered`).
Seven fail, in two distinct modes:

| Mode | States | Evidence |
|---|---|---|
| **Under-coverage** — precincts not resolving to a district | AL, IN, MS, OK, VA, WA | 68–91% of the certified state vote recovered, against a 97.1% median among passing states |
| **Double counting** | NC | 180% of the certified state vote recovered — almost certainly vote-mode rows not collapsed |

Neither is fixed. Both are now *visible* and refused, which is the difference between a
known gap and a silent error. Diagnosing them is per-state work and is scoped, not done.

**The party fix changed nothing in 2024, verified rather than assumed.** The live specials
take `baseline_dem_share` from `cd_presidential_baseline_2024.parquet`, so the fix could
have moved numbers the sealed pre-registration depends on. Rebuilding all 8 states of that
file with the fix and diffing district by district: **172 of 172 districts identical, max
change 0.0000000000.** None of those states has a DFL- or NPL-style affiliate label, so
there was nothing for the fallback to recover — which is the expected result and is now a
checked one. The ten districts with compiled specials are unchanged to six decimals.

**What B did buy, and it is not nothing:** the live 2025–26 specials sit on 2022-era lines
and their baseline is 2024 presidential, which *is* now buildable in-house nationally. Those
rows currently take `baseline_dem_share` from a third-party tracker. Replacing that with our
own precinct arithmetic removes a secondary source from the one estimator that currently
feeds a live projection — a governance and quality win for the number actually in use, even
though it leaves the historical bound where it was.

## What is already done

`general_margin_swing` is **derived from certified returns** already in the repo
(`data/gold/house_panel.parquet`, MEDSL 1976–2024), so no compilation is needed for it:

| Pair | National two-party Dem share | Margin swing |
|---|---|---:|
| `2017_2018` | 0.502526 (2016) → 0.536674 (2018) | **+0.0683** |
| `2019_2020` | 0.536674 (2018) → 0.521001 (2020) | **−0.0313** |
| `2021_2022` | 0.521001 (2020) → 0.491987 (2022) | **−0.0580** |
| `2023_2024` | 0.491987 (2022) → 0.492224 (2024) | **+0.0005** |

What remains per row: `specials_overperformance`, `specials_n`, and `verified_by`.

## ⚠️ What the derived half already suggests — read before compiling

**The sign flips.** Two of the four generals moved toward Democrats and two moved toward
Republicans. Special-election overperformance has been consistently *positive* for
Democrats across these same cycles. If that holds when the specials are compiled, the
realised shrinkage will be **negative in at least two of four pairs** — meaning the
specials pointed one way and the general went the other.

**And one pair is near-degenerate.** The 2022→2024 national swing was +0.0005, essentially
zero. Divided by any non-trivial specials overperformance, its realised shrinkage is
approximately zero regardless of what the specials half turns out to be.

This is provisional — it is an inference from one half of the data, and the compilation may
contradict it. But it changes what success looks like, so it should be said in advance
rather than discovered afterwards:

- The bound may **not narrow** the current 0.25–1.00 sweep. It may widen it, or shift it to
  include zero and negative values.
- A bound spanning negative to positive would say the specials-to-general relationship has
  no consistent *direction*, not merely an uncertain magnitude. That would be a far more
  damaging finding about the specials estimator than "we can't pin the number down", and it
  would argue for demoting specials to a cross-check and prioritising NE-003 (generic
  ballot) or NE-004 (economic fundamentals) as the primary estimator.
- **Either outcome is a result.** A bound that fails to narrow the sweep is not a failed
  piece of work; it is evidence that the current estimator is weaker than its band implies.
  Record it, publish it, and change the plan accordingly.

Compile the specials half before concluding any of this. The point of writing it down now
is that neither outcome can then be treated as the one that was expected all along.

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

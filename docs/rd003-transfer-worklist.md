# Old-to-New Vote Transfer: Collection Worklist (RD-003)

_Machinery built 2026-09-30 (`features/plan_transfer.py`, 11 tests). Sources **registered**
2026-09-30 in `docs/dataset-registry.md`. **Nothing is downloaded yet**, and
`plan_transfer.transfer` raises `UnregisteredSourceError` if asked to run without them._

## What this unblocks

173 of 435 House seats — 39.8% of the chamber — currently have no prior on their 2026
boundaries. They fall back to their state's presidential lean with sigma 0.1450 against a
modelled 0.1121, which widened the projection's 90% seat range by 32%. That fallback is
honest and crude. A transferred prior is the only thing that makes those seats informative
again, and it is now the highest-value modelling item in the project.

## The chain, and where it leaks

```
precinct results --(areal/population weight)--> census block --(BAF)--> new district
```

Each link loses something, which is why the output carries **three confidence components
that are never collapsed into one score**:

| Component | Falls when | What it means for the prior |
|---|---|---|
| `unsplit_share` | precincts straddle new district lines | votes were divided by a population guess, not counted |
| `old_district_majority_share` | the new seat blends several old ones | the prior inherits several incumbency and candidate effects at once |
| `geocoded_share` | precincts cannot be placed in blocks | the transfer extrapolates from a subset |

A district can score well on one and badly on another. A single collapsed number would hide
exactly the distinction a consumer needs.

## Collection tasks, in order

1. **Fill `baf_url` in the plan-version register.** It is empty on all 23 rows. Census
   publishes BAFs for plans it has ingested, which lags mid-decade redraws — so for several
   of the nine 2026 states the authoritative assignment exists only as a state legislative
   or court file. Each state-published BAF must be registered individually before use.
2. **Acquire P.L. 94-171 for the pilot state.** Use **VAP**, not total population: the
   question is electoral. Note that the 2020 file is differentially private — block counts
   carry injected noise and do not always sum consistently. Tolerable as allocation
   weights, but it belongs in the stated uncertainty, not treated as ground truth.
3. **Acquire one precinct-boundary and precinct-result source.** Redistricting Data Hub is
   registered and its terms are captured at
   `docs/terms_and_conditions/redistricting-datahub-data-download.md`. **Its attribution
   strings are mandatory on any published output** and must be added to
   `blog/README.md` before the first post that uses this data. Its permitted uses —
   noncommercial, nonpartisan, explicitly not for gerrymandering — match this project's own
   constitution, which is not a coincidence but must still be honoured in writing.
4. **Run the Virginia 2020→2022 backtest.** Virginia is the registered first case because
   both maps and both generals are observed. `backtest_transfer` scores the transfer
   against the two comparators the plan names: **no prior at all**, and **the state-lean
   fallback the projection uses today**.
5. **Take the sigma from that backtest.** `transfer_sigma_from_backtest` refuses an
   unmeasured sigma, and refuses one whose transfer does not beat the fallback — the
   projection already has the fallback, and replacing it with something worse while calling
   it a transfer would be a regression wearing a better name.

## Pilot state

Virginia, per `docs/redistricting-change-plan.md` Track D. It is the backtest case rather
than a 2026 state on purpose: the point of the first run is to *measure the method's error*
where the answer is known, not to produce a 2026 prior. Only once the sigma is measured do
the nine 2026 states get transferred priors.

## Convergence with the audit module

RD-004: the block base table and block-to-plan assignments built here are written under
`docs/redistricting/` storage conventions and **are** the audit module's Phase 1
deliverables, minus the adjacency graph. The forecasting fix lays the audit module's
foundation and picks its pilot state. No ensemble, objective or scoring code is introduced
by this work.

## Done when

MAE is reported against both comparators; `transfer_sigma` is measured rather than assumed;
the historical and live transfer paths share one code path (test-pinned); and the three
confidence components are reported per district without being collapsed.

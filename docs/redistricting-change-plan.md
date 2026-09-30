# Redistricting Change (F-008): Architecture Plan

_Drafted 2026-09-14. Supersedes the implicit design in which a House district's plan was a
function of the cycle year._

## The decision this document records

`plan_era(cycle)` in `features/incumbency.py` assigns every House district to one map per
decade: 1972, 1982, … 2022. Every redistricting-aware piece of the stack — incumbency
breaks, the swing-ratio panel, the House lag, the 435-seat universe — keys on it. That was
correct for every cycle in the backtest. It is wrong for 2026, because several states
enacted or were ordered into new congressional maps between 2024 and 2026, and under
`plan_era` a redrawn district's 2024 result silently becomes its 2026 prior.

The code already knows this. `race_universe.py` stamps every House row
`boundary_confidence = "unverified"` and lists "post-2022 mid-decade redistricting" under
`not_derivable`. But `projection.project_house` never reads that column, and
`reports/projection_2026.txt` prints 435 projected seats with no boundary caveat. The flag
exists; nothing consumes it.

The change is to **stop deriving the plan from the year and start recording it per state
per cycle, with sources** — then make the projection refuse to use an old-territory prior
for a redrawn seat. Where a transferred prior can be built from precinct returns and a
block-level crosswalk, use it with an explicit confidence score; where it cannot, fall
back with widened uncertainty and say so. Never the old district number by default.

Three consequences follow, and they are the three tracks below. A fourth section records
how this converges with the redistricting audit module rather than competing with it.

| Track | Item | What it changes | Gated on |
|---|---|---|---|
| A | RD-001 | The plan is a sourced register, not a decade function | hand compilation from official portals |
| B | RD-002 | The projection consumes `boundary_confidence` and reports its treatment | RD-001 (the list) |
| C | RD-003 | Old-to-new vote transfer with a confidence score, backtested on 2020→2022 | P.L. 94-171 + BAF + precinct boundaries registered |
| — | RD-004 | Track C's block table and assignments become audit-module Phase 1 | RD-003 pilot state |

Governance note: every input here is Tier 0/1 (certified returns, Census blocks, enacted
plan files). The register records *what was enacted, by whom, when, and where it says
so* — it does not label any map. Whether a map is an outlier is the audit module's
question, answered against ensembles, never by an adjective in a reference table
(`docs/redistricting/CLAUDE.md` §8).

---

## Track A — Plan-version register (RD-001)

### The claim

Which states use a different congressional map in 2026 than in 2024 is a small,
enumerable, sourceable fact. It belongs in a hand-compiled reference table with the same
discipline as `data/reference/special_elections_2025_2026.csv`: every row carries a
`source_url` and `retrieved_on`, and validation refuses rows without them.

### Architecture

Add `data/reference/house_plan_versions.csv`, one row per (state, plan):

| Column | Meaning |
|---|---|
| `state_po` | Postal code |
| `plan_id` | Stable label, e.g. `TX_2021`, `TX_2025`; matches the shapefile/BAF version |
| `first_cycle` | First general election held under this plan |
| `last_cycle` | Last general election under it, or blank if current |
| `authority` | `legislature` / `commission` / `court` / `referendum` |
| `enacted_on` | Date the plan became law or was ordered |
| `status` | `in_effect` / `enjoined` / `pending` — as of `retrieved_on` |
| `source_url` | State redistricting portal, legislative GIS office, or court order |
| `baf_url` | Block-assignment file for the plan, if published |
| `retrieved_on` | Date the row was verified |
| `notes` | Neutral description only (e.g. "replaces 2021 plan; 38 districts") |

Add `features/plan_versions.py`:

- `read_plan_versions(path) -> DataFrame` and `validate_plan_versions(df)` — the latter
  fails on a missing `source_url`/`retrieved_on`, on overlapping cycle ranges within a
  state, and on any state with no `in_effect` plan for a requested cycle.
- `plan_id(state_po, cycle) -> str`, which **falls back to** `f"{state_po}_{plan_era(cycle)}"`
  for any state with no register row. The decennial rule stays the default; the register
  only overrides it. That keeps every historical backtest byte-identical until a row says
  otherwise.
- `boundary_confidence(state_po, cycle) -> str` with four values:
  `unchanged` (same `plan_id` as `cycle - 2`), `redrawn` (different `plan_id`, status
  `in_effect`), `pending` (a plan exists with status `enjoined`/`pending`), and
  `unverified` (no register row and `cycle` is later than the last cycle in the returns —
  i.e. the live cycle, where the decennial default is an assumption rather than a fact).

`race_universe.build_race_universe` replaces its hardcoded `"unverified"` with the
function above, and gains `plan_id` in `UNIVERSE_COLUMNS`.

### Compilation scope

The states to verify first are those reported to have enacted, been ordered into, or
litigated a new 2026 congressional map since 2024. Working list to confirm against each
state's official portal — none of these rows enter the register from this document:
Texas, California, Missouri, North Carolina, Ohio, Utah, Louisiana; plus a watch list of
states whose legislatures discussed a redraw without one being confirmed at drafting time.
Every other state gets `unchanged` by default and needs no row, which is what keeps the
compilation to a dozen rows rather than fifty.

### Acceptance criteria

- No 2026 House row carries `boundary_confidence = "unverified"` once the register is
  compiled; each `redrawn`/`pending` row traces to a `source_url`.
- ~~`plan_id` for every 1976–2024 row equals the decennial default (a test pins this, so
  adding the register cannot move the backtest).~~ **Superseded 2026-09-30.** The register
  applies to every cycle, history included: AL, LA and NC each changed maps between 2022
  and 2024, so pinning history to the decennial default knowingly gave 27 district-cycles a
  lag across territory that had changed. The criterion was written to stop the register
  moving the backtest *by accident*; it was landed in two commits instead, the first with
  the plumbing and history provably unmoved, the second flipping the consumers and
  reporting the delta.

  Measured effect of the flip (`reports/p1_results.json`, leave-one-cycle-out):

  | Quantity | Decennial | Register | Delta |
  |---|---:|---:|---:|
  | House MAE | 0.078782 | 0.078694 | −0.000088 |
  | House Brier | 0.061393 | 0.061159 | −0.000234 |
  | House ECE | 0.048012 | 0.048193 | +0.000181 |
  | House 90% coverage | 0.903158 | 0.902723 | −0.000435 |
  | Panel district-cycles | 7,662 | 7,638 | −24 |
  | Redistricting breaks | 2,172 | 2,199 | +27 |
  | Seats fit by the model | 391 | 367 | −24 |
  | P(Dem control), 2024 sim | 0.4743 | 0.4892 | +0.0149 |

  The model got marginally *better* on every headline accuracy measure, which is the
  expected direction: the removed lags were comparisons across different territory, i.e.
  noise. The real cost is coverage — 24 more seats now carry a partisanship prior instead
  of a fitted one (model coverage 89.9% → 84.4%), which is honest rather than good.
  President and Senate are bit-identical, confirming the change touched only House
  boundaries.
- `validate_plan_versions` fails the build on an overlapping or sourceless row.

### What would falsify this track

Nothing — it records facts. The risk is staleness: `status` can change by court order
weeks before the election. `retrieved_on` is what makes that visible; the projection
report should print the oldest `retrieved_on` among `redrawn`/`pending` rows.

---

## Track B — The projection consumes boundary confidence (RD-002)

### The claim

This is the piece that makes the current output defensible, and it depends on nothing
except the list from Track A. It can ship before any crosswalk exists, because its job is
to stop a wrong prior, not to supply a right one.

### Architecture

`project_house` gains a routing step before `district_lean` is computed:

| `boundary_confidence` | `prior_dem_share` treatment | `source` | `sigma` |
|---|---|---|---|
| `unchanged` | as now (last result under the same `plan_id`) | `model` | `resid_sigma` |
| `redrawn`, transferred prior available (Track C) | transferred share on new boundaries | `model_transferred` | `resid_sigma` inflated by transfer uncertainty |
| `redrawn`, no transfer | old-number prior **discarded**; state presidential lean substituted | `fallback_state_lean` | `resid_sigma` × documented factor |
| `pending` | as `redrawn` — the seat is projected on whichever plan `status` says is in effect, with the alternative noted | as above | as above |
| `unverified` | **refuse**: raise unless `allow_unverified=True`, in which case treat as `unchanged` and count it | `model_unverified` | `resid_sigma` |

The fallback deserves a sentence. The Senate model already predicts statewide races from
`state_pres_lean` + incumbency, and a redrawn district with no transferred prior is, from
the model's point of view, a seat whose only known geography is its state. Using the
state's lean with a much wider sigma is honest about that: it says "somewhere in this
state's distribution" rather than "exactly where the old district was". The inflation
factor is a **documented assumption, not an estimate**, until Track C's backtest yields a
measured one — same discipline as `MIN_VOTE_SHARE_OF_STATE_MEDIAN` in `cd_baseline.py`.

`coverage` gains `seats_by_boundary_confidence` and `seats_by_source`.
`scripts/project_2026.py` prints both, plus one line per `redrawn`/`pending` state naming
the plan and its `retrieved_on`, in the same block that currently states the incumbency
assumption.

### Acceptance criteria

- A test constructs a `redrawn` seat and asserts its projected share does **not** equal
  the model applied to its old-number prior, whatever else it equals.
- A test asserts `project_house` raises on an `unverified` seat by default.
- `reports/projection_2026.txt` states the count of redrawn seats and their treatment as
  text, not as a column the reader must infer from.
- The House control band (`house_p_dem` across the shrinkage sweep) is re-reported with
  the redrawn seats routed; whether it moves is a finding either way.

### What would falsify this track

If routing redrawn seats through the fallback moves `house_p_dem` across 0.5 somewhere in
the band, the fallback's sigma is doing load-bearing work and Track C stops being optional.
Re-check whenever the register changes.

---

## Track C — Old-to-new vote transfer with a confidence score (RD-003)

### The claim

F-008's acceptance criterion is an "old-to-new vote transfer score and crosswalk
confidence." The project already has most of the inputs: 2020 and 2024 MEDSL precinct
files for every state (5.3 GB, registered and profiled), the 2024 TIGER CD layer, and
`cd_baseline.py`, which already aggregates precinct presidential votes to districts and —
deliberately — **excludes** precincts that span districts because there was no crosswalk
to allocate them with. This track builds that crosswalk, and the decennial 2020→2022
redraw is its natural held-out test.

### The measurement trap to avoid

The House model's `district_lean` is on the **House-vote** basis: `lag_dem_share` is the
prior House result, not the presidential one. A transferred *presidential* share on new
boundaries is the cleaner geographic quantity (no incumbency, no uncontested races), but
it is not the quantity the fitted model consumes. Two options, and the plan should pick
one before the first number is produced:

1. Transfer the **2024 House vote** onto 2026 boundaries. Like-for-like with the model,
   but it carries the old districts' incumbency and uncontested effects into territory
   where they do not apply.
2. Transfer the **2024 presidential vote** onto 2026 boundaries and map it to a House-basis
   lean through the fitted presidential-to-House relationship, with that mapping's
   residual added to the seat's sigma.

Option 2 is recommended: its error is measurable, and `cd_presidential_baseline_2024`
already exists at the old boundaries as a check. Either way, the historical and live paths
must share one code path — a test should assert the 2020→2022 backtest and the 2026
transfer call the same function.

### Architecture

Inputs (all Tier 0/1; **each must be registered in `docs/dataset-registry.md` before
use** — none of the first three has a registry row today):

- Census **P.L. 94-171** block-level VAP for 2020 (the allocation weight).
- Census **block-assignment files** (BAFs) for the old and new plans — from the Census
  Redistricting Data Office for the 118th/119th Congress, or the state's portal for a
  mid-decade plan (`baf_url` in the register).
- **Precinct boundaries** matching each returns file's election date — Redistricting Data
  Hub is registered as `rdh_precinct_boundaries` with terms unreviewed; VEST is the
  alternative. Precinct geometry drifts between elections, so the 2024 returns need 2024
  boundaries, not 2020 ones.
- MEDSL precinct returns (already acquired).

Add `features/plan_transfer.py`:

1. `precinct_block_weights(precincts, blocks, vap)` — for each precinct, the share of its
   VAP in each block it intersects (area-weighted intersection, then VAP-weighted). A
   precinct wholly inside one block group of one new district has weight 1.0 to that
   district; that is the confident case and the majority case.
2. `transfer_returns(returns, weights, baf_new)` — allocate each precinct's votes to new
   districts through blocks. Absentee / central-count reporting units with no geometry
   (present in most MEDSL precinct files) are allocated by the county's in-person vote
   distribution **and counted separately**, because that is an assumption, not a measurement.
3. `transfer_confidence` per new district, three components reported separately, never
   collapsed to one number in the table:
   - `share_from_unsplit_precincts` — fraction of the district's transferred vote that
     came from precincts assigned whole (no allocation assumption at all);
   - `share_from_old_district_majority` — fraction inherited from the single largest old
     district (1.0 = renumbered, not redrawn);
   - `share_from_ungeocoded_units` — fraction that came from absentee/central-count
     allocation.
4. Output `data/gold/cd_transfer_<cycle>_<plan_id>.parquet` with the transferred two-party
   shares and the three confidence columns, keyed on (`geography_id`, `plan_id`).

`cd_baseline.py` keeps its exclusion rule as the confidence-1.0 subset; its
`MIN_VOTE_SHARE_OF_STATE_MEDIAN` under-coverage flag applies unchanged to transferred
districts.

### The backtest

Run the same pipeline on 2020 precinct returns, the 2012-era BAF, and the 2022-era BAF for
a pilot state, producing a transferred 2020 share for every 2022 district. Then feed it to
the House model as the 2022 prior and score against the actual 2022 result — versus two
comparators: (a) the current behaviour (no prior; `redistricting_break`), and (b) Track B's
fallback (state lean, widened sigma). Report MAE, winner accuracy, and coverage of the
widened intervals. The **sigma inflation factor** for `model_transferred` comes from this
backtest's residual, replacing the documented assumption in Track B.

Pilot state for the *method*: Virginia — cleanest precinct coverage in the 2024 file
(0.7% split precincts, `vote_share_of_state_median` 0.78–1.16). Pilot state for the
*2026 application*: whichever `redrawn` state has the best 2024 precinct coverage; check
Arizona-style under-coverage before committing, since a state whose 2024 precincts already
lose a quarter of some districts' votes will not transfer cleanly.

### Acceptance criteria

- P.L. 94-171, the relevant BAFs, and one precinct-boundary source registered with
  license, tier, and attribution before any transfer runs.
- The 2020→2022 backtest for the pilot state, with MAE against both comparators.
- Three confidence components per transferred district, with a test that fails if a
  transfer table is emitted with any of them missing.
- Historical and live transfers share one code path (test-pinned).
- `model_transferred` seats in the 2026 projection carry the backtest-derived sigma, and
  the report says which districts they are.

### What would falsify this track

If the transferred prior does not beat Track B's fallback on the 2020→2022 backtest —
MAE no better, or interval coverage no better at the same width — then the crosswalk has
bought precision it cannot deliver, and the honest answer for 2026 is the fallback with
the wider sigma. Decide the comparison metric before the pilot runs; do not extend to more
states in search of a better result.

### Cost

The block-level join is the expensive part: a full state's 2020 blocks (Texas has ~700k)
against precinct polygons, once per precinct vintage. GeoParquet + a spatial index makes
it tractable; it is not a pandas job. The BAF joins and aggregation are cheap. Budget the
precinct-boundary licensing review (RDH terms) as the schedule risk, not the compute.

---

## Track D — Convergence with the audit module (RD-004)

Track C's deliverables are, item for item, Phase 1 of
`docs/redistricting/implementation-roadmap.md`: block base table
(`blocks_{state}_{year}.parquet`), block-to-district assignment
(`block_to_enacted_district_{state}_{plan_id}.parquet`), and return-to-block allocation.
The one Phase 1 item Track C does not need is the block **adjacency graph**, which only
ensembles use.

So the sequencing decision is: **build Track C's block table and assignments under the
audit module's storage conventions** (`data/processed/blocks/{state}/{year}.parquet`,
`data/processed/plans/{state}/{plan_id}.parquet`), not under an ad-hoc forecasting path.
The pilot state chosen for Track C's backtest becomes the audit module's Phase 0 pilot by
default, which closes `PROJECT_CONTEXT.md` open question #5 for congressional districts.
Nothing in this plan generates an ensemble, scores a plan against one, or applies any
objective function; that remains P2–P3 and remains audit-only.

---

## Sequencing

1. **RD-001 and RD-002 start immediately.** RD-001 is a dozen sourced rows; RD-002 is a
   routing step plus report lines and can be written against a stub register with one
   `redrawn` row. Together they turn "435 seats projected" into "435 seats projected, N
   of them on new boundaries, treated as follows."
2. **RD-003 begins with the registry rows**, because three of its four inputs cannot be
   used before they are registered (CLAUDE.md §7). The Virginia 2020→2022 backtest is the
   first deliverable and is achievable with Census BAFs alone, before any mid-decade plan
   file is touched.
3. **RD-003's 2026 application follows the backtest**, one state at a time, in order of
   2024 precinct coverage.
4. **RD-002 and RD-003 are not competitors.** The fallback path stays in the code after
   transfers exist — a `redrawn` state with unusable precinct data still needs it.

## Changes to existing code (summary)

- `features/incumbency.py` — `plan_era` stays; `redistricting_break` is computed from
  `plan_id` inequality rather than era inequality, so a mid-decade redraw also breaks the
  incumbency lookup.
- `models/baseline/house.py` — `build_house_panel` groups the lag by
  (`geography_id`, `plan_id`) instead of (`geography_id`, `plan_era`). Identical output for
  every historical cycle (test-pinned); different only where the register says so.
- `models/baseline/generic_ballot.py` — swing panel grouped the same way.
- `features/race_universe.py` — `plan_id` column; `boundary_confidence` from the register.
- `models/baseline/projection.py` — routing table above; `allow_unverified` flag;
  coverage counts.
- `scripts/project_2026.py` — prints boundary treatment alongside the incumbency line.
- `reporting/model_cards.py` — House card gains a "Redistricting treatment" line listing
  redrawn states and their source.

## Open questions

- Whether `geography_id` should embed `plan_id`. Current position: no — the canonical
  spine stays on FIPS/GEOID (CLAUDE.md §3) and `plan_id` travels as a sibling column, so a
  redrawn district keeps its GEOID and any join that forgets `plan_id` is caught by the
  lag test rather than by an ID mismatch.
- Which option in Track C's measurement trap (House-vote transfer vs presidential transfer
  through the fitted relationship). Recommended: presidential; decide before the pilot.
- Whether `pending` seats should be projected under both plans and reported as two rows.
  Current position: one row on the in-effect plan, with the alternative named in the
  report; two rows would double-count a seat in the simulation.
- What the Track B sigma inflation factor is before RD-003 measures it. It is an
  assumption either way; pick something a reader can reason about (e.g. the Senate
  model's residual, which is the same "statewide only" information set) and label it.

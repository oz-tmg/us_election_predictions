# Plan-Version Register: Verification Worklist (RD-001)

_Drafted 2026-09-15. **Every row in `data/reference/house_plan_versions.csv` is UNVERIFIED
until a human checks it against the cited source and fills `verified_by`.** Nothing in the
forecasting stack reads the register yet._

## What this is

RD-001 of `docs/redistricting-change-plan.md`. `plan_era()` derives a House district's map
from the cycle year — one map per decade — which is wrong for 2026. This register records,
per state, which congressional plan is actually in effect for which cycles, with a source
for each claim. States with no row fall back to the decennial default, so the register
only needs rows where something changed.

The register records **what was enacted, by whom, when, and where it says so**. It carries
no judgment about any map. Whether a plan is an outlier is the audit module's question,
answered against ensembles (`docs/redistricting/CLAUDE.md` §8).

## Headline

**Nine states use a different congressional map in November 2026 than in 2024: AL, CA, FL,
LA, NC, OH, TN, TX, UT.** Those states hold **173 of 435 House seats — 39.8% of the
chamber**. Every one of those seats is currently projected from a 2024 result that
describes different territory.

Two states needed care and are the reason this was researched rather than recalled:

- **Missouri enacted a new map and is not using it.** HB 1 (2025-09-28) is suspended
  pending a November referendum (Proposition A). The Missouri Supreme Court ordered the
  2022 map used for the general (2026-09-03), Justice Kavanaugh denied a stay
  (2026-09-08), and the U.S. Supreme Court blocked the new map's use (2026-09-10). The
  August 2026 primary ran on the 2025 map; the general reverts to 2022. Missouri's 2024
  prior is therefore **valid**, and the naive assumption "Missouri redrew, so discard its
  prior" would have been wrong.
- **Georgia, New York, and Virginia did not redraw.** Georgia's legislature declined the
  governor's June special session; New York's litigation was voluntarily dismissed
  (2026-03-19) leaving the 2024 map; Virginia's amendment passed in April and was struck
  down by the state Supreme Court (2026-05-08). All three are `unchanged` and need no row.

Context for the second wave: the U.S. Supreme Court decided **Louisiana v. Callais on
2026-04-29**, narrowing Section 2 of the Voting Rights Act. AL, FL, LA, and TN all enacted
new maps within about five weeks of that decision. This is a post-cutoff development —
it is the main reason the register had to be built from sources rather than from memory.

## How to verify a row

For each row, open `source_url` and confirm: the **enactment/order date**, the **authority**
that enacted it, the **number of districts**, and that the plan is **currently in effect for
the November 3, 2026 general**. Then put your initials in `verified_by` and correct
`retrieved_on` to the date you checked. A row without `verified_by` should be treated as a
lead, not a fact.

`validate_plan_versions` (not yet written) will fail on a missing `source_url` or
`retrieved_on`, on overlapping cycle ranges within a state, and on any state with no
`in_effect` plan for a requested cycle.

## Row status

| State | Plan | Enacted | Authority | Source quality | Priority |
|---|---|---|---|---|---:|
| TX | TX_2025 (PLANC2333) | 2025-08-29 | legislature | **official** — Texas Legislative Council | 1 |
| CA | CA_2025 (Prop 50) | 2025-11-04 | referendum | ⚠️ secondary — **needs CA Secretary of State** | 1 |
| FL | FL_2026 (EOGPCRP2026) | 2026-05-04 | legislature | **official** — Florida Senate | 2 |
| NC | NC_2025 (SB 249 / SL 2025-95) | 2025-10-22 | legislature | **official** — NC General Assembly | 2 |
| OH | OH_2025 | 2025-10-31 | commission | **official** — Ohio Secretary of State | 2 |
| TN | TN_2026 | 2026-05-07 | legislature | **official** — TN Secretary of State | 2 |
| LA | LA_2026 (SB 121 / Act 2) | 2026-05-29 | legislature | **official** — Louisiana Legislature | 2 |
| AL | AL_2026 | 2026-06-02 | legislature | ⚠️ portal only — **needs act number** | 1 |
| UT | UT_2025 (remedial) | 2025-11-10 | court | ⚠️ secondary — **needs court docket** | 1 |
| MO | MO_2022 in effect; MO_2025 enjoined | — | legislature | ⚠️ portal only — **needs official confirmation** | 1 |

Three additional pre-2026 rows (NC_2022, LA_2022, AL_2021) document earlier mid-decade
changes in those states and are marked `PRE-2026 ROW` in `notes`. They are lower priority
to verify — see the second design question below for whether code will read them at all.

Priority 1 rows are those whose source is not yet an official state or court record, or
whose classification is contested. Verify those first.

## Open design question this surfaced

Missouri breaks the `boundary_confidence` vocabulary as written in the plan. The spec says
`pending` means "a plan exists with status `enjoined`/`pending`", and RD-002 routes
`pending` like `redrawn` — discarding the old prior. For Missouri that is **wrong**: the
map in effect for the general *is* the 2024 map, so the 2024 prior is exactly right.

The register currently classifies Missouri as `unchanged`, on the reading that
`boundary_confidence` describes the relationship between *this cycle's territory and the
prior cycle's*, given whichever plan is in effect — not whether litigation is live. That
keeps the routing correct but drops a real signal: Missouri's boundaries could still move
before November, and the 8th Circuit case is live.

**Recommendation:** split the two ideas. Keep `boundary_confidence` about territory
(`unchanged` / `redrawn` / `unverified`), and add a separate `litigation_risk` flag
(`none` / `active`) that the report prints but the routing ignores. That needs your
sign-off because it changes the RD-002 vocabulary, which is already implemented and
tested.

## Second design question: does the register apply to history?

The register now carries pre-2026 rows, because **AL, LA, and NC each changed maps between
2022 and 2024 as well** — Louisiana under *Robinson*, Alabama under *Allen v. Milligan*,
North Carolina from a court-ordered interim plan to a legislative one. Those are facts and
they belong in the register. But they create a consequence the plan did not anticipate.

`docs/redistricting-change-plan.md` states as an acceptance criterion that *every 1976–2024
`plan_id` equals the decennial default, test-pinned, so adding the register cannot move the
backtest*. With these rows present that is no longer true for AL, LA, and NC: consulting
the register for historical cycles would break the 2022→2024 lag in those three states and
mark their 2024 races `redistricting_break`.

That would arguably be **more correct** — those districts genuinely were different
territory — but it changes the fitted House model and every backtest number downstream.
The choice is yours:

| Option | Effect | Argument |
|---|---|---|
| **A. Register applies to 2026 forward only** | Backtest frozen; historical `plan_id` stays decennial | Isolates the change; the plan's stated criterion holds; historical error stays as it has always been |
| **B. Register applies to all cycles** | AL/LA/NC lose their 2022→2024 lag; model refits | More accurate; but it re-opens the backtest at the same time as everything else, and the panel loses ~40 district-cycles |

**Recommendation: A for now, B as a separate change with its own before/after comparison.**
Mixing a boundary correction into the same commit as a model refit would make it impossible
to attribute any change in the backtest. The pre-2026 rows stay in the register either way
— they are documentation regardless of whether code reads them.

## Also worth knowing

- **Texas, Alabama, and Missouri all had a lower court rule against the map and a higher
  court permit it anyway.** Status can change on a stay, not just on an enactment, which
  is why `retrieved_on` matters more here than in any other reference table. The projection
  report should print the oldest `retrieved_on` among non-`unchanged` rows.
- **Ohio's plan is not a mid-decade partisan redraw**, it is the constitutionally required
  successor to a four-year plan, adopted unanimously by the commission. The register records
  the authority and date; it does not group states by motive.
- **`baf_url` is empty for every row.** Block-assignment files are what RD-003 needs to
  build transferred priors, and none has been located yet. That is the next collection task
  after verification.
- **Primary vs general can differ.** Missouri's August primary used a map its November
  general will not. Any future primary-level modelling cannot assume one plan per cycle.

## Sources consulted

Aggregators used to build the candidate list (not cited as authority for any row):
All About Redistricting (Loyola Law School) <https://redistricting.lls.edu/>, Ballotpedia
<https://ballotpedia.org/Redistricting_ahead_of_the_2026_elections>, and Wikipedia's
2025–2026 United States redistricting article. Per-row claims are cited to the state or
court source in `source_url`, except where the table above marks the source as secondary.

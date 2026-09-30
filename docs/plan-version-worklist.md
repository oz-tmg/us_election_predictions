# Plan-Version Register: Verification Worklist (RD-001)

_Drafted 2026-09-15. **Verified 2026-09-30 by AO — all 23 rows now carry `verified_by`.**
Sources were corrected to official state records where the draft had used aggregators, and
three substantive corrections came out of verification (below). **Nothing in the forecasting
stack reads the register yet** — `features/plan_versions.py` and `validate_plan_versions`
are still to be written, so the 2026 projection continues to flag all 435 seats
`unverified`._

## What verification changed

- **Alabama is not using a new 2026 map.** It restored the legislature's previously
  struck-down **2023** plan (`AL_2023_LEG`), which is *not* the Allen v. Milligan remedial
  plan used in 2024 (`AL_2023`). Ivey signed reversion bills 2026-05-08; SCOTUS lifted the
  injunctions 2026-05-11; a three-judge panel blocked it again 2026-05-26 as an intentional
  racial gerrymander under the Fourteenth Amendment and the VRA; SCOTUS stayed that block
  6-3 on 2026-06-02, clearing it for the midterms. Alabama remains **redrawn** relative to
  2024 — the two 2023 plans are different territory — but the draft's characterisation of
  the 2026 map as a fresh legislative enactment was wrong.
- **Missouri's cycle ranges must stay open-ended.** `MO_2022` runs through 2026 and beyond;
  `MO_2025` has no cycle range because it has never been used. Closing `MO_2022` at 2024
  leaves the state with no `in_effect` plan for 2026 and hands the cycle to an enjoined map
   — the exact error the register exists to prevent.
- **Sources upgraded to official records** for CA (Secretary of State), MO (SOS Blue Book
  federal chapter and the Proposition A petition certification), TX (SOS advisories), UT
  (Utah courts), NC (NCSBE / General Assembly) and LA (SOS session-act archives).

The headline is unchanged by verification: **nine states use a different congressional map
in November 2026 than in 2024 — AL, CA, FL, LA, NC, OH, TN, TX, UT — 173 of 435 seats,
39.8% of the chamber.**

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

## How a row was verified

For each row: open `source_url` and confirm the **enactment/order date**, the **authority**
that enacted it, the **number of districts**, and that the plan is **currently in effect for
the November 3, 2026 general**. Then initials in `verified_by` and `retrieved_on` set to the
date checked. A row without `verified_by` is a lead, not a fact — there are none left.

`validate_plan_versions` (still to be written) must fail on a missing `source_url` or
`retrieved_on`, on a missing `verified_by`, on overlapping cycle ranges within a state, and
on any state with no `in_effect` plan for a requested cycle. That last check is the one that
catches the Missouri error, so write its test first.

## Row status

| State | Plan in effect for 2026 | Enacted | Authority | Verified |
|---|---|---|---|---|
| TX | TX_2025 (PLANC2333) | 2025-08-29 | legislature | AO — TX Secretary of State |
| CA | CA_2025 (Prop 50 / ACA 8, Res. Ch. 156) | 2025-11-04 | referendum | AO — CA Secretary of State |
| FL | FL_2026 (EOGPCRP2026, SB 8D / HB 1D) | 2026-05-04 | legislature | AO — Florida Senate |
| NC | NC_2025 (SB 249 / SL 2025-95) | 2025-10-22 | legislature | AO — NC General Assembly |
| OH | OH_2025 | 2025-10-31 | commission | AO — Ohio Secretary of State |
| TN | TN_2026 | 2026-05-07 | legislature | AO — TN Secretary of State |
| LA | LA_2026 (SB 121 / Act 2) | 2026-05-29 | legislature | AO — LA SOS act archive |
| AL | **AL_2023_LEG** (legislature's 2023 plan, restored) | 2026-05-08 (reversion) | legislature | AO — see correction above |
| UT | UT_2025 (remedial) | 2025-11-10 | court | AO — Utah courts |
| MO | **MO_2022** in effect; MO_2025 enjoined and never used | 2022-05-18 | legislature | AO — MO SOS |

Three additional pre-2026 rows (NC_2022, LA_2022, AL_2021) document earlier mid-decade
changes in those states and are marked `PRE-2026 ROW` in `notes` — see the second design
question below for whether code will read them at all.

## Design question this surfaced — RESOLVED 2026-09-30

Missouri breaks the `boundary_confidence` vocabulary as written in the plan. The spec says
`pending` means "a plan exists with status `enjoined`/`pending`", and RD-002 routes
`pending` like `redrawn` — discarding the old prior. For Missouri that is **wrong**: the
map in effect for the general *is* the 2024 map, so the 2024 prior is exactly right.

The register currently classifies Missouri as `unchanged`, on the reading that
`boundary_confidence` describes the relationship between *this cycle's territory and the
prior cycle's*, given whichever plan is in effect — not whether litigation is live. That
keeps the routing correct but drops a real signal: Missouri's boundaries could still move
before November, and the 8th Circuit case is live.

**Resolved: split the two ideas** (signed off 2026-09-30, implemented in
`features/plan_versions.py`). `boundary_confidence` is territory only — `unchanged`,
`redrawn`, `unverified` — and `pending` is gone from the vocabulary. A separate
`litigation_risk` flag (`none` / `active`) rides on every seat, is printed in the
projection's coverage report, and is never consulted by the routing; a test flips only that
flag and asserts the priors come back byte-identical.

⚠️ **`litigation_risk` values are not independently verified.** They are derived from each
row's own verified notes — AL, LA, MO and TN read `active` — and need their own pass with
the same discipline as the rest of the register before anything leans on them.

## Second design question: does the register apply to history? — RESOLVED 2026-09-30

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

**Resolved: Option B — the register applies to all cycles.** Landed as two commits rather
than one so the refit stays attributable: the first added the plumbing with history provably
unmoved, the second flipped the consumers and measured the delta. The full before/after table
is in `docs/redistricting-change-plan.md`. Headline: House MAE improved by 0.000088, 27 more
redistricting breaks, 24 fewer district-cycles in the panel, model seat coverage 89.9% → 84.4%,
and president and Senate bit-identical.

## Also worth knowing

- **Texas, Alabama, and Missouri all had a lower court rule against the map and a higher
  court permit it anyway.** Status can change on a stay, not just on an enactment, which
  is why `retrieved_on` matters more here than in any other reference table. The projection
  report should print the oldest `retrieved_on` among non-`unchanged` rows.
- **Ohio's plan is not a mid-decade partisan redraw**, it is the constitutionally required
  successor to a four-year plan, adopted unanimously by the commission. The register records
  the authority and date; it does not group states by motive.
- **`baf_url` is empty for every row.** Block-assignment files are what RD-003 needs to
  build transferred priors, and none has been located yet. **This is now the next collection
  task.** Redistricting Data Hub is a candidate source; its terms of use are captured at
  `docs/terms_and_conditions/redistricting-datahub-data-download.md` and require
  noncommercial, nonpartisan, non-gerrymandering use plus a specific attribution string —
  register those obligations in `docs/dataset-registry.md` before any download.
- **Primary vs general can differ.** Missouri's August primary used a map its November
  general will not. Any future primary-level modelling cannot assume one plan per cycle.

## Sources consulted

Aggregators used to build the candidate list (not cited as authority for any row):
All About Redistricting (Loyola Law School) <https://redistricting.lls.edu/>, Ballotpedia
<https://ballotpedia.org/Redistricting_ahead_of_the_2026_elections>, and Wikipedia's
2025–2026 United States redistricting article. Per-row claims are cited to the state or
court source in `source_url`, except where the table above marks the source as secondary.

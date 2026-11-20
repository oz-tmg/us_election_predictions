# November 15 UTC Capture and Certified-Subset Scoring

Heartbeat: `2026-11-15T01:50:48.927Z`, which was November 14 at 18:50:48 in
America/Vancouver. Retrieval and observation dates use the actual UTC day,
**November 15**, not the local November 14 date. No observation was backdated.

## Guidance and Existing Work

Read the results runbook and pre-election checklist first. `AGENTS.md` and
`PROJECT_CONTEXT.md` remain absent; the revoked AGENTS instructions were not
restored. Existing modifications to the runbook and the untracked November 12/13
audits were retained. No branch, forecast, source compilation or registration was
changed.

An existing November 14 snapshot contains **209 contests in 24 states**, rather
than the earlier two-state coverage. Its schema, compiled hash and all 37 source
receipts verify. It was created by a separate capture implementation, not by this
run. Its zero-certified observation remains intact at SHA-256
`9a906d9994bfbaf45b40d07fbde1485614883811621f408a5d2f6bb5fe60ec44`.

## Acquisition and Validation

Reused the implementation that produced the expanded observation, from the clean
capture-code worktree at commit `5845f08680f410fc48cfcea1adb91e517cac641e`:

`/Users/alexoswald/Projects/Elections/us_election_predictions-capture-run`

The implementation was reviewed and used read-only, with bytecode/cache writes
disabled or directed to temporary storage. Its acquisition logic selects specific
public aggregate reports, not personal voter/donor files, and performs ordinary
HTTPS requests/form submissions without evading security challenges. No worktree
was switched, merged or edited.

Fresh releases were obtained for all 24 covered states, with no fetch/extraction
failure. Their current contest sets match the frozen October 29 universe.
Eighteen state parsers have recorded 2024 certified-result tests; six use the
explicitly weaker 2026 layout-versus-state-summary cross-check. These gates come
from the reviewed implementation's catalog, identified in the capture report.
The main checkout's older catalog was not rewritten or falsely upgraded.

All returned releases and certification context were preserved through
`python -m election_prediction.build_results_2026 preserve-source`, retaining
actual retrieval timestamps, official URLs and SHA-256. The 40 source receipts
are listed in the daily manifest and capture report. No personal records were
ingested.

## New Observation

Appended through `python -m election_prediction.build_results_2026 capture` with
`--observed-on 2026-11-15` and matching `--source-evidence`:

`data/raw/source=state_canvass/dataset=us_house_2026/snapshot=2026-11-15.csv`

SHA-256: `bb8139183f43ac2f3cae17f8b8b9a0f6574a049111854116bd93330655e90ee2`.

- 209 contests: 194 House and 15 Senate, across 24 states.
- Three contests accepted as certified and resolved; 206 not certified in this observation.
- Louisiana House retains six `first_round` rows, with LA-05 and LA-06 explicitly
  unresolved. No unresolved first round enters the scored subset.
- Earlier CSVs, manifests and raw releases remain unchanged. A replay as of
  November 14 still has zero accepted certified outcomes; later evidence does not leak backward.

Detailed machine-readable acquisition/provenance report:
`reports/captures/capture_2026-11-15.json`.

## Certification Evidence

**Vermont House:** the preserved [authority results page](https://sos.vermont.gov/elections/election-info-resources/elections-results-data)
lists the 2026 general results as official, and the separately preserved election
index at `https://static.electionresults.vermont.gov/elections/68d61e96-1d28-4210-8c1d-8e90512ae105.json`
explicitly has `electionDetails.isOfficial=true`. The associated federal file
contains the winner identity and counts. This is authority evidence, not a media call.

**Wyoming House and Senate:** the preserved [Secretary of State announcement](https://sos.wyo.gov/)
explicitly says the 2026 general election was certified by the State Canvassing
Board on November 10. The preserved results ZIP contains the official statewide
candidate summary for both federal contests. Certification was not inferred
merely from its filename or a news report.

Both authority pages and the Vermont election index have their own raw receipts
in the snapshot manifest. The earlier capture report already noted official
labels but did not accept certification. This run adds reviewed certification
evidence and records **first-observed certification on November 15 UTC**. Wyoming's
stated legal certification date is not substituted for the ledger observation date.

## Scoring

Built only the three certified, resolved outcomes:

`data/gold/actual_2026_certified_asof_2026-11-15.csv`

SHA-256: `8e57a240a91b638e1827cc739ba1b5295b899863e99fee579befcbc89d0baa6e`.

The sealed September forecast was scored through the registered module CLI,
with an explicit November 15 as-of cutoff and no void geography asserted for
these three eligible statewide/at-large VT/WY contests. This is not a legal
clearance of every unscored map dispute.

- Primary score: `reports/scored_2026_asof_2026-11-15/sealed_forecast.json`.
- All four frozen runs: `reports/scored_2026_asof_2026-11-15/frozen_comparisons.json`.
- Every run includes all five assumptions on the same three outcomes; no best
  assumption or run was selected after seeing results. The South Texas scenario
  remains informational, not a forecast.
- The primary score reports 3 of 468 registered seats scored, with 465 unscored
  as not certified. Comparison denominators follow their respective frozen universes.
- Only two House contests are scoreable. Chamber error/coverage and the registered
  failure condition remain `not_evaluable_incomplete_chamber`, with `triggered=null`.

The comparison scores use the registered scoring engine with verbatim,
hash-verified frozen JSON inputs. In-memory adapters provide the scorer's payload
shape and runtime integrity checksum; they are **not** newly sealed/backdated
registrations. Comparison outputs explicitly distinguish frozen-source integrity
from the September seal. No adapter registration was written and no forecast
parameters were recomputed. Comparison limitations remain those documented with
their frozen runs; this three-seat subset cannot establish overall calibration
or comparative model quality.

## Remaining Work

**26 states have no compiled observation:**

AK, AZ, CT, FL, IA, IL, KS, KY, MA, ME, MI, MO, MS, NH, NJ, NM, NV, NY, OH, OK,
OR, RI, SD, TN, TX, WI.

These are project coverage gaps, not claims that the authorities released nothing.
They were not freshly checked live in this run. All 24 attempted states succeeded;
there is no claim of complete 50-state capture. Broaden governed extraction/manual
downloads for the remaining states and review their explicit certification evidence.
Source landing reachability and older access-failure statuses are not current feed
validation.

Integrate the reviewed broader capture implementation into the automation's main
checkout only through an approved code review; this run did not merge the separate
worktree. Until then, its provenance and catalog must remain explicit when reused.
Continue observing certifications, revocations, recounts and any December 12 Louisiana
runoffs. Preserve all first-round/final-round distinctions and never repair the
November 3-11 capture gap retrospectively.

This trigger was 18:50:48 Vancouver, not the intended 22:00. Timing remains
unverified; keep manual fallback. Continue until final resolution or January 4,
2027 and request any required extension. The automation remains useful and was
not deleted or rescheduled.

## Verification

- Reviewed capture implementation: **105 tests passed in 4.31 seconds**, with one
  existing Hawaii trailing-delimiter fixture parser warning.
- Main capture/evidence/scoring/parser regressions: **70 passed in 5.42 seconds**.
- Daily snapshot hash, all 40 raw receipts, and the three prior observations verify.
- All four sealed-file hashes and all eight frozen-comparison file hashes match;
  the September seal verifier passed.
- No full-worktree quality run, commit, publication or runner deployment is claimed.

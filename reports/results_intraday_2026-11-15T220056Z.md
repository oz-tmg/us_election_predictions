# November 15 Intraday Source Review

Heartbeat: `2026-11-15T22:00:56.366Z`, or 15:00:56 America/Vancouver. The intended
22:00 local timing remains unverified; manual fallback is still required.

The November 15 UTC daily observation was already saved earlier today. This run
preserved fresh evidence only: **no second compiled observation, revised as-of
date, overwritten score or new unattended-capture claim**.

## Guidance and Code

Read the results runbook and pre-election checklist first. `AGENTS.md` and
`PROJECT_CONTEXT.md` remain absent; the revoked AGENTS instructions were not
restored. Existing working-tree edits and earlier audits were left intact.

Reused the same reviewed acquisition implementation, read-only at commit
`5845f08680f410fc48cfcea1adb91e517cac641e` in the separate capture-run worktree.
Preservation ran through the main checkout's module CLI. The implementation,
main code/catalog, source compilations and forecast parameters were not changed.

## Fresh Evidence

Refreshed and parsed all 24 currently covered states: **209 contests**, with no
fetch or extraction failures. Every state still matches the frozen contest universe.
Retained 37 aggregate/support releases plus three certification-context responses,
all through `preserve-source --aggregate-only`, with actual retrieval timestamps,
official URLs and SHA-256 checksums.

The detailed immutable raw-file receipts, source checksums and per-state comparisons
are indexed in `reports/captures/intraday_2026-11-15T220056Z.json`. Aggregate acquisition
ran from 22:03:58 through 22:04:52 UTC; certification-context refreshes followed at
22:06:07 through 22:06:09 UTC. No personal voter/donor records were acquired.

Four uncertified contests have revised counts: two in Indiana and two in Maryland.
No leading-party change was verified. Null and empty `winner_party` values both
mean missing/unresolved and are not treated as party changes. Louisiana House
districts 5 and 6 remain unresolved first rounds; neither is scoreable.

The freshly preserved Vermont official-results page, its explicit
`electionDetails.isOfficial=true` metadata, and Wyoming's certification announcement
remain consistent with the three already accepted certified contests. No new
certification or revocation was verified in these reviewed sources. Unchanged
publisher labels do not establish the status of every unreviewed state.

## Observation and Scoring Unchanged

The existing November 15 snapshot remains at SHA-256
`bb8139183f43ac2f3cae17f8b8b9a0f6574a049111854116bd93330655e90ee2`.
All 40 new raw receipts verify, and every earlier observation/manifest checked
against the saved capture hashes remains unchanged.

The certified-only actual table remains at SHA-256
`8e57a240a91b638e1827cc739ba1b5295b899863e99fee579befcbc89d0baa6e`.
No newly scoreable result or certified-count revision requires another score.
Existing reports retain all four frozen runs and all five assumptions on the
same three outcomes; incomplete-chamber evaluation remains unavailable with
`triggered=null`. No score report was overwritten or rerun for provisional changes.

All four sealed-file hashes and all eight frozen-input hashes were reverified.
The seal verifier passed. No new full-worktree test run, commit, publication,
scheduler change or deployment is claimed.

## Remaining Work

Coverage is still 24 states, with these **26 states absent from compiled observations**:

AK, AZ, CT, FL, IA, IL, KS, KY, MA, ME, MI, MO, MS, NH, NJ, NM, NV, NY, OH, OK,
OR, RI, SD, TN, TX, WI.

These states were not checked live in this run. Their absence is a project coverage
gap, not evidence that they published no results. No 50-state capture is claimed.

For the next UTC day, acquire fresh releases and combine every verified state
before invoking the single append-only daily capture. Integrating the broader
reviewed acquisition code into the main checkout remains operator-reviewed work.
Continue explicit certification/revocation, recount and runoff review, including
any December 12 Louisiana final rounds. Do not reconstruct missing November 3-11
observations. Stop at final resolution or January 4, 2027 and request any necessary
extension. The ongoing automation remains useful and was left unchanged.

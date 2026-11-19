# November 12 Results Capture Review

Heartbeat: 2026-11-12T22:04:58.391Z. This run verified an existing daily snapshot
and preserved fresh intraday releases. It did not append a second observation or
score unofficial outcomes.

## Workflow Restored; Existing Snapshot Verified

The checkout is now at `8d497ca` (merge of post-poll-closing-updates). The source
catalog, evidence-preservation CLI, round/as-of safeguards and frozen comparison
set are present again. The November 5 checkout blocker is resolved.

Read `docs/results-2026-runbook.md` and `docs/pre-election-2026-checklist.md` first.
`AGENTS.md` and `PROJECT_CONTEXT.md` were not present at their requested paths.
The prior AGENTS instructions were explicitly revoked; none was restored or
reinstated from history. Available operating guidance and this heartbeat's
capture/privacy/seal requirements governed the review.

The already saved observation is
`data/raw/source=state_canvass/dataset=us_house_2026/snapshot=2026-11-12.csv`.
Its SHA-256 matches its manifest:
`b8e462deaf65d7078924f682827a1c4e349a00a7f64afaaf4db77ce05b8d18b5`.
Both referenced raw receipts and byte checksums verify. Replaying the registered
parsers reproduces all vote counts and `winner_party` fields exactly:

| State | House contests | Senate contests | Certified |
|---|---:|---:|---:|
| MT | 2 | 1 | 0 |
| NC | 14 | 1 | 0 |
| Total | 16 | 2 | 0 |

The as-of ledger for November 12 has **zero certified, resolved outcomes**.
No certified subset exists to build or score, and no score report was generated.
Uncertified winner fields are not certification or a declaration of elected winners.
The existing daily snapshot and its manifest were not changed. The ledger allows
one observation per UTC day; no duplicate capture was attempted or backdated.

## Fresh Official Releases Preserved

Both downloads were checked against the registered aggregate parsers before
preservation with the module CLI `preserve-source --aggregate-only`. Their receipts
record the actual retrieval timestamps, official URLs, raw paths and SHA-256 values.

**North Carolina:**

- URL: https://dl.ncsbe.gov/ENRS/2026_11_03/results_pct_20261103.zip
- Retrieved: `2026-11-12T22:07:43.856006+00:00`.
- SHA-256: `bfe3ef5706bfa728127c32f761db36fab8ea86d8b37eb4ab2604ce36fe8af9b6`.
- Receipt under `data/raw/source=state_canvass_evidence/state=NC/retrieved=20261112T220743856006Z/sha256=bfe3ef5706bfa728127c32f761db36fab8ea86d8b37eb4ab2604ce36fe8af9b6/NC_2026GE_results_pct_20261103.zip.source.json`.
- Fifteen federal contests parse. Relative to the earlier daily observation,
  counts changed in NC-01, NC-14 and the U.S. Senate contest; no `winner_party`
  field changed. The [authority's results page](https://www.ncsbe.gov/results-data/election-results)
  describes the 2026 midterm reporting as unofficial, not certified.

**Montana:**

- URL: https://electionresults.mt.gov/ResultsExport.aspx
- Retrieved: `2026-11-12T22:09:48.423359+00:00`.
- SHA-256: `5b0762adbf054a68123a8207a20fef9f78906446846898739243092c5366a9eb`.
- Receipt under `data/raw/source=state_canvass_evidence/state=MT/retrieved=20261112T220948423359Z/sha256=5b0762adbf054a68123a8207a20fef9f78906446846898739243092c5366a9eb/MT_2026GE_Statewide_Results.xlsx.source.json`.
- Retrieved the statewide export by posting the page's own form fields, the same
  action as its download link. The workbook explicitly says `2026 Unofficial
  General Election Results`. All three federal contest counts and winner fields
  match the earlier observation. Its embedded download time changes the bytes;
  a new checksum alone is not a vote revision.

These fresh releases are **intraday evidence only**, not a second November 12
ledger observation. They were not used to revise the sealed forecast or scores.
No personal voter/donor records were downloaded.

## Coverage and Source Gaps

**48 states are absent from the compiled observation**, not necessarily absent
from the authorities' own reporting systems:

AK, AL, AR, AZ, CA, CO, CT, DE, FL, GA, HI, IA, ID, IL, IN, KS, KY, LA, MA, MD,
ME, MI, MN, MO, MS, ND, NE, NH, NJ, NM, NV, NY, OH, OK, OR, PA, RI, SC, SD, TN,
TX, UT, VA, VT, WA, WI, WV, WY.

Additional catalog-derived checks in this run:

- MA's [2026 general-election search](https://electionstats.state.ma.us/elections/search/year_from:2026/year_to:2026/stage:General)
  returned state-legislative specials, not a verified November federal release.
  No primary/special was substituted for the November House/Senate outcomes.
- WI's listed results page returned HTTP 403 through the web tool.
- MO's listed fallback results page timed out through the web tool.
- The other 45 states were not checked live in this run. These are explicitly
  incomplete checks, not a claim of nationwide capture or site-wide outages.

The unchanged catalog has five historical-parser validations (MA, MO, MT, NC, WI),
45 `manual_review_pending` entries, and access statuses of five `automated_ok`,
seven previously `blocked_manual_download`, and 38 `untested`. Historical parser
tests and readable landings do not prove current feeds or certification.

## Checks and Next Work

Focused capture, evidence, scoring and parser tests: **70 passed in 5.56 seconds**.
Command: `.venv/bin/pytest tests/unit/test_results_2026.py tests/unit/test_results_sources.py tests/unit/test_score_preregistration.py tests/unit/test_state_extraction.py -q`.
The seal verifier and all four previously recorded sealed-file hashes passed.
All eight file hashes in the frozen four-run comparison set also match.

Next UTC observation: reacquire current official releases, combine every verified
state available before invoking `capture --source-evidence`, and retain missing
states explicitly. Do not alter the earlier snapshot, reconstruct the November
3-11 gap, or turn today's intraday evidence into an invented second observation.
Record certification only from explicit authority evidence. Follow revocations,
recounts and runoffs; a certified but unresolved Louisiana House first round
remains unscoreable. Continue until final resolution or January 4, 2027, requesting
any necessary extension.

This heartbeat was 15:04:58 America/Vancouver, not the intended 22:00. Manual
invocation remains necessary until actual timing is confirmed. No scheduler,
branch, source compilation, forecast parameter or registration was changed, and
no complete or new unattended compiled capture is claimed by this run.

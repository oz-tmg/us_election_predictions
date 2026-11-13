# November 13 Partial Results Capture

Heartbeat: 2026-11-13T22:04:13.887Z. A fresh UTC-dated observation was saved and
validated for MT and NC. Coverage remains two states, with no certified outcomes.
Routine count updates did not change the leading party in any recorded contest.

## Guidance and Preservation

Read the results runbook and pre-election checklist before operating the capture
workflow. `AGENTS.md` and `PROJECT_CONTEXT.md` remain absent at their requested
paths; the previously revoked AGENTS instructions were not reinstated. The checkout
remains at `8d497ca`; no branch or forecast configuration was changed.

The pre-existing November 12 audit was left untouched. The September registration,
its seat table and findings, source compilations, catalog, parameters and frozen
comparison set were not edited. No personal voter or donor records were acquired.

## Fresh Sources

Each source was preserved using the module CLI `preserve-source --aggregate-only`.
The daily snapshot manifest records the exact raw files and source-evidence receipts.

| Source | Actual retrieval timestamp (UTC) | SHA-256 |
|---|---|---|
| NC precinct aggregate ZIP | 2026-11-13T22:08:19.653432+00:00 | `68a3bc6daa0d95f23ffbc0a2a9254c1c24acea3fe668c162db1a7f7b26d7bf3c` |
| NC unofficial reporting-status page | 2026-11-13T22:08:21.807769+00:00 | `df37a12e7f61f039f24e36d8e841c014fb01940bdf3aa65794972701e3127057` |
| MT statewide aggregate workbook | 2026-11-13T22:08:24.257767+00:00 | `780b4462c5ee3985f070ade527851ce759e28e72f6e811c4874eb22005f01df8` |

Source URLs:

- NC counts: https://dl.ncsbe.gov/ENRS/2026_11_03/results_pct_20261103.zip
- NC status: https://www.ncsbe.gov/results-data/election-results
- MT counts/status: https://electionresults.mt.gov/ResultsExport.aspx

The NC authority page explicitly describes the 2026 midterm reporting as unofficial;
the matching HTML was retained. The MT workbook explicitly says `2026 Unofficial
General Election Results`. Its download was the page's normal statewide-export
form submission, not a bypass of a security challenge. Precinct completion was
not treated as certification.

Both historical parser gates were replayed against preserved 2024 files before
capture: MT three races and NC fourteen races, all exact against certified history.
This validates those historical extraction paths, not nationwide live coverage.

## Saved Observation

The module CLI `capture --observed-on 2026-11-13 --source-evidence ...` appended:

`data/raw/source=state_canvass/dataset=us_house_2026/snapshot=2026-11-13.csv`

Compiled SHA-256:
`f043467cb87121d8894e9a9aa0c63ab5d409a1c091c46a3bb513aa02d9184f03`.

| State | House contests | Senate contests | Certified |
|---|---:|---:|---:|
| MT | 2 | 1 | 0 |
| NC | 14 | 1 | 0 |
| Total | 16 | 2 | 0 |

Rows retain the ordinary November general-round identity and source-derived
candidate-party leader fields. These fields are not calls or certified elected
winners. All rows remain `certified=False`; no Louisiana/RCV first round was
silently treated as a final outcome.

Compared with the November 12 daily observation, fourteen NC contests and two MT
contests have revised counts. No `winner_party` field changed. The earlier
observation remains byte-for-byte intact at SHA-256
`b8e462deaf65d7078924f682827a1c4e349a00a7f64afaaf4db77ce05b8d18b5`.
Yesterday's intraday files and receipts were also retained, not overwritten.

The November 13 as-of ledger contains zero certified, resolved outcomes. No
certified subset exists to build or score, so no actual-results/scoring artifact
was generated. Partial coverage cannot evaluate the registered chamber condition.

## Missing States and Unverified Sources

Forty-eight states are absent from the compiled observations:

AK, AL, AR, AZ, CA, CO, CT, DE, FL, GA, HI, IA, ID, IL, IN, KS, KY, LA, MA, MD,
ME, MI, MN, MO, MS, ND, NE, NH, NJ, NM, NV, NY, OH, OK, OR, PA, RI, SC, SD, TN,
TX, UT, VA, VT, WA, WI, WV, WY.

These are project coverage gaps, not claims that the states have released nothing.
Additional catalog-derived checks today:

- MA's 2026 general-election search showed state-legislative specials, not a
  verified November federal count release. None was substituted for federal results.
- WI's listed results page returned HTTP 403 through the web tool.
- MO's fallback page linked November 3 unofficial reporting. Its ENR page was
  readable through the web tool but exposed no count table there; a direct honest
  research-client request returned HTTP 403. A readable landing is not a validated feed.
- The other 45 states were not checked live in this run. The catalog remains at
  five historical-parser validations and 45 pending extraction reviews; no status
  was upgraded based on reachability. The seven prior manual-download blockers
  were not freshly revalidated today.

## Verification and Follow-Up

Focused capture, evidence, scoring and parser tests: **70 passed in 8.35 seconds**.
Both daily snapshot hashes and every receipt referenced by their manifests verify.
All four sealed-file hashes and all eight frozen-comparison file hashes match.
The seal verifier passed. No full-worktree quality run or deployment is claimed.

The heartbeat arrived at 15:04:13 America/Vancouver, not the intended 22:00.
Retain manual fallback until actual scheduling is verified. Continue daily UTC
observations, explicit certification/revocation review and missing-state reporting.
Louisiana House first rounds remain unscoreable if unresolved, even if certified;
track any December 12 runoff, recounts and recertifications. Never backdate the
November 3-11 gap. Stop at final resolution or January 4, 2027, requesting any
necessary extension. The automation remains useful and was not deleted or changed.

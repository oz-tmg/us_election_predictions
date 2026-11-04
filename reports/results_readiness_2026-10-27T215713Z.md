# October 27 Results-Capture Readiness

Heartbeat: 2026-10-27T21:57:13.994Z, or 14:57:13 America/Vancouver on October 27.
Pre-election readiness check only. No general-election releases acquired, production
observations captured or certified-subset scoring attempted.

Read first: `AGENTS.md`, `PROJECT_CONTEXT.md`, `docs/results-2026-runbook.md` and
`docs/pre-election-2026-checklist.md`. Only this report is added; sealed forecast and
registration files, parameters, source compilations, scheduler configuration and
unrelated working-tree edits remain unchanged.

## Material Blockers

1. **State extraction is still untested in all 50 states.** The source catalog passes
   its 50-state schema/key checks, but all rows remain `manual_review_pending`.
   Demonstrate actual House/Senate aggregate extraction against prior official releases,
   record certification evidence and retain a manual fallback for every state before
   relying on election-night capture. Reachable landing pages are not validated feeds.
2. **The actual trigger does not match 22:00 Vancouver.** The saved automation is active
   and specifies Vancouver timezone/hour 22, but this heartbeat arrived at 14:57 local.
   Correct 22:00 execution is not verified. Keep the manual runbook fallback; no scheduler
   repair, deployed runner or unattended results-capture success is claimed.

## Source Evidence

The latest saved probe remains
`reports/refresh_2026-10-22/results_source_checks.json`, checked at
2026-10-23T00:08:07.381642Z (October 22 Vancouver). It found 30 reachable primary
landings and neither landing readable for **AK, AZ, ME, MA, MI, MT, NH, OH, TN and WI**.
These are the last recorded access failures, not fresh October 27 network findings.
No new network probe was run. All 65 preserved reachable-page files still exist and
match their checksums. All states remain extraction-untested regardless of reachability.

## Local Checks

- The read-only cached-data preflight passes with `EP_REQUIRE_LIVE_DATA=1` and an explicit
  checkout-local `EP_DATA_ROOT`; no missing data or modifications are reported.
- Fresh focused tests pass: **58 in 7.98 seconds**, using
  `.venv/bin/pytest tests/unit/test_results_2026.py tests/unit/test_results_sources.py tests/unit/test_score_preregistration.py -q`.
  They exercise capture/evidence/certification/scoring logic, not live state extraction.
- Capture CLI, ledger, source-evidence module, scorer, historical rehearsal script and
  state source catalog match their hashes from the earlier full verification. A new
  full-worktree test run is not claimed.
- The seal verifier passes and all four sealed files match the hashes in
  `reports/polling_lean_2026-10-25_senate2024_final/study.json`.
- No production state-canvass CSV snapshots exist; this is expected before November 3
  and is not a successful capture.

## Remaining Execution Boundary

Before November 3, continue readiness-only checks. From Election Night, preserve actual
official public aggregate releases with their true retrieval timestamps, URLs and SHA-256
through `preserve-source`; use append-only daily UTC observations with
`capture --source-evidence`, then build and score certified resolved subsets only.
An unresolved Louisiana House first round remains unscoreable even if certified.
Keep missing/unreadable states, rounds, certification revocations and revisions explicit.
Continue through recounts and December runoffs; stop after final resolution or January 4,
2027 and request any necessary extension. Never infer certification from a media call.

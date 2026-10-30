# October 28 Results-Capture Readiness

Heartbeat: 2026-10-28T21:59:52.416Z, or 14:59:52 America/Vancouver on October 28.
Read first: `AGENTS.md`, `PROJECT_CONTEXT.md`, `docs/results-2026-runbook.md` and
`docs/pre-election-2026-checklist.md`. This was a pre-election readiness check, not a
general-election results capture or forecast evaluation.

## Material Blockers

1. **All 50 state extraction paths remain untested.** The catalog validates as exactly
   50 states, but every extraction status remains `manual_review_pending`. Test actual
   public House/Senate aggregate extraction against prior official releases, review
   certification evidence and retain state-specific manual fallbacks. Landing-page
   reachability is not a validated feed or acceptance of a November extraction path.
2. **The automated client cannot read either listed landing in 11 states:** AK, AZ, ME,
   MA, MI, MO, MT, NH, OH, TN and WI. Missouri is newly affected relative to the October
   22 local probe: its primary returned HTTP 403; its fallback timed out. This establishes
   client access failures, not site-wide outages or the absence of other official routes.
   Manual review or an alternative official entry point is still required.
3. **Actual scheduling still disagrees with the intended 22:00 Vancouver time.** The
   active saved configuration specifies Vancouver timezone/hour 22, but this heartbeat
   arrived at 14:59:52 local. Retain manual invocation of the runbook and verify an actual
   22:00 local execution before relying on unattended operation. No schedule repair or
   unattended results-capture success is claimed.

## Fresh Source Probe

Command: `.venv/bin/python -m election_prediction.build_results_2026 check-sources --out reports/results_source_checks_2026-10-28T215952Z.json`.

The probe started at 2026-10-28T22:00:58.843341Z. Unlike the preceding readiness audits,
this check refreshed the official landing-page inventory rather than reporting only
older access failures. It examined all 50 catalog entries and their primary/fallback
URLs. Results and per-URL errors are preserved in
`reports/results_source_checks_2026-10-28T215952Z.json`:

- 30 primary landings readable; 39 states have at least one readable listed landing.
- 64 landing-page snapshots preserved with actual UTC retrieval times, URLs and SHA-256;
  all 64 files exist and their recorded checksums match.
- Preserved-page retrieval timestamps range from 22:00:59.331795Z to 22:02:14.855789Z
  on October 28. Archive/source dates were not substituted for retrieval time.
- Every state remains `capture_ready=False`; all 50 extraction paths are untested.
- `outcomes_captured=0`. Only landing HTML and candidate release links were retained;
  no vote counts, winner identities or certification status were compiled.

Raw landing evidence is under `data/raw/source=state_canvass_readiness_2026/`. The older
October 22 probe and its snapshots were retained, and the source catalog was not edited.

## Local Checks and Preservation

- Read-only local cached-data preflight passed with `EP_REQUIRE_LIVE_DATA=1` and an
  explicit checkout-local `EP_DATA_ROOT`; no missing inputs or modifications reported.
- Fresh capture/evidence/certification/scoring regressions: **58 passed in 4.62 seconds**.
  Command: `.venv/bin/pytest tests/unit/test_results_2026.py tests/unit/test_results_sources.py tests/unit/test_score_preregistration.py -q`.
  These tests do not validate any live state extraction path.
- Capture CLI, ledger, source-evidence module, scorer, historical rehearsal script and
  source inventory match their hashes from the earlier full local verification. This
  heartbeat does not claim a new full-worktree test run or CI deployment.
- The seal verifier passed. All four sealed files still match their recorded hashes
  after the network probe. Forecast parameters, source compilations, scheduler settings
  and unrelated working-tree edits were not changed.
- No production state-canvass CSV observations exist; none was created here. Preserved
  landing-page evidence is not a production results snapshot.

## Election-Night Boundary

Before November 3, perform readiness checks only. From Election Night, preserve actual
official public aggregate releases with true retrieval timestamps, URLs and SHA-256
through `preserve-source`; then use daily UTC observations with append-only
`capture --source-evidence`. Build and score certified resolved subsets under the
existing as-of rules. A certified unresolved Louisiana House first round remains
unscoreable. Do not infer certification from media calls or collect voter/donor records.
Retain missing/unreadable states, revocations, recounts and runoff status explicitly.
Continue until final resolution or January 4, 2027 and request any necessary extension.

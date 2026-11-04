# October 25 Results-Capture Readiness

Heartbeat received: 2026-10-25T22:06:31.551Z, or 15:06:31 America/Vancouver.
Pre-election readiness check only. No general-election releases acquired, no compiled
production snapshot saved, and no certified-subset scoring attempted.

Read first: `AGENTS.md`, `PROJECT_CONTEXT.md`, `docs/results-2026-runbook.md` and
`docs/pre-election-2026-checklist.md`. These governing files and all source compilations,
forecast parameters, sealed registration files and unrelated working-tree edits were
left unchanged. This report is not proof of an unattended capture.

## Material Blockers

1. **Actual extraction is untested in all 50 states.** The current source catalog is
   valid and contains exactly 50 states, but every `extraction_status` remains
   `manual_review_pending`. A reachable portal is not a validated aggregate feed.
   Before Election Night, test each actual House/Senate extraction against a prior
   official release and document the certification evidence and manual fallback.
2. **The actual trigger still disagrees with the intended time.** The existing
   automation is active and its saved configuration specifies 22:00 America/Vancouver;
   this heartbeat instead arrived at 15:06 local. Saved configuration therefore does
   not establish correct scheduling. Retain manual invocation of the runbook and verify
   an actual 22:00 local run before relying on unattended operation. No schedule was
   changed and no duplicate automation was created by this check.

The latest saved landing-page probe was checked at 2026-10-23T00:08:07.381642Z
(October 22 Vancouver), not today. It found 30 reachable primary URLs and neither
landing readable for **AK, AZ, ME, MA, MI, MT, NH, OH, TN and WI**. Those are the last
recorded access failures, not a claim of fresh October 25 network failures. No new
network probe was run; all states remain extraction-untested regardless of reachability.
The probe is `reports/refresh_2026-10-22/results_source_checks.json`. All 65 preserved
reachable-page evidence files still exist and match their saved SHA-256 values.

## Local Verification

The completed quality report `reports/polling_archive_verification_2026-10-25.json`
was saved at 22:04:44 UTC, shortly before this heartbeat. All eight checks passed,
including 697 tests, lint, formatting, mypy, the privacy guard and historical scoring
rehearsal. Current code/reference fingerprints still match that saved validation.
The sealed registration passes its verifier; no forecast inputs were changed here.

The read-only cached-data preflight passes with `EP_REQUIRE_LIVE_DATA=1` and
`EP_DATA_ROOT` explicitly pointing to this checkout's `data` directory; no inputs are
missing and no data are modified. The unconfigured interactive invocation does not
have a default `EP_DATA_ROOT`/`ELECTION_DATA_ROOT`; this is not evidence of a deployed
self-hosted runner. Runner registration remains an optional operator action, not a
prerequisite for the local/manual fallback.

## Operational Boundary

Do not put rehearsals or invented outcomes in production capture storage. Starting
Election Night, preserve actual official public aggregate releases with their true
retrieval timestamps, URLs and SHA-256 through `preserve-source`, then use append-only
`capture --source-evidence`. Score only certified, resolved subsets with the existing
as-of rules. A certified unresolved Louisiana House first round remains unscoreable.
Continue through revocation, recounts and December runoffs; stop after final resolution
or January 4, 2027 and request an extension if needed. Neither complete capture nor
unattended success is claimed by this readiness audit.

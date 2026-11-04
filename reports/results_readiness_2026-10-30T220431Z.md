# October 30 Results-Capture Readiness

Heartbeat: 2026-10-30T22:04:31.910Z, or 15:04:31 America/Vancouver on October 30.
Read first: `AGENTS.md`, `PROJECT_CONTEXT.md`, `docs/results-2026-runbook.md` and
`docs/pre-election-2026-checklist.md`. This is a pre-election readiness audit, not
a 2026 general-election observation, release capture or forecast evaluation.

## Material Blockers

1. **46 state extraction paths remain untested.** The current catalog has four
   `parser_tested_2024` entries (MA, MO, MT, WI) and 46 `manual_review_pending`
   entries. The four historical parsers are meaningful progress, not proof of a
   working 2026 feed. The checklist's all-state extraction acceptance target remains
   unmet. Review the actual 2026 release format, contest coverage, rounds and
   certification evidence before compiling any observation.
2. **Seven states still require manual browser downloads:** AK, AZ, ME, MI, NH, OH
   and TN. Their latest saved extraction rehearsal records automated-access blocks;
   the other 39 unreviewed states have `download_access=untested`. No fresh network
   probe was performed in this audit. None of the eleven states in the October 28
   landing-probe failure group has a tested statewide election-night feed; keep
   the runbook's manual election-night fallback. The historical MA/WI/MO routes help
   with later canvasses. MT's export is explicitly unofficial even though its 2024
   counts reconcile: separate canvass evidence is still needed for certification.
3. **Actual scheduling still differs from the intended 22:00 Vancouver time.** The
   saved automation remains active with Vancouver timezone/hour 22, but this
   heartbeat arrived at 15:04:31 local, consistent with the earlier approximately
   22:00 UTC triggers. Do not rely on the November 3 afternoon trigger to preserve
   an election-night release. Invoke the runbook manually that night unless actual
   intended-time execution has been confirmed. Preserve intraday raw releases
   separately; if manual and automated runs share a UTC day, the ledger still allows
   only one compiled observation. Do not overwrite it or invent a new date.

## Historical Evidence Rechecked

The current evidence is `reports/extraction_rehearsal_2026-10-30/summary.json`,
the four reconciliation CSVs in that directory and the raw files they reference.
All **13 saved raw files** exist and match their recorded SHA-256 values. Replaying
the registered parsers locally, without downloads or writes, reproduced the saved
reconciliation summaries:

| State | Saved files | 2024 races | D/R reconciliation |
|---|---:|---:|---|
| MA | 10 | 10 | All exact |
| WI | 1 | 9 | All exact |
| MO | 1 | 9 | All exact |
| MT | 1 | 3 | All exact |

These checks cover 31 historical race totals, not 2026 availability, certification,
all candidate identities or every election-night format. They supersede the older
readiness reports' statement that all 50 paths were untested. No catalog entry,
earlier evidence, parser or source compilation was changed by this audit.

## Local Checks

- Read-only cached-data preflight passed with `EP_REQUIRE_LIVE_DATA=1` and the
  checkout-local `EP_DATA_ROOT`. It reported no missing inputs or data modifications.
- Focused capture, source-evidence, certification, scoring and extraction tests:
  **69 passed in 3.51 seconds**. Command:
  `.venv/bin/pytest tests/unit/test_results_2026.py tests/unit/test_results_sources.py tests/unit/test_score_preregistration.py tests/unit/test_state_extraction.py -q`.
  These tests do not establish live-feed completeness or unattended execution.
- The seal verifier passed. All four sealed file hashes match their previously
  recorded values. All eight file hashes in the four-run frozen comparison set,
  `reports/comparison_set_2026-11-03.json`, also match. No new refresh was run or added.
- No production `data/raw/source=state_canvass/**/snapshot=*.csv` observations exist.
  None was created or scored. No full-worktree verification, runner deployment,
  scheduler correction or unattended results-capture success is claimed.

Only this audit report was added. The sealed September forecast and registration,
forecast parameters, frozen comparisons, source compilations, scheduler configuration
and pre-existing working-tree content were left unchanged.

## Next Boundary

Continue readiness-only checks before November 3. From election night onward, preserve
actual official public aggregate releases with their true retrieval timestamps, URLs
and SHA-256 using `preserve-source`, then use append-only daily UTC observations with
`capture --source-evidence`. Build and score only certified resolved subsets under the
existing as-of rules and frozen comparison policy. A certified but unresolved Louisiana
House first round is not scoreable. Report missing states and unreadable sources;
never infer certification from a media call or collect personal voter/donor records.
Track certification revocation, recounts and December runoffs. Stop after final
resolution or January 4, 2027 and request any needed extension.

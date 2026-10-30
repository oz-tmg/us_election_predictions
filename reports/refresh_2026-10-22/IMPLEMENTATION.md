# Pre-Election Execution: October 22

Owner: Alex Oswald. Nonpartisan internal research. This report distinguishes delivered
code/evidence from accepted sources, deployed operations and a future November freeze.
The September 30 forecast and registration are unchanged. No general-election results,
public forecast release, commit, push or runner deployment are claimed.

Report/review dates use the project's America/Vancouver calendar. Late October 22 work
may have October 23 UTC acquisition timestamps in raw manifests; those timestamps are
preserved, not backdated. The future general-results ledger separately uses explicit
UTC calendar days throughout, as specified in the runbook.

| Step | Delivered | Remaining acceptance gate |
|---|---|---|
| 1. Results sources | All 50 states inventoried with primary/fallback URLs and certification requirements; 100 landing probes saved with HTML/checksums or explicit errors; raw aggregate preservation and source-evidence matching added | 30 primary URLs reachable; 40 states have at least one reachable landing. Every November extraction path still needs reviewed testing. Reachable HTML is not a validated feed. |
| 2. Schedule/rounds | Automation prompt and explicit Vancouver timezone recurrence saved/read back; Louisiana round/resolution safeguards; UTC ledger dates; module CLI and installed entry point verified | Prior trigger was near 15:02 local. A separate timezone field was rejected, but timezone-qualified recurrence was accepted. Next actual 22:00 trigger remains unverified; manual fallback required. B.C. stays UTC-7 this November. |
| 3. Candidacies | 182 -> 203 verified races: 187 House/16 Senate; all ten original identity ambiguities resolved by exact-pair reviews, including distinct Trever/Troy. New official Delaware/NJ extracts and NE/WV positive Senate observations | 267 unknown, including 19 Senate contests. Coons alias source returned 403; additional NJ given-name cases and NJ12 absence remain unresolved. Partial major-party extraction cannot prove retirement. |
| 4. Transfers | Official NC original returns and archived election-year polygons acquired with hashes. Both years reconcile by major party. Improved 2020 placement conserves all 5,443,065 offered votes; independent 2020->2022 diagnostic covers 14 districts, MAE 0.0175 versus fallback 0.1086 | 2024 precinct polygons produce ambiguous block assignments. Election-day vintage review and complete confidence/calibration review remain necessary. 2020 placement includes 2,288,330 county-allocated votes, not exact precinct geocoding. No new priors admitted; 135 fallbacks retained. |
| 5. Source repairs | Fresh Kansas workbook again parsed and compared with certified totals. NC original returns provide a reconciled alternative to the flagged input. All raw sources immutable | Kansas short 17 D/27 R; never balanced or suppression-reversed. Florida replacement ZIP and Maine ballot workbook returned 403. IN/LA/OK/NJ defects remain excluded. |
| 6. Fresh evidence | Both Florida 2025 congressional specials reverified against actual federal-results table, all D/R/other counts unchanged; actual source URL/retrieval updated. Original Marist/Emerson releases re-acquired; separate dated cross-check rebuilt | No newer eligible national district vote-intention survey established from reviewed catalogs. Quinnipiac chamber-control preference excluded as a distinct question. Remaining specials retain actual earlier dates; Tennessee PDF returned 403. No macro/poll/correlation promotion. |
| 7. Rehearsal/testing | Raw evidence checksums; interrupted-write recovery; exclusive daily snapshots; UTC boundaries; revoked/reinstated certification; unresolved rounds; malformed inputs; explicit other-party winner; source tampering and cached-retrieval provenance regressions. Historical scoring rehearsal and local data preflight exercised | Manual extraction and certification interpretation remain operator review tasks. Hosted live-data CI still requires isolated runner/admin setup. Historical rehearsal is not forecast evaluation. |
| 8. Audit package | Dated projection/seal comparison, source/identity/transfer reports, reproducibility hashes, package versions, saved verification commands, runbook and acceptance checklist | November 1-2 rerun/freeze and official map/legal-status review are future work. Dirty-worktree hashes do not substitute for an approved reviewed commit and independently reproduced checkout. |

## Verification

`verification_final.json` contains final command output, package/code/reference hashes,
unchanged-during-checks assertion, seal-byte verification, local preflight and rehearsal.
Every command must have return code zero before calling the check complete. The earlier
`verification.json` preserves its 647-test run; focused final intake/capture tests passed
68/68 after the last transform changes. Final full-suite count is recorded in the final
artifact rather than inferred from the earlier run. `verification_final.json` is the
current acceptance result. Final full-suite result: **648 passed**, Ruff/format/mypy,
privacy filename guard, local data preflight and historical rehearsal all passed. Code
and reference hashes were unchanged during the final checks; all three seal file hashes
match the pre-work values. `scheduler_audit.json` records saved configuration, not an
observed unattended run.

The installed `ep-results-2026` entry point was repaired by reinstalling this editable
project with build isolation and without changing runtime dependencies. The runbook
also uses the explicit `.venv/bin/python -m ...` form, which does not depend on a wrapper.
The source helper now retains existing acquisition manifests on cache reuse and rejects
changed registered bytes/URLs. A rebuild cannot silently make cached evidence look fresh.
`privacy_worktree_scan.json` additionally applies the existing filename guard to tracked
and nonignored untracked files (540 at that check), with no violations. It is explicitly
a filename/bulk-file guard, not a comprehensive personal-data content audit.

No production snapshots exist in
`data/raw/source=state_canvass/dataset=us_house_2026/`. That is expected before November 3.

## Outstanding Access/Operations

Both inventoried landing URLs failed with this acquisition client for AK, AZ, ME, MA,
MI, MT, NH, OH, TN and WI. This is not a claim that the state publishes no results or
that a human browser cannot access them. Exact HTTP/errors and retained reachable pages
are in `results_source_checks.json`. Candidate-source reachability is a separate check.

Remaining Senate evidence queue: AK, AR, CO, DE, GA, ID, KS, LA, ME, MA, MS, NM, OK, OR,
RI, SC, SD, TN and VA. Official general ballots are required; filing-only and primary
lists encountered during research were not accepted as nomination evidence.

Do not deploy a public-repository self-hosted runner on a workstation with personal or
acquisition credentials. Operator/admin registration and a first reviewed hosted run
remain pending. Local reconciliation succeeds with `EP_DATA_ROOT` explicitly pointed
at this public-data lake; no system-wide environment setting was changed.

## Reproduce

```bash
.venv/bin/python -m election_prediction.build_ballots --as-of 2026-10-22
.venv/bin/python scripts/audit_priority_transfers.py
.venv/bin/python scripts/repair_official_sources.py
.venv/bin/python -m election_prediction.build_generic_ballot --as-of 2026-10-22
.venv/bin/python scripts/refresh_2026.py --as-of 2026-10-22
.venv/bin/python scripts/verify_pre_election.py --out reports/pre_election_checks_NEW.json
```

Kansas repair intentionally exits nonzero. Dated source probes, Florida review and final
verification refuse report overwrite; retain their original artifacts and use a new
observation/review date for new evidence. Inspect the runbook before any production use.
These commands need the registered local snapshots; an empty checkout alone is insufficient.

Source review: `evidence_review.md`. Operating acceptance list:
[`docs/pre-election-2026-checklist.md`](../../docs/pre-election-2026-checklist.md).

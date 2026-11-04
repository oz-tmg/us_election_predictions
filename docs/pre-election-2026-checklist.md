# Pre-Election Acceptance Checklist

Owner: Alex Oswald. October 22, 2026. Implementation is not acceptance. No 2026 general
outcomes have been collected. The September 30 seal remains the scored holdout.

## Completed or Exercised

- Fifty-state source inventory, primary/fallback reachability audit, immutable landing
  evidence and explicit untested-extraction status. This is not a 50-state results feed.
- Raw public-aggregate preservation command with URL, timezone-aware actual retrieval,
  SHA-256 and exclusive writes. Production compiled captures require matching evidence.
- Certification revocation/recertification episodes, unresolved Louisiana first rounds,
  UTC dates, malformed inputs, interruption/retry, duplicate capture and source tampering
  covered by focused regression tests. Historical scoring rehearsal remains non-evaluative.
- Exact-pair candidate identity reviews preserve distinctions such as Trever versus Troy.
  Official Delaware/New Jersey lists and positive Nebraska/West Virginia Senate reviews
  extend coverage where the evidence is readable and identity matches.
- Fresh Kansas acquisition still fails certified totals. Official original NC results
  reconcile in both 2020 and 2024; geometry/calibration gates remain separate.

## Before October 30

1. For every state, inspect the actual November House/Senate download, demonstrate the
   extraction against a prior official release, document certification evidence and
   update the inventory's extraction status only after a reviewed test. Keep a manual
   fallback and report blocked states. Save the first election-night release separately.
2. Finish unresolved Senate candidacies and House cases from official general ballots.
   Do not use primary placeholders, filing-only lists or partial extraction as absence
   evidence. Work from the dated ballot coverage/identity reports, not the old total.
3. Review official NC precinct geography and historical transfer calibration. Florida's
   official replacement ZIP returned HTTP 403; acquire a readable official replacement
   or retain fallback. No balancing votes or reversed suppression/privacy noise.
4. Reverify remaining specials using their exact election/round and official aggregates.
   Polling refresh must use national district vote-intention questions with field dates,
   sample/mode and publication date; chamber-control preference is a separate construct.

## November 1-2 Freeze

1. Run `python scripts/verify_pre_election.py --out reports/pre_election_checks_DATE.json`
   with the project virtualenv; review every failure and saved command output.
2. Run the dated refresh, archive input/code/environment hashes and review the change
   report. Do not overwrite any September registration or historical dated evidence.
3. Recheck official legal/map status for the redrawn states and Missouri; record exact
   authority links and actual retrieval dates. Geometry alone does not settle litigation.
4. Review exclusions and remaining 135 redrawn-seat fallbacks. Macro/polling and measured
   correlation experiments stay unpromoted unless their existing gates genuinely pass.
5. Verify the scheduler's NEXT ACTUAL trigger. An explicit Vancouver timezone recurrence
   is saved, but actual 22:00 execution is not confirmed. B.C. remains UTC-7 with no
   November 1 fall-back; see the runbook's official source. Keep the computer/app running
   and manually invoke the runbook if the scheduled run is absent.
6. Review/push an approved commit if desired. No commit, publication or runner deployment
   is implied by a local verification report. An isolated CI runner needs operator/admin
   setup; local validation and manual capture do not depend on it.

## Election Night and After

Use `docs/results-2026-runbook.md`. Capture official aggregates as unofficial until the
authority certifies them, track missing/unreadable states and unresolved rounds, and
score only certified resolved subsets. Never assert complete chamber evaluation from
partial results. Follow certifications, revocations, recounts and December runoffs.
The automation stops no later than January 4, 2027; request extension if unresolved.

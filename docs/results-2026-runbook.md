# 2026 Results Capture and Scoring

Owner: Alex Oswald. Updated and rehearsed 2026-10-22 with historical fixtures only. No real 2026
general-election results exist yet. Do not store rehearsals in the production capture directory.

## Capture Schedule

- November 3: retain the first official House/Senate aggregate release, labeled unofficial.
- November 4 onward: capture daily while totals or certification status change; retain each
  state's official source URL and actual retrieval date. Review every day through certification.
- Continue through any December runoff, recount, court decision or revised canvass. Do not
  mark a race certified merely because a news organization called it.
- Review map changes separately: a void geography requires an explicit sourced reason under
  the sealed rules. Candidate changes are not a carve-out from the registered forecast.

On October 21 the active thread automation `capture-official-2026-election-results`
was installed for **22:00 America/Vancouver daily**, through January 4, 2027. Before
November 3 it checks readiness only. From election night it attempts official aggregate
capture, validates append-only observations and reports missing/unreadable sources.
It must not claim a capture succeeded without a saved validated snapshot. Review initial
runs; this is not a guaranteed 50-state data feed. The computer and desktop app must be
running for local-project tasks ([official scheduling guidance](https://learn.chatgpt.com/docs/automations?surface=app)).
Owner: Alex Oswald; no third party was contacted or assigned work.

**The next actual trigger is not verified.** The October 22 heartbeat arrived at
22:02 UTC, about 15:02 Vancouver, rather than the intended 22:00 local. A separate
timezone field was rejected, but a recurrence with an explicit Vancouver timezone was
then accepted and read back from the existing automation's saved configuration. No
duplicate was created. Check the next actual trigger and keep the manual fallback;
saved configuration is not proof of unattended execution. See `scheduler_audit.json`
in the October 22 report. The prompt includes round/revocation safeguards and this checklist.

B.C. remains at UTC-7 this November; there is **no November 1 fall-back** in Vancouver.
The local timezone database agrees: November 3 at 22:00 is November 4 at 05:00 UTC,
not 06:00 UTC. Do not apply a U.S. Pacific winter offset to this schedule.
[B.C. government announcement](https://news.gov.bc.ca/releases/2026AG0013-000209)

## Source Inventory and Raw Evidence

`data/reference/results_sources_2026.csv` lists all 50 voting states, primary/fallback
landing URLs, expected formats and certification-document requirements. The October 22
probe saved HTML/checksums and explicit errors in
`reports/refresh_2026-10-22/results_source_checks.json`. Reachability is NOT verified
extraction or 2026 outcome availability; all extraction paths still need review. Discover
and retain the actual release link, not merely the portal's home page. No personal voter,
donor, absentee-request or voter-history records may be downloaded.

For every release, manually review that it is public aggregate data, preserve the actual
download with its retrieval timestamp, and retain the returned `.source.json` path:

```bash
.venv/bin/python -m election_prediction.build_results_2026 preserve-source \
  --file /absolute/path/official-aggregate.csv --state VA \
  --url https://official-authority.example/aggregate.csv \
  --retrieved-at ACTUAL_ISO_TIMESTAMP_WITH_TIMEZONE --aggregate-only
```

The URL/timestamp above are placeholders, not a source or an observed result. Capture
requires matching raw evidence for every row in the default production directory and
checks the preserved bytes' SHA-256. Retain intraday releases separately even though the
compiled ledger accepts only one observation per UTC day. Raw releases and observations
are never overwritten. Failed writes do not publish partial CSV snapshots. Repeated
same-day capture fails explicitly; do not invent a later retrieval date to bypass it.

## Input and Commands

Compile only public aggregates, one row per race, from state election authorities. Required
columns: `state_po,district_num,office,dem_votes,rep_votes,other_votes,certified,source_url,retrieved_on`.
Use `us_house` or `us_senate`; leave `district_num` blank for Senate, use 0 for an at-large
House seat. Votes must be nonnegative integers. Preserve unofficial versus certified status.
Supply optional `winner_party` (`DEMOCRAT`, `REPUBLICAN`, `OTHER`) from the official result
whenever a third party could have won. Aggregate `other_votes` cannot identify one candidate;
the actual-results builder refuses a certified possible third-party winner without that field.
The scorer uses explicit `actual_dem_win` for winner/chamber metrics while retaining two-party
share for vote-share error. Independent party identity is not inferred from a two-party share.
Use a complete status report per capture where feasible; partial snapshots carry unchanged
races forward. Do not silently substitute a same-state regular race for a special election.
The current schema refuses simultaneous same-office statewide races; extend its race keys
before capturing a future cycle with two Senate contests in the same state.

Optional fields are `election_round` (`general`, `first_round`, `runoff`, `rcv_final`)
and boolean `outcome_resolved`. Both are **required for Louisiana House**. Louisiana
holds its first House round November 3 and, where necessary, a final round December 12;
its Senate election is an ordinary November general. A certified first-round tally with
an unresolved runoff has `outcome_resolved=False` and remains unscoreable. Do not merge
rounds or interpret a nomination-primary winner as an elected member.
[Louisiana SOS election types](https://www.sos.la.gov/elections-voting/types-of-elections)

All ledger dates (`retrieved_on`, `observed_on`, `--as-of`) use **UTC calendar days**.
For example, November 3 at 22:00 Vancouver is November 4 UTC. Raw retrieval timestamps
keep their explicit offsets; the preservation command derives `retrieved_on` in UTC.
This avoids silently comparing a UTC timestamp to a local midnight cutoff.

```bash
.venv/bin/python -m election_prediction.build_results_2026 capture \
  --snapshot /absolute/path/official-compiled.csv --observed-on 2026-11-04 \
  --source-evidence /absolute/path/release.source.json
.venv/bin/python -m election_prediction.build_results_2026 actual \
  --as-of 2026-11-20 --out data/gold/actual_2026_asof_2026-11-20.csv
python -m election_prediction.evaluation.score_preregistration \
  --actual data/gold/actual_2026_asof_2026-11-20.csv --as-of 2026-11-20 \
  --no-void-geographies --out reports/scored_2026_asof_2026-11-20.json
python scripts/dry_run_scoring.py
```

The scorer takes the sealed JSON and actual CSV, refuses to overwrite a score report, and
requires either an explicit no-void assertion or `--void-geographies` with a sourced JSON
mapping. Use its `--as-of` cutoff. Never regenerate or edit
`reports/preregistration_2026-11-03.{json,md}` or its `_seats.csv` sibling.

## Interpretation

`certified_on` is the **first observation of certified status in our snapshots**, not an
asserted legal certification date. Missing observations cannot be reconstructed retrospectively.
If official certification is revoked or the outcome becomes unresolved, it is unscoreable
from that observation onward. A later recertification starts a new episode; earlier as-of
replays retain the state that was observed then. Certified vote revisions within an
uninterrupted episode retain its first-observed certification date.
The as-of ledger excludes later vote revisions as well as later certifications. Snapshots
are append-only and cannot overwrite another capture on the same date; the present CLI
supports daily rather than intraday observations.

Per-seat scores may be reported for the certified subset, with denominators and omissions.
House chamber error, interval coverage and the registered failure condition are **not
evaluable until every registered House seat has a scoreable outcome**. A partial count must
not produce a reassuring `false` failure flag. Senate chamber intervals are not part of the
original sealed chamber scoring rule. Missing-party historical fixtures can remain unscoreable.

The rehearsal covers both offices, delayed certification, an earlier as-of replay and seal
verification. Its numerical scores compare historical outcomes with a 2026 forecast and are
not evidence of forecasting quality.

## Continuous Integration

`.github/workflows/quality.yml` runs lint, formatting, mypy, unit/integration tests and the
privacy guard on hosted runners. Live-data reconciliation is an explicit manual job on a
self-hosted runner labeled `elections-data`, with repository variable `ELECTION_DATA_ROOT`
pointing at registered local data. That runner and variable still need operator setup.
The October 21 [runner handoff](live-data-ci-setup.md) specifies isolation, read-only
data outside the disposable checkout, default-branch-only manual dispatch and the
read-only `scripts/check_live_runner.py` preflight. No runner deployment is claimed.
`EP_REQUIRE_LIVE_DATA=1` makes missing raw inputs fail rather than skip; known quarantined
source defects remain explicitly documented exclusions, not silently repaired datasets.

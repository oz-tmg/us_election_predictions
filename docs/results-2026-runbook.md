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

**Measured 2026-10-29: the automation fires at about 22:00 UTC, not 22:00 Vancouver.**
Its five readiness reports (October 25-29) are stamped 22:06, 22:01, 21:57, 21:59 and
22:02 UTC — about 15:00 Vancouver every day. The saved "22:00 America/Vancouver" setting
is not what executes. Consequences, unless it is fixed in the app:

- November 3 run: about 15:00 Vancouver, before any polls close. Readiness only.
- November 4 run: about 15:00 Vancouver on November 4 (UTC day November 4). It sees the
  morning-after unofficial totals, not the election-night release.
- The election-night release is therefore **manual**: run the capture on the night of
  November 3 Vancouver (after 05:00 UTC November 4 the UTC day is already November 4, so
  that manual capture and the automated 22:00 UTC run fall on the same UTC day and the
  ledger accepts only one; preserve both raw releases, capture the evening one, and keep
  the afternoon one as preserved evidence only).
- Fix options in the app: set the time to 05:00 UTC (22:00 Vancouver, since B.C. stays at
  UTC-7), or keep 22:00 UTC and treat election night as manual. Confirm with the next
  report's timestamp, not the saved configuration.

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

## Scored Comparison Set (frozen 2026-10-29)

`reports/comparison_set_2026-11-03.json` fixes which runs are scored and records each
file's SHA-256 and the commit that holds it:

| Run | Role |
|---|---|
| `preregistration_2026-11-03` | The scored holdout, sealed 2026-09-30 |
| `refresh_2026-10-22` | Last refresh before the Senate specification change |
| `refresh_2026-10-29` | Final pre-election refresh (`v1_open_seat_holder`) |
| `scenario_south_texas_2026-10-29` | Scenario; scored for information only, not a forecast |

No further refresh joins this set. A rerun is allowed only to correct a registered data or
code defect: new dated directory, labelled a correction with the defect named, scored beside
(never instead of) the runs above. Every run is scored on the same certified returns and
`as_of` dates with every assumption reported; choosing the best run or assumption afterwards
is forking paths. The Texas poll cross-check is reported beside them for information.

## Rehearsal Log

**2026-10-29 (Vancouver; 2026-10-30 UTC).** Operator path rehearsed outside production,
in a scratch directory: a real historical aggregate file (Virginia 2024 certified House and
Senate, 12 seats, labelled with its true MEDSL provenance rather than an official state URL)
was preserved with `results_sources.preserve_source`, captured with `--source-evidence`
(observed on the UTC day, 2026-10-30), a same-day repeat was refused as designed, and
`actual` assembled 12/12 certified seats. `scripts/dry_run_scoring.py` passed end to end;
the chamber failure condition correctly reported `not_evaluable_incomplete_chamber`. The
seal verified unchanged and no production canvass directory was created.

Not rehearsed, and still the main risk: **state extraction**. All 50 extraction paths are
`manual_review_pending`, and the October 28 probe could read neither listed landing for 11
states (AK, AZ, ME, MA, MI, MO, MT, NH, OH, TN, WI). Certification status must be observed
as it happens; vote extraction for certified results can follow later from the preserved
releases.

## State Extraction: the 11 Probe-Failure States (tested 2026-10-30)

`scripts/test_state_extraction.py` ran each state's parser (`data/state_parsers.py`) on
its own 2024 official release and reconciled race by race with certified 2024 returns
(`reports/extraction_rehearsal_2026-10-30/`). The catalog records the outcome in
`extraction_status` (`parser_tested_2024` only on a passed reconciliation) and
`download_access`.

| State | 2024 test | Access from this machine | Election-week plan |
|---|---|---|---|
| MA | 10/10 exact | automated (electionstats.state.ma.us) | Certified per-contest CSVs post after certification; parse with `MA`. |
| WI | 9/9 exact | automated (files under /sites/default/files) | WEC canvass workbook after certification; parse with `WI`. |
| MO | 9/9 exact | automated with the honest research UA | Certified canvass PDF after certification; parse with `MO`. |
| MT | 3/3 exact | automated (export page) | Export is labelled unofficial; certification from the canvass document. |
| MI | not run | **blocked** (site refuses connections; Akamai 403) | Manual download from a browser; no 2024 file URL confirmed. |
| NH | not run | **blocked** (Akamai 403) | Manual; town-level Excel per district must be summed. |
| OH | not run | **blocked** (Cloudflare challenge) | Manual: official `statewide-race-summary.xlsx`; layout uninspected. |
| TN | not run | **blocked** (CloudFront; may be geographic) | Manual `…AllbyPrecinct.xlsx`; retest from a U.S. network. |
| AK | not run | **blocked** (AWS WAF captcha) | Manual PDFs; RCV: record first and final rounds separately. |
| AZ | not run | **blocked** (Cloudflare challenge) | Manual statewide canvass PDF (URL unconfirmed). |
| ME | not run | **blocked** (CloudFront) | Manual town-level Excel; CD2 RCV rounds separately. |

What this does and does not settle: four states now have a parser proven against a past
certified result, so their certified 2026 releases can be parsed rather than retyped. The
other seven are blocked to automated clients by the sites themselves (a separate U.S.
fetcher was refused too), so their releases must be saved by hand from a browser and
preserved with `preserve-source`. For those states, write and test a parser on the first
hand-saved file before relying on it. No state here publishes a statewide election-night
feed that we have tested, so election-night numbers for all eleven are manual; the
parsers matter for the certified releases, which is what is scored.

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

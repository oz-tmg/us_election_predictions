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

## Daily Capture: One Command (from 2026-11-12)

```bash
python scripts/capture_daily.py --dry-run     # fetch, preserve to a temp dir, extract, validate
python scripts/capture_daily.py               # write today's UTC observation + reports/captures/
python scripts/capture_daily.py --certified NC=https://<certification evidence URL>
```

- Covers every state with a registered fetcher (`data/state_fetchers.py` and
  `data/state_layouts/`): its release downloads with the honest research client **and**
  its parser has a recorded check. As of 2026-11-13, 24 states, 209 seats.
  - `parser_tested_2024` (18 states, 131 seats): the parser that reads 2026 reproduced
    2024 certified results (exactly, except Colorado CD1 within tolerance). AR, CO, DE,
    GA, HI, IN, LA, MD, MN, MT, NC, PA, SC, UT, VA, VT, WV, WY.
  - `parser_cross_checked_2026` (6 states, 78 seats): the state changed its layout, so
    the 2026 parser cannot be run on certified data. The 2024-layout parser reproduced
    certified 2024 exactly, and the 2026 parser matched, race by race, a summary the
    state publishes separately (`reports/extraction_cross_check_2026-11-13/`). This is
    weaker: treat these seats' counts with that in mind, and re-run
    `scripts/record_cross_checks.py` if a state changes its page. AL, CA, ID, ND, NE, WA.
  - Each capture report names every state's `parser_status`; a state whose catalog row
    is still `manual_review_pending` is refused.

  Other states are manual (preserve-source + capture) and must be compiled into the
  **same** snapshot, because the ledger takes one observation per UTC day: add their
  rows and evidence to one `build_results_2026 capture` call, or add their fetchers first.

  | Status (2026-11-13) | States |
  |---|---|
  | Parser tested, fetcher pending the certified release | MA, WI, MO (certified files post after certification) |
  | Blocked to automated clients (manual browser download) | AK, AZ, FL, KS, KY, ME, MI, NH, NM, NV, NY, OH, OK, RI, TN; PA from 2026-11-20 (the whole site now answers the research client with an Incapsula challenge, HTTP 403; its November 15 rows stand until a manual download) |
  | 2024 release unavailable to test against | IA, OR, TX (2024 blocked or timed out) |
  | 2026 release not yet published | IL (after the December canvass), MS, NJ |
  | Other | CT (lookup file holds candidate addresses; manual), SD (no party labels in the export) |

  Louisiana House rows are first rounds; CD5 and CD6 are unresolved until the
  December 12 runoff. The Louisiana fetcher reads the portal's election list on every
  run and adds the runoff's race files on or after its election day, once posted.
  Posting an election in advance can expose empty templates, not returns. The
  November 20 safeguard skips future elections; check the first capture after
  December 12 before allowing runoff rows to replace first-round tallies.
- The run refuses before fetching if today's UTC slot is taken, refuses a state whose
  races do not match the frozen universe (`reports/refresh_2026-10-29/projection_seats.csv`),
  and reports a failing state while still capturing the rest (exit 1 if any failed).
- **Certification is never inferred.** `--certified STATE=URL` is the operator's
  attestation, with the URL of the certification evidence; it is refused if the release
  labels itself unofficial (Montana's export always does: certify MT from its canvass).
- **An attestation carries forward.** A captured `--certified` state is written to
  `data/reference/certifications_2026.csv` and applied to every later run, so a plain
  `python scripts/capture_daily.py` keeps those seats certified. Without this the ledger
  would read the next plain capture as a revocation. Commit the file with the capture
  index. To revoke, delete the state's row and give the reason in the commit message.
- **A recount keeps one seat unresolved.** A state can certify while one contest is
  being recounted. List that seat in `data/reference/unresolved_seats_2026.csv`
  (state, office, district, reason, evidence URL) and it is captured with
  `outcome_resolved=False` and no winner, so certifying the state does not make it
  scoreable. Remove the row when the recount is final.
- Each run writes `reports/captures/capture_<date>.json` (seats, certification flags and
  evidence URLs, release checksums, failures): commit it, as the index of the git-ignored
  ledger, and add a line to the Capture Log below.

### Scheduled run (from 2026-11-20)

`scripts/run_scheduled_capture.sh` is run once a day by a launchd agent on the operator's
Mac (`deploy/launchd/ca.savepointanalytics.elections-capture.plist`, installed under
`~/Library/LaunchAgents/`), at 22:05 by the Mac's clock, which is 05:05 UTC. It runs
`capture_daily.py` and then the interim scorecard for that UTC day, and logs to
`~/Library/Logs/elections-capture/capture_<UTC date>.log`.

- If the day's observation already exists it does nothing, so it coexists with a manual
  capture or the older heartbeat job: whoever runs first takes the day.
- It commits and pushes nothing. Review and commit `reports/captures/`,
  `reports/scorecards/` and any change to the two reference files above.
- It marks no new certification: that still needs `--certified STATE=URL` by hand, on a
  day whose slot is still free (run the capture by hand before 05:05 UTC).
- The Mac must be awake; a run missed while asleep fires at the next wake. Check the log
  after each morning. Remove with
  `launchctl bootout gui/$(id -u)/ca.savepointanalytics.elections-capture`.

## Interim Scorecards and the Results Page

```bash
python scripts/interim_scorecard.py --as-of 2026-11-20      # certified seats only
ep-export-dashboard results "data/raw/source=state_canvass/dataset=us_house_2026" --as-of 2026-11-20
```

- `interim_scorecard.py` scores all four frozen runs (seal, both refreshes, scenario) with
  the registered scorer on the as-of ledger. The seal is verified by digest and the other
  runs by the comparison set's checksums. Every assumption is reported; nothing is
  selected. Only **certified, resolved** seats count; chamber error and the failure
  condition stay `not_evaluable` until all 435 House seats are scoreable. Output goes to
  `reports/scorecards/scorecard_asof_<date>.{json,md}` and is never overwritten.
- A seat becomes certified in the ledger only through `capture_daily.py --certified
  STATE=<evidence URL>`. Dates to expect are in `data/reference/certification_calendar_2026.csv`.
- `ep-export-dashboard results` writes the vault's Results bundle: every observed seat
  with its status (certified or unofficial) beside the selected run. It displays; it
  does not score.

## Capture Log

The ledger lives in the git-ignored data lake; this log is its committed index.

| Observed (UTC) | States | Seats | Certified | Source evidence | Notes |
|---|---|---:|---:|---|---|
| 2026-11-03 to 2026-11-11 | none | 0 | 0 | none | **Gap.** The working checkout was on `post-poll-closing-updates`, cut from an unpulled pre-October `main`; the Nov 5 automation refused to capture without the evidence safeguards (`reports/results_capture_blocked_2026-11-05T192029Z.md`). Checkout restored to `origin/main` 2026-11-12. Certification first observed after this date cannot be backdated. |
| 2026-11-12 | MT, NC | 18 | 0 | `data/raw/source=state_canvass_evidence/state={MT,NC}/retrieved=20261112T06…/` | MT statewide export (labelled unofficial, 728/728 precincts); NC `results_pct_20261103.zip` (last-modified 2026-11-11 22:21 UTC, 100/100 counties, uncertified). Both parsers reproduce 2024 certified exactly. `winner_party` recorded for every row (MT Senate has an independent in second). |
| 2026-11-13 | MT, NC | 18 | 0 | `data/raw/source=state_canvass_evidence/state={MT,NC}/retrieved=20261113T2208…/` | Fresh official aggregate releases and NC unofficial-status page preserved with the module CLI; appended with matching source evidence. Historical parser replay and stored-byte validation passed. Counts revised in 14 NC and two MT contests versus the November 12 daily snapshot; no leading-party changes. Forty-eight states remain missing. See `reports/results_capture_2026-11-13T220413Z.md`. |
| 2026-11-14 | AL, AR, CA, CO, DE, GA, HI, ID, IN, LA, MD, MN, MT, NC, ND, NE, PA, SC, UT, VA, VT, WA, WV, WY | 209 | 0 | `data/raw/source=state_canvass_evidence/state=<ST>/retrieved=20261114T00…/`; index `reports/captures/capture_2026-11-14.json` | First `capture_daily.py` run (00:05 UTC), no failures. 18 states at `parser_tested_2024`, 6 (AL, CA, ID, ND, NE, WA) at the weaker `parser_cross_checked_2026`. Releases label themselves: 12 unofficial, 10 no statement, 2 official (VT, WY). No state marked certified: no operator attestation was given. LA CD5 and CD6 are first rounds. Interim scorecard `reports/scorecards/scorecard_asof_2026-11-14.md`: 0 scoreable seats. Re-verified by the November 15 scheduled run (schema, compiled hash and all 37 source receipts), which did not rewrite it. |
| 2026-11-15 | 24 states | 209 | 3 | 40 receipts in `snapshot=2026-11-15.manifest.json` | Fresh releases preserved and captured with the module CLI. VT House and WY House/Senate accepted as certified from preserved authority evidence, first observed November 15 UTC. Only those three resolved contests scored, across every frozen run/assumption. Twenty-six states remain missing; LA-05/06 first rounds unresolved. See `reports/results_capture_2026-11-15T015048Z.md` and `reports/captures/capture_2026-11-15.json`. |
| 2026-11-16 to 2026-11-19 | none | 0 | 0 | none | **Gap.** No observation was captured on these four UTC days; the scheduled job did not run after November 15. They cannot be backdated; a certification first seen on a later day is recorded on that day. |
| 2026-11-20 | 23 states (the November 14 list without PA) | 192 | 3 | index `reports/captures/capture_2026-11-20.json` | `capture_daily.py` at 19:46 UTC. Pennsylvania's Report Center returned HTTP 403 to the research client and was left out; its November 15 rows stand. VT House and WY House/Senate stay certified, carried forward from `data/reference/certifications_2026.csv`. Releases label themselves: 8 unofficial, 9 no statement, 6 official (AR, GA, ID, ND, VT, WY). No new state was marked certified: an official label is not an attestation. **Flawed rows:** LA-05 and LA-06 were recorded as zero-vote December 12 runoff templates instead of their November first rounds (fetcher fault, fixed the same day). Both seats were unresolved either way; the next capture restores the first-round tallies. |

One observation per UTC day: a capture early in a UTC day takes that day's slot, so
add states to the same compiled snapshot before capturing, never in a second run.

The November 15 acquisition reused the reviewed capture implementation at commit
`5845f08680f410fc48cfcea1adb91e517cac641e` from the separate `-capture-run` worktree,
read-only; preservation and the production append ran through the main checkout's
module CLI. Its catalog distinguishes historical parser tests from weaker 2026
summary cross-checks. The main checkout's catalog/code were not silently replaced
or promoted. The capture JSON records the implementation and source catalog used.
Integrating that broader implementation into the main automation checkout remains
operator-reviewed work; no branch switch or merge is implied by this capture.

That integration was done on 2026-11-16: the 24-state capture code, its catalog and the
scheduled run's November 12 to 15 reports are now in this checkout, so later captures
run `scripts/capture_daily.py` here and no longer need the `-capture-run` worktree.

The later November 15 UTC heartbeat preserved a further 40 intraday source receipts
for the same 24 states, including refreshed VT/WY certification context. Today's
compiled observation and scores were not overwritten: no new certification,
leading-party, coverage or Louisiana resolution change was verified. Four
uncertified IN/MD contests had revised counts. See
`reports/captures/intraday_2026-11-15T220056Z.json` and
`reports/results_intraday_2026-11-15T220056Z.md`; these are not a second daily capture.

**November 20 intraday review (trigger 19:39:52 UTC).** A separate capture completed
during the review and took today's slot. Its snapshot, manifest and scorecard were
verified and left unchanged. A further **57 source receipts** were preserved with the
module CLI, including authority certification statements, publisher flags and two
empty future runoff templates. The full evidence index and missing-state checks are
in `reports/captures/intraday_2026-11-20T193952Z.json`.

The review verified new certification evidence for **SC, MN and ND**, but these
certifications are **not yet recorded in a daily snapshot**. Recheck and include them
on the next actual UTC observation day; never backdate their ledger certification to
this evidence review or the authority's earlier board date. Minnesota's authority
explicitly reports a requested recount in **U.S. House District 1**, starting November
30, with the board reconvening December 8 if necessary. Compile that seat with
`outcome_resolved=False` while the recount remains pending. A blanket Minnesota
`--certified` invocation without that per-seat flag would incorrectly make it
scoreable. SC's authority also describes its recount returns as official; ND's
announced legislative District 41 recount concerns a state office, not its federal
at-large House seat. AR/GA/ID/LA publisher official flags were preserved separately
and were not treated as additional certification attestations.

**Two Louisiana rows in the already-saved November 20 snapshot require a later dated
correction.** The earlier capture replaced LA-05/06 November counts with zero-filled
December 12 templates. Those zeros are not observed runoff results. Both seats remain
uncertified and unscoreable, so the three scored contests are unaffected. The fetcher
now skips future elections; replay against today's preserved responses restores seven
November contests, with LA-05/06 still unresolved first rounds. Two regression cases
verify that future templates do not erase those counts and that actual runoff-day
returns can subsequently replace them. Preserve the flawed daily observation as
history and restore the verified November rows in the next dated capture.

Pennsylvania's aggregate export returned HTTP 403, leaving 17 November 15 contests
stale; the ledger still covers 209 contests in 24 states, with **26 states missing**.
Reachable landing pages for missing states were not promoted to validated feeds.
Today's existing four-run scorecard still scores only VT House and WY House/Senate
under all five assumptions; its primary scores were independently reproduced from
`data/gold/actual_2026_certified_asof_2026-11-20.csv`. Chamber evaluation remains
incomplete. Only the September registration is sealed: other scorecard runtime
digest checks do not create historical seals; their original files were verified
against the frozen comparison manifest. Ninety-two focused tests passed before the
guard change, 32 capture/extraction tests passed with it, and the two final regression
cases and changed-file lint/format checks passed. Sealed/frozen files and previous
observations remain unchanged. AGENTS.md and PROJECT_CONTEXT.md remain absent.

This heartbeat arrived at **12:39 Vancouver**, not the intended 22:00. Scheduler
execution remains unverified and the manual fallback remains necessary. No schedule
change, new certification append, overwrite, merge, commit or unattended complete
capture is claimed by this intraday review.

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

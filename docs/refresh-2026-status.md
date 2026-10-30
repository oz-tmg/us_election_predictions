# October 25 Manual Polling Research Update

**Later October 25:** the missing 2024 Senate CSV is now acquired directly from the
November 29, 2024 Wayback capture (2,628 answer rows, 1,142 questions). The user's newer
March 2025 capture instead contained early hypothetical 2026 matchups and was not
admitted. The new final study, `reports/polling_lean_2026-10-25_senate2024_final/README.md`,
adds 18 eligible 2024 Senate races, giving 241 Senate held-out races across ten cycles;
House remains 420 across seven. Both offices remain unpromoted. The file-download gap
is filled, not the publication/geography/fundamentals-vintage gates. The earlier
same-day status below is retained as history. Consolidated source inventory and
granularity: [Polling Data Guide](polling-data-guide.md).

Current research: `reports/polling_lean_2026-10-25_final/README.md`. Four user-supplied
CSV originals are preserved with exact Wayback URLs and SHA-256; browser retrieval
times are unknown, distinct from archive dates and actual project ingestion. A new
candidate-answer adapter replaces overlapping ratings office-cycles rather than
double counting surveys or re-admitting date-excluded questions. The historical study
adds 30 polled 2024 House races, not full-chamber coverage. Senate research metrics
improve, while House proxy metrics fail promotion. Both retain publication/feature
vintage gates and remain unpromoted; September seal and live parameters are unchanged.

**Still needed:** a 2024-cycle `senate_polls.csv`. The supplied file's exact capture is
November 2, 2021, with fieldwork ending October 27, 2021; it does not supply 2024 polls.
The other three files do not need replacement. Exact inventory and broader remaining
gates: [polling-lean downloads](polling-lean-downloads.md).

# October 23 Polling-Lean Research (Historical)

Separate research tooling and chronological three-pipeline experiment:
`reports/polling_lean_2026-10-23_final/README.md`. No changes to the September seal,
2026 source compilations, forecast parameters or estimator promotion. The 1998-2022
ratings archive supports a retrospective Senate diagnostic; the House proxy is not the
article's presidential district lean. Missing publication/feature vintages and 2024
poll coverage remain gates. Four candidate-poll download endpoints returned HTML;
exact manual file request: [polling-lean downloads](polling-lean-downloads.md).
No numerical 2026 race-poll correction or complete chamber evaluation is claimed.

# October 22 Pre-Election Implementation

Latest internal comparison: [October 22](../reports/refresh_2026-10-22/README.md).
Eight-step execution and remaining gates:
[implementation report](../reports/refresh_2026-10-22/IMPLEMENTATION.md),
[acceptance checklist](pre-election-2026-checklist.md).

- Candidacy evidence increased from 182 to **203/470**: 187 House and 16 Senate;
  **267 unknown**, including 19 Senate contests. The ten previously flagged identities
  were resolved by explicit reviewed pairs, including the distinct Trever/Troy finding.
  New Delaware/New Jersey identity gaps remain; a blocked alias source is not accepted.
- Fifty-state official-source landing inventory and primary/fallback probes are saved.
  Thirty primary URLs were reachable; ten states had neither landing reachable by the
  automated client. All still require reviewed November extraction paths. These checks
  are not general-election results or proof of complete capture readiness.
- Capture now preserves raw source evidence, enforces checksums, uses explicit UTC dates,
  handles certification revocation/recertification and blocks unresolved Louisiana House
  first rounds from scoring. Same-day snapshots remain append-only; interrupted writes
  cannot publish a partial snapshot. Module CLI and installed entry point are available.
- Official original North Carolina precinct returns reconcile exactly in **both 2020 and
  2024**. The improved 2020 placement and 14-district 2020->2022 diagnostic pass; 2024
  polygons still contain ambiguous block assignments. Neither live transfer is admitted.
  All **135 redrawn-seat fallbacks** remain. Florida's
  official replacement ZIP returned HTTP 403; Kansas still falls short 17 D/27 R votes.
- Two original national vote-intention polls were re-acquired; no newer eligible release
  was established from the reviewed source catalogs. Quinnipiac's newer national release
  asks preferred chamber control, a distinct construct, and is not added to this average.
  Macro/poll diagnostics and measured correlation experiments remain unpromoted.
- Florida's two April 2025 congressional specials were reverified against the actual
  federal-results table with all D/R/other totals unchanged. Source URLs/retrieval dates
  were updated; other specials retain their actual earlier verification dates.
- The automation prompt and explicit Vancouver timezone recurrence were saved, but
  **the next actual 22:00 trigger is still unverified**. B.C. remains UTC-7 this November,
  unlike U.S. Pacific winter time. Manual fallback, operator runner setup and the
  November 1-2 freeze remain open. See the runbook and `scheduler_audit.json`.

The September 30 seal and forecast parameters are unchanged. No production 2026
general-election capture, public publication, commit or CI deployment is claimed.

## October 21 Implementation and Remaining Work

Current report: [October 21 comparison](../reports/refresh_2026-10-21/README.md).
The eight requested steps have substantial implementation, but **are not all complete**.
Acquisition, passing code tests and experimental estimates are not source acceptance
or model promotion. The September 30 seal is untouched.

| Step | Delivered October 21 | Still Required |
|---|---|---|
| 1. Candidacies/maps | House Clerk 435-seat roster; official CA/TX/NC/FL/NY/MD/MI ballots; 182 verified candidacies (169 House, 13 Senate); moving-incumbent indicators and distinct-given-name guard | 288 unknown, including ten identity cases; remaining states and court-order review. Trever Nehls is not Troy Nehls. |
| 2. Transfers | Official Census CD120 block equivalencies for nine redrawn states; eight additional states audited historically and live | None newly admitted: CA lacks a VTD member; AL/OH/TN placement poor, FL/NC incomplete, LA historical source absent/current partial, UT loses to fallback. 135 seats still fall back; validated Texas 38 retained. |
| 3. Source repairs | Official Kansas five-sheet workbook parsed with explicit layouts, suppressions and all 105 counties; strict certified-total comparison | Short 17 D and 27 R votes, so unadmitted. No invented balancing or suppression reversal. IN/LA/OK/NJ defects remain. County completeness does not establish district assignment. |
| 4. Fresh evidence | Immutable dated FEC pull, historical crosswalk retained; GA-13 admitted after count verification; GA-14 URL corrected and first-round legislative-vote contamination fixed; NJ counts verified but signal excluded for baseline quality; dated projection/seal comparison | Other special counts retain September retrieval dates. Finish source review and precinct repairs. No real November general outcomes yet. |
| 5. Macro | Actual ALFRED income/unemployment/CPI vintages; fixed cutoff and chronological alternatives/benchmarks | Income has only two held-out cycles, loses to both benchmarks and covers 0/2. Not promoted; earlier income needs a verified archive. |
| 6. Generic ballot | Two cited original live releases; publication-aware national schema/average; earlier-cycle shrunken effect code; eleven historical publisher-average diagnostics | Poll-level archive malformed; publisher averages rebuilt in 2020 do not establish real-time performance or house effects. Thin coverage; not promoted. |
| 7. Chamber validation | Five complete-435-seat held-out folds (2014/2016/2020/2022/2024), including missing-share fallbacks; canonical winners exclude ballot-status artifacts; control proper scores and intervals | Retrospective ballot availability/map vintages still block live promotion; historical independent/caucus and incomplete/duplicate cycles remain excluded. Senate 100-seat replay blocked. Presidential OLS loses to persistence. |
| 8. Operations | Intake CI dependencies; trusted-branch self-hosted dispatch guard and data preflight; daily 22:00 Vancouver thread follow-up installed through certification/runoffs, ending January 4 | Runner needs operator approval/registration token; GitHub CLI absent. Automation does not guarantee complete capture. Keep computer/app running and review initial runs. |

Artifacts: `ballot_coverage.json`, `transfers/audit.json`, `kansas_official_repair.json`,
`special_source_refresh.json`, `economic_cross_check.json`, `generic_ballot_cross_check.json`,
`full_chamber_evaluation.json` in `reports/refresh_2026-10-21/`.
Methods and failed gates: [cross-check model card](../reports/model_cards/cross_checks_2026-10-21.md).

Reproduce with registered cached snapshots and `.[dev,geo,model,intake]`:

```bash
python -m election_prediction.build_ballots --as-of 2026-10-21
python -m election_prediction.build_fec --from-cycle 2026 --refresh
python -m election_prediction.build_economics --as-of 2026-10-21
python -m election_prediction.build_generic_ballot --as-of 2026-10-21
python scripts/audit_map_transfers.py
python scripts/evaluate_full_chamber.py
python scripts/refresh_2026.py --as-of 2026-10-21
python scripts/dry_run_scoring.py
```

`repair_official_sources.py` intentionally fails the Kansas discrepancy.
`refresh_special_sources.py` is a one-shot dated review and refuses to overwrite its
existing source-review report. No blanket source waiver was added. The earlier 192
candidacies used initial-only matching; ten unresolved cases were removed before the
final projection. Final verified coverage is **182**, not 192.

## Historical October 18 Snapshot

Owner/reviewer: Alex Oswald. Internal research, not a published forecast. The dated
[comparison report](../reports/refresh_2026-10-18/README.md) and adjacent JSON/CSV artifacts
were the October 18 results; September reports and the sealed November 3 registration are
historical artifacts and remain unchanged.

## Five Workstreams

| Workstream | Delivered | Remaining acceptance boundary |
|---|---|---|
| Senate coverage and candidacy | Official 100-seat roster; class-II regular contests plus FL/OH specials; 35 modeled races and 65 holdovers; caucus reconciles 47/53; name-safe filing join; ten sourced retirement/open-seat decisions and two ballot confirmations | Only 12 Senate candidacies verified; 23 Senate and all 435 House candidacies remain unknown. Filing is not nomination evidence. |
| Results capture and scoring | Null-district Senate certification fixed; as-of vote replay; integer/boolean validation; append-only snapshots; partial-chamber failure condition suppressed; explicit third-party winner handling; executable scorer; historical House/Senate rehearsal | Operator must capture official releases beginning election night. Daily snapshots cannot recover an unobserved certification transition. See the [runbook](results-2026-runbook.md). |
| Quality and honest backtests | Formatting/mypy repaired; hosted quality workflow; opt-in live-data workflow; forward-only evaluation excludes same-year Senate presidential truth, future national truth and single-vintage ACS | Live runner needs setup. Historical candidates and boundaries are not archived forecast-date vintages; this benchmark is stricter than LOO, not a complete real-time historical replay. Presidential benchmark loses to persistence. |
| Refresh and attribution | Panels rebuilt from corrected live cached returns; dated scenario/seal comparison; per-prior national reference fixed; special baselines refreshed only where validated; explicit national-input definitions and input hashes | No new generic-ballot series, fresh FEC pull or newly certified general-election results. Special counts remain the September compilation, not reverified October results. NJ turnout denominator removed; its older share remains a documented weak input. |
| Geography and shared error | Public TLC precinct maps; all 38 Texas 2024 priors transferred onto PLANC2333; third-state 2020->2022 transfer backtest; measured state-specific transfer sigma; held-out correlation experiment | 135 redrawn House seats still fall back. Candidate correlation split is not promoted from incomplete-seat evidence. Other state source defects and current map/legal-status rechecks remain open. |

## Geographic Evidence

Texas live transfer places all 11,228,537 two-party presidential votes, with 9,712 matched
precincts and 38 districts. The independent historical transfer places all 11,146,541 votes;
294 unmatched precinct keys are explicitly county-allocated, not declared exact matches.
Its vote-share MAE is 0.0838 versus 0.2129 for the state-lean fallback. The live projection
uses the **full measured transfer sigma 0.1223**, not the more flattering geography-only
diagnostic. This includes cross-office/candidate noise and is deliberately conservative.
Population weighting is an assumption, not voter-level geography. No partisan map drawing
or optimization is performed. Source hashes and confidence distributions accompany the
registered prior; wrong plans, stale elections, partial coverage and changed inputs fail.

Current map status is inherited from `house_plan_versions.csv`; geometric placement does
not establish that no later court order exists. Reverify legal status before publication.

## Source Gaps and Freshness

- Indiana 2020 (53/92 counties), Louisiana 2020 (missing), Louisiana 2024 (partial),
  Kansas 2024 (missing), Oklahoma 2024 (OK-03 lookup missing), New Jersey 2024 (mixed-level
  duplicate totals) and Indiana 2024 (inflated totals) remain quarantined/flagged.
- Harvard's latest metadata API returned HTTP 403 on October 18 both inside and outside the
  sandbox. Its public 2024 landing page still shows V1.0. No corrected file was acquired or
  substituted. Do not call repeated downloads of the same source a repair.
- Kansas publishes a potential [official presidential precinct workbook](https://sos.ks.gov/elections/24elec/2024-General-Election-President-Precinct-Level-Results.xlsx).
  The [official legislative testimony describing its layout](https://www.kslegislature.gov/li/b2025_26/committees/ctte_spc_2025_on_cmpgn_contrib_and_trnsprncy_1/documents/testimony/20251015_04.pdf)
  identifies inconsistent layouts for the four largest counties. Register/review terms,
  use an XLSX library and explicit per-sheet transforms, then reconcile all 105 counties
  against certified totals before promoting it. It has not been ingested.
- GA-13's July 28 election was mislabeled a runoff, with a nonexistent April 22 first-round
  instruction. The [official call](https://sos.ga.gov/news/call-special-election-congressional-district-13)
  confirms July 28 first round/August 25 runoff. Metadata is corrected; existing counts stay
  excluded pending verification. This does not change the inclusion rule to fit an outcome.
- Polling permission is source-specific. No YouGov ingestion or automatic scraping was
  performed; generic-ballot evidence remains an open source/evaluation task.

## Macroeconomic Cross-Check

NE-004 remains a separate modeling task, not a replacement for the sensitivity band.
The source review supports this narrow starting specification:

| Input | Primary source | Treatment |
|---|---|---|
| Real disposable income per capita growth | [BEA Personal Income](https://www.bea.gov/data/income-saving/personal-income) | First growth term; real/per-capita, observed before cutoff, not nominal income |
| National/state unemployment change | [BLS LAUS](https://www.bls.gov/lau/) | Alternative specification and regional diagnostic, not another unrestricted fitted term |
| Inflation | [BLS CPI](https://www.bls.gov/cpi/) | Separate robustness specification; avoid adding correlated predictors until sample size supports them |
| Historical information sets | [FRED/ALFRED real-time periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html) | Set real-time start/end explicitly; today's revised historical values are not historical forecast inputs |

Before any pull, register exact series, terms, transformations, publication lag, vintage
cutoff and review owner. Save observation date, release date, vintage date and retrieval
date separately. Fit incumbent-party national share with one growth term, president on
ballot and consecutive terms; map to Democratic share only at the end. Evaluate whole
cycles chronologically against persistence and midterm-only benchmarks, with interval
coverage and proper scores. Midterm output is a cross-check with honest residual sigma,
not independent evidence to multiply into the specials signal. No macro series has yet
been acquired or fitted in this change.

## Reproduction

Use the registered cached live data and existing environment; a clean checkout also needs
those raw snapshots/manifest checksums and the P0/CD-baseline builds. No synthetic fallback
was used for this refresh. Large raw/Parquet artifacts remain in the ignored data lake.

```bash
python scripts/register_transfer_snapshots.py
python scripts/refresh_2026.py --as-of 2026-10-18
python scripts/dry_run_scoring.py
ruff check .
ruff format --check .
mypy src/election_prediction
pytest -q
python pipelines/validate/check_no_restricted_data.py --all
```

The transfer CLI accepts registered public precinct geometry via `--precinct-boundaries`
and `--precinct-column CNTYVTD`, with the 2024 old plan supplied separately via `--old-plan`.
Use the paths recorded in the dated transfer JSON reports, `--district-column District`
for PLANC2333, and `--backtest 2022` for the historical case. The transfer register pins
all admitted table/report/calibration hashes; regenerate and review those hashes together.

Final verification: [596 tests passed](../reports/refresh_2026-10-18/VERIFICATION.md),
including the live-data suite. Lint, formatting, mypy, privacy and seal checks pass.

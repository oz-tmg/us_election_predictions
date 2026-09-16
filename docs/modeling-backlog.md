# Modeling Backlog

This backlog prioritizes analytical questions and feature-engineering tasks for the US Election Prediction project. It assumes a solo-owned project, so tasks are scoped around clear success criteria and incremental delivery.

Priority labels:

- **P0:** required foundation;
- **P1:** high-value next step;
- **P2:** important but not first release;
- **P3:** advanced research or later extension.

Status labels:

- `todo`
- `in_progress`
- `blocked`
- `done`

## P0 — Data and Entity Foundation

| ID | Task | Why It Matters | Acceptance Criteria | Status |
|---|---|---|---|---|
| P0-001 | Create canonical election cycle table | Every model needs consistent election dates and office types. | Table has cycle, election date, office, jurisdiction, election type. | done (cycle table + prospective race universe: 435 House + 33 Senate for 2026, with current seat-holders; candidate filings still need `fec_api`) |
| P0-002 | Create canonical geography table | Prevents FIPS/GEOID/district mismatch. | State, county, district, precinct, media market keys documented. | done (nation/state/county/CD; precinct + media market deferred) |
| P0-003 | Create candidate and party normalization rules | Candidate names and party labels vary across sources. | Reusable crosswalk with aliases, party, office, cycle, source IDs. | done 2026-09-13 (`features/candidate_crosswalk.py`: exact-match aliases; `ballot_party` vs `caucus_party` split; FEC roster join; ballot-status rows no longer win races) |
| P0-004 | Build source manifest schema | Enables reproducibility and legal review. | Every raw source snapshot has source, date, checksum, license, privacy tier. | done |
| P0-005 | Ingest MIT/MEDSL federal returns | Core historical baseline. | President, House, Senate available in standardized silver tables. | done (all three series live/manual 1976-2024; validated) |
| P0-006 | Ingest Census ACS features | Core demographics. | ACS variables selected, transformed, and joined to geography table. | done |
| P0-007 | Ingest TIGER/Line boundaries | Core geospatial layer. | Current state/county/CD boundaries stored in PostGIS/GeoParquet. | done |
| P0-008 | Build model-ready race table | Central model grain. | One row per race/candidate or race/party with results and metadata. | done |
| P0-009 | Build data-quality report | Makes gaps visible. | Missingness, duplicate keys, vote-total reconciliation, stale sources. | done |

## P1 — Baseline Forecasting

| ID | Task | Analytical Question | Acceptance Criteria | Status |
|---|---|---|---|---|
| P1-001 | Presidential fundamentals model | How much can we predict without polls? | Backtest by state for 2008–2024 with MAE and calibration. | done |
| P1-002 | House district baseline | What is each district's normal partisan lean? | District partisanship score using presidential and House history. | done (score + district fundamentals forecast model; complete 435-seat chamber simulation) |
| P1-003 | Senate/governor baseline | How much do state partisanship and incumbency explain? | Backtest statewide races with incumbency/open-seat indicators. | done (Senate); governor **ingestion complete** — all five cycles 2016-2024 landed, **103 state-cycles**, enough to fit. Model not yet fitted |
| P1-004 | Generic ballot adjustment | How should national environment affect districts? | Historical relationship estimated and documented. | done (swing ratio estimated from certified returns). **Live national-environment input still open**: swing ratio is unidentified for the 2022 plan era and polls are blocked on redistribution terms (NE-000). Architecture reworked 2026-09-09: the shrinkage band is the output, not a parameter to fit. See `docs/national-environment-plan.md` and NE-000..NE-004 below |
| P1-005 | Correlated simulation layer | How does race-level uncertainty translate to seat control? | Simulation returns win probability, seat distribution, chamber probability. | done |
| P1-006 | Forecast evaluation notebook | Are probabilities calibrated? | Brier score, log score, calibration curve, interval coverage. | done |

## P1 — National Environment

Tracked separately from P1-004 because the blocker is not the district relationship — that
is estimated and documented — but the *national input* it consumes. Full rationale,
architecture and decision gates: `docs/national-environment-plan.md`.

| ID | Task | Analytical Question | Acceptance Criteria | Status |
|---|---|---|---|---|
| NE-000 | Resolve poll redistribution terms | May this project store and redistribute public poll toplines? | Written answer recorded in `dataset-registry.md` with the terms cited; `redistribution_allowed` set from it rather than hardcoded to the synthetic flag. | todo — **human decision, blocks NE-003** |
| NE-001 | National-environment estimator contract | Can a projection consume a band without collapsing it to a point? | `models/baseline/national_environment.py` returns a uniform shape carrying `identified`, `assumptions` and `provenance`; `shrinkage`'s default removed; a validator fails any specials-derived estimate claiming `identified = True`; band conclusions stated as text in the projection report. | **done 2026-09-15** — `NationalEnvironment` contract + `validate`/`projectable` (an unidentified non-scenario point raises); `SHRINKAGE_UNCALIBRATED` deleted and `shrinkage` made a required keyword; `control_conclusion` writes the band's verdict as text; band also emitted to `reports/national_environment_<date>.json`. Current read: House favored across the whole band, **Senate unresolvable by the band** |
| NE-002 | Historical calibration pairs (bound, not fit) | How wide is the plausible shrinkage band? | Four cycle pairs (2017→18, 2019→20, 2021→22, 2023→24) compiled to the existing specials schema; `calibration_pairs` + `band_from_pairs` return an interval with `status = "bound"`; a test fails if a scalar shrinkage is ever returned; same `compute_overperformance` path as the live estimate. | todo — House-only pairs first |
| NE-003 | Generic ballot as primary estimator | Can the national environment be measured rather than inferred? | National geography row + `us_house_generic` office accepted by `validate_polls`; average built from `polling.average_polls`; specials demoted to `cross_check` with disagreement reported and never blended; at least one held-out cycle backtested before promotion to primary. | blocked on NE-000 |
| NE-004 | Economic fundamentals estimator | Does election-year economic growth predict the incumbent party's national share, out of sample? | FRED/BEA/BLS series registered with a **vintage policy** before any pull (`data/fred.py`, `FRED_API_KEY`); `features/national_fundamentals.py` panel with `data_vintage` on every row (test-pinned), target = **incumbent-party** share, mapped to Dem share only at the end via `_white_house_party`; `national_environment.from_fundamentals` returns the NE-001 contract with sigma from leave-one-cycle-out residuals; pre-registered specification (one growth term + `president_on_ballot` + `consecutive_terms`); LOO MAE and coverage vs. persistence and vs. midterm-penalty-only; appears in `cross_check` for 2026. **Cross-check only in midterms; primary in a presidential year only until a backtested poll estimator exists.** Approval excluded until NE-000. | todo — after NE-001; not on the 2026 critical path, on the 2028 one |

## P1 — Feature Engineering

| ID | Feature | Offices | Why It Matters | Acceptance Criteria | Status |
|---|---|---|---|---|---|
| F-001 | Incumbency status | House, Senate, Gov, State Leg, Judicial | Large effect across offices. | Incumbent running, open seat, appointed incumbent flags. | done (House/Senate, derived; redistricting-aware). Appointed-incumbent flag not derivable from returns |
| F-002 | Past presidential vote | All geographic races | Strong baseline for partisanship. | Latest and previous presidential two-party vote by geography. | done |
| F-003 | District partisanship score | House, State Leg | Core prior. | Standardized score with cycle and plan version. | done |
| F-004 | Fundraising totals | Federal, Gov, Judicial | Proxy for candidate viability and campaign intensity. | Receipts, disbursements, cash, outside spending by reporting period. | done 2026-09-13 (federal only; `features/fundraising.py` — party receipts ratio, `coverage_gap_days` and `post_election_coverage` leakage guards). Outside spending, governor, judicial not covered |
| F-005 | Candidate quality | House, Senate, Gov, Judicial | Candidate effects matter in non-presidential races. | Prior elected office, office level, prior run, scandal indicator if sourced. | todo |
| F-006 | Demographics | All | Explains geography and MRP poststrata. | Age, race/ethnicity, education, income, urbanicity. | in_progress |
| F-007 | Race ratings | House, Senate, Gov | Useful expert prior. | Cook/Sabato/Inside/Split Ticket ordinal encoding. | todo |
| F-008 | Redistricting change | House, State Leg | Boundary changes break historical baselines. | Old-to-new vote transfer score and crosswalk confidence. | **planned 2026-09-14** — `plan_era` assumes one map per decade, which 2026 breaks; the 2026 projection does not yet consume `boundary_confidence`. Split into RD-001..RD-004 below; see `docs/redistricting-change-plan.md` |
| F-009 | Ballot roll-off | Judicial, State Leg | Down-ballot drop-off affects low-information races. | Top-of-ticket votes minus office votes by geography. | todo |
| F-010 | Judicial performance recommendation | Judicial retention | Often key official signal. | Recommendation, score, commission source, date. | todo |

## P1 — Redistricting Change

Tracked separately from F-008 because the blocker is not a feature but a stale
assumption: the plan is derived from the cycle year, and the projection never reads the
`boundary_confidence` flag the race universe already sets. Full rationale, architecture,
routing table and decision gates: `docs/redistricting-change-plan.md`. All inputs are
Tier 0/1; nothing here generates or scores an ensemble — that stays in the audit module.

| ID | Task | Analytical Question | Acceptance Criteria | Status |
|---|---|---|---|---|
| RD-001 | Plan-version register | Which states vote under a different congressional map in 2026 than in 2024? | `data/reference/house_plan_versions.csv` with `source_url` + `retrieved_on` per row; `features/plan_versions.py` with `plan_id(state, cycle)` falling back to the decennial default; `boundary_confidence` ∈ {unchanged, redrawn, pending, unverified}; validator fails sourceless/overlapping rows; every 1976–2024 `plan_id` equals the decennial default (test-pinned). | todo — **hand compilation from official portals; start first** |
| RD-002 | Projection consumes boundary confidence | Can a redrawn seat ever be projected from its old-number prior? | `project_house` routes on `boundary_confidence`: unchanged → model; redrawn without transfer → state-lean fallback with documented sigma inflation; unverified → raise unless `allow_unverified`; `coverage` reports seats by confidence and source; report states redrawn count and treatment as text; House band re-reported. | **done 2026-09-15** — routing + `UnverifiedBoundaryError`; redrawn seats **discard** the old-number prior; fallback sigma = `hypot(residual, β_lean × within-state lean sd)`, both inputs measured, no defaults; `TRANSFERRED_PRIOR_COLUMN` names the RD-003 seam. Report states the assumption for all 435 seats until RD-001 lands |
| RD-003 | Old-to-new vote transfer | Can 2024 returns be placed on 2026 boundaries with a stated confidence? | P.L. 94-171 VAP, Census/state BAFs, and one precinct-boundary source **registered before use**; `features/plan_transfer.py` allocates precinct → block → new district; three confidence components per district (unsplit share, old-district-majority share, ungeocoded share), never collapsed; 2020→2022 backtest on Virginia vs. no-prior and vs. RD-002 fallback; sigma for `model_transferred` taken from that backtest; historical and live paths share one code path (test-pinned). | todo — registry rows first; Virginia backtest is the first deliverable |
| RD-004 | Converge with audit-module Phase 1 | Does the forecast's block table double as the audit module's foundation? | RD-003's block base table and block-to-plan assignments written under `docs/redistricting/` storage conventions; pilot state recorded as the audit module's Phase 0 choice in `PROJECT_CONTEXT.md`; no ensemble, objective, or scoring code introduced. | todo — follows RD-003 |

## P2 — Polling and MRP

| ID | Task | Analytical Question | Acceptance Criteria | Status |
|---|---|---|---|---|
| P2-001 | Poll ingestion schema | Can polls be compared across pollsters? | Pollster, sponsor, mode, field dates, sample, population, weights, toplines. | done |
| P2-002 | Polling average | What is the current topline signal? | Time decay, sample-size weighting, pollster house effect placeholder. | done |
| P2-003 | Pollster house effects | Which pollsters systematically lean? | Historical estimates with uncertainty. | todo |
| P2-004 | MRP prototype | Can national/state survey data estimate district opinion? | Model using demographics + geography with poststratification frame. | todo |
| P2-005 | MRP uncertainty report | Are district estimates overconfident? | Posterior intervals include survey and poststratification uncertainty. | todo |
| P2-006 | Issue salience MRP | Which issues vary most by district? | District-level issue estimates with caveats. | todo |

## P2 — Turnout Modeling

| ID | Task | Analytical Question | Acceptance Criteria | Status |
|---|---|---|---|---|
| T-001 | Aggregate turnout baseline | What turnout should be expected by race and geography? | Historical turnout model by office, cycle, and geography. | todo |
| T-002 | Midterm drop-off model | Which districts change most between presidential and midterm years? | Predicted midterm electorate relative to presidential electorate. | todo |
| T-003 | Early/mail vote module | Does early vote improve forecast or mislead? | Separate documentation of counting rules and partisan bias risks. | todo |
| T-004 | Ballot roll-off model | Where do voters skip down-ballot races? | Roll-off predictions for state leg and judicial races. | todo |
| T-005 | Voter-file turnout prototype | Can individual turnout improve aggregate forecast? | Private-only model using synthetic or legally acquired data. | blocked |

## P2 — State Legislature

| ID | Task | Analytical Question | Acceptance Criteria | Status |
|---|---|---|---|---|
| SL-001 | State legislative returns ingestion | Can we build historical chamber baselines? | Lower/upper chamber returns by state, district, year where available. | source found 2026-09-01 — `medsl_state_office_2016` is ~12.4k state-legislative rows (9,311 State Rep + 3,100 State Senator); Klarner 1967-2016 also registered |
| SL-002 | Uncontested race treatment | How should missing opposition vote be handled? | Documented imputation or exclusion strategy with sensitivity test. | todo |
| SL-003 | Chamber-control simulation | What is probability of each chamber outcome? | Seat simulation by district with correlated state-level error. | todo |
| SL-004 | Redistricting crosswalk | Can old results map to current districts? | Crosswalk confidence and transfer estimates for target states. | todo — reuse RD-003's `plan_transfer` path with state-legislative BAFs; do not build a second crosswalk |

## P2 — Judicial Elections

| ID | Task | Analytical Question | Acceptance Criteria | Status |
|---|---|---|---|---|
| J-001 | Judicial race registry | Which judicial seats are elected or retained? | State, court, seat, selection type, term, election year. | todo |
| J-002 | Retention baseline model | What is normal yes-share by state/court? | Historical retention model with roll-off and yes-share. | todo |
| J-003 | Partisan judicial model | How do partisan court races behave relative to statewide politics? | Backtest partisan judicial races by state and cycle. | todo |
| J-004 | Nonpartisan cue extraction | Can endorsements/spending infer support coalitions? | Structured fields for endorsements, donors, appointment source. | todo |
| J-005 | Judicial spending feature | Does outside spending shift low-information races? | Spending by candidate/group and time window where available. | todo |

## P3 — Persuasion and Causal Inference

| ID | Task | Analytical Question | Acceptance Criteria | Status |
|---|---|---|---|---|
| C-001 | Experiment design template | How should voter-contact experiments be evaluated? | RCT design doc with power, randomization, outcomes, ethics. | todo |
| C-002 | Uplift model prototype | Who changes behavior because of contact? | Private-only synthetic example; no real voter data in public repo. | todo |
| C-003 | Geo experiment design | Can ad/media effects be evaluated by geography? | Matched-market design with spillover caveats. | todo |
| C-004 | Synthetic control case study | Did a major event or spending surge move vote share? | Public aggregate example using county/district returns. | todo |

## P3 — Election Night

| ID | Task | Analytical Question | Acceptance Criteria | Status |
|---|---|---|---|---|
| EN-001 | Live returns schema | Can unofficial results be stored safely? | Source, timestamp, geography, batch type, candidate totals, expected vote. | todo |
| EN-002 | Expected vote model | How much vote remains? | County/precinct expected vote with uncertainty. | todo |
| EN-003 | Reporting-order model | Are reporting units biased toward one party? | Historical reporting patterns and batch-type adjustment. | todo |
| EN-004 | Race-call rule simulation | When is a lead mathematically/probabilistically safe? | Call threshold documented and backtested. | todo |
| EN-005 | Election-night dashboard | How should provisional estimates be shown? | Clear distinction between estimate, call, unofficial total, certified result. | todo |

## P3 — Post-Election Analysis

| ID | Task | Analytical Question | Acceptance Criteria | Status |
|---|---|---|---|---|
| PE-001 | Forecast miss decomposition | Where did the model fail? | Error by state/district/office/source. | todo |
| PE-002 | Polling miss report | Was error from polling, turnout, undecideds, or model assumptions? | Polling error by mode, pollster, timing, geography. | todo |
| PE-003 | Ecological inference prototype | How did demographic groups vote? | Aggregate model with uncertainty and caveats. | todo |
| PE-004 | CVR analysis | What ballot-level patterns are visible where CVRs exist? | Ticket splitting, roll-off, ballot exhaustion where applicable. | todo |
| PE-005 | District profile autogeneration | Can profiles be produced from gold tables? | One completed report generated from template and data snapshot. | todo |

## First Four-Week Build Suggestion

### Week 1: Source and Entity Foundation

- Finish source manifest schema.
- Ingest MEDSL president/county, House district, and Senate state returns.
- Ingest ACS and TIGER basics.
- Create canonical geography and race tables.

### Week 2: Baseline Models

- Build fundamentals-only presidential model.
- Build House district partisanship score.
- Build Senate/governor baseline.
- Create first evaluation notebook.

### Week 3: Forecast Simulation

- Add correlated error simulation.
- Add seat-control simulation for House and Senate.
- Create model card template.
- Produce first public forecast example using historical backtest only.

### Week 4: Reporting and Governance

- Generate one House district profile.
- Complete source reliability matrix with actual source snapshots.
- Add data-quality report.
- Add public/private data boundary checks.

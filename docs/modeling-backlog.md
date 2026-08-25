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
| P0-001 | Create canonical election cycle table | Every model needs consistent election dates and office types. | Table has cycle, election date, office, jurisdiction, election type. | todo |
| P0-002 | Create canonical geography table | Prevents FIPS/GEOID/district mismatch. | State, county, district, precinct, media market keys documented. | in_progress |
| P0-003 | Create candidate and party normalization rules | Candidate names and party labels vary across sources. | Reusable crosswalk with aliases, party, office, cycle, source IDs. | todo |
| P0-004 | Build source manifest schema | Enables reproducibility and legal review. | Every raw source snapshot has source, date, checksum, license, privacy tier. | done |
| P0-005 | Ingest MIT/MEDSL federal returns | Core historical baseline. | President, House, Senate available in standardized silver tables. | in_progress |
| P0-006 | Ingest Census ACS features | Core demographics. | ACS variables selected, transformed, and joined to geography table. | done |
| P0-007 | Ingest TIGER/Line boundaries | Core geospatial layer. | Current state/county/CD boundaries stored in PostGIS/GeoParquet. | done |
| P0-008 | Build model-ready race table | Central model grain. | One row per race/candidate or race/party with results and metadata. | done |
| P0-009 | Build data-quality report | Makes gaps visible. | Missingness, duplicate keys, vote-total reconciliation, stale sources. | done |

## P1 — Baseline Forecasting

| ID | Task | Analytical Question | Acceptance Criteria | Status |
|---|---|---|---|---|
| P1-001 | Presidential fundamentals model | How much can we predict without polls? | Backtest by state for 2008–2024 with MAE and calibration. | done |
| P1-002 | House district baseline | What is each district's normal partisan lean? | District partisanship score using presidential and House history. | done |
| P1-003 | Senate/governor baseline | How much do state partisanship and incumbency explain? | Backtest statewide races with incumbency/open-seat indicators. | todo |
| P1-004 | Generic ballot adjustment | How should national environment affect districts? | Historical relationship estimated and documented. | todo |
| P1-005 | Correlated simulation layer | How does race-level uncertainty translate to seat control? | Simulation returns win probability, seat distribution, chamber probability. | done |
| P1-006 | Forecast evaluation notebook | Are probabilities calibrated? | Brier score, log score, calibration curve, interval coverage. | done |

## P1 — Feature Engineering

| ID | Feature | Offices | Why It Matters | Acceptance Criteria | Status |
|---|---|---|---|---|---|
| F-001 | Incumbency status | House, Senate, Gov, State Leg, Judicial | Large effect across offices. | Incumbent running, open seat, appointed incumbent flags. | todo |
| F-002 | Past presidential vote | All geographic races | Strong baseline for partisanship. | Latest and previous presidential two-party vote by geography. | done |
| F-003 | District partisanship score | House, State Leg | Core prior. | Standardized score with cycle and plan version. | done |
| F-004 | Fundraising totals | Federal, Gov, Judicial | Proxy for candidate viability and campaign intensity. | Receipts, disbursements, cash, outside spending by reporting period. | todo |
| F-005 | Candidate quality | House, Senate, Gov, Judicial | Candidate effects matter in non-presidential races. | Prior elected office, office level, prior run, scandal indicator if sourced. | todo |
| F-006 | Demographics | All | Explains geography and MRP poststrata. | Age, race/ethnicity, education, income, urbanicity. | in_progress |
| F-007 | Race ratings | House, Senate, Gov | Useful expert prior. | Cook/Sabato/Inside/Split Ticket ordinal encoding. | todo |
| F-008 | Redistricting change | House, State Leg | Boundary changes break historical baselines. | Old-to-new vote transfer score and crosswalk confidence. | todo |
| F-009 | Ballot roll-off | Judicial, State Leg | Down-ballot drop-off affects low-information races. | Top-of-ticket votes minus office votes by geography. | todo |
| F-010 | Judicial performance recommendation | Judicial retention | Often key official signal. | Recommendation, score, commission source, date. | todo |

## P2 — Polling and MRP

| ID | Task | Analytical Question | Acceptance Criteria | Status |
|---|---|---|---|---|
| P2-001 | Poll ingestion schema | Can polls be compared across pollsters? | Pollster, sponsor, mode, field dates, sample, population, weights, toplines. | todo |
| P2-002 | Polling average | What is the current topline signal? | Time decay, sample-size weighting, pollster house effect placeholder. | todo |
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
| SL-001 | State legislative returns ingestion | Can we build historical chamber baselines? | Lower/upper chamber returns by state, district, year where available. | todo |
| SL-002 | Uncontested race treatment | How should missing opposition vote be handled? | Documented imputation or exclusion strategy with sensitivity test. | todo |
| SL-003 | Chamber-control simulation | What is probability of each chamber outcome? | Seat simulation by district with correlated state-level error. | todo |
| SL-004 | Redistricting crosswalk | Can old results map to current districts? | Crosswalk confidence and transfer estimates for target states. | todo |

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

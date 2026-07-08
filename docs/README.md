# US Election Prediction

A nonpartisan analytics project for forecasting, explaining, and auditing U.S. election outcomes across presidential, U.S. Senate, U.S. House, gubernatorial, state legislative, and elected judicial races.

The project combines public election returns, district geography, Census demographics, polling, campaign-finance data, historical race context, and carefully governed licensed data sources when available. The intended result is a reproducible election analytics platform that can produce forecasts, district profiles, source-quality assessments, and post-election diagnostics without becoming a black-box partisan targeting system.

## Intended Use

This project is intended for:

- building reproducible election forecasts with explicit uncertainty;
- comparing polling, fundamentals, turnout, and geography-based models;
- producing public-facing district and race profiles;
- studying how elections differ across offices and geographies;
- supporting post-election analysis of turnout, persuasion, ticket splitting, demographic shifts, and model error;
- creating a portfolio-quality analytics project that demonstrates data engineering, statistical modeling, causal inference, geospatial analysis, and responsible data governance.

## What This Project Is

This project is:

- **Nonpartisan.** It evaluates electoral probability and uncertainty without optimizing for a party, faction, candidate, or ideological outcome.
- **Probabilistic.** Forecasts should be communicated as ranges, simulations, and calibrated probabilities, not deterministic predictions.
- **DataOps-first.** Data acquisition, lineage, validation, versioning, and legal review are treated as core modeling infrastructure.
- **Geospatial.** Many election problems are district, precinct, county, media-market, and state problems before they are national problems.
- **Auditable.** Every model output should be traceable to a model version, data snapshot, assumptions file, and evaluation report.
- **Privacy-aware.** Public data does not automatically mean low-risk data. Voter files, donor records, CRM data, and inferred voter attributes require strict handling.

## What This Project Is Not

This project is not:

- a tool for voter suppression, intimidation, harassment, or deceptive targeting;
- a gerrymandering optimizer designed to maximize seats for a party;
- a replacement for certified election results or official election administration sources;
- a claim that elections are fully predictable;
- a project that publishes individualized voter-level predictions or sensitive personal records;
- a repository for proprietary campaign data unless there is a documented legal basis, usage restriction, retention plan, and privacy review.

Redistricting analysis, if added, should focus on nonpartisan diagnostics: compactness, contiguity, population equality, Voting Rights Act considerations, partisan symmetry, efficiency gap, ensemble comparison, communities of interest, and representation effects. It should not generate partisan-maximizing maps.

## Race Coverage

| Office Type | Forecast Target | Typical Unit | Notes |
|---|---:|---|---|
| President | state vote share, Electoral College, national popular vote | state, county, precinct | Poll-heavy; correlated state errors are central. |
| U.S. Senate | statewide vote share and seat control | state, county | Mixed polling and fundamentals; candidate quality matters. |
| U.S. House | district vote share, seat control | district, county split, precinct | Strong geography and incumbency effects; redistricting complicates baselines. |
| Governor | statewide vote share and winner | state, county | More state-specific than federal races; national environment still matters. |
| State Legislature | district vote share, chamber control | district, precinct | Sparse polling; requires historical baselines, district crosswalks, and simulations. |
| Judicial Elections | vote share, retention yes/no share, roll-off, ideological control | state, district, county | Methods differ for partisan, nonpartisan, and retention elections. Often low-information and spending-driven. |

## Proposed Repository Structure

```text
us-election-prediction/
  README.md
  docs/
    methodology.md
    data-governance-and-privacy.md
    district-profile-template.md
    source-reliability-matrix.md
    modeling-backlog.md
    ingestion-playbook.md
    public-data-sources.md
    licensed-data-sources.md
    dataset-registry.md
    elections-domain.md
  data/
    raw/                 # Immutable source snapshots; no manual edits.
    bronze/              # Parsed but minimally transformed.
    silver/              # Standardized schemas, IDs, and geography.
    gold/                # Modeling-ready feature tables and marts.
    manifests/           # Checksums, source metadata, licenses, extraction logs.
  pipelines/
    ingest/              # Source-specific acquisition jobs.
    validate/            # Schema, total, geography, and freshness checks.
    transform/           # Crosswalks, feature engineering, aggregation.
  models/
    baseline/            # Fundamentals and prior-only models.
    polling/             # Poll aggregation and house effects.
    mrp/                 # Survey + poststratification models.
    turnout/             # Aggregate and voter-file turnout models.
    election_night/      # Live returns and remaining-vote models.
    post_election/       # Decomposition, ecological inference, CVR analysis.
  reports/
    districts/           # House district profiles.
    states/              # Senate, governor, presidential state reports.
    judicial/            # Judicial race reports.
    model_cards/         # Model assumptions, performance, and limitations.
  notebooks/
    exploration/         # Ad hoc analysis; promote reusable logic to pipelines.
  src/
    election_prediction/
      data/
      geography/
      features/
      models/
      evaluation/
      reporting/
  tests/
    data_quality/
    unit/
    integration/
```

## Core Modeling Principles

1. **Start with transparent baselines.** Past vote, incumbency, district partisanship, national environment, and simple polling averages should be hard to beat.
2. **Separate vote share from win probability.** Model the expected vote and uncertainty first; derive win probability through simulation.
3. **Model correlated error.** Presidential and congressional forecasts fail when they treat states or districts as independent.
4. **Respect office-specific behavior.** Judicial retention, state legislative, governor, federal, and presidential races have different information environments and voter behavior.
5. **Evaluate calibration.** Backtests should measure Brier score, log score, calibration curves, coverage, MAE, district/state error, and seat-control error.
6. **Publish uncertainty honestly.** Close races should look close. Do not over-sharpen probabilities for storytelling.

## Core Data Sources

Starter source families:

- MIT Election Data and Science Lab election returns.
- State and county election offices for official certified returns.
- Census ACS for demographic and socioeconomic covariates.
- Census TIGER/Line for geography and district boundaries.
- Redistricting Data Hub, VEST, MGGG, and related geospatial election datasets.
- FEC campaign-finance data for federal races.
- State campaign-finance portals for state, local, and judicial races.
- Polling aggregators and pollster-level releases.
- AP, Decision Desk HQ, and state feeds for election-night results.
- Ballotpedia, state court sites, judicial performance commissions, and state election offices for judicial election context.
- Licensed voter files and campaign CRM data only after legal, privacy, and use-case review.

## Minimum Viable Forecast

A first useful version should include:

1. canonical race, candidate, geography, and party tables;
2. historical election returns by office and geography;
3. Census and geography feature tables;
4. a baseline fundamentals model for president, Senate, House, and governor;
5. a poll-average module where polling exists;
6. simulation outputs for winner, vote share, seat count, and chamber control;
7. a model-card template explaining assumptions and known limitations;
8. data-quality dashboards showing freshness, missingness, and source reliability.

## Ethical Boundary

The public version of this project should produce race-level and geography-level insights, not individualized voter-level action lists. Voter-level models, if ever used in a permitted research or campaign environment, must stay behind strict access controls and should not be published, exported, or repurposed beyond the documented lawful purpose.

# Redistricting Module Implementation Roadmap

## Phase 0 — Scoping decisions

Decide the initial scope:

- office: congressional districts first, then state legislative districts;
- states: start with one or two states with good public data;
- cycle: 2020-cycle maps first, then 2025/2026 mid-decade maps if data is available;
- tooling: Python/GerryChain, R/redist, or both;
- output: static reports first, then dashboard/maps.

Recommended first state selection criteria:

- high-quality precinct returns;
- available enacted and proposed shapefiles;
- contested redistricting history;
- enough districts to make ensemble analysis meaningful;
- public interest.

## Phase 1 — Data foundation

### Tasks

- Create data inventory for one pilot state.
- Download Census P.L. 94-171 data.
- Download TIGER/Line block shapefiles.
- Download enacted congressional district shapefile.
- Download historical precinct returns.
- Download precinct/VTD boundaries, if available.
- Build block-level base table.
- Build block adjacency graph.
- Build block-to-district assignment table.
- Build election-return-to-block allocation method.

### Deliverables

- `blocks_{state}_{year}.parquet`
- `block_graph_{state}_{year}.json`
- `block_to_enacted_district_{state}_{plan_id}.parquet`
- `district_scores_{state}_{plan_id}.parquet`
- data validation report

## Phase 2 — Plan scoring MVP

### Tasks

- Validate population equality.
- Validate contiguity.
- Calculate district demographics.
- Calculate election composites.
- Classify districts into competitiveness bands.
- Calculate basic compactness metrics.
- Count county and municipality splits.
- Produce district-level report table.

### Deliverables

- enacted plan audit MVP;
- district profile table;
- map visualizations;
- scorecard JSON.

## Phase 3 — Neutral ensemble MVP

### Tasks

- Generate neutral ensemble using GerryChain or redist.
- Track population tolerance and contiguity.
- Add compactness and split constraints.
- Score every simulated plan.
- Compare enacted plan to simulated distribution.
- Produce ensemble diagnostics.

### Deliverables

- simulation config file;
- ensemble plan assignments;
- ensemble score table;
- enacted-vs-ensemble report.

## Phase 4 — Objective-driven simulations

### Tasks

Create simulation families for:

- competitiveness-seeking maps;
- compactness-prioritized maps;
- county/municipality-preserving maps;
- partisan-advantage hypothesis maps;
- incumbent-protection hypothesis maps;
- minority-opportunity screening maps;
- dummymander-risk maps.

### Deliverables

- objective definitions;
- objective-driven plan ensembles;
- tradeoff frontiers;
- hypothesis-fit report.

## Phase 5 — Stress testing

### Tasks

- Add uniform swing scenarios.
- Add non-uniform swing scenarios.
- Add presidential-year vs midterm electorate assumptions.
- Add turnout sensitivity.
- Add candidate-quality/incumbency sensitivity.
- Evaluate dummymander risk.

### Deliverables

- seats-votes curves;
- district flip curves;
- map durability score;
- competitiveness under swing report.

## Phase 6 — Analytical products

### Tasks

- Build static Markdown report templates.
- Build notebook-to-report workflow.
- Build map export pipeline.
- Build summary tables for public explainers.
- Build technical appendix generator.

### Deliverables

- plan audit report;
- district change report;
- competitiveness report;
- community split report;
- hypothesis-fit report;
- public explainer.

## Phase 7 — Governance and ethics

### Tasks

- Add data-use register for voter-file and licensed data.
- Add privacy controls for PII.
- Separate public outputs from restricted inputs.
- Add review checklist for claims about race, protected classes, and legal violations.
- Add reproducibility checklist.

### Deliverables

- redistricting ethics checklist;
- legal/context review checklist;
- public-release checklist;
- reproducibility checklist.

## Suggested repository structure

```text
us-election-prediction/
  docs/
    redistricting/
      README.md
      how-redistricting-works.md
      data-sources-and-acquisition.md
      simulation-and-ensemble-methods.md
      hypothesis-driven-map-analysis.md
      metrics-and-scoring.md
      analytical-products.md
      implementation-roadmap.md
  data/
    raw/
      census/
      elections/
      redistricting/
    interim/
      geocrosswalks/
      cleaned_returns/
    processed/
      blocks/
      plans/
      district_scores/
      ensembles/
  src/
    redistricting/
      ingest_census.py
      ingest_returns.py
      build_graph.py
      assign_blocks_to_plan.py
      score_plan.py
      simulate_neutral.py
      simulate_objective.py
      compare_to_ensemble.py
      hypothesis_fit.py
      stress_test.py
      report.py
  notebooks/
    redistricting/
  configs/
    redistricting/
      states/
      objectives/
      simulations/
  reports/
    redistricting/
```

## Initial backlog

| Priority | Task | Notes |
|---:|---|---|
| P0 | Choose pilot state | Prefer good public data and high substantive value |
| P0 | Build Census block base table | Foundation for all scoring |
| P0 | Build enacted plan scoring | Required before simulation |
| P0 | Validate official district populations | Prevent silent data errors |
| P1 | Add election returns and composite vote score | Needed for partisan and competitiveness metrics |
| P1 | Build adjacency graph | Needed for simulations |
| P1 | Generate first neutral ensemble | Core audit method |
| P1 | Compare enacted map to ensemble | First real product |
| P2 | Add competitiveness-seeking simulation | Supports constructive alternatives |
| P2 | Add partisan-hypothesis simulation | Supports gerrymander resemblance testing |
| P2 | Add stress testing | Avoid one-election-year conclusions |
| P3 | Add CVAP and minority-opportunity screening | Requires careful caveats |
| P3 | Add turnout-opportunity analysis | Research-oriented and less certain |
| P3 | Build public explainer template | Useful for communication |

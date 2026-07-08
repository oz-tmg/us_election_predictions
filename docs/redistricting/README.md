# Redistricting Audit Module

## Purpose

This module documents the redistricting-analysis component of the U.S. Election Prediction project.

The goal is not to provide a playbook for manipulating districts. The goal is to build an analytical system that can audit how redistricting and map choices affect:

- election outcomes;
- representation;
- competitiveness;
- partisan advantage;
- minority voting opportunity;
- community and county splits;
- turnout incentives;
- durability of a map under different electoral environments.

The key idea is that a proposed or enacted map should not be judged only against one alternative map or one fairness metric. It should be compared against a large family of legally plausible maps generated under explicit constraints and objectives.

## Core question

> Given the legal, geographic, demographic, and administrative constraints that govern a state, is the enacted or proposed plan a normal member of the plausible map universe, or does it resemble a map optimized for a particular political or representational objective?

## What this module is

This module is an audit and simulation framework for:

1. Ingesting redistricting-relevant data.
2. Building small-unit geographic graphs.
3. Scoring enacted, proposed, and simulated district plans.
4. Generating neutral and objective-driven map ensembles.
5. Testing hypotheses about likely map-drawing intent.
6. Producing analytical reports for public, journalistic, research, litigation-support, or civic-analysis use.

## What this module is not

This module is not:

- a partisan map-drawing tool;
- a voter suppression tool;
- a system for targeting individual voters;
- legal advice;
- a substitute for expert Voting Rights Act analysis;
- proof of intent by itself.

A simulated map can show that a plan is consistent with a given objective function. It cannot, by itself, prove why decision-makers drew the map they drew. Strong claims require documentary evidence, public statements, legal context, and expert review.

## Conceptual workflow

```text
Raw inputs
  ├── Census blocks / TIGER geometries
  ├── P.L. 94-171 redistricting data
  ├── CVAP / ACS demographics
  ├── precinct / VTD election returns
  ├── voter file summaries, if licensed and permitted
  ├── enacted and proposed plans
  └── legal constraints by state

Processing layer
  ├── standardize geography
  ├── build adjacency graph
  ├── crosswalk precincts ↔ blocks ↔ districts
  ├── aggregate election and demographic variables
  └── validate population, contiguity, and splits

Simulation layer
  ├── neutral ensembles
  ├── compactness-constrained ensembles
  ├── community-preservation ensembles
  ├── competitiveness-seeking ensembles
  ├── turnout-opportunity ensembles
  ├── partisan-advantage hypothesis ensembles
  └── minority-opportunity / VRA-sensitive ensembles

Scoring layer
  ├── seats-votes curves
  ├── partisan bias / symmetry
  ├── efficiency gap and wasted votes
  ├── competitiveness bands
  ├── compactness
  ├── county / municipality / community splits
  ├── minority CVAP / opportunity districts
  ├── incumbent pairings
  └── robustness under swing scenarios

Output layer
  ├── plan audit reports
  ├── enacted-vs-ensemble outlier analysis
  ├── district change profiles
  ├── competitiveness reports
  ├── community split reports
  ├── VRA risk screening summaries
  ├── hypothesis-fit reports
  └── public map explanations
```

## Recommended files in this module

- [`CLAUDE.md`](./CLAUDE.md) — operating rules for AI agents in this module (audit-only ethics, method framework, metrics, governance, reporting-language rules).
- [`AGENTS.md`](./AGENTS.md) — tool-agnostic mirror of `CLAUDE.md` for any coding agent.
- [`how-redistricting-works.md`](./how-redistricting-works.md) — conceptual mechanics of map drawing.
- [`data-sources-and-acquisition.md`](./data-sources-and-acquisition.md) — data inputs, source systems, and acquisition notes.
- [`simulation-and-ensemble-methods.md`](./simulation-and-ensemble-methods.md) — stronger approach based on ensembles and stress tests.
- [`hypothesis-driven-map-analysis.md`](./hypothesis-driven-map-analysis.md) — simulating objectives and comparing enacted maps to those objectives.
- [`metrics-and-scoring.md`](./metrics-and-scoring.md) — plan, district, and ensemble metrics.
- [`analytical-products.md`](./analytical-products.md) — reports and reusable product templates.
- [`implementation-roadmap.md`](./implementation-roadmap.md) — project build sequence.

## Open-source tools to evaluate

| Tool | Language | Role |
|---|---:|---|
| GerryChain | Python | Markov chain districting ensembles and plan evaluation |
| gerrytools | Python | Data preparation, unit maps, plan analysis, plotting |
| redist | R | Simulation-based redistricting, especially SMC/MCMC workflows |
| ALARM 50-state simulations | R / data | Public simulated congressional plans and replication templates |
| Dave's Redistricting | Web / GitHub ecosystem | Public map-drawing and map-inspection reference |
| PlanScore | Web / methods reference | Partisan fairness metrics and public map scoring |

## Primary references

- U.S. Census Bureau — Decennial Census P.L. 94-171 Redistricting Data: https://www.census.gov/programs-surveys/decennial-census/about/rdo/summary-files.html
- U.S. Census Bureau — TIGER/Line Shapefiles: https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html
- GerryChain documentation: https://gerrychain.readthedocs.io/
- GerryChain GitHub: https://github.com/mggg/GerryChain
- redist GitHub: https://github.com/alarm-redist/redist
- ALARM 50-state simulations paper: https://arxiv.org/abs/2206.10763
- Dave's Redistricting GitHub organization: https://github.com/dra2020
- PlanScore: https://planscore.org/

# AGENTS.md — Redistricting Audit Module

> Tool-agnostic guide for **any** AI coding agent (Claude, Cursor, Copilot, Codex,
> Aider, etc.). Mirror of `CLAUDE.md` in this folder; derived from the module docs.
> If this conflicts with `CLAUDE.md`, `CLAUDE.md` wins for Claude; for ethics and
> privacy, the **stricter** rule always wins.
> **Last updated:** 2026-07-08

---

## Module in brief

An audit-and-simulation framework that scores enacted/proposed district plans against
large ensembles of legally plausible maps — for representation, competitiveness, partisan
advantage, minority opportunity, and community splits. It is **not** a map-drawing tool,
a voter-targeting tool, or legal advice. Part of the US Election Prediction project;
inherits that project's nonpartisan and privacy rules and adds stricter ones.

**Core question:** is the enacted plan a normal member of the plausible map universe, or
does it resemble a map optimized for a political/representational objective?

## The seven rules you must not break

1. **Audit, never optimize-for-a-party.** No partisan seat-maximizing or dilution map ships as a deliverable.
2. **Ensembles over single alternatives.** Compare to thousands of constraint-satisfying maps, not one.
3. **Multi-metric.** No single score decides fairness; combine plan metrics, district diagnostics, ensemble position, stress tests.
4. **Sampling ≠ optimization ≠ hypothesis-fit.** Keep the three distinct; use all three.
5. **Consistency, not intent.** A simulated map can't prove why a map was drawn; strong claims need documentary + legal + expert evidence.
6. **Stress-test first.** Swing (uniform + non-uniform), presidential vs midterm electorate, turnout — before any conclusion.
7. **VRA is a screen, not a verdict.** Flag minority-opportunity concerns; never make final legal determinations.

## Build order (see `implementation-roadmap.md`)

Scoping (office/state/cycle/tooling) → data foundation (P.L. 94-171 + TIGER blocks,
adjacency graph, block↔district assignment, return→block allocation) → plan-scoring MVP
(population, contiguity, demographics, composites, competitiveness, compactness, splits) →
neutral ensemble MVP (GerryChain/redist; place enacted plan in the distribution) →
objective-driven simulations (competitiveness / compactness / community / partisan-hypothesis
/ incumbent / minority-screen / dummymander) → stress testing (seats-votes + flip curves,
durability) → analytical products → governance & ethics checklists.

**Pilot-state criteria:** high-quality precinct returns; available enacted + proposed
shapefiles; contested redistricting history; enough districts for meaningful ensembles;
public interest.

## Tooling

GerryChain + gerrytools (Python, MCMC/ReCom), redist + ALARM (R, SMC/MCMC), Dave's
Redistricting and PlanScore as references. Geography: Census blocks bridged to VTD/precinct;
PostGIS/GeoParquet; deterministic geometry validation/repair; adjacency by shared boundary.

## Data & governance

- Blocks = population (P.L. 94-171); precincts = behavior. Crosswalking them is the hard
  part — preserve and report allocation uncertainty; version precinct geometry by election date.
- Respect Census differential privacy on tiny blocks; aggregate for sensitive analysis.
- Voter-file / licensed / CRM data (Tier 3–5): private, governed, access-controlled; never
  in Git; never used to infer or expose individual vote choice. Modeled partisanship is Tier 5.
- Store raw inputs immutably with source/license/quality metadata; keep a license register;
  log random seeds, constraints, and parameters for reproducibility.

## Metrics (multi-metric, ensemble-relative)

Plan-level: expected seats, seat share, seats-votes curve, partisan bias, efficiency gap,
mean-median, declination, competitiveness count, compactness summary, county/city splits,
minority-opportunity count, incumbent pairings, ensemble percentile. District-level:
population + deviation, race/VAP/CVAP, two-party share, composite partisanship, turnout,
competitiveness band, multiple compactness measures, split contributions, incumbent
residence/pairing, swing sensitivity. Always report the enacted map's ensemble percentile
with the election composite and swing assumptions stated.

## Reporting language

Use: "outlier relative to neutral simulations", "consistent with a partisan-advantage
objective", "sensitive to the selected election composite", "fragile under modest swing",
"requires VRA expert review". Avoid: "proved intent", "definitely illegal", "compactness
alone proves the case."

## What "done" looks like

Enacted plan scored on all metric families at an explicit ensemble percentile under stated
composites/swings; neutral + objective ensembles with honest hypothesis-fit and sensitivity
tests; fully reproducible (seeds/constraints/params logged); no partisan map produced; no
PII or vote-choice inference exposed; VRA flagged for expert review.

## Pointers

- Module rules (Claude): `CLAUDE.md` · Overview: `README.md`
- Mechanics: `how-redistricting-works.md` · Data: `data-sources-and-acquisition.md`
- Methods: `simulation-and-ensemble-methods.md` · Hypotheses: `hypothesis-driven-map-analysis.md`
- Metrics: `metrics-and-scoring.md` · Products: `analytical-products.md` · Roadmap: `implementation-roadmap.md`
- Project: `../../CLAUDE.md` · `../../PROJECT_CONTEXT.md` · `../../COMPANY_CONTEXT.md` · Vertical: `../../../CLAUDE.md`

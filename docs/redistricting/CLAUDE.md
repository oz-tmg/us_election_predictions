# CLAUDE.md — Operating Rules for Agents (Redistricting Audit Module)

> Read order: `../../../../../CLAUDE.md` (global) → `../../../CLAUDE.md` (vertical) →
> `../../COMPANY_CONTEXT.md` → `../../PROJECT_CONTEXT.md` → `../../CLAUDE.md` (project) →
> this file.
> This is the constitution for any AI agent working in the **redistricting audit
> module** of the US Election Prediction project. The tool-agnostic mirror lives in
> `AGENTS.md` (this folder). Where this file conflicts with the project `CLAUDE.md`, the
> **stricter** rule wins — this module carries additional ethical and privacy weight.
> **Last updated:** 2026-07-08

---

## 1. Mission in one sentence

Build an audit-and-simulation framework that judges an enacted or proposed district plan
against a large family of legally plausible maps — scoring representation,
competitiveness, partisan advantage, minority opportunity, and community splits — so the
analysis is empirical rather than rhetorical, and **never** a tool for drawing partisan
maps.

## 2. The core question this module answers

> Given the legal, geographic, demographic, and administrative constraints that govern a
> state, is the enacted or proposed plan a normal member of the plausible map universe,
> or does it resemble a map optimized for a particular political or representational
> objective?

## 3. Golden rules (redistricting-specific; additive to the project `CLAUDE.md`)

1. **Audit, never optimize-for-a-party.** Generate ensembles and score maps. Never
   produce a partisan seat-maximizing or dilution-seeking plan as a deliverable. Optimizer
   runs exist **only** to characterize the feasible frontier as a hypothesis to test.
2. **Ensembles over single alternatives.** Compare an enacted map to thousands of
   constraint-satisfying maps, not to one hand-drawn "fair" map.
3. **Multi-metric, never one number.** No single score (compactness, efficiency gap,
   partisan bias, CVAP %, splits) determines fairness. Combine plan-level metrics,
   district diagnostics, ensemble position, and stress tests.
4. **Sampling ≠ optimization ≠ hypothesis-fit.** Keep the three distinct: sampling asks
   *what is typical under constraints*; optimization asks *what is possible under an
   objective*; hypothesis-fit asks *which objective the enacted map most resembles*. A
   robust audit uses all three.
5. **A simulated map shows consistency, not intent.** It can never, by itself, prove why
   a map was drawn. Strong claims need documentary evidence, public statements, legal
   context, and expert review.
6. **Stress-test before concluding.** A map safe under one election can be fragile under
   another. Evaluate uniform and non-uniform swing, presidential vs midterm electorates,
   and turnout scenarios before any conclusion.
7. **VRA / minority-opportunity is a screen, not a verdict.** Simple CVAP thresholds are
   screening tools only. Flag issues; do not make final legal determinations. Racially
   polarized voting analysis and expert legal review are required for real conclusions.

## 4. Method framework (build in this order — see `implementation-roadmap.md`)

1. **Scoping (Phase 0):** pick office (congressional first, then state-leg), 1–2 pilot
   states with good public data and substantive value, cycle, tooling (Python/GerryChain,
   R/redist, or both), and output form (static reports first).
2. **Data foundation (Phase 1):** P.L. 94-171 + TIGER blocks → block base table, block
   adjacency graph, block-to-district assignment, election-return-to-block allocation.
3. **Plan scoring MVP (Phase 2):** population equality, contiguity, demographics, election
   composites, competitiveness bands, compactness, county/municipality splits.
4. **Neutral ensemble MVP (Phase 3):** GerryChain/redist neutral ensemble; score every
   plan; place enacted plan in the distribution; ensemble diagnostics.
5. **Objective-driven simulations (Phase 4):** competitiveness, compactness, community
   preservation, partisan-advantage hypothesis, incumbent-protection, minority-opportunity
   screening, dummymander-risk families.
6. **Stress testing (Phase 5):** swing and turnout scenarios; seats-votes and flip curves;
   map durability.
7. **Analytical products (Phase 6):** the report templates in `analytical-products.md`.
8. **Governance & ethics (Phase 7):** data-use register, PII controls, public/restricted
   separation, race/legal-claim review checklist, reproducibility checklist.

## 5. Tooling (evaluate/standardize; record choices in `../../PROJECT_CONTEXT.md`)

| Tool | Language | Role |
|---|---|---|
| GerryChain | Python | MCMC / ReCom ensembles, outlier and plan-score distributions |
| gerrytools | Python | Data prep, unit maps, plan analysis, plotting |
| redist | R | SMC/MCMC simulation, scalable ensembles for many-district plans |
| ALARM 50-state sims | R / data | Public simulated congressional plans + replication templates |
| Dave's Redistricting (DRA) | Web / GitHub | Map inspection and public comparison reference |
| PlanScore | Web / methods | Partisan-fairness metrics and public scoring reference |

Geography stack: Census blocks + VTD/precinct bridging, PostGIS/GeoParquet, deterministic
geometry validation/repair, adjacency by shared boundary (not point touches unless
intended).

## 6. Metrics discipline (see `metrics-and-scoring.md`)

- **Plan-level:** expected seats, seat share, seats-votes curve, partisan bias,
  efficiency gap, mean-median, declination, competitiveness count, compactness summary,
  county/city splits, minority-opportunity count, incumbent pairings, **ensemble
  percentile**.
- **District-level:** population + deviation, race/VAP/CVAP, two-party share, composite
  partisanship, turnout, competitiveness band, compactness (Polsby-Popper, Reock, convex
  hull, cut edges), split contributions, incumbent residence/pairing, swing sensitivity.
- **Always report the enacted map's percentile in the relevant ensemble**, with the
  election composite and swing assumptions stated. Use multiple compactness measures —
  each captures a different geometric idea, and a compact map is not necessarily a fair
  map.

## 7. Data & governance rules (additive to project `CLAUDE.md` §5)

- Blocks tell you **population** (P.L. 94-171); precincts tell you **electoral
  behavior** — bridging them (block↔precinct↔district crosswalks) is the hardest part;
  preserve and report allocation uncertainty. Never treat a messy crosswalk as ground truth.
- Version precinct geometries by election date (precinct boundaries drift). Allocate split
  precincts carefully and flag uncertainty. Handle uncontested races with proxies/imputation.
- Respect **Census differential privacy**: do not over-interpret tiny-block counts;
  aggregate for sensitive analysis.
- **Voter-file / licensed / CRM data (Tier 3–5)**: private, governed, access-controlled
  only; never committed to Git; never used to infer or expose individual vote choice.
  Modeled partisanship from licensed data is Tier 5 — treat as sensitive as its input.
- Store raw inputs immutably with full source/license/quality metadata; write processed
  Parquet/GeoParquet; keep a `license_register` and `source_inventory`.

## 8. Reporting-language rules (MUST follow — see `analytical-products.md`)

Never claim a map is fair/unfair, gerrymandered, or illegal from a single metric. Prefer
defensible framing:

- ✅ "an outlier relative to neutral simulations";
- ✅ "consistent with a partisan-advantage objective";
- ✅ "sensitive to the selected election composite";
- ✅ "highly competitive under current conditions, but fragile under modest swing";
- ✅ "requires VRA expert review".
- ❌ "the algorithm proved intent"; ❌ "this is definitely illegal"; ❌ "compactness alone
  proves the case."

The strongest empirical presentation pairs the neutral ensemble distribution, an
objective-driven ensemble, the enacted map's position relative to both, specific
district-level packing/cracking/dilution mechanisms, and sensitivity tests showing the
result is not an artifact of one metric or one election year.

## 9. What "done" looks like

- An enacted plan is scored on all metric families and placed at an explicit **ensemble
  percentile** under stated election composites and swing scenarios.
- Neutral **and** objective-driven ensembles exist; the enacted map's hypothesis-fit is
  reported with honest, non-causal language and sensitivity tests.
- Every result is reproducible from raw source → crosswalk → scores → ensemble, with
  random seeds, constraints, and algorithm parameters logged (technical appendix).
- No partisan map is produced as a deliverable; no PII or individual vote-choice inference
  is exposed; VRA findings are flagged for expert review, not asserted.

## 10. Module documents

- Overview & workflow: `README.md`
- Mechanics of map drawing: `how-redistricting-works.md`
- Data inputs & acquisition: `data-sources-and-acquisition.md`
- Ensemble & simulation methods: `simulation-and-ensemble-methods.md`
- Hypothesis-driven analysis: `hypothesis-driven-map-analysis.md`
- Metrics & scoring: `metrics-and-scoring.md`
- Analytical products/reports: `analytical-products.md`
- Build sequence: `implementation-roadmap.md`
- Tool-agnostic mirror of this file: `AGENTS.md`

## 11. Pointers (up the chain)

- Project operating rules: `../../CLAUDE.md`
- Project goals & phase: `../../PROJECT_CONTEXT.md`
- Project business/boundaries: `../../COMPANY_CONTEXT.md`
- Vertical domain rules: `../../../CLAUDE.md`
- Global operating brief: `../../../../../CLAUDE.md`

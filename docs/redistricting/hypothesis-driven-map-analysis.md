# Hypothesis-Driven Map Analysis

## Purpose

This document defines how the redistricting module should simulate and test different map-drawing goals.

The central idea is:

> To argue that a map is suspicious, do not merely show that it has partisan consequences. Show that it resembles maps produced by a specific objective function more closely than it resembles maps produced by neutral or public-interest constraints.

## Why hypothesis simulation matters

A map can favor one party for several reasons:

- intentional partisan gerrymandering;
- residential sorting;
- legal requirements;
- protection of minority opportunity districts;
- compactness or county-preservation constraints;
- incumbent protection;
- protection of communities of interest;
- random chance in the valid-plan universe.

Hypothesis-driven simulation asks which explanation is most consistent with the observed plan.

## Hypothesis families

### H0 — Neutral legal baseline

The map is a typical product of legal and geographic constraints.

Simulation objective:

- satisfy population equality;
- maintain contiguity;
- apply state rules;
- avoid political scoring in the proposal mechanism, except where required for legal/VRA constraints.

Evidence against H0:

- enacted plan falls in the extreme tail for expected seats, competitiveness, minority-opportunity loss, or splits.

### H1 — Partisan advantage

The map was drawn to maximize expected seats for one party.

Simulation objective:

- maximize expected seats for Party A under historical election composites and swing scenarios;
- keep districts above a target safety threshold where possible;
- preserve enough compactness and split metrics to remain legally or publicly defensible.

Audit comparison:

- Does the enacted plan's seat count match the partisan-optimization frontier?
- Are the same opposition voters packed or cracked in similar places?
- Does the enacted plan show similar margins to optimized maps?
- Does it protect against reasonable statewide swing?

### H2 — Incumbent protection

The map was drawn to protect current incumbents rather than simply maximize party seats.

Simulation objective:

- keep incumbents in favorable districts;
- avoid pairing incumbents from the map-drawing party;
- pair or disadvantage opposing incumbents where possible;
- maintain district continuity around incumbent homes or bases.

Audit comparison:

- How many incumbents receive safer districts?
- How many opposition incumbents are paired or shifted into less favorable districts?
- Does the map sacrifice party-seat maximization to protect specific incumbents?

### H3 — Competitiveness

The map was drawn to create more competitive elections.

Simulation objective:

- maximize the number of districts in a defined competitive band;
- avoid too many landslide districts;
- maintain population, contiguity, and community constraints.

Possible competitive bands:

- Toss-up: two-party margin within 0–5 points.
- Lean: margin within 5–10 points.
- Competitive: margin within 0–10 or 0–12 points.

Audit comparison:

- Does the enacted map create more or fewer competitive districts than feasible alternatives?
- Did it reduce competitiveness while claiming to improve representation?
- Are competitive districts durable under turnout and swing scenarios?

### H4 — Turnout opportunity

The map was drawn to increase voter engagement or preserve communities with shared turnout conditions.

Simulation objective:

- keep communities with shared civic infrastructure together;
- avoid splitting municipalities, school districts, reservations, college communities, or language communities;
- maximize districts where electoral competition is plausible enough to motivate participation;
- avoid districts where one side is structurally hopeless.

Audit comparison:

- Does the map increase the number of meaningfully contestable districts?
- Does it preserve communities likely to organize politically?
- Does it reduce the number of districts with extreme partisan margins?

### H5 — Minority opportunity / VRA-sensitive representation

The map was drawn to preserve or create districts where protected minority communities can elect candidates of choice.

Simulation objective:

- meet legal requirements;
- test multiple CVAP thresholds and coalition definitions;
- preserve compact minority communities where legally and demographically appropriate;
- avoid unnecessary dilution.

Audit comparison:

- Are opportunity districts preserved, improved, or weakened?
- Do plausible alternatives create more effective minority opportunity while satisfying other constraints?
- Does the map use minority voters to justify partisan outcomes that could have been achieved differently?

This requires expert legal and racially polarized voting analysis. The module should flag issues; it should not make final legal determinations.

### H6 — Community preservation

The map was drawn to preserve communities of interest.

Simulation objective:

- minimize county, municipality, school district, tribal area, or neighborhood splits;
- maximize overlap with commuting, media, housing, school, economic, cultural, or watershed regions;
- respect public-submission community boundaries where available.

Audit comparison:

- Does the enacted map split more communities than necessary?
- Are splits concentrated in politically useful locations?
- Were similar community-preserving alternatives available?

### H7 — Dummymander / overreach

The map was drawn to maximize seats too aggressively, resulting in many narrow seats that could flip under modest swing.

Simulation objective:

- maximize seats with low safety margins;
- allow many districts barely above the winning threshold;
- test under swing and turnout shifts.

Audit comparison:

- Does the map create many fragile districts?
- Does a small swing turn a large intended advantage into losses?
- Are the risk patterns similar to aggressive partisan-optimization maps?

## Hypothesis-fit scoring

For each enacted or proposed map, calculate a similarity score to each simulation family.

Example scores:

| Score | Description |
|---|---|
| Seat-count similarity | Difference between enacted expected seats and simulation-family expected seats |
| Margin-distribution similarity | Distance between district margin vectors |
| Geography similarity | Unit assignment similarity, adjusted Rand index, district overlap matrix |
| Packing/cracking similarity | Similarity in distribution of opposition vote share and minority CVAP |
| Split-pattern similarity | Similarity in county, city, and community splits |
| Incumbent-effect similarity | Similarity in incumbent protection or pairing patterns |
| Robustness similarity | Similarity in response to swing scenarios |

The audit should report:

```text
The enacted map is closest to:
  1. Partisan-advantage hypothesis ensemble
  2. Incumbent-protection hypothesis ensemble
  3. Neutral baseline ensemble

This does not prove intent, but it shows which stated or unstated objective best matches the plan's observable structure.
```

## The strongest argument against a gerrymandered map

A strong argument is not simply:

> This map benefits one party.

A stronger argument is:

> When we simulate maps under the same legal constraints, the enacted map closely resembles maps optimized for partisan advantage and is an extreme outlier relative to neutral, compactness-preserving, community-preserving, and competitiveness-seeking alternatives. The same voters or communities are packed and cracked in ways that are unnecessary under alternative valid maps.

The strongest empirical presentation includes:

1. Neutral ensemble distribution.
2. Partisan-advantage objective ensemble.
3. Competitiveness or representation objective ensemble.
4. Enacted map position relative to all three.
5. Specific district-level mechanisms showing packing, cracking, or dilution.
6. Sensitivity tests showing the result is not an artifact of one metric or one election year.

## Guardrails

- Do not infer individual vote choice from voter files.
- Do not expose personally identifiable voter data.
- Do not claim legal violations without legal review.
- Do not use protected-class data to recommend discriminatory map manipulation.
- Do document assumptions, constraints, and uncertainty.
- Do compare multiple plausible explanations.

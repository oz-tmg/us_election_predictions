# Metrics and Scoring

## Summary

Redistricting scoring should be multi-metric and ensemble-aware.

No single score can determine whether a map is fair, competitive, representative, or gerrymandered. Compactness, efficiency gap, partisan bias, minority CVAP, and county splits each capture different concepts.

## Plan-level metrics

| Metric | Description | Use | Caveat |
|---|---|---|---|
| Expected seats | Number of seats each party is expected to win under a given election composite | Main political outcome | Depends heavily on election choice and swing assumptions |
| Seat share | Expected seats divided by total seats | Comparability across states | Can hide district-level mechanisms |
| Votes-seats curve | Seat share across statewide vote-share scenarios | Measures responsiveness and symmetry | Requires modeling swing assumptions |
| Partisan bias | Difference in seat outcomes at equal vote share | Fairness / symmetry | Sensitive to geography and swing assumptions |
| Efficiency gap | Difference in wasted votes divided by total votes | Packing/cracking signal | Should not be used alone |
| Mean-median difference | Difference between average vote share and median district vote share | Asymmetry signal | Can miss complex maps |
| Declination | Measures asymmetry in district vote distribution | Gerrymandering signal | Less intuitive to nontechnical audiences |
| Competitiveness count | Number of seats within target margin bands | Electoral competition | Depends on chosen band |
| Compactness summary | Distribution of compactness scores across districts | Shape reasonableness | Compact maps are not always fair maps |
| County / city splits | Number of administrative splits | Community preservation | Some splits are unavoidable |
| Minority opportunity count | Number of districts where minority communities can elect candidates of choice | Representation / VRA screening | Requires more than a simple percentage threshold |
| Incumbent pairing count | Number of incumbent pairings caused by the map | Incumbent impact | Incumbent residence data must be accurate |
| Ensemble percentile | Where enacted plan falls in simulated distribution | Outlier analysis | Depends on ensemble design |

## District-level metrics

| Metric | Description |
|---|---|
| Total population | District population from P.L. 94-171 or relevant official source |
| Population deviation | Difference from ideal district population |
| Race / ethnicity composition | Total population, VAP, and CVAP where available |
| Two-party vote share | District-level vote share from each reference election |
| Composite partisanship | Average or modeled partisan score using multiple elections |
| Turnout rate | Votes cast divided by eligible or registered population, depending on denominator |
| Competitiveness band | Safe, likely, lean, toss-up, etc. |
| Compactness | Polsby-Popper, Reock, convex hull ratio, cut edges, or other measures |
| County split contribution | Whether district splits counties or municipalities |
| Community split contribution | Whether district divides named communities of interest |
| Incumbent residence | Which incumbents live in the district |
| Pairing status | Whether multiple incumbents are assigned to one district |
| Swing sensitivity | How quickly the district flips under statewide or demographic swing |

## Compactness metrics

Use several compactness measures because each captures a different geometric idea.

| Metric | Intuition | Caveat |
|---|---|---|
| Polsby-Popper | Area relative to perimeter squared | Penalizes coastlines and irregular borders |
| Reock | Area relative to minimum enclosing circle | Sensitive to long thin shapes |
| Convex hull ratio | Area relative to convex hull | Penalizes concavity |
| Cut edges | Number of adjacency edges crossing district boundaries | Graph-based; depends on unit geography |
| County / municipal splits | Administrative compactness / coherence proxy | A split-minimizing map can still be partisan |

## Partisan metrics

### Efficiency gap

Efficiency gap measures the difference in wasted votes between parties divided by total votes. Wasted votes include losing votes and excess winning votes beyond what was needed to win.

Use it as one diagnostic of packing and cracking, not a definitive verdict.

### Partisan bias and symmetry

Partisan bias asks whether each party would receive similar seat shares at the same statewide vote share. Seats-votes curves are usually more informative than a single point estimate.

### Mean-median difference

The mean-median difference compares the average district vote share to the median district vote share. If the median district is much more favorable to one party than the statewide average, that can indicate asymmetry.

### Declination

Declination measures the geometry of district vote shares and can identify asymmetric packing/cracking patterns.

## Competitiveness metrics

Recommended bands:

| Band | Two-party margin |
|---|---:|
| Toss-up | 0–5 points |
| Lean | 5–10 points |
| Likely | 10–15 points |
| Safe | 15+ points |
| Landslide / packed | 30+ points |

Competitiveness should be reported under multiple electoral environments:

- recent presidential year;
- recent midterm year;
- statewide composite;
- D+2 / R+2 swing;
- high-turnout and low-turnout assumptions.

## Representation metrics

Representation is not only party seats.

Track:

- minority total population;
- minority voting-age population;
- citizen voting-age population;
- language minority populations;
- tribal area preservation;
- coalition district composition;
- district-level turnout opportunity;
- whether communities are packed, cracked, or preserved.

For Voting Rights Act-sensitive analysis, simple thresholds are screening tools only. Final evaluation often requires racially polarized voting analysis, election history, candidate-of-choice evidence, and legal context.

## Turnout and engagement metrics

The project should explore whether maps affect electoral engagement.

Possible metrics:

| Metric | Meaning |
|---|---|
| Competitive-population share | Share of residents living in competitive districts |
| Competitive-CVAP share | Share of eligible voters living in competitive districts |
| Competitive-registered-share | Share of registered voters in competitive districts |
| Turnout-weighted competitiveness | Competitiveness weighted by historical turnout |
| Mobilizable community preservation | Whether high-potential turnout communities are kept intact |
| Hopelessness index | Share of electorate in districts where one party is structurally noncompetitive |

## Ensemble-relative metrics

For each metric, report the enacted map's percentile in the ensemble.

Example:

```text
Expected Democratic seats:
  Neutral ensemble median: 7
  Neutral ensemble 5th–95th percentile: 5–9
  Enacted plan: 3
  Percentile: 1.2

Interpretation:
  The enacted plan creates fewer Democratic seats than 98.8% of neutral simulated plans under this election composite.
```

## Recommended scoring table

Every plan should produce a table like this:

| Category | Score | Ensemble percentile | Notes |
|---|---:|---:|---|
| Expected Party A seats | TBD | TBD | Election composite: TBD |
| Expected Party B seats | TBD | TBD | Election composite: TBD |
| Competitive districts | TBD | TBD | Margin band: 0–10 |
| Mean district compactness | TBD | TBD | Metric: Polsby-Popper |
| County splits | TBD | TBD | State rule: TBD |
| Municipality splits | TBD | TBD | State rule: TBD |
| Minority opportunity districts | TBD | TBD | Screening threshold only |
| Incumbent pairings | TBD | TBD | Includes only declared incumbents |
| Dummymander risk | TBD | TBD | Measured under swing scenarios |

## Reporting rule

Never present a map as fair or unfair based on one score. Use language like:

- “consistent with a partisan-advantage objective”;
- “an outlier relative to neutral simulations”;
- “sensitive to the selected election composite”;
- “requires VRA expert review”;
- “highly competitive under current conditions, but fragile under modest swing.”

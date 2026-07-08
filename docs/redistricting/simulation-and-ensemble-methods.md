# Simulation and Ensemble Methods

## Summary

The stronger approach to redistricting analysis is ensemble-based.

Instead of comparing an enacted map to one hand-drawn alternative, generate thousands of legally plausible maps under explicit constraints. Then compare the enacted or proposed map to the distribution of outcomes from those maps.

## The stronger approach: four steps

### Step 1 — Generate many legally plausible alternative maps

Create an ensemble of maps that satisfy the same baseline constraints as the enacted plan:

- correct number of districts;
- population balance;
- contiguity;
- state-specific split rules;
- compactness constraints or penalties;
- Voting Rights Act-sensitive constraints where appropriate;
- preservation of counties, municipalities, tribal areas, or communities of interest where required.

The ensemble should be large enough to characterize the range of plausible plans, not just produce a few examples.

### Step 2 — Apply the same election and demographic data to every map

For every simulated map, compute the same metrics:

- district population deviation;
- race / ethnicity / VAP / CVAP composition;
- past presidential, Senate, governor, and statewide vote share;
- composite partisanship;
- expected seat count;
- competitiveness bands;
- compactness;
- county and municipality splits;
- minority-opportunity districts;
- incumbent pairings;
- turnout opportunity and turnout history.

### Step 3 — Compare the enacted/proposed map to the distribution

Ask where the enacted map falls compared with the ensemble:

- Is it in the extreme tail for partisan seat advantage?
- Is it unusually uncompetitive?
- Does it create fewer opportunity districts than plausible alternatives?
- Does it split more counties, municipalities, or communities than necessary?
- Does it resemble maps optimized for a particular party more than neutral maps?
- Is its advantage durable under reasonable swing scenarios?

### Step 4 — Evaluate the full pattern, not one metric

A single metric is not enough. A map can look acceptable on compactness and still be highly biased. A map can have a modest efficiency gap because of natural geography, while still raising representational concerns in specific communities.

A complete audit should combine:

- ensemble position;
- multiple partisan metrics;
- district-level diagnostics;
- legal and state-rule context;
- racial and CVAP analysis;
- competitiveness and responsiveness;
- community-split analysis;
- stress testing;
- sensitivity to assumptions.

## Why simulations should include multiple objectives

A neutral ensemble is essential, but it is not the whole story.

To audit a map, the system should simulate several plausible objectives:

| Simulation family | Objective | Audit use |
|---|---|---|
| Neutral baseline | Satisfy legal/geographic constraints without political scoring | Establish normal range |
| Compactness-prioritized | Improve compactness while respecting population and contiguity | Test whether shape was unnecessarily irregular |
| County / municipality preservation | Minimize splits | Test whether local communities were unnecessarily divided |
| Competitiveness-seeking | Maximize number of plausible competitive districts | Show whether more competitive maps were feasible |
| Representation-seeking | Preserve or improve minority opportunity and community coherence | Evaluate representation alternatives |
| Turnout-opportunity | Preserve coherent high-turnout or mobilizable communities | Test whether maps encourage or depress electoral engagement |
| Partisan-advantage hypothesis | Maximize expected seats for one party under constraints | Test whether enacted map resembles a partisan optimum |
| Incumbent-protection hypothesis | Minimize incumbent risk or avoid pairings | Test whether incumbent protection explains boundaries |
| Dummymander-risk hypothesis | Maximize seats aggressively, allowing narrow seats | Identify fragile partisan designs |

The point is not to produce one best map. The point is to understand the feasible map space and infer which objectives the enacted plan most closely resembles.

## Algorithms to evaluate

### Markov Chain Monte Carlo / ReCom

MCMC methods sample district plans by making small or structured changes to a current plan. ReCom-style moves merge neighboring districts and split them again using spanning trees. This can produce more coherent changes than moving one unit at a time.

Use cases:

- outlier analysis;
- enacted-vs-ensemble comparison;
- stress testing;
- plan-scoring distributions.

Open-source tools:

- GerryChain: Python MCMC redistricting library.
- redist: R package supporting modern redistricting simulation workflows.

### Sequential Monte Carlo

Sequential Monte Carlo builds plans progressively, often district by district or region by region, while maintaining weights that account for the sampling process.

Use cases:

- scalable simulation workflows;
- state legislative plans with many districts;
- reproducible ensemble generation;
- comparison with MCMC ensembles.

Open-source tools:

- redist.
- ALARM project replication code and 50-state simulations.

### Optimization and heuristic search

Optimization methods search for maps that maximize or minimize an objective function.

Use cases:

- competitiveness-maximizing maps;
- partisan-advantage hypothesis maps;
- minimum-split maps;
- high-compactness maps;
- turnout-opportunity maps;
- stress testing the maximum feasible advantage under constraints.

Examples:

- simulated annealing;
- integer programming;
- genetic algorithms;
- local search;
- GerryChain optimization utilities;
- custom objective functions over partitions.

## Important distinction: sampling vs optimizing

| Approach | What it answers |
|---|---|
| Sampling / ensembles | What is typical under constraints? |
| Optimization | What is possible if a map drawer pursues a specific objective? |
| Hypothesis simulation | Which objective does the enacted map most resemble? |

A robust audit uses all three.

## Recommended simulation outputs

Each simulation run should produce:

- plan ID;
- random seed;
- algorithm;
- constraints;
- objective function, if any;
- population deviation;
- district assignments;
- district-level demographic scores;
- district-level election scores;
- plan-level partisan scores;
- compactness scores;
- split counts;
- competitiveness scores;
- minority-opportunity scores;
- validation status;
- diagnostics for convergence or sample quality.

## Convergence and validation checks

Simulation results are only useful if the ensemble is credible.

Track:

- number of accepted plans;
- number of rejected plans;
- acceptance rate;
- duplicate plan rate;
- effective sample size where applicable;
- distribution stability over time;
- sensitivity to starting plan;
- sensitivity to population tolerance;
- sensitivity to compactness and county-preservation parameters;
- whether different algorithms produce compatible conclusions.

## Warning against overclaiming

Do not claim:

> The enacted map is gerrymandered because it is less compact than average.

Prefer:

> Under stated constraints and across multiple simulation methods, the enacted map is in the extreme tail of the ensemble for partisan seat advantage while also producing more cracked minority communities and fewer competitive districts than most plausible alternatives. This pattern is consistent with a partisan-advantage objective, subject to legal review and data limitations.

That language is more defensible.

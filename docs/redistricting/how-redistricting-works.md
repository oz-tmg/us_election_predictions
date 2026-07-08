# How Redistricting Works

## Summary

Redistricting converts a state into a set of electoral districts. In practice, that means assigning many small geographic units to districts while satisfying legal, demographic, administrative, and political constraints.

For auditing purposes, the important point is this:

> A district plan is not just a map. It is an optimization result under constraints.

The same map can be evaluated as a legal artifact, a geographic partition, a representation system, an election-outcome generator, and a political strategy.

## 1. Geographic units

Map drawers usually begin with small geographic units. The exact unit depends on the office, data availability, state law, and mapping platform.

| Unit | Description | Typical role |
|---|---|---|
| Census block | Smallest standard Census geography; used for decennial population counts | Core building block for equal-population requirements |
| Block group | Cluster of blocks | Useful for ACS data, but often too coarse for final line drawing |
| Census tract | Larger statistical unit | Useful for socioeconomic context and community analysis |
| Voting tabulation district / VTD | Census approximation of election precinct geography | Useful bridge between election returns and census geography |
| Precinct | Local election administration unit | Key for past vote and turnout, but precinct boundaries change frequently |
| Municipality / county | Administrative geography | Used for split-count metrics and community preservation |
| Congressional or legislative district | Target assignment | Output of the redistricting process |

### Why census blocks matter

Census blocks are central because redistricting requires accurate population counts at very small geographies. The Census Bureau's P.L. 94-171 redistricting data provides population tabulations used by states for legislative redistricting, including race, Hispanic origin, voting-age population, and group quarters fields.

### Why precincts matter

Blocks tell you population. Precincts tell you electoral behavior. To evaluate partisan impact, analysts must bridge between the block-level population world and the precinct-level election-return world.

Common approaches:

- allocate precinct election results to blocks using voting-age population or registered-voter counts;
- aggregate blocks to precincts where boundaries align;
- use VTDs as a proxy where official precincts are unavailable;
- preserve uncertainty when geography does not line up cleanly.

## 2. Hard legal and administrative constraints

Hard constraints define which maps are allowable or at least defensible. They vary by state and office.

| Constraint | Meaning | Audit implication |
|---|---|---|
| Equal population | Districts must have nearly equal population, especially congressional districts | Validate total population deviation |
| Contiguity | Each district should be connected | Validate graph connectivity |
| Voting Rights Act compliance | Maps cannot unlawfully dilute protected minority voting power | Requires expert review, CVAP analysis, and often racially polarized voting analysis |
| Compactness | Districts should avoid unnecessary sprawl where required or normatively desired | Score with multiple compactness metrics, not one |
| County / city preservation | Some states restrict unnecessary splits | Count splits and compare to simulated alternatives |
| Communities of interest | Districts should preserve meaningful social/economic/cultural communities | Hard to quantify; can use proxies and qualitative evidence |
| Nesting | Some state legislative maps require lower districts to nest inside upper districts | Validate parent-child assignments |
| Incumbency rules | Some states prohibit or permit incumbent protection | Track incumbent addresses and pairings carefully |
| Tribal / reservation considerations | Tribal geographies may be protected or politically salient | Preserve as explicit geography where relevant |

## 3. Political scoring

Once a valid or near-valid map exists, analysts score it politically.

Common scoring inputs:

- presidential vote share;
- U.S. Senate vote share;
- governor vote share;
- state attorney general / secretary of state vote share;
- composite statewide-election average;
- party registration, where available;
- voter-file modeled partisanship, if licensed;
- turnout history;
- incumbency and candidate-quality measures;
- district-level demographic composition;
- elasticity under swing scenarios.

Common outputs:

- expected Democratic and Republican seats;
- safe / likely / lean / toss-up classification;
- average district margin;
- competitiveness distribution;
- median seat margin;
- seat responsiveness to statewide swing;
- number of opportunity districts;
- incumbent-pairing count;
- map durability under different national environments.

## 4. Packing, cracking, unpacking, pairing, bleaching, and dummymander risk

These are common conceptual operations in partisan and racial map analysis. The module should model them as hypotheses to audit, not as goals to implement.

| Concept | Description | Analytical signal |
|---|---|---|
| Packing | Concentrating a group into a few districts it wins overwhelmingly | Very high vote share for one group or party in fewer districts than expected |
| Cracking | Splitting a group across multiple districts so it cannot form a majority or winning coalition | A group appears large regionally but remains just below effective strength in many districts |
| Unpacking | Moving excess voters out of packed districts into surrounding districts | Formerly lopsided districts become less lopsided while nearby target districts become more favorable |
| Pairing | Placing two incumbents, often from the same opposing party, into the same district | Incumbent-address overlay shows forced member-vs-member contests |
| Bleaching / dilution risk | Reducing minority voting opportunity by spreading minority voters or altering coalition districts | Decline in minority CVAP or effective coalition strength compared with alternatives |
| Dummymander risk | Over-optimizing for too many narrow wins, leaving the map vulnerable to a small swing | Many seats sit just barely above winning threshold for favored party |

## 5. Stress testing the map

A single past election is not enough. A map may look safe under one year and unstable under another.

Stress tests should include:

- uniform swing: D+2, R+2, D+5, R+5;
- non-uniform swing by region, race, education, urbanicity, and turnout mode;
- presidential-year electorate;
- midterm electorate;
- low-turnout scenario;
- high-turnout scenario;
- incumbent advantage scenario;
- candidate-quality shock;
- turnout-mobilization scenario;
- demographic trend scenario;
- alternative election composite scenario.

## 6. Why intent cannot be inferred from one map alone

A map may look partisan because of intentional gerrymandering, natural political geography, Voting Rights Act requirements, incumbency protection, community preservation, or a combination of those factors.

The stronger approach is not to say:

> This map looks strange, therefore it is a gerrymander.

The stronger approach is to say:

> Under the same legal and geographic constraints, thousands of plausible maps rarely produce this level of partisan advantage, minority-district alteration, or competitiveness reduction. The enacted map is much closer to maps optimized for that objective than to neutral maps.

That framing makes the audit empirical rather than rhetorical.

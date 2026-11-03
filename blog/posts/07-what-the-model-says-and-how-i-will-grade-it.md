# What the Model Says, and How I Will Grade It

*Polls close tonight. Here is the prediction, frozen on October 29, every row of it — and the rules I wrote in September for scoring it, which I am no longer allowed to change.*

**Savepoint Analytics · US Election Analysis · modelled projection, published as a band · final run 2026-10-29 · published 2026-11-03**

---

## The short version

My model says Democrats are favoured to win the House under every assumption I am willing to make about the national environment, and that the Senate leans Democratic but crosses the coin flip at the most conservative of those assumptions. It says both of those things with wide intervals, and I am publishing the intervals, not a headline.

[Five weeks ago I wrote that I would not publish this](05-the-forecast-i-am-not-publishing.md). Two of the three reasons have since been fixed, the third I have decided to accept, and the postscript on that post explains the reversal. What follows is the prediction itself, in the form it has to take if it is going to be graded rather than believed.

## Why there are five rows and not one

The model's view of the national environment comes from eight special elections held between April 2025 and June 2026, in which Democratic candidates beat their district's 2024 presidential baseline by an average of 21.2 points of margin. Special electorates are not general electorates — they are smaller, more engaged and occur wherever a vacancy happened — so some fraction of that overperformance carries into November. The fraction is called shrinkage. One cycle of specials cannot identify it, and [the four historical cycles I checked span too wide a range to narrow it](03-the-parameter-that-wasnt-there.md). So the model does not estimate shrinkage. It sweeps it, from 0.25 to 1.0, and reports every row.

That is the whole table. Reading one row and ignoring the others is the thing the design exists to prevent.

| Shrinkage | Implied national Dem share | House mean seats | House 90% range | P(Dem House) | Senate Dem seats (of 100) | P(Dem Senate) |
|---:|---:|---:|---|---:|---:|---:|
| 0.25 | 0.524 | 234.7 | 123–355 | 0.584 | 51.1 | 0.481 |
| 0.33 | 0.532 | 240.3 | 129–361 | 0.616 | 51.7 | 0.517 |
| 0.50 | 0.550 | 252.3 | 142–373 | 0.681 | 53.0 | 0.591 |
| 0.75 | 0.577 | 270.0 | 160–389 | 0.762 | 55.0 | 0.698 |
| 1.00 | 0.603 | 287.8 | 177–402 | 0.832 | 56.9 | 0.791 |

*Final pre-election run, 2026-10-29. Source: `reports/refresh_2026-10-29/`. The 2024 House national input (contested races, total-vote weighted) is 0.497; each row adds a shrinkage multiple of the specials swing to it.*

![Two frozen runs, both before any vote was counted](../figures/fig-09-sealed-vs-current.png)

**The House.** Democrats are favoured at every row. The 90% seat range straddles 218 at every row too — the low end of the sweep allows for a Republican House of 123 Democratic seats and the high end for a Democratic House of 402 — which is what it costs to admit that 135 of 435 seats are projected from their state's partisan lean rather than their own history. More on that below.

**The Senate.** Four rows above one half, one at 0.481. Mean Democratic seats run from 51 to 57, with 34 Democratic holdovers not on the ballot and 35 races up. The control probability sits well below where the mean seat count would put it under independence, because the simulation shares error across races: if the environment is a point worse than the row assumes, it is worse in Iowa and Texas at the same time. I would describe this as a lean, not a call. The seats the model has closest to even at the middle assumption are North Carolina (0.58), Iowa (0.50), Texas (0.49), Maine (0.49) and Montana (0.44). They look close because they are close.

## What was sealed in September, and why October is different

The dashed lines in the figure are a second prediction, sealed on September 30 and hashed (`4de09ecf…`), which my scoring code treats as the registered holdout. It will be graded alongside the October run, by the same rules, on the same certified returns. I am showing both so that a reader can see which direction the model moved in the five weeks between them and decide for themselves whether that was drift or improvement.

The House moved modestly: +6 to +13 mean seats across the sweep. About 4.6 seats of that at every row came from restoring New York's 26 districts, which an over-strict validator had quarantined ([F-2 and F-3 in the findings](../../reports/preregistration_2026-11-03_findings.md)); the rest from a refreshed specials baseline that raised the measured swing from 18.8 to 21.2 points of margin.

The Senate moved a lot — from 0.27–0.55 to 0.48–0.79 — and it is important to be clear that none of that came from new evidence about the national environment. It came from three changes to the model, each recorded with its gate:

1. **An open-seat term.** The September specification credited every seat with its incumbent's advantage, including seats the incumbent is leaving. A specification that treats an open seat as held by its party but without the personal incumbency term was promoted by a chronological backtest across 661 held-out Senate races (MAE 0.0645 → 0.0638, open-seat MAE 0.0663 → 0.0638, 90% coverage 0.935 → 0.944). Seven Republican-held open seats — Alabama, Iowa, Kentucky, Montana, North Carolina, Texas, Wyoming — moved 13 to 17 points toward the Democratic candidate. Four Democratic-held open seats — Illinois, Michigan, Minnesota, New Hampshire — moved 5 to 7 points the other way.
2. **The party crosswalk reconciles.** The seal derived party from certified returns and came up two seats short of the actual Democratic caucus. The October run uses the official roster: 34 Democratic holdovers, 47 caucus, 100 seats accounted for.
3. **Two more races.** The Florida and Ohio special Senate elections are in the universe, taking it from 33 to 35.

So October's Senate is a better-specified model, not a better-informed one. The environment is exactly as unidentified as it was in September.

## What the forecast is standing on

A prediction is only as honest as its list of known weaknesses, and these were declared before the outcome:

- **135 House seats have no prior on their 2026 boundaries.** Nine states — Alabama, California, Florida, Louisiana, North Carolina, Ohio, Tennessee, Texas and Utah — use a different congressional map this year than in 2024, covering 173 seats ([the register, and what it cost](06-the-map-is-not-the-territory-and-neither-is-the-number.md)). For Texas's 38, a precinct-level vote transfer onto the new plan was built and backtested, and its measured sigma (0.122) is used. The other 135 fall back to their state's presidential lean with sigma 0.146 against the model's 0.112. These are the least-informed seats in the chamber and should score visibly worse.
- **Renomination is assumed for 267 of 470 seats.** Candidacy was verified from official general-election ballots for 203 seats, and 52 seats are recorded as ones the sitting member is not contesting; for the remaining 267 the sitting member is assumed to be on the ballot.
- **The national environment is unidentified**, as above. Shrinkage is swept, not estimated.
- **The correlated-error split** (45% national, 25% regional, 30% state) is asserted, not estimated from residuals; a held-out estimate did not pass its gate. Chamber-level interval width depends on it.
- **Litigation is live in nine of the ten states with map activity.** The register records the plan in effect as of its last verification; a court could in principle still move one. Missouri is the instructive case — it enacted a 2025 map that the courts have blocked, votes its 2022 map, and so keeps its 2024 priors.

## How this will be graded

The rules were written into the registration on September 30 and they bind both runs:

- **Scored on certified returns only** — not election-night calls, not unofficial counts — once the states certify. December runoffs and recounts are followed to their conclusion.
- **Every row is scored and every row is reported.** Picking the shrinkage assumption that did best afterwards is forbidden; doing so would void the registration.
- **Per seat:** Brier and log score on win probability; calibration over the same ten bins as the backtest; mean absolute error on two-party share; 90% and 95% interval coverage.
- **Per chamber:** absolute error on mean seats; whether the realised count fell inside the 90% interval; whether the directional claim held.
- **Split evaluation.** The 262 model seats, the 38 transferred seats and the 135 fallback seats are reported separately. A pooled number would hide which part of the chamber the model actually knows anything about.
- **Comparators fixed in advance:** naive persistence (every seat repeats its 2024 share) and the state-lean fallback applied everywhere, plus the backtest's own leave-one-cycle-out House MAE of 0.0787 as the in-sample reference.
- **Pre-declared failure condition.** If the realised Democratic seat count falls outside the 90% interval under every row of the band, the model's stated uncertainty was too narrow. That is a failure of the forecast, to be reported as one.

For calibration, the model's record on past elections: on a forward-only chronological evaluation, the House baseline beats naive persistence (MAE 0.065 vs 0.080 across 15 cycles, 91% coverage of its 90% intervals) and so does the Senate (0.064 vs 0.084 across 21 cycles, 94% coverage). The presidential baseline does not beat persistence, which is why there is no presidential forecast here and never has been.

## What happens next

Tonight I capture official releases as they are posted and label them unofficial until the authorities certify them. The scorecard — both runs, every row, the split by seat source, and the comparators — gets published when enough of the chamber is certified to be evaluable, and not before. If the model did badly, that post will be longer than this one.

---

*Every number above is read from a committed build artefact: `reports/refresh_2026-10-29/` (final run, frozen in `reports/comparison_set_2026-11-03.json`), `reports/preregistration_2026-11-03.json` (seal), and `reports/refresh_2026-10-29/senate_specification_gate.json`. Figure generated by [`blog/figures/make_figures.py`](../figures/make_figures.py). Data: [MIT Election Data and Science Lab](https://electionlab.mit.edu/) certified U.S. federal returns 1976–2024; U.S. Census Bureau ACS 5-year estimates (vintage 2023), TIGER/Line and Block Assignment Files; Federal Election Commission candidate filings (aggregate use only); Texas Legislative Council precinct geography; compiled special elections with per-row sourcing. This project is nonpartisan: it models probability and uncertainty, not a preferred outcome, and no probability here has been sharpened to carry a storyline. Historical returns are certified; everything else is modelled and labelled as such.*

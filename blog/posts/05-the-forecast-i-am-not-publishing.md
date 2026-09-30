# The Forecast I Am Not Publishing

*The model runs. It produces a number. The number is wrong in a way I can describe precisely, which is the only reason I get to say so.*

**Savepoint Analytics · US Election Analysis · modelled projection, withheld · snapshot 2026-09-30**

---

## The question

By mid-September I had all the parts. Fifty years of certified returns, ingested and validated. Three calibrated baselines that beat naive persistence. A correlated simulation layer. A 2026 race universe — 435 House seats and 33 Senate seats, with current holders derived from returns. A national-environment estimator. Campaign finance filings joined in.

I ran the projection. It completed in seconds, wrote a report, and told me who was going to win the House.

I am not going to publish that number as a forecast, and this post is my attempt to explain why in enough detail that you could check my reasoning and disagree with it.

## Why an election forecast is harder to observe than it looks

The seductive thing about a district-level model is that it appears to be forecasting *a place*. TX-35 voted this way in 2024; here is the national environment; therefore TX-35 will vote that way in 2026.

But the model is not forecasting a place. It is forecasting *a row keyed to a district number*, and a district number is not a place. It is a label attached to a piece of territory by a legislature, and legislatures move it.

This is the part of *Altered Carbon* that always seemed to me more useful as an analytical idea than as science fiction. A person's stack gets moved into a new sleeve. The identity persists, the body is entirely different, and everyone who knew them has to decide how much of what they knew still applies. A redrawn congressional district is a resleeved district. The number is continuous. The territory is not. And every historical lag in my model — the district's previous result, its partisan lean, its incumbent's performance — is attached to the number.

My code, until very recently, assumed one congressional map per decade. That is true most of the time. It is not true now.

## What the projection actually says about itself

Here is the output, and the first thing worth noticing is what it says in its own footer:

```
house seats projected: 435/435   senate seats up: 33
district boundaries: {'redrawn': 173, 'unchanged': 262}
projected by source: {'fallback_state_lean': 173, 'model': 262}
litigation active: AL, LA, MO, TN
```

Two hundred and sixty-two House seats are projected from their own 2024 result. One hundred and seventy-three are not allowed to be, because the territory behind those district numbers changed.

This footer is the second version. The first one read `{'unverified': 435}` — every seat flagged as *unknown*, not *unchanged*, because the model could not tell which districts had moved. Getting from that line to this one is what the rest of this post is about, and it is worth being precise that the two lines are different kinds of admission. The first says "I don't know." The second says "I know, and here is what it costs."

The mechanism underneath both is a design decision I want to dwell on. The projection function **routes on boundary confidence**. Seats marked `unchanged` go to the model. Seats marked `redrawn` are thrown off the model entirely — they do not keep their old-number prior, because that prior describes someone else's territory now — and fall back to a state-lean estimate with an inflated sigma, computed as `hypot(residual_sigma, β_lean × within-state lean sd)`, both inputs measured rather than assumed. And seats marked `unverified` **raise an exception** unless the caller explicitly passes `allow_unverified`.

For weeks the only way to get a number out of this pipeline was to pass that flag. The default behaviour of my own forecasting code, asked to project a seat whose boundaries it could not vouch for, was to refuse and crash. That flag is now gone from the script, because the register answers the question the exception was asking.

## How much of the chamber is affected

This is the one part of the post where I can give you a hard number, and it took a few hours of reading state government websites to earn it.

I compiled a plan-version register — which states, per state, which congressional plan is actually in effect for which cycles, with a source for every claim — and then verified every row against an official state or court record. **Nine states use a different congressional map in November 2026 than they used in 2024: Alabama, California, Florida, Louisiana, North Carolina, Ohio, Tennessee, Texas and Utah — 173 of 435 seats, 39.8% of the chamber.**

So: two fifths of the House is currently being projected from results that describe different territory. The register now knows that. The forecasting code does not — `plan_versions.py` is unwritten, nothing reads the CSV, and every seat is still flagged `unverified`. Having the fact and having the model consume the fact are separate pieces of work, and only the first one is done.

Verification was not a formality. It changed two rows in ways that reversed their meaning, and both corrections cut against the obvious move.

**Missouri enacted a new map and is not using it.** The 2025 plan is suspended pending a November referendum; the state supreme court ordered the 2022 map used for the general, a stay was denied, and the U.S. Supreme Court blocked the new map's use. The August primary ran on one map and the general reverts to another. So the naive correction — "Missouri redrew, therefore discard Missouri's prior" — is *wrong*. Missouri's 2024 prior is exactly right. A crude fix would have destroyed good data in eight districts.

**Alabama did not enact a new map — it restored an old one.** The draft recorded a fresh 2026 legislative enactment. What actually happened is that Alabama brought back the legislature's previously struck-down **2023** plan: reversion bills signed 2026-05-08, injunctions lifted by the Supreme Court on 2026-05-11, blocked again on 2026-05-26 by a three-judge panel as an intentional racial gerrymander under the Fourteenth Amendment and the Voting Rights Act, then cleared 6–3 on 2026-06-02 by an emergency stay. Alabama is still redrawn relative to 2024 — the 2023 legislative plan is not the Allen v. Milligan remedial map that 2024 was run on — but *which* map and *by what authority* were both wrong in the draft, and a register that records the wrong plan identity cannot support a vote transfer later.

And **Georgia, New York and Virginia did not redraw**, despite each being widely expected to: a legislature declined, a case was voluntarily dismissed, an amendment was struck down. Three states that a from-memory list would very likely have included.

I mention these because they are the reason the register had to be *researched* rather than *recalled*, and because they demonstrate the specific failure this whole exercise guards against: a correction applied with confidence and insufficient sourcing does not reduce error, it relocates it.

## The other two reasons

Boundaries are the largest problem. They are not the only one.

**The Senate band does not resolve.** As [the previous post](03-the-parameter-that-wasnt-there.md) lays out, the national environment is an unidentified band rather than an estimate, and Senate control sits inside it: P(Democratic control) runs from 27.2% to 54.5% across the swept assumption — unchanged by everything below, because Senate races are statewide and have no district boundaries to get wrong. It crosses the coin flip. There is no number in that range I could publish without the assumption doing the talking, and no defensible way to pick a point on it.

![Chamber-control probability across the swept shrinkage assumption](../figures/fig-06-shrinkage-band.png)

**The party crosswalk is two seats wrong, and it says so.** From the returns, the projection derives 67 Senate holdover seats not up in 2026, 32 of them Democratic-held, plus 13 currently-Democratic seats on the ballot — a derived caucus of 45 of 100.

The actual Democratic caucus is 47.

The report prints this, in the output, as a note: *"2 seats short of the actual Democratic caucus — unresolved party crosswalk."* It is a visible arithmetic error in a quantity that any reader could check in thirty seconds. The cause is known — deriving party from certified returns does not cleanly handle appointments, party switches and independents who caucus with a party — and it is an open backlog item.

Two seats out of a hundred, in a chamber whose control the band already could not resolve. Publishing a Senate probability on top of a Senate seat count I know to be wrong would be its own small scandal.

And underneath all three: the incumbency layer assumes **renomination for everybody**. 458 sitting members have a 2026 FEC filing; 10 were not found in the roster, and absence in that roster is not the same as retirement — it misses most departures. Primaries are not compiled at all. The model is projecting a chamber of candidates it has not confirmed are running.

## The assumptions doing the heavy lifting — in the decision, not the model

There is a version of this post where I have found a devastating flaw and heroically suppressed a bad number. That is not what happened, and I want to be accurate about the epistemics.

**The boundary objection is the one I no longer have.** When this post was first drafted, the argument was that I could not state the forecast's error: 173 seats sat on territory the model could not vouch for, carrying an uncertainty term I had not measured and could not bound. That was true, and it is not true any more. The register says which seats moved, the routing discards their stale priors, and the cost is now a number rather than a worry.

Here is that number. Feeding sourced boundaries into the projection widened the House 90% seat range from an average of **178 seats to 235** — a 32% increase in stated uncertainty — because 173 seats swapped a fitted prior (sigma 0.112) for a state-lean fallback (sigma 0.145). At the low end of the shrinkage band the range went from 146–318 seats to **117–352**.

That is the shape of an honest correction: the forecast did not get better, it got *wider*, and the widening is the part that was previously missing rather than wrong. A model that knows it is ignorant about 40% of the chamber produces a less impressive interval than one that doesn't, which is exactly why the second kind is more common.

One counter-intuitive result fell out of it, and I want to record it because I did not predict it. The House **control probability band narrowed slightly** — from 51.8–79.2% to 53.6–77.0% — even as the seat range widened by a third. Wider per-seat uncertainty pulls extreme probabilities toward the coin flip from both directions, so a less certain seat forecast can produce a *more* stable control probability. Seat-count precision and probability precision are not the same quantity and do not have to move together.

**So why is this still not published?** Because two objections survived. The Senate band straddles 0.5 and no amount of boundary work touches it — Senate races are statewide. And the party crosswalk is two seats wrong, below. Boundaries were the largest blocker and are now the smallest.

**The second assumption is about what publication does.** A number in a report I can revise. A number on the internet with my name on it becomes a citation, gets screenshotted without its band, and outlives every caveat attached to it. In *The Boys*, Vought's entire business model is the distance between a measured quantity and the number that reaches the public, and the distance is created almost entirely by stripping context that was technically present in the source. I do not need a PR department to do that to my own work; a chart with a big number and a small footnote will do it unassisted.

## What I would change, in order

1. ~~**Verify the register.**~~ Done — every row confirmed against an official state or court record, which is what surfaced the Alabama and Missouri corrections above.
2. ~~**Split litigation risk from boundary confidence.**~~ Done. `boundary_confidence` now describes territory alone; `litigation_risk` is a separate flag the report prints and the routing ignores. Missouri's live case no longer costs it eight valid priors. A test flips only that flag and asserts the priors come back byte-identical.
3. ~~**Wire the register into the projection.**~~ Done — and it moved the backtest, deliberately. Alabama, Louisiana and North Carolina each changed maps between 2022 and 2024 too, so the register applies to history as well as forward. That cost 27 district-cycles their lag and dropped model seat coverage from 89.9% to 84.4%. It was landed as two commits — plumbing with history pinned, then the flip — so the refit stayed attributable. House MAE moved by −0.000088 and president and Senate came back bit-identical, which is how I know the change touched only what it was supposed to.
4. **Build the vote transfer and backtest it.** This is now the whole game. Allocate 2024 precinct results onto 2026 boundaries via census blocks, with three separate confidence components per district — unsplit share, old-district-majority share, ungeocoded share — that are never collapsed into a single score. Then backtest it on Virginia 2020→2022, where the answer is already known, against two comparators: no prior at all, and the state-lean fallback. The sigma for a transferred prior comes out of that backtest **measured**, not assumed. Until that number exists, a redrawn seat has no honest prior.

Only then does the House band get re-reported, with the redrawn-seat count and its treatment stated in the text.

## The broader lesson

The painted table at Dragonstone is a beautiful map of a kingdom that no longer looks like that. Everyone in the room plans against it anyway, because it is the map they have, and because the alternative is admitting they are planning against nothing.

Analytical systems have exactly this failure mode, and the pressure runs entirely one direction. There is always a deadline, always a stakeholder, always a perfectly good number sitting right there. "We can't measure this yet" is the least rewarded sentence in the discipline. Nobody was ever promoted for a null result, an inconclusive test, or a forecast withheld.

Which is precisely why the refusal has to be **engineered in advance**, before anyone knows which way the result points. Mine is a function that raises `UnverifiedBoundaryError` by default, a national-environment estimator that returns `status = "band"` and a required `shrinkage` argument with no default, a validator that will not let an unidentified quantity claim otherwise, and a report that prints its own boundary-confidence counts in the footer whether or not I want to read them. None of that was built in the moment of deciding. In the moment of deciding I wanted the number, like everybody does.

A model's most valuable output is occasionally a refusal. But refusals do not survive contact with a deadline unless they are load-bearing infrastructure — a raised exception, a required argument, a printed count — rather than a resolution.

So: the model produced a 2026 projection. It says Democrats are favoured for the House across every assumption in the band, and that the Senate is unresolvable. It is not published as a forecast.

But the reason has changed while I was writing, and I would rather say so than leave the original framing standing. Three of the four items above are done. The boundary problem — the one this post was built around — went from an unbounded unknown to a measured 32% widening of the interval. What is left is a Senate band that no boundary work can fix and a two-seat arithmetic error in the party crosswalk.

The refusal was right when the error could not be stated. Now that it can, the honest position is narrower and less comfortable: the House band is defensible and the Senate one is not, and the decision about what to do with that is a judgement rather than a constraint. The infrastructure did its job — it held the line until the evidence arrived, and then it got out of the way.

That is the least glamorous critical path I have ever written down, and it is the real one.

---

*Figure generated by [`blog/figures/make_figures.py`](../figures/make_figures.py) from `reports/national_environment_2026-09-15.json`, a committed output of a real build. Projection output: `reports/projection_2026.txt`. **The plan-version register described here was verified row-by-row against official state and court records on 2026-09-30, but no code in the forecasting stack reads it yet** — the projection still flags all 435 seats `unverified`, which is the subject of this post. Data: [MIT Election Data and Science Lab](https://electionlab.mit.edu/) certified federal returns 1976–2024; Federal Election Commission filings (aggregate use only); compiled special elections with per-row sourcing. This project is nonpartisan, models probability and uncertainty rather than preferred outcomes, and treats redistricting as an audit question — never a map-drawing one.*

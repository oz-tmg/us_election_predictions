# Public writing

Everything in this directory is written for publication outside the repository. Nothing
else in the project is — reports, plans and backlogs are working documents that assume a
reader who already has the context.

Two rules govern this directory:

1. **Every number traces to a committed build artefact.** Posts cite `reports/*.json`,
   `reports/*.md` or `data/reference/*.csv`; figures are generated from those same files by
   [`figures/make_figures.py`](figures/make_figures.py), which a reader can run. No number
   is retyped from memory and no figure is drawn by hand.
2. **One post is a live prediction, and it says so.** Posts 1–4 are about historical
   backtests; post 5 is an account of why the 2026 projection was withheld in September and
   post 7 is that projection, published on 2026-11-03 before any vote was counted, as the
   full sensitivity band with the September seal beside it. Historical, modelled and
   certified quantities are labelled distinctly, in the prose and on every figure.

Written in first person for Alex Oswald (Savepoint Analytics). Every claim is sourced from
the repository's own documentation and build outputs; nothing about motivation or process
is invented. Review the voice before publishing.

## The series

The posts are independent essays that cross-reference each other. Read in order they build
an argument — a forecast is a promise, promises are kept or broken in the error structure,
some parameters cannot be estimated at all, exclusions are levers, and the conclusion is
sometimes a refusal.

| # | Post | Core statistical idea | Figures | Status |
|---|---|---|---|---|
| 1 | [A Forecast Is a Promise, and Most of Them Are Broken](posts/01-a-forecast-is-a-promise.md) | Proper scoring rules, reliability curves, interval coverage, holdout design | 1, 2, 3 | **Ready** |
| 2 | [The Control Rods All Had Graphite Tips](posts/02-the-control-rods-all-had-graphite-tips.md) | Correlated error, design effect, cluster randomisation, effective sample size | 4 | **Ready** |
| 3 | [The Parameter That Wasn't There](posts/03-the-parameter-that-wasnt-there.md) | Identification vs. sample size, sensitivity bands, pre-registration, data vintage | 5, 6 | **Ready** |
| 4 | [Thirty-Four Races That Do Not Add Up](posts/04-thirty-four-races-that-do-not-add-up.md) | Exclusion criteria as researcher degrees of freedom, sensitivity analysis | 7 | **Ready** |
| 5 | [The Forecast I Am Not Publishing](posts/05-the-forecast-i-am-not-publishing.md) | Knowing when the instrument does not measure the thing; engineering a refusal, and retiring it when the evidence arrives | 6 | **Ready — postscript added 2026-11-03** |
| 6 | [The Map Is Not the Territory, and Neither Is the District Number](posts/06-the-map-is-not-the-territory-and-neither-is-the-number.md) | Sourcing versus recall; training-data edges; corrections that widen error bars | 8 | **Ready — publish before 2026-11-03** |
| 7 | [What the Model Says, and How I Will Grade It](posts/07-what-the-model-says-and-how-i-will-grade-it.md) | Publishing a band rather than a point; a public post as a pre-registration; scoring two frozen runs side by side; seat-level honesty tiers | 9, 10 | **Ready — publish 2026-11-03 before polls close** |

### Post 5 was revised when its own premise expired

The post was written while all 435 House seats carried `boundary_confidence = "unverified"`
and the projection could only run behind an `allow_unverified` opt-in. Both are now false:
the register supplies sourced confidence for every seat (262 `unchanged`, 173 `redrawn`),
and the opt-in has been deleted from `scripts/project_2026.py`.

Rather than patch the numbers around the old framing, the argument was re-grounded. The
boundary objection — "I cannot state this forecast's error" — is retired and replaced with
the measured cost of fixing it: the House 90% seat range widened from an average of 178 to
235 seats (+32%), while the control-probability band *narrowed* from 51.8–79.2% to
53.6–77.0%. The post now ends on the uncomfortable version: two of the original objections
survive, the boundary one does not, and what remains is a judgement rather than a
constraint. That is a better post than the one it replaced, and it is only available
because the work got done.

### Post 6 is time-sensitive

It is the only piece in the series that decays: the register is news until 2026-11-03 and
history afterwards. If one post goes out this month, this is the one.

### How post 6 came about

The plan-version register was **verified row-by-row on 2026-09-30** against official state
and court records. Post 5 was revised accordingly: it now states the nine-state, 173-seat
count as a finding rather than a lead, and reports the two corrections verification
produced (Alabama restored its struck-down 2023 legislative plan rather than enacting a new
map; Missouri's 2022 plan governs the general and its cycle range must stay open).

Verification unblocked the sixth post, now written: nine states redrew for 2026 (173 of 435
seats, 39.8%); Missouri enacted a map it is not using; Alabama restored one that had been
struck down; Georgia, New York and Virginia did not redraw despite expectations. It keeps
the register's own discipline — what was enacted, by whom, and where it says so, with no
state grouped by motive — and its second half is about what the correction *cost*: a 32%
wider seat interval, which is the part nobody wants to publish and the reason it is worth
publishing.

## Figures

Generated by [`figures/make_figures.py`](figures/make_figures.py) (requires the `viz`
extra: `pip install -e '.[viz]'`). Every figure carries its time period, geographic unit,
data source, snapshot date, an uncertainty note, and a historical-vs-modelled label, per
`CLAUDE.md` §6. The categorical palette is validated for colour-vision deficiency
separation; series identity is never carried by colour alone, and every figure has a
companion table in the post body.

| File | Shows |
|---|---|
| `fig-01-baseline-vs-naive.png` | MAE of each baseline against naive persistence, three offices |
| `fig-02-reliability-curve.png` | Reliability curves, faceted by office, marker area ∝ bin count |
| `fig-03-interval-coverage.png` | 90% and 95% interval coverage against nominal |
| `fig-04-correlated-vs-independent.png` | The same 435-seat simulation under two correlation structures |
| `fig-05-swing-ratio-by-era.png` | Swing ratio by redistricting era, with the 2022 era unidentified |
| `fig-06-shrinkage-band.png` | Chamber-control probability and House seat range across the swept assumption |
| `fig-07-quarantine.png` | The 34 quarantined races by descriptive reason |
| `fig-08-redrawn-and-its-cost.png` | Seats on new territory for 2026, and the interval widening that admitting it caused |
| `fig-09-sealed-vs-current.png` | The September 30 seal beside the October 29 run, both chambers, every assumption |
| `fig-10-contestable-seats.png` | Every Senate race and the 47 model-informed contestable House seats, each as its own band across the sweep |

## Attribution required on publication

Reproduce these lines wherever a post is published:

- **MIT Election Data and Science Lab** — certified U.S. federal returns, 1976–2024.
  <https://electionlab.mit.edu/>
- **U.S. Census Bureau** — American Community Survey 5-year estimates (vintage 2023);
  TIGER/Line Shapefiles (2022 tabulation blocks, 2023 118th-Congress districts, 2024
  boundaries); Block Assignment Files. Public domain; cited because the chain of custody
  matters, not because the licence demands it.
- **Federal Election Commission** — candidate and committee filings. Aggregate use only;
  contributor fields are never used for solicitation, list-building or targeting.

**Mandatory the moment any post uses Redistricting Data Hub data** (registered 2026-09-30;
terms at `docs/terms_and_conditions/redistricting-datahub-data-download.md`). RDH requires
these strings verbatim, and its licence is noncommercial, nonpartisan and explicitly
anti-gerrymandering:

- Analysis: *"This analysis was conducted using data from the Redistricting Data Hub."*
- Map: *"This map was created using data from the Redistricting Data Hub."*
- Reposting data: *"This data was obtained from the Redistricting Data Hub."*

**Mandatory the moment any post uses the FiveThirtyEight polling archive** (NE-000,
answered 2026-10-02; terms at
`docs/terms_and_conditions/poll-topline-redistribution-terms.md`):

- *"Data from FiveThirtyEight, used under CC BY 4.0."*

**YouGov is available non-commercially, with one open question.** Its Public Data License
grants CC BY-NC 4.0, and this project is non-commercial, so the grant applies and the licence
states that permitted non-commercial use — "academic research", unpaid publication — needs no
permission. Required attribution, verbatim, plus a link to the original source:

- *"Source: YouGov plc, [Year], © All rights reserved"*

Two caveats attach. The licence is **copyleft** — "any modified or remixed work must be
licensed under the same terms (CC BY-NC 4.0)" — which costs nothing for work that is never
sold but should be stated where a derived figure is published. And one sentence in its
"Additional restrictions" section bars using the data to "train, fine-tune, or develop"
AI/ML, stated to apply independent of the licence; `docs/terms_and_conditions/` sets out why
that most likely targets training corpora rather than a poll average, and why one email to
legal@yougov.com would settle it before a post leans on the data.

**The Roper Center remains closed.** Its subscriber agreement excludes "compilations or
manipulations of data or datasets" from permitted derivative works, so a stored topline
panel is the excluded category regardless of commercial status.

## Editorial boundaries

These are not stylistic preferences. They are the project's operating rules, and they apply
to public writing more strictly than anywhere else:

- Nonpartisan throughout. The posts model probability and uncertainty; they do not argue
  for an outcome, and framing, language and source selection stay neutral.
- **The 2026 projection is published as a band, never as a point** (decision 2026-11-03,
  reversing 2026-09-30). The September decision withheld the projection because 173 seats
  rested on a state-lean fallback, the Senate band straddled the coin flip, and the party
  crosswalk was two seats wrong. By October 29 the crosswalk reconciled against the official
  roster, 38 Texas seats carried a measured transferred prior, and a backtest-gated open-seat
  specification moved the Senate band to 0.48–0.79. The frozen October 29 run
  (`reports/refresh_2026-10-29/`, final in `reports/comparison_set_2026-11-03.json`) is
  published as the project's prediction under four conditions: every row of the shrinkage
  sweep appears wherever any row appears; the September 30 seal is shown beside it and
  scored beside it, never replaced by it; the Senate is described as a lean that crosses one
  half at the most conservative assumption, not as resolved; and the registration's scoring
  rules apply unchanged to both runs. The publication itself, timestamped before polls
  closed, is the public seal. The private seal (`reports/preregistration_2026-11-03.*`) is
  untouched.
- Close races look close. No probability is sharpened to carry a storyline.
- Unofficial results, calls, estimates and certified returns are labelled distinctly and
  never share a sentence without one.
- Redistricting is treated as an audit and record-keeping question. The register records
  what was enacted, by whom, and where it says so; it groups no state by motive, and a
  simulated map can show consistency with an objective but never proves intent.
- No individual-level data appears anywhere: no voter records, no person-level scores, no
  inferred attributes. Every figure is at state, district or race level.

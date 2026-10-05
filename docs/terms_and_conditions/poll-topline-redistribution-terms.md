# Poll topline redistribution terms — the NE-000 evidence file

_Captured 2026-10-02 by reading each source's published terms. Quotations are verbatim from
the pages cited; follow the link for the authoritative current text, which can change
without notice._

`docs/national-environment-plan.md` lists **NE-000 — "Poll redistribution terms answered"**
as a human gate on NE-003, because `build_p2.py` sets `redistribution_allowed=synthetic`
(i.e. `False` for any real poll) and nothing may store a real topline until the question is
answered in writing. This file is the reading. The decision it supports is recorded in
`docs/dataset-registry.md` § "NE-000: poll topline redistribution".

## What is actually being asked

Three separable permissions, which the sources grant and withhold differently:

1. **Store** a topline (pollster, field dates, sample size, population, Dem/Rep numbers) in
   a database in this repository.
2. **Model** on it — i.e. fit or calibrate a forecast, which several terms treat as
   "machine learning" or "AI model development" whether or not that is what a regression is.
3. **Redistribute** it — publish the stored table, or a derived average, as a data product.

A source can permit (1) and forbid (2). One of them does, explicitly.

---

## YouGov — re-read in full 2026-10-04, and the first reading was wrong in one way that matters

> **Correction.** The 2026-10-02 reading of this licence came from a summarised fetch, not
> the raw page. The quotations in it were accurate, but two things were not: the grant was
> not identified as a standard Creative Commons licence, and the conclusion was stated as
> "refused, structurally." It is not structural. The licence names an address for exactly
> this request. What follows is from the raw page text.

Public Data License: <https://yougov.com/en-gb/about/terms/public-data-license> and
<https://yougov.com/en-us/about/terms/public-data-license> — identical text, **last updated
07 March 2025**, fetched 2026-10-04. Website terms: last updated 18 December 2025.

### The grant is CC BY-NC 4.0

> "We provide the data available on our public websites (the "Licensed Data") under the
> Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0) license."

Permitted, verbatim:

> "✅ Use, share, and adapt the Licensed Data for non-commercial purposes (e.g. academic
> research, journalism, critique, personal blogs, and newsletters)."

> "✅ Modify and remix the Licensed Data, as long as you provide appropriate attribution to
> us and a link to the original data source. **Any modified or remixed work must be licensed
> under the same terms as this license (CC BY-NC 4.0).**"

Refused under the grant, verbatim:

> "❌ Use the Licensed Data for **purely commercial purposes** (e.g., resale, AI model
> development, or integration into commercial datasets) **without our prior written
> consent**."

Note what that bullet actually does: "AI model development" is an *example* of a purely
commercial purpose, and the whole bullet is conditioned on absence of consent. Read alone, it
would leave room for a non-commercial forecaster.

### But a second, independent section closes that room

> "**Additional restrictions on AI & automated data extraction.** While the Licensed Data is
> available under CC BY-NC 4.0, the following additional restrictions apply:
>
> **AI model training & machine learning.** You may not use the Licensed Data to train,
> fine-tune, or develop artificial intelligence (AI), machine learning (ML), or large
> language models (LLMs).
>
> **Automated scraping & crawling.** You may not use bots, crawlers, or automated scripts to
> extract or copy the Licensed Data without our express written permission.
>
> **Aggregation into commercial datasets.** You may not incorporate the Licensed Data into
> any dataset, database, or repository for commercial AI applications, **predictive
> analytics**, or resale.
>
> **These restrictions are independent of the CC BY-NC 4.0 license and apply to any use of
> the Licensed Data.**"

And the TDM section:

> "We explicitly reserve our rights to opt out of text and data mining (TDM) for machine
> learning purposes. Any use of the Licensed Data for automated data mining is prohibited
> unless expressly authorised."

### Reading it against the obvious objection

The objection is a good one and it is half right: clauses like this are normally aimed at
(a) privacy exposure from individual-level inference and (b) stopping third parties from
rebuilding the publisher's product. A nonpartisan aggregate forecast does neither.

**The motive reading is almost certainly correct, and YouGov's own site is the evidence.**
The same navigation that links this licence also sells *Profiles API & MCP* — "Ingest YouGov
Profiles data directly into your systems, AI models, agentic workflows" — and *BrandIndex
API* — "Infuse BrandIndex data directly into your in-house systems, AI models, and
solutions" — and *Parallax*, "AI twins answer all your questions instantly." YouGov monetises
AI ingestion and sells synthetic respondents. The AI clause protects a product line. That is
exactly the competitive motive, not a privacy one.

**But three things stop that from being a defence here.**

1. **Nothing in the clause is privacy-scoped.** There is no individual-level language in it,
   and there could not usefully be: the Licensed Data is published aggregate results with no
   respondent records. "We are not connecting it to individuals" is true and is not the
   condition the clause sets. The privacy rationale is simply absent from the text.
2. **The ML bullet carries no commercial qualifier**, unlike the two bullets either side of
   it, and the section closes by saying the restrictions "apply to **any use**." That
   sentence is written to defeat precisely the non-commercial defence.
3. **There are two independent hooks, not one.** Even granting the argument that a
   hierarchical regression is not "AI/ML" in the sense intended, the third bullet separately
   names **"predictive analytics"** — which an election forecast is, without strain.

And if the competitive motive *is* the operative one, it points against this project rather
than for it: a forecasting product built on their toplines sits closer to competing with
what they sell than any privacy concern would.

### Two further issues that are not about AI at all

**Is this project "non-commercial"?** CC BY-NC 4.0 defines NonCommercial as "not primarily
intended for or directed towards commercial advantage or monetary compensation." Savepoint
Analytics is a commercial entity, and `PROJECT_CONTEXT.md` §2 says this vertical "creates
optionality toward future paid campaign/civic work." The blog is unpaid public research and
looks NC-eligible; the platform's purpose is less clear-cut. This question exists
independently of the AI clause and would survive any AI permission.

**The licence is copyleft.** "Any modified or remixed work must be licensed under the same
terms as this license (CC BY-NC 4.0)." If toplines entered the stack and a derived forecast
counts as a modified or remixed work, the project's own outputs would inherit CC BY-NC — the
same share-alike hazard flagged below for Wikipedia, sitting inside this licence too. Whether
a forecast is a "remix" of an input dataset is arguable; that it is a hazard worth asking
about is not.

### The correction that matters most: it is waivable, and nobody has asked

> "**Contact & permissions.** If your intended use falls within the permitted non-commercial
> activities outlined in these terms, you do not need to seek permission. This includes
> personal blogs, unpaid newsletters, academic research, and standard journalistic reporting.
>
> For commercial use requests **or AI-related permissions**, please contact us at
> legal@yougov.com."

So the position is **not permitted by default, and explicitly available on request** — not
closed. The earlier "structural" framing was wrong. A written grant from legal@yougov.com
would convert this from a reading of ambiguous text into a document, and the ask is
unusually easy to say yes to: nonpartisan, public-interest, attributed in their required
form, no republication of whole datasets, no resale, no synthetic respondents, no overlap
with Profiles, BrandIndex or Parallax. A draft request is at
`docs/terms_and_conditions/yougov-permission-request-draft.md`.

Independent of any permission, the **scraping clause survives**: collection would have to be
manual, because "bots, crawlers, or automated scripts" need express written permission even
for otherwise-permitted use.

## Roper Center — also closed, for a different reason

<https://ropercenter.cornell.edu/terms-and-conditions> (fetched 2026-10-02)

Access requires a "Subscriber Agreement". Permitted derivative works are limited to:

> "original, written editorial narratives, accompanied by limited citations of supporting
> data in tabular or charted form. Raw data, as well as any compilations or manipulations
> of data or datasets, are excluded."

And:

> "Redistributing or monetizing the Content in any manner other than the creation of
> Derivative Works as allowed."

**Reading.** A stored topline panel *is* a compilation of data, which is the excluded
category. Roper is an excellent archive and is not a route to a modelling table.

## Pew Research Center — permissive, but not a generic-ballot source

<https://www.pewresearch.org/about/terms-and-conditions/> (fetched 2026-10-02)

> "you may access, print, copy, reproduce, cite, link, display, download, distribute,
> broadcast, transmit, publish, license, transfer, sell, modify, create derivatives of, or
> otherwise exploit the Content"

Bounded by:

> "Under no circumstances may the Content be reproduced in principal part, mirrored,
> catalogued, framed, displayed simultaneously with another site or otherwise republished
> in its entirety or in principal part without the express written permission"

> "You must also provide proper attribution to the Center in connection with your use of
> any Content with express reference to the Center"

> prohibits use "in any manner that implies, suggests, or could otherwise be perceived as
> attributing a particular policy or lobbying objective or opinion to the Center"

**Reading.** Unusually permissive, including commercial use and derivatives. Pew does not
run a regular congressional generic ballot, so this matters for context and approval
series rather than for NE-003's estimator. The "principal part" limit means citing
individual results, never mirroring a Pew dataset wholesale. The no-implied-endorsement
clause aligns with CLAUDE.md §2 and costs this project nothing.

## FiveThirtyEight — the licence is right and **the data is gone**

Repository: <https://github.com/fivethirtyeight/data> · LICENSE fetched 2026-10-02 reads
`Attribution 4.0 International`, and the repository states:

> "Unless otherwise noted, our data sets are available under the Creative Commons
> Attribution 4.0 International License, and the code is available under the MIT License."

CC BY 4.0 permits storage, modelling, commercial use, derivatives and redistribution, with
attribution, and is **irrevocable** — a lawfully made copy stays licensed even if the
publisher withdraws the original.

**But the live feed is dead.** Every URL in `polls/README.md` points at
`projects.fivethirtyeight.com/polls-page/data/…`. Checked 2026-10-02:
`generic_ballot_polls.csv` returns `302` and follows to `https://abcnews.com/politics`,
serving an HTML page, not a CSV. ABC closed FiveThirtyEight in March 2025. `polls/` is no
longer in the GitHub tree either.

A third-party mirror made while the data was published does remain:
<https://github.com/simonw/fivethirtyeight-polls> — `LICENSE` present, `README.md` states
it mirrors `fivethirtyeight/data/polls` and that "They license it under Creative Commons
Attribution 4.0 International license". `generic_ballot_polls.csv` is in the repository
root and carries `cycle, pollster, fte_grade, sample_size, population, methodology,
start_date, end_date, url, dem, rep, ind` — the fields `polling/schema.py` wants, including
the per-row `url` that makes each topline independently citable.

**Reading.** This is the one route that cleanly permits all three of store, model and
redistribute. It is **historical only**: the mirror stops when the upstream stopped, so it
can satisfy NE-003's backtest requirement ("at least one historical cycle backtested") and
cannot supply a 2026 live estimate.

## Wikipedia generic-ballot tables — permitted, but share-alike is contagious

Wikipedia content is CC BY-SA 4.0. Share-alike would oblige this project to license any
redistributed derivative dataset under CC BY-SA, which is a constraint on the *project's*
outputs rather than on its inputs. Flagged, not recommended: the obligation outlives the
convenience.

## Individual pollster releases — the live route, and it is hand compilation

A single poll's topline is a set of facts: who polled, when, how many, and the numbers.
Under US law a compilation of facts attracts copyright only in its original selection and
arrangement (*Feist Publications v. Rural Telephone Service*, 499 U.S. 340 (1991)), and
individual facts attract none. What binds instead is **contract**: a site's terms of use,
accepted by the person who accesses that site. YouGov's prohibitions above are of that
kind.

So the live path is the one `docs/special-elections-sourcing.md` already uses for specials:
compile by hand from each pollster's own release, one row per poll, each carrying its
`source_url` and `retrieved_on`, and cite per row. AAPOR's disclosure standard (Code of
Professional Ethics & Practices §III.A) requires a releasing pollster to publish sponsor,
population, mode, field dates, sample size and margin of error, which is why the fields the
schema needs are reliably present in a public release.

This is slow and it is auditable, which is the same trade `special_elections_compiled`
makes.

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

## YouGov — the restrictive case, and it is decisive for the direct route

Website terms: <https://yougov.com/en-us/about/terms/website> (fetched 2026-10-02)

> "systematically scrape, crawl, harvest, retrieve, or otherwise gather by electronic means
> any data or other content from our sites to copy, create, acquire or compile … a
> collection compilation, database directory or similar."

> "modify, copy, reproduce, create derivative works, republish, display, upload, post,
> transmit, or distribute in any way the content, materials and information made available
> on our site except in accordance with the Public Data License"

Public Data License: <https://yougov.com/en-gb/about/terms/public-data-license> (fetched
2026-10-02). It **permits** non-commercial use, sharing and adaptation, and use in
commercial journalistic content, with attribution. It **prohibits**:

> "You may not use the Licensed Data to train, fine-tune, or develop artificial
> intelligence (AI), machine learning (ML), or large language models"

> "purely commercial purposes (e.g., resale, AI model development, or integration into
> commercial datasets)"

> "You may not incorporate the Licensed Data into any dataset, database, or repository for
> commercial AI applications"

Required attribution, where use is permitted:

> "Source: YouGov plc, [Year], © All rights reserved"

**Reading.** The Economist/YouGov weekly generic ballot is the most frequent US series and
the one a 2026 live estimator would most want. Collecting it from YouGov's own site is
**not available to this project**: Savepoint Analytics is a commercial entity, the
prohibition on ML/model development is explicit, and a forecasting model is squarely what
the clause describes whether or not one calls a hierarchical regression "AI". The
scraping clause closes the automated route independently. This is a clear no, not a
judgement call.

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

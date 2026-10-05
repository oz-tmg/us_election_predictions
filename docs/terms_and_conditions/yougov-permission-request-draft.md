# Draft permission request — YouGov Public Data License

_Drafted 2026-10-04. **Not sent.** Sending it is the project owner's decision, and the
address comes from the licence itself: "For commercial use requests or AI-related
permissions, please contact us at legal@yougov.com."_

## Why ask rather than decide

Most of what this draft was written for has since resolved: the project is non-commercial
and unaffiliated, so CC BY-NC's grant applies and the licence says permitted non-commercial
use needs no permission. One sentence is left — the unqualified bar on using the data to
"train, fine-tune, or develop" AI/ML, stated to apply independent of the licence. The
contextual reading is that it targets training corpora, not a poll average; that reading is
reasonable and it is an interpretation, and reasoning about what YouGov probably meant is
not a licence. A reply from legal@yougov.com is. One email, and a "no" leaves the position
already held.

Three things to decide before sending, because they change the ask:

1. **Which use is being requested** — the historical backtest only, the live 2026 estimator,
   or both. Asking for the narrower thing is more likely to succeed and may be all that is
   needed, since the backtest can run on the FiveThirtyEight archive instead. With the
   non-commercial question resolved there is less reason to narrow it than there was.
2. ~~Whether to raise the NonCommercial question.~~ **Resolved 2026-10-05:** the project is
   non-commercial and unaffiliated, so the grant's own non-commercial permission applies and
   the licence says no permission is needed for it. Do **not** raise it as a question — doing
   so would invite doubt about something the licence already answers. State it as a fact.
3. ~~Whether the copyleft condition is acceptable.~~ **Resolved:** inheriting CC BY-NC 4.0
   costs nothing for work that is never sold. Mention it only as a commitment, not a query.

## Draft

> **Subject:** Public Data License — permission request for nonpartisan election forecasting
> (aggregate toplines, no redistribution)
>
> Dear YouGov Legal team,
>
> I am writing under the "Contact & permissions" provision of your Public Data License
> (last updated 7 March 2025), which directs AI-related permission requests to this address.
>
> **Who we are.** I run an independent, non-commercial, nonpartisan election-analysis
> project that publishes forecasting methodology and calibration results openly. It is not
> part of any company, nothing it produces is sold, and no part of it is used commercially.
> Its own operating rules require nonpartisanship and prohibit individualised political
> targeting and any use of data for solicitation or list-building.
>
> **What we would like to use.** Published congressional generic-ballot toplines — pollster,
> field dates, sample size, population and the headline party numbers. Aggregate figures as
> published. No respondent-level data, and none exists in the public releases.
>
> **What we would do with them.** Include each topline as one row in a cited time series, and
> use the series as an input to a published statistical forecast of national House vote
> share. Each row would carry its source URL and your required attribution, "Source: YouGov
> plc, [year], © All rights reserved", with a link to the original.
>
> **Why I am writing at all.** The non-commercial grant plainly covers this use, and your
> terms say such use needs no permission. I am writing only because of one sentence in the
> "Additional restrictions on AI & automated data extraction" section — "you may not use the
> Licensed Data to train, fine-tune, or develop artificial intelligence (AI), machine
> learning (ML), or large language models" — which is stated to apply independent of the
> licence. Reading that section alongside its scraping bullet and your text-and-data-mining
> opt-out, I take its target to be ingestion of your data as a training corpus rather than
> the use of a published topline as an input to an ordinary statistical model. I would rather
> have that confirmed than assume it.
>
> **What we would not do.** No republication of full datasets. No resale or sublicensing. No
> training of generative models, no synthetic respondents or simulated panels, and no product
> that substitutes for Profiles, BrandIndex, Parallax or any YouGov service. No automated
> collection: we would transcribe published figures by hand. No implication of YouGov
> endorsement.
>
> **Our questions.**
>
> 1. Would you grant written permission for the use described above — aggregate published
>    toplines as an input to a published, attributed, nonpartisan statistical forecast?
> 2. Is my reading of the AI restriction correct — that it addresses training corpora and
>    model development rather than the use of published aggregate results as an input to a
>    statistical forecast? If it is not, I will not use the data.
>
> We are happy to accept conditions — a stated attribution format, a cap on how many of your
> toplines appear, a review of anything before publication, or a term limit.
>
> Thank you for considering it.
>
> [name, role, contact, project URL]

## If the answer is no, or there is no answer

Nothing in the project depends on this. The FiveThirtyEight CC BY 4.0 archive covers the
historical backtest, and the live estimator runs on hand-compiled toplines from other
pollsters' own releases. A refusal removes the single most frequent US series from the
average and is recorded as a declared limitation — which is what the current state already
assumes.

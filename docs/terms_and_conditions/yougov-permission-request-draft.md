# Draft permission request — YouGov Public Data License

_Drafted 2026-10-04. **Not sent.** Sending it is the project owner's decision, and the
address comes from the licence itself: "For commercial use requests or AI-related
permissions, please contact us at legal@yougov.com."_

## Why ask rather than decide

The Public Data License's AI section is broader than its evident motive
(`poll-topline-redistribution-terms.md`). Reasoning about what YouGov probably meant is not
a licence; a reply from legal@yougov.com is. The cost of asking is one email, and the
downside of a "no" is a position we already hold.

Three things to decide before sending, because they change the ask:

1. **Which use is being requested** — the historical backtest only, the live 2026 estimator,
   or both. Asking for the narrower thing is more likely to succeed and may be all that is
   needed, since the backtest can run on the FiveThirtyEight archive instead.
2. **Whether to raise the NonCommercial question too.** It is separate from AI and would
   survive an AI permission. Raising it invites a harder conversation; not raising it leaves
   a known gap. Recommendation: raise it, because discovering it later is worse.
3. **Whether the copyleft condition is acceptable** if granted on standard terms. "Any
   modified or remixed work must be licensed under the same terms (CC BY-NC 4.0)" could
   attach to derived forecasts. Ask for it to be addressed explicitly rather than assumed
   away.

## Draft

> **Subject:** Public Data License — permission request for nonpartisan election forecasting
> (aggregate toplines, no redistribution)
>
> Dear YouGov Legal team,
>
> I am writing under the "Contact & permissions" provision of your Public Data License
> (last updated 7 March 2025), which directs AI-related permission requests to this address.
>
> **Who we are.** Savepoint Analytics runs a public, nonpartisan election-analysis project
> that publishes forecasting methodology and calibration results. The work is research
> output, published openly and not sold. Our own operating rules require nonpartisanship,
> prohibit individualised political targeting, and prohibit any use of data for solicitation
> or list-building.
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
> **Why we are asking rather than relying on the non-commercial grant.** Your "Additional
> restrictions on AI & automated data extraction" section prohibits using the Licensed Data
> to "train, fine-tune, or develop" AI or ML, and separately prohibits incorporation into a
> repository for "predictive analytics", and states that these restrictions apply to any use.
> A statistical forecasting model is plainly within that language, whatever the intended
> target of the clause, so we do not think the non-commercial permission covers us and we
> have not proceeded on an optimistic reading.
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
> 2. Does your NonCommercial grant extend to research published openly and without charge by
>    a commercial entity, where the research itself is not sold? We would rather have your
>    view than assume.
> 3. If permission is granted, would the requirement that "any modified or remixed work must
>    be licensed under the same terms" attach to a derived forecast, or only to a
>    republication of the data itself?
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

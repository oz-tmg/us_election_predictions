# Licensed / Procurement Data Sources for U.S. Election Analytics

_Last updated: 2026-07-04_

This catalog tracks data sources that likely require procurement, licensing, membership, affiliation, campaign/party authorization, API contracts, or paid vendor agreements. These are the sources most likely to matter if the objective moves from public election analysis into serious campaign advisory, live election-night operations, voter targeting, paid-media intelligence, or district-specific polling.

---

## 1. Live election results, race calls, and election-night feeds

| Source / vendor | Category | What it provides | Why it matters | Procurement / access notes | Priority |
|---|---|---|---|---|---:|
| Associated Press Elections API | Live results and race-call infrastructure | Real-time national, state, and local election results from poll close to certification; AP classification system | Core for news-style election-night dashboards and reliable standardized live results | Commercial/API access through AP Developer; requires key/contract | High for news product; Medium for modeling |
| Decision Desk HQ API / feeds | Live results and election data | Live election results, race calls, turnout, election dashboards, historical data products | Alternative or supplement to AP for live results and forecasting workflows | Commercial data/feed relationship | High for live products |
| Edison Research / National Election Pool | Exit polls, election night survey, live election operations | Exit polls, election-night data, voter surveys, projections for media clients | Major media election-night interpretation | Procurement likely through media/client agreements | Medium to High for newsroom-style use |
| SSRS / The Voter Poll | Election survey / media product | Election-night voter survey used by major news organizations beginning with 2025 clients | Replacement/competitor layer for exit-poll-style electorate interpretation | Client-facing survey product | Medium |
| AP VoteCast client products | Election survey / media product | Voter survey and electorate composition products | Useful for media analysis and calls/explainers | Public-use files exist after elections, but client products are licensed | Medium |

---

## 2. Commercial voter files and modeled electorate data

| Source / vendor | Category | What it provides | Why it matters | Procurement / access notes | Priority |
|---|---|---|---|---|---:|
| Catalist | Progressive voter file / modeled data | National voter file, voter history, demographic/behavioral models, early/absentee vote dashboards | High-value for Democratic/progressive campaign targeting, turnout modeling, post-election autopsies | Client/partner/vendor access; ideological/client restrictions likely | High if working with progressive campaigns |
| TargetSmart | Democratic/progressive voter data | Voter file, registration trends, turnout/partisanship models, dashboards, outreach data | Campaign-grade data and dashboards for Democratic campaigns/advocacy | Vendor agreement; likely political-client restrictions | High if working with Democratic/progressive clients |
| L2 Political | Commercial voter file / consumer append | National voter file, voter history, demographics, consumer fields, model scores, phones/emails | Cross-partisan/commercial voter targeting and district analysis | Paid license; usage restrictions | High if independent/nonpartisan procurement is possible |
| Data Trust | Republican voter file | GOP-aligned voter file and modeled data | Campaign-grade Republican data layer | Access likely restricted to Republican/center-right clients | High if working with GOP campaigns |
| i360 | Republican/conservative data platform | Voter file, modeling, activism, targeting, data products | Campaign-grade conservative data and turnout/contact layer | Vendor/client access; likely ideological restrictions | High if working with GOP/conservative clients |
| State voter files via official request | Public-records but procurement-like | Official state voter registration and turnout files | Baseline for independent turnout/registration modeling | Fees, affidavits, permitted-use restrictions, PII handling; varies by state | High |
| Phone/email append vendors | Contact data | Phones, emails, address standardization, match keys | Needed for outreach modeling and campaign operations | Paid vendor agreement; consent/compliance concerns | Medium to High for campaigns |
| Consumer data vendors: Experian, Acxiom, Epsilon, TransUnion/Neustar-style products | Consumer/demographic append | Consumer attributes, household data, lifestyle segments, digital identity graphs | Augments voter file for targeting and persuasion models | Paid license; privacy/compliance review essential | Medium |

---

## 3. Campaign platforms and first-party operational data

| Source / platform | Category | What it provides | Why it matters | Procurement / access notes | Priority |
|---|---|---|---|---|---:|
| NGP VAN / EveryAction / SmartVAN | Campaign CRM / field | Canvass results, calls, texts, volunteer activity, contact history, survey responses, turf | Core Democratic/progressive field operations and closed-loop campaign analytics | Client/platform access; often campaign/party controlled | High for campaign advising |
| NationBuilder | Campaign CRM | Contacts, donations, outreach, web/email activity | Useful for smaller campaigns or civic orgs | Paid SaaS; data export depends plan/admin rights | Medium |
| Action Network | Advocacy/email platform | Email/SMS list behavior, actions, petitions, events, donations | Mobilization and list-growth analysis | Paid/organizational access | Medium |
| ActBlue campaign account data | Fundraising platform | Donations, recurring gifts, refunds, donor metadata, campaign downloads | Democratic fundraising analysis and donor segmentation | Campaign account/admin access; public FEC only gives partial view | High for Democratic fundraising work |
| WinRed campaign account data | Fundraising platform | Donations and donor behavior for Republican campaigns | GOP fundraising analysis and donor segmentation | Campaign account/admin access | High for Republican fundraising work |
| Peer-to-peer texting platforms: Scale to Win, GetThru, Hustle, RumbleUp, etc. | Outreach ops | Text sends, replies, opt-outs, contact status, scripts | Message testing, GOTV, persuasion, compliance | Paid platform access; campaign-owned data | Medium to High |
| Dialer/calling platforms | Outreach ops | Call attempts, contacts, results, scripts | Voter contact quality and field conversion | Paid platform access; compliance review | Medium |

---

## 4. District-specific polling and survey infrastructure

| Source / vendor | Category | What it provides | Why it matters | Procurement / access notes | Priority |
|---|---|---|---|---|---:|
| YouGov custom polling | Online survey panel | District/state/national surveys, message tests, MRP inputs | Strong for issue/message testing and public-opinion modeling | Paid custom survey or academic team content | High |
| Ipsos KnowledgePanel | Probability-based panel | National/state/custom survey samples | High-quality survey infrastructure | Paid survey procurement | Medium to High |
| SSRS | Survey vendor | Phone/web/address-based sampling; media election products | Strong survey operations and election products | Paid custom polling/client relationship | Medium to High |
| Siena College Research Institute | Pollster | High-profile public/private polling, often state/district | Credible topline polling and crosstabs | Public releases are open; custom/private work requires procurement | Medium |
| Marist, Quinnipiac, Monmouth, Suffolk, SurveyUSA, Emerson, Data for Progress, Navigator, Blueprint, etc. | Pollsters / survey orgs | Public or private state/district polling | Race context, issue salience, polling history | Microdata rarely public; custom work is paid | Medium |
| Roper Center membership / data services | Polling archive | Historical public opinion microdata and state collection | Deep polling archive and benchmarking | Institutional membership or data services arrangement | Medium |

---

## 5. Paid media, ad intelligence, and communications data

| Source / vendor | Category | What it provides | Why it matters | Procurement / access notes | Priority |
|---|---|---|---|---|---:|
| AdImpact | Political ad intelligence | TV, digital, radio, spending, creative tracking, future reservations, market-level spend | Very useful for campaign/news competitive intelligence | Paid license | High for serious campaign/media analytics |
| Kantar/CMAG-style political ad tracking | Political advertising intelligence | TV/radio/digital ad occurrences, creative, spend estimates | Longstanding media tracking and message analysis | Paid license | Medium to High |
| Vivvix | Ad intelligence | Cross-media ad creative and spend intelligence | Competitive media monitoring | Paid license | Medium |
| TVEyes / broadcast monitoring | Media monitoring | TV/radio mentions and clips | Earned media tracking, rapid response, ad verification | Paid license | Medium |
| Meltwater / Cision / Brandwatch / Talkwalker | Social and media listening | News/social mentions, sentiment, influencer analysis | Earned media and narrative monitoring | Paid SaaS; social API restrictions apply | Medium |
| X API paid tiers | Social media API | Post/search/stream access depending tier | Candidate/supporter discourse, virality, message diffusion | Paid API; terms/limits | Medium |
| TikTok Research API | Social media research | Access to TikTok public data for approved researchers | Youth/meme/influencer election discourse | Approval process; not campaign targeting | Medium |

---

## 6. Geospatial, demographic, and commercial enrichment data

| Source / vendor | Category | What it provides | Why it matters | Procurement / access notes | Priority |
|---|---|---|---|---|---:|
| Esri Business Analyst / ArcGIS Living Atlas premium layers | Geospatial/demographic | Demographics, consumer segments, business/commute/geospatial layers | Mapping, trade-area style district analysis, enrichment | Paid Esri subscription for premium features | Medium |
| Social Explorer | Demographic data platform | Census/ACS/CVAP and historical demographic exports | Quick demographic exploration and export | Subscription/license | Low to Medium if Census API is sufficient |
| Dave’s Redistricting / Maptitude for Redistricting / AutoBound Edge | Redistricting/geospatial tools | District maps, election data, demographics, plan analysis | Geospatial workflow, district composition, map analysis | Paid or freemium depending tool | Medium |

---

## Procurement decision matrix

| Objective | Must-have licensed/procurement data | Nice-to-have | Public fallback |
|---|---|---|---|
| Independent House-race forecasting | State voter files, if legally obtainable | Commercial voter file, district polling, AdImpact | CES + ACS/CVAP + MIT/OpenElections + FEC + public polls |
| Campaign advising | Voter file, campaign CRM/contact history, ballot-return data, polling/message tests | Consumer append, ad intelligence, phone/email append | Public returns and ACS are not enough for targeting |
| News election-night dashboard | AP or DDHQ live results feed | AP VoteCast/SSRS, AdImpact, historical AP data | Scraping official county/state sites, but high operational risk |
| Post-election autopsy | Voter file turnout, precinct returns, final FEC, campaign contact history | Catalist/TargetSmart/L2 modeled data | MIT/OpenElections + CES/Pew/AP VoteCast + ACS/CVAP |
| Paid-media strategy | AdImpact/Kantar/Vivvix, platform account data | Meta/Google/FCC scraping and creative classification | Meta/Google/FCC public archives |
| Persuasion/message analytics | District/state polling, survey experiments, ad account data, contact history | Social listening, focus groups | CES/Nationscape/Pew/ANES + public ads |

---

## Recommended procurement priority for Savepoint-style independent analytics

1. **State voter files for target states**: highest value for House-race turnout and electorate analysis, but handle PII and permitted use carefully.
2. **District-specific polling budget or survey partner**: needed for actual advising, especially close/open-seat races.
3. **AdImpact or comparable media intelligence**: valuable if analyzing campaign behavior, paid-media strategy, or news-facing race dynamics.
4. **Roper membership or institutional route**: useful for historical polling and public-opinion benchmarking.
5. **Commercial voter-file vendor**: only after target client segment is clear; access may depend on partisan alignment and budget.
6. **CRM/platform data access**: not something to buy speculatively; acquire through client work.

---

## Due-diligence checklist before buying data

- What exact fields are included?
- What is the geography and vintage?
- Is the data individual-level, household-level, aggregate, modeled, or sampled?
- Are there historical snapshots or only current-state records?
- Are PII fields included, and what are storage/compliance requirements?
- What use cases are prohibited?
- Can derived models be retained after license termination?
- Can outputs be published publicly, shown to clients, or used in marketing?
- Are there API limits, export limits, audit rights, or deletion obligations?
- Does the vendor permit nonpartisan/independent research use?

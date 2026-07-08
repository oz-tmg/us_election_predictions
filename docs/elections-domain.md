# U.S. Elections Domain Framework

_Last updated: 2026-07-04_

This document defines the conceptual framework for U.S. election analytics, with a focus on public analysis, news use cases, and eventual advisory work for U.S. House, Senate, presidential, gubernatorial, and state races.

---

## 1. Core election-analysis audiences

### News organizations

News-side election analysts are usually asked to answer:

1. **Who is likely to win?**
   - Forecasting before Election Day.
   - Race-call support after polls close.
   - Path-to-overtake analysis while vote remains outstanding.

2. **What vote remains?**
   - Where uncounted ballots are geographically located.
   - Whether remaining vote is early, mail, absentee, provisional, in-person, Election Day, overseas, or late-arriving.
   - Whether the reporting pattern is likely to be biased toward one party or candidate.

3. **What changed?**
   - Turnout shifts.
   - Persuasion/swing shifts.
   - Demographic coalition changes.
   - Geographic realignment.
   - Candidate- or issue-specific deviations from baseline partisanship.

4. **What can be called responsibly?**
   - Avoiding premature calls.
   - Distinguishing official certification from media projections.
   - Communicating uncertainty clearly.

5. **Are there anomalies?**
   - Reporting delays.
   - Outlier precincts or counties.
   - Ballot rejection/provisional rates.
   - Tabulation and reconciliation issues.
   - Unexpected turnout or ticket-splitting patterns.

### Political campaigns

Campaign-side analysts are usually asked to answer:

1. **Who should we contact?**
   - Base voters.
   - Low-propensity supporters.
   - Persuadable voters.
   - Donors.
   - Volunteers.
   - Ballot-request and ballot-return targets.

2. **Where should resources go?**
   - Field offices.
   - Candidate visits.
   - Door knocking.
   - Phones/texts/mail.
   - TV/radio/digital ad spend.
   - GOTV operations.

3. **What message works?**
   - Issue tests.
   - Candidate contrast tests.
   - Negative vs. positive messaging.
   - Local vs. national framing.
   - Identity, economic, cultural, and candidate-quality messages.

4. **Who has already voted?**
   - Remove already-voted voters from persuasion/GOTV universes.
   - Chase requested but unreturned absentee/mail ballots.
   - Monitor turnout gaps by party, geography, and modeled support.

5. **What happened after the election?**
   - Turnout vs. persuasion decomposition.
   - Field-contact conversion.
   - Paid-media efficiency.
   - Geographic and demographic erosion/gains.
   - Forecast calibration and model failure review.

---

## 2. Units of analysis

| Unit | Useful for | Major pitfalls |
|---|---|---|
| Individual voter | Campaign targeting, turnout models, contact strategy | PII, legal restrictions, no ballot choice, model bias |
| Household | Canvassing, mail, consumer append, family voting patterns | Household membership changes; privacy concerns |
| Precinct / VTD | Ground-level electoral geography, turnout shifts, maps | Precinct boundaries change; precincts split districts |
| Census block / block group / tract | Demographics and district composition | Census geography does not equal election precincts |
| County | County-level swings, early vote reporting, administration | House districts often split counties; ecological fallacy |
| Congressional district | House forecasts and district strategy | Districts change after redistricting; CD survey samples can be small |
| State | Senate, governor, presidential, ballot measures | Too coarse for House races |
| Media market / DMA | TV ad buying and news coverage | Crosses state/district lines |
| Digital audience segment | Ad targeting, creative tests | Platform opacity and delivery bias |

For U.S. House work, **congressional district and precinct/VTD are the most important geographies**. County-level data is useful context, but not sufficient because counties and congressional districts often overlap imperfectly.

---

## 3. Outcome variables

### Electoral outcomes

- Vote share by candidate/party.
- Two-party vote share.
- Margin.
- Winner/loss.
- Turnout count.
- Turnout rate using VEP, VAP, CVAP, registered voters, or active voters.
- Over/underperformance relative to baseline.
- Split-ticket rate.
- Ballot roll-off / undervote.

### Campaign outcomes

- Contact attempt.
- Successful contact.
- Support ID.
- Persuasion response.
- Volunteer signup.
- Donation/contribution.
- Absentee/mail ballot request.
- Ballot return.
- Vote history after election.
- Email/SMS open, click, reply, unsubscribe, opt-out.

### Media/message outcomes

- Ad impressions.
- Ad spend.
- Estimated CPM.
- Creative topic/tone.
- Earned media mentions.
- Social engagement.
- Search interest.
- Debate/presser clips.
- Message recall or issue salience in polling.

---

## 4. Core explanatory layers

### Layer A — Fundamentals

These are the baseline variables most likely to dominate election outcomes.

- District/state partisan lean.
- Incumbency.
- National political environment.
- Presidential approval.
- Economic indicators.
- Midterm penalty / presidential coattails.
- Candidate experience and quality.
- Fundraising and outside spending.
- Scandals or major local events.
- Redistricting changes.
- Electoral rules and voting access.

### Layer B — Electorate composition

- Age.
- Race/ethnicity.
- Education.
- Gender.
- Income.
- Religion and religious attendance.
- Urban/suburban/rural geography.
- Homeownership/rentership.
- Language and nativity.
- Occupation/industry.
- Registration and turnout history.
- Party registration where available.

### Layer C — Candidate positioning

- Ideology / moderation / extremism.
- Issue emphasis.
- Local vs. national focus.
- Alignment with party leadership.
- Roll-call voting for incumbents.
- Campaign website/platform text.
- Interest-group endorsements/ratings.
- Campaign finance network ideology.

### Layer D — Communication style and persona

This is where “swagger,” charisma, and physical/performative traits should be operationalized carefully.

Potential measurable proxies:

- Charisma / confidence language.
- Dominance language.
- Negativity and personal attacks.
- Emotional tone.
- Linguistic style matching in debates.
- Authenticity/localness.
- Readability and simplicity.
- Topic discipline.
- Visual presentation in ads/social media.
- Facial competence/attractiveness ratings in research settings.
- Voice pitch and speaking rate.
- Height or other physical cues, with caution.

These variables are likely most useful in:

- Close races.
- Open seats.
- Primaries.
- Low-information down-ballot races.
- Races with weak partisan anchors.
- Candidate-quality comparisons.

They should not replace fundamentals.

### Layer E — Campaign operations

- Field contact rate.
- Contact quality.
- Volunteer capacity.
- Canvass coverage.
- Mail frequency.
- Digital ad spend and creative mix.
- TV/radio spend by market.
- Fundraising velocity.
- Absentee/mail ballot chase effectiveness.

This layer is mostly unavailable to independent analysts unless working with a campaign.

---

## 5. Key modeling frameworks

### Forecasting model

Goal: estimate probability of victory and expected vote margin.

Typical inputs:

- Prior election results.
- Partisan lean.
- Polls.
- Incumbency.
- Fundraising/spending.
- Candidate quality.
- District demographics.
- National environment.
- Redistricting changes.

Recommended method:

- Hierarchical Bayesian model.
- Polling model with house effects and time decay.
- Fundamentals prior.
- District/state random effects.
- Simulation of correlated errors.

### MRP / small-area estimation

Goal: estimate district-level opinion from national/state survey data.

Typical inputs:

- CES, Nationscape, Pew, ANES, AP VoteCast, PRRI.
- ACS/CVAP demographic cells.
- District/county/tract geography.

Recommended method:

- Multilevel regression by demographics and geography.
- Post-stratification to district population or electorate cells.
- Validate against election returns and known survey benchmarks.

### Turnout model

Goal: estimate who will vote and where turnout will change.

Typical inputs:

- Voter file vote history.
- Registration date.
- Party registration/model score.
- Age, geography, district, precinct.
- Early/mail ballot status.
- Weather, voting method, election type.

Recommended method:

- Logistic regression / gradient boosting / Bayesian hierarchical model.
- Separate presidential-year, midterm, primary, special election models.
- Calibrate to aggregate turnout expectations.

### Persuasion model

Goal: identify voters whose candidate preference may be movable.

Typical inputs:

- Survey experiments.
- Canvass/call responses.
- Past vote behavior.
- Demographics and issue attitudes.
- Media exposure.

Recommended method:

- Uplift modeling / causal forests / randomized experiments where possible.
- Avoid naive “persuadable score” if no treatment/control data exists.

### Election-night model

Goal: estimate final result while votes are being counted.

Typical inputs:

- Live returns.
- Historical precinct/county returns.
- Reporting unit sequence.
- Ballot method splits.
- Early/mail/Election Day composition.
- Outstanding vote estimates.

Recommended method:

- Remaining-vote model by geography and ballot method.
- Reporting-bias adjustment.
- Path-to-overtake calculation.
- Conservative uncertainty communication.

### Post-election autopsy

Goal: explain why the result happened.

Typical inputs:

- Certified returns.
- Voter file turnout.
- Survey validated voters.
- Precinct/district/county swing.
- Campaign contact data.
- Spending/ad data.

Recommended method:

- Decompose turnout vs. persuasion.
- Compare modeled expectations to realized returns.
- Segment by geography, demography, vote history, and campaign contact.

---

## 6. House-race analytics requirements

For U.S. Representative advisory work, minimum viable data should include:

1. Current congressional district boundaries.
2. Historical election returns allocated to current district boundaries.
3. Precinct/VTD-level results where possible.
4. ACS/CVAP district demographics.
5. Voter file turnout/registration data if legally obtainable.
6. Public polling and CES-style survey inputs.
7. FEC fundraising and spending.
8. Candidate biography, platform, social media, ads, and endorsements.
9. District-specific polling or MRP estimates for issue attitudes.
10. Campaign contact/CRM data if advising an actual campaign.

Without voter file or district-specific polling, an independent analyst can produce useful public forecasts and strategic context, but should avoid pretending to have campaign-grade targeting precision.

---

## 7. Data pitfalls and analytical risks

### Ecological fallacy

Do not infer individual behavior directly from aggregate county or precinct results. Example: a heavily Hispanic county shifting Republican does not prove all Hispanic voters shifted equally.

### County/district mismatch

Counties often split across congressional districts. County-level survey or election data can be misleading for House races unless allocated properly.

### Redistricting

District boundaries change. Historical results must be reallocated to current districts when possible.

### Survey sample size

A survey with state or congressional district identifiers may still have too few respondents in a given district. Use MRP rather than simple district averages.

### Voter file limitations

Voter files show registration and turnout history, not ballot choice. Party registration is available only in some states and is not the same as vote choice.

### Early vote interpretation

Early vote party registration or modeled partisanship is not the same as candidate vote. Election timing and ballot method composition can distort narratives.

### Polling and likely-voter models

Likely-voter models attempt to predict a future electorate. They can be wrong, especially in low-turnout, special, primary, or rapidly changing elections.

### Platform ad opacity

Public ad libraries expose spend/impression ranges, not complete account-level performance or platform delivery logic.

### Privacy and compliance

Voter files, contact data, donor data, and ballot-return files require careful handling, even when legally obtainable.

---

## 8. Initial project deliverables

### Public-facing deliverables

- District profile report.
- Race fundamentals forecast.
- Candidate ideology and issue positioning brief.
- Campaign finance tracker.
- Ad/message tracker.
- Election-night dashboard.
- Post-election autopsy.

### Internal deliverables

- Dataset registry.
- Data dictionary.
- Modeling assumptions log.
- Source reliability matrix.
- Ingestion and validation tests.
- Ethics/privacy checklist.
- Forecast backtesting notebook.
- MRP modeling notebook.
- District boundary and crosswalk notes.

---

## 9. Suggested MVP roadmap

### Phase 1 — Public baseline

- Ingest MIT/OpenElections/FEC/Census/CVAP/Voteview.
- Build district-level profiles.
- Create historical election baseline.
- Build simple fundamentals model.

### Phase 2 — Survey and MRP layer

- Add CES cumulative and recent election-year data.
- Add Pew, AP VoteCast, ANES, Nationscape, PRRI as interpretive/validation sources.
- Build district-level issue-attitude estimates.

### Phase 3 — Candidate and communication layer

- Add campaign websites, social media, ads, debates, endorsements, biographies.
- Extract issue topics, tone, negativity, localness, and style features.
- Test whether candidate-style features improve close-race models after fundamentals.

### Phase 4 — Campaign-grade data

- Add state voter files where legally obtainable.
- Add district polling or survey experiments.
- Add client CRM/contact data where available.
- Move from public analysis to campaign advisory.

---

## 10. Working principle

The model hierarchy should be:

1. Fundamentals first.
2. Electorate composition second.
3. Survey and issue attitudes third.
4. Candidate positioning fourth.
5. Communication style/persona fifth.
6. Campaign operations when available.

“Swagger” may matter, but it should be tested as an incremental feature after stronger structural variables are already accounted for.

# District Profile Template: `STATE-DISTRICT`

Use this template for U.S. House district reports. Keep a completed profile reproducible by linking every chart and claim to a data snapshot.

---

## Metadata

| Field | Value |
|---|---|
| District | `STATE-DISTRICT` |
| Cycle | `YYYY` |
| Report Date | `YYYY-MM-DD` |
| Author | `Name` |
| Data Snapshot | `manifest_id` |
| Model Version | `model_version` |
| Privacy Tier | Public aggregate |
| Status | Draft / Reviewed / Published |

## Executive Summary

One short paragraph describing the district, the race, the partisan baseline, the candidates, and the current forecast.

Example structure:

> `STATE-DISTRICT` is a `[safe/likely/lean/toss-up]` district with a `[party]` baseline, shaped by `[metro/rural/suburban/exurban]` geography, `[key demographic/economic context]`, and `[incumbency/open seat/redistricting]`. The current model estimates `[candidate]` at `[x]%` two-party vote share with a `[x-y]%` interval, implying a `[x]%` win probability.

## Race Snapshot

| Attribute | Value |
|---|---|
| Incumbent |  |
| Incumbent Party |  |
| Incumbent Running? | Yes / No |
| Challenger(s) |  |
| Open Seat? | Yes / No |
| Primary Date |  |
| General Election Date |  |
| Race Rating Consensus |  |
| Model Rating |  |
| Forecasted Two-Party Vote |  |
| Win Probability |  |
| Main Uncertainty |  |

## Geography

Describe the district’s geographic footprint.

Include:

- counties and county splits;
- major cities and suburbs;
- rural/exurban/urban composition;
- media markets;
- college towns, military bases, tribal lands, or major employers;
- geographic changes from redistricting.

### County / Locality Coverage

| County / Locality | Share of District Population | Share of District Vote | Notes |
|---|---:|---:|---|
|  |  |  |  |

### Map Placeholder

`![District Map](../assets/maps/STATE-DISTRICT-map.png)`

## Demographic Profile

Use ACS and district-level crosswalks.

| Metric | District | State | U.S. | Notes |
|---|---:|---:|---:|---|
| Population |  |  |  |  |
| Voting-age population |  |  |  |  |
| Citizen voting-age population |  |  |  |  |
| Median age |  |  |  |  |
| College degree share |  |  |  |  |
| Median household income |  |  |  |  |
| Poverty rate |  |  |  |  |
| Homeownership |  |  |  |  |
| Urban/suburban/rural mix |  |  |  |  |

### Race and Ethnicity

| Group | Share of Population | Share of CVAP | Notes |
|---|---:|---:|---|
| White non-Hispanic |  |  |  |
| Black |  |  |  |
| Hispanic / Latino |  |  |  |
| Asian |  |  |  |
| Native American / Alaska Native |  |  |  |
| Multiracial / Other |  |  |  |

## Economic and Social Context

Describe the district’s economy and issue environment.

Prompts:

- What industries dominate employment?
- Is the district growing, declining, or changing demographically?
- Are housing costs, migration, unionization, energy, agriculture, defense, education, tourism, or healthcare major local issues?
- Are there notable local institutions?

## Political Baseline

| Metric | Value | Source / Snapshot |
|---|---:|---|
| Presidential vote, latest cycle |  |  |
| Presidential vote, prior cycle |  |  |
| House vote, latest cycle |  |  |
| Governor vote in district |  |  |
| Senate vote in district |  |  |
| District partisanship score |  |  |
| Generic ballot adjustment |  |  |
| Incumbency adjustment |  |  |

### Historical Election Results

| Year | Office | Democratic % | Republican % | Other % | Margin | Turnout | Notes |
|---:|---|---:|---:|---:|---:|---:|---|
|  | President |  |  |  |  |  |  |
|  | House |  |  |  |  |  |  |
|  | Senate |  |  |  |  |  |  |
|  | Governor |  |  |  |  |  |  |

## Redistricting and Boundary Notes

- Current district plan:
- Previous district comparison:
- Estimated old-to-new district vote transfer:
- Counties/precincts split:
- Crosswalk confidence:
- Known data caveats:

## Turnout Profile

| Metric | Presidential Year | Midterm Year | Special / Primary | Notes |
|---|---:|---:|---:|---|
| Total votes |  |  |  |  |
| Turnout rate |  |  |  |  |
| Ballot roll-off |  |  |  |  |
| Early/mail share |  |  |  |  |
| Registration trend |  |  |  |  |

### Turnout Drivers

Discuss likely turnout effects:

- presidential vs midterm electorate;
- competitive statewide races;
- ballot measures;
- candidate enthusiasm;
- demographic change;
- early/mail voting rules;
- weather or administrative disruptions, if relevant.

## Candidates

### Candidate A

| Attribute | Value |
|---|---|
| Party |  |
| Role / Background |  |
| Prior Offices |  |
| Fundraising |  |
| Cash on Hand |  |
| Outside Support |  |
| Endorsements |  |
| Strengths |  |
| Weaknesses |  |

### Candidate B

| Attribute | Value |
|---|---|
| Party |  |
| Role / Background |  |
| Prior Offices |  |
| Fundraising |  |
| Cash on Hand |  |
| Outside Support |  |
| Endorsements |  |
| Strengths |  |
| Weaknesses |  |

## Campaign Finance

| Candidate / Group | Receipts | Disbursements | Cash on Hand | Debt | Notes |
|---|---:|---:|---:|---:|---|
|  |  |  |  |  |  |

Include federal FEC data for House races and outside spending where available. Do not publish individual donor lists unless there is a clear journalistic or research purpose and the report follows donor-data rules.

## Polling and Ratings

| Source | Date | Candidate A | Candidate B | Sample | Population | Mode | Notes |
|---|---|---:|---:|---:|---|---|---|
|  |  |  |  |  |  |  |  |

| Forecaster | Rating | Date | Notes |
|---|---|---|---|
| Cook Political Report |  |  |  |
| Sabato's Crystal Ball |  |  |  |
| Inside Elections |  |  |  |
| Split Ticket |  |  |  |
| Internal Model |  |  |  |

## Forecast

| Output | Estimate |
|---|---:|
| Candidate A expected two-party vote |  |
| Candidate B expected two-party vote |  |
| 80% interval |  |
| 95% interval |  |
| Candidate A win probability |  |
| Candidate B win probability |  |
| Probability margin within 1 point |  |
| Probability margin within 5 points |  |

### Main Model Drivers

| Driver | Direction | Estimated Impact | Confidence |
|---|---|---:|---|
| District partisanship |  |  |  |
| National environment |  |  |  |
| Incumbency |  |  |  |
| Fundraising/spending |  |  |  |
| Candidate quality |  |  |  |
| Turnout composition |  |  |  |
| Polling |  |  |  |

## Scenario Analysis

| Scenario | Assumption | Candidate A Vote | Candidate B Vote | Winner |
|---|---|---:|---:|---|
| Baseline | Current model |  |  |  |
| High Democratic turnout |  |  |  |  |
| High Republican turnout |  |  |  |  |
| Polling miss toward D |  |  |  |  |
| Polling miss toward R |  |  |  |  |
| Low turnout |  |  |  |  |

## Local Issues and Media Environment

Summarize the issues that may affect the race.

Potential categories:

- cost of living;
- immigration;
- abortion;
- healthcare;
- crime;
- education;
- energy and climate;
- agriculture;
- labor and unions;
- transportation;
- housing;
- foreign policy or defense;
- local scandals;
- judicial or redistricting issues.

## Data Quality Notes

| Data Area | Status | Caveat | Action Needed |
|---|---|---|---|
| Election returns | Complete / Partial / Missing |  |  |
| Precinct geography | Complete / Partial / Missing |  |  |
| ACS data | Complete / Partial / Missing |  |  |
| Candidate metadata | Complete / Partial / Missing |  |  |
| FEC data | Complete / Partial / Missing |  |  |
| Polling | Complete / Sparse / None |  |  |
| Race ratings | Complete / Sparse / None |  |  |
| Redistricting crosswalk | High / Medium / Low confidence |  |  |

## Analyst Notes

- What would change the forecast most?
- What are the biggest unknowns?
- Is the district likely to nationalize or localize?
- Is the current rating consistent with other forecasters?
- What data would improve confidence?

## Publication Checklist

- [ ] All source dates are included.
- [ ] No individual voter-level data is exposed.
- [ ] Donor data is aggregated or used under an approved journalistic/research purpose.
- [ ] Model version is listed.
- [ ] Forecast uncertainty is explained.
- [ ] Data-quality caveats are visible.
- [ ] Charts are reproducible from stored data snapshots.

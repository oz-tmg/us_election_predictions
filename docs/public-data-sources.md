# Public Data Sources for U.S. Election Analytics

_Last updated: 2026-07-04_

This catalog tracks publicly available or mostly public data sources relevant to U.S. election prediction, campaign analytics, news analytics, electorate interpretation, and adjacent analytics work. “Public” does not always mean frictionless: some sources require a free account, codebook interpretation, scraping, FOIA/public-records requests, or careful license review.

## How to read this catalog

- **Access level**: `Open`, `Open with account`, `Public-records request`, `Restricted public-use`, or `Mostly open but messy`.
- **Granularity**: the finest practical geography or unit usually available.
- **Best use**: where the dataset is most valuable in an election-prediction or advisory workflow.
- **Cautions**: traps that can produce bad analysis.

---

## 1. Official election results and electoral geography

| Source | Access level | Typical granularity | Best use | Cautions / notes | Link |
|---|---:|---|---|---|---|
| MIT Election Data and Science Lab | Open | President/Senate/House/statewide/county/precinct depending on dataset | Historical results backbone; returns normalization; precinct project; election administration research | Coverage and release lag vary by office/year/geography | https://electionlab.mit.edu/data |
| MIT MEDSL GitHub | Open | Often precinct/county/state; repo-specific | Programmatic ingestion, reproducible data workflows | Repos vary in completeness and standardization | https://github.com/MEDSL |
| OpenElections | Open | State, county, precinct depending on state and year | Standardized official election results for civic/journalistic analysis | Not every state/year/race is complete; source files can be irregular | https://openelections.net/ and https://github.com/openelections |
| State election offices / Secretaries of State | Open / public-records request | State, county, precinct, district, sometimes cast vote records | Source of truth for certified returns, candidate lists, turnout, registration, absentee reports | 50-state fragmentation; schemas and update cadence vary widely | State-specific |
| County election offices | Open / public-records request | Precinct, ballot style, sometimes tabulator or cast vote record | Most granular official returns; election-night updates; local recount/post-election analysis | County formats are inconsistent; may require manual collection | County-specific |
| Redistricting Data Hub | Open with account / terms | Precinct boundaries, election results, legislative boundaries, census layers | Joining geography to results; redistricting and district composition analysis | Need to review data vintage, boundary alignment, and source notes | https://redistrictingdatahub.org/data/about-our-data/ |
| U.S. Census TIGER/Line | Open | Census block, block group, tract, county, state, congressional district | Spatial joins, district overlays, maps, crosswalks | Boundaries must match election year and redistricting cycle | https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html |
| Census PL 94-171 Redistricting Data | Open | Census block and above | Redistricting baseline population and race/ethnicity data | Not a voter file; population is not turnout | https://www.census.gov/programs-surveys/decennial-census/about/rdo/summary-files.html |
| Cast Vote Records, where released | Open / public-records request | Ballot-level anonymous records within jurisdictions | Ticket-splitting, undervotes, ballot order, precinct/contest patterns | Availability varies; ballot secrecy and small-cell disclosure must be handled carefully | Jurisdiction-specific; research examples exist |
| FiveThirtyEight election-results GitHub | Open | State/district/county depending on file | Quick outcome data for model prototyping | Verify against official returns for production use | https://github.com/fivethirtyeight/election-results |

---

## 2. Demographics, population, and district context

| Source | Access level | Typical granularity | Best use | Cautions / notes | Link |
|---|---:|---|---|---|---|
| U.S. Census ACS 5-year | Open | Block group, tract, county, district, state | Demographic, socioeconomic, housing, language, commuting features | ACS estimates have margins of error; district definitions can lag | https://www.census.gov/programs-surveys/acs |
| Census CVAP Special Tabulation | Open | Block group and above | Eligible electorate denominator by race/ethnicity; Voting Rights Act context; turnout rates | CVAP estimates differ from registered voters and actual voters | https://www.census.gov/programs-surveys/decennial-census/about/voting-rights/cvap.html |
| Census API | Open | API endpoint dependent | Reproducible pulls of ACS/CVAP/decennial variables | Variable names change across products/years | https://www.census.gov/data/developers.html |
| Census Congressional District Profiles | Open | Congressional district | District-level demographics and comparisons | Ensure correct Congress and boundary cycle | https://www.census.gov/mycd/ |
| IPUMS NHGIS | Open with account | Census tract/block group/county/district; time series | Harmonized historical census and ACS data | Requires free registration and citation | https://www.nhgis.org/ |
| Geocorr / MCDC crosswalks | Open | Crosswalks across Census geographies | Estimating district/county/tract overlaps | Allocation assumptions matter | https://mcdc.missouri.edu/applications/geocorr.html |
| PRRI Census of American Religion | Open reports / data tools; microdata varies | State/county modeled estimates | Religion/culture context for districts and counties | Modeled contextual estimates, not campaign microdata | https://www.prri.org/research/census-2023-american-religion/ |

---

## 3. Voter registration, turnout, and election administration

| Source | Access level | Typical granularity | Best use | Cautions / notes | Link |
|---|---:|---|---|---|---|
| State voter files | Public-records request / state-specific restrictions | Individual registered voter, address, precinct, vote history, party registration where available | Turnout modeling, registration shifts, district electorate composition | Rules vary by state; cannot show ballot choice; may contain PII; use restrictions apply | State-specific; summary rules: https://www.ncsl.org/elections-and-campaigns/access-to-and-use-of-voter-registration-lists |
| State/county absentee and early-vote files | Public-records request / public reports | Individual or aggregate ballot request/return; county/precinct in some states | Early-vote tracking, ballot chase, turnout monitoring | Availability and fields vary; party data unavailable in many states | State-specific |
| UF Election Lab / U.S. Elections Project | Open | State/county/party/race/age/gender where available | Early vote, turnout statistics, election timing, VEP denominator work | Early-vote party composition is not vote choice | https://election.lab.ufl.edu/ and https://www.electproject.org/ |
| EAC Election Administration and Voting Survey | Open | State and local election jurisdiction depending on file | Registration, list maintenance, UOCAVA, provisional ballots, mail voting, election admin benchmarking | Lagged biennial data; definitions vary by state | https://www.eac.gov/research-and-data/studies-and-reports |
| Stanford-MIT Election Performance Index | Open | State | Election administration performance indicators | State-level only; not a race forecast input by itself | https://electionlab.mit.edu/election-performance-index |
| National Neighborhood Data Archive voter registration/turnout | Open / ICPSR terms | County | Longitudinal county registration and turnout context | County-level only | https://www.icpsr.umich.edu/web/ICPSR/studies/38506 |

---

## 4. Survey, public opinion, and voter behavior data

| Source | Access level | Typical granularity | Best use | Cautions / notes | Link |
|---|---:|---|---|---|---|
| Cooperative Election Study (CES/CCES) | Open with account / Dataverse | Respondent-level; state, congressional district, ZIP, imputed county FIPS in cumulative files | Best public backbone for House/district MRP, issue attitudes, vote choice, demographics | CD samples are not designed as standalone representative district polls; use MRP/hierarchical modeling | https://cces.gov.harvard.edu/ and https://tischcollege.tufts.edu/research-faculty/research-centers/cooperative-election-study/data-downloads |
| Democracy Fund + UCLA Nationscape | Open with account | Respondent-level; broad subnational coverage incl. many counties/CDs/cities | Large-scale 2019–2021 opinion baseline; subnational validation | Mainly 2020-cycle era; not current-cycle tracker | https://www.voterstudygroup.org/nationscape |
| Pew Research Center datasets | Open with free account | Respondent-level; public ATP data masks detailed geography | National coalition analysis, issue attitudes, validated-voter studies | American Trends Panel public data does not release ZIP/detailed geography | https://www.pewresearch.org/datasets/ and https://www.pewresearch.org/american-trends-panel-datasets/ |
| AP VoteCast public-use files | Open with registration / terms | Respondent-level election survey; geography varies by release | Election-night/post-election electorate interpretation | Better for state/national coalition analysis than single House races | https://apnorc.org/projects/ap-votecast-puf/ |
| ANES public-use data | Open with account | Respondent-level; public geographies usually state/CD/region | Deep voter behavior, long time series, political psychology | County/ZIP/tract geocodes are restricted via ICPSR VDE | https://electionstudies.org/data-center/ |
| ANES restricted geocodes | Restricted public-use | County, ZIP, tract, other geographies depending study | Merge contextual geography with deep survey data | Requires application and secure access; not open | https://electionstudies.org/data-center/restricted-data-access/rda-geocodes/ |
| PRRI American Values Atlas | Open reports / data access varies | State and modeled substate estimates | Religion, values, cultural divides, state/district context | Microdata/geography access may be limited; modeled estimates require careful interpretation | https://www.prri.org/american-values-atlas/ |
| MIT Survey of the Performance of American Elections (SPAE) | Open | State-level survey | Election administration experience, wait times, confidence, voting method | State-level; not a district poll | https://electionlab.mit.edu/research/survey-performance-american-elections |
| Roper Center public opinion archive | Membership/licensed; some public metadata | Study-dependent; national/state polls | Historical polling archive and state-poll discovery | Microdata access often requires institutional membership/payment | https://ropercenter.cornell.edu/ |
| FiveThirtyEight poll datasets | Open | Poll-level metadata and toplines | Poll aggregation, pollster ratings, national/state forecast features | Not always respondent-level; transformations needed | https://github.com/fivethirtyeight/data |

---

## 5. Campaign finance, donations, and elite ideology

| Source | Access level | Typical granularity | Best use | Cautions / notes | Link |
|---|---:|---|---|---|---|
| FEC data portal | Open | Committee, candidate, contribution, expenditure, filing | Federal campaign finance, donor geography, fundraising momentum, independent expenditures | Federal only; filings can be amended; itemization thresholds matter | https://www.fec.gov/data/ |
| FEC API / OpenFEC | Open API key | Candidate, committee, receipt, disbursement, filings | Reproducible ingestion of federal finance data | Rate limits and API schema management | https://api.open.fec.gov/developers/ |
| FEC bulk data / .FEC files | Open | Raw filings and bulk extracts | Warehouse-grade ingestion and backfills | Parsing complexity; amendments and duplicate handling | https://www.fec.gov/data/browse-data/ |
| OpenSecrets | Open reports; API/licensing varies | Candidate, committee, industry, donor aggregates | Money-in-politics context and aggregation | Bulk/API may require agreement; verify against FEC for federal source-of-truth | https://www.opensecrets.org/ |
| FollowTheMoney / National Institute on Money in Politics | Open/search; data access varies | State campaign finance | State races, ballot measures, state legislative finance | State disclosure rules vary | https://www.followthemoney.org/ |
| Voteview / DW-NOMINATE | Open | Legislator, roll-call vote, Congress | Incumbent ideology, polarization, roll-call-based positioning | Works for incumbents; not challengers | https://voteview.com/data |
| DIME / CFscores | Open / academic data access | Donors, candidates, PACs, contribution networks | Ideology estimates from campaign finance; challengers and elites | Requires careful versioning and methodology notes | https://data.stanford.edu/dime |
| State campaign finance portals | Open / state-specific | Candidate/committee/contribution/expenditure | Governor, state legislative, local/state races | Highly fragmented schemas and legal thresholds | State-specific |

---

## 6. Political ads, media, and communication style

| Source | Access level | Typical granularity | Best use | Cautions / notes | Link |
|---|---:|---|---|---|---|
| Meta Ad Library API | Open with API access/terms | Ad creative, page, dates, spend/impression ranges, demographics for political/social issue ads | Digital ad monitoring, message testing, sponsor analysis, creative features | Ranges not exact values; archive retention and platform policy can change | https://www.facebook.com/ads/library/api/ |
| Google Political Ads Transparency Report / BigQuery dataset | Open | Verified advertiser, creative, spend, impressions, targeting categories | Google/YouTube/display political ad monitoring | Google’s election-ad definitions vary by country/region; issue-ad coverage may differ | https://adstransparency.google.com/political and https://cloud.google.com/blog/topics/developers-practitioners/how-get-started-political-ads-transparency-report-dataset |
| FCC Online Public Inspection File / political files | Open | Station-level political ad orders, request files, issue/candidate files | TV/radio ad buys, rates, station-level media analysis | PDF-heavy, unstandardized, time-consuming | https://www.fcc.gov/media/policy/political-programming |
| Wesleyan Media Project / CREATIVE datasets | Open GitHub datasets | Political ad labels/features; dataset-specific | Ad tone, negativity, entity linking, race focus, party classifiers | Check each dataset’s training labels and intended use | https://github.com/Wesleyan-Media-Project/datasets |
| Presidential debate transcript datasets | Open GitHub | Transcript line/speaker | Debate NLP, attacks, tone, style matching | Presidential-focused; not House races | https://github.com/jamesmartherus/debates |
| M-Arg multimodal debate dataset | Open GitHub | Audio/transcript argumentation annotations | Multimodal debate analysis, attacks/support claims | 2020 debate-specific; limited generalization | https://github.com/rafamestre/m-arg_multimodal-argumentation-dataset |
| Campaign websites / CampaignView | Open research dataset | Candidate website platforms and biographies | Candidate issue positioning and self-presentation | Best developed for U.S. House 2018–2022; website availability can change | https://www.nature.com/articles/s41597-025-05491-x |
| WEB-Scores | Open GitHub | Candidate positioning estimates from website text | Candidate ideology/issue position modeling | Derived measure; inspect methodology before production use | https://github.com/crcase/WEB-Scores |
| Social media public datasets: X/Twitter 2024, TikTok 2024, Truth Social 2024 | Open research releases | Post/video IDs, text/transcripts, metadata depending dataset | Election discourse, virality, rhetoric, misinformation, affect | Platform terms, deleted content, sampling bias, API limitations | Examples: https://github.com/sinking8/usc-x-24-us-election and https://github.com/gabbypinto/US2024PresElectionTikToks |

---

## 7. Polling, forecasts, and election-night reference data

| Source | Access level | Typical granularity | Best use | Cautions / notes | Link |
|---|---:|---|---|---|---|
| Public pollster releases | Open | Poll-level; crosstabs vary | Current race tracking, issue salience, public trend monitoring | Crosstabs can be underpowered; toplines often lack microdata | Pollster-specific |
| FiveThirtyEight polling data | Open | Poll-level metadata/toplines | Poll aggregation and pollster comparison | Methodology/rating systems change over time | https://github.com/fivethirtyeight/data |
| RealClearPolitics polling averages | Open webpage | Race/state poll averages | Quick reference for public polls | Limited data export; methodology not fully reproducible | https://www.realclearpolitics.com/ |
| Decision Desk HQ public pages | Open web; API licensed | Race-level live results/forecasts | Public reference; possible validation | API/data feed requires procurement | https://decisiondeskhq.com/ |
| AP public results articles/pages | Open web | Race-level | News context and official/semi-official reference | Not a bulk data replacement | https://apnews.com/hub/election-2024 |

---

## 8. Adjacent public sports / analytics sources noted by the user

These are not U.S. election sources, but they are useful reference points for building a multi-domain analytics consultancy and demonstrate how a public-event data source can support modeling, documentation, and reproducible pipelines.

| Source | Access level | Typical granularity | Best use | Cautions / notes | Link |
|---|---:|---|---|---|---|
| MLB Baseball Savant / Statcast Search CSV | Open web CSV | Pitch/event/player/game | Baseball analytics, model prototyping, public data pipeline examples | Not election-related; terms and scraping limits must be respected | https://baseballsavant.mlb.com/csv-docs |
| pybaseball | Open-source Python package | Pitch/event/player/team/season depending function | Programmatic access pattern for public sports data | Scrapes multiple sites; verify source terms and cache responsibly | https://github.com/jldbc/pybaseball |

---

## Recommended initial ingestion priority

1. **Election returns and geography**: MIT/MEDSL, OpenElections, state results, RDH, Census TIGER.
2. **Demographic context**: ACS, CVAP, congressional district profiles, NHGIS.
3. **Survey layer**: CES cumulative and current election-year files, Pew ATP, AP VoteCast PUF, Nationscape, ANES public.
4. **Campaign finance and ideology**: FEC API/bulk, Voteview, DIME, OpenSecrets/FollowTheMoney where allowed.
5. **Media/message layer**: Meta Ad Library, Google political ads, FCC political files, CampaignView/WEB-Scores, debate/social datasets.
6. **Election administration and early voting**: EAC EAVS, UF Election Lab, state ballot-return files where available.

---

## Data ethics and compliance notes

- Treat voter files and ballot-return files as sensitive even when legally public.
- Never imply voter files reveal ballot choice; they reveal registration and turnout history, not votes cast for candidates.
- Store PII separately from modeling outputs where possible.
- Use aggregated outputs for public products unless there is a clear legal and ethical basis for more granular use.
- Track licenses, terms of use, and permitted use in `dataset-registry.md` before ingestion.

# Source Reliability Matrix

This matrix scores datasets for election prediction and analysis. Scores are directional starter ratings and should be updated after each source is acquired and profiled.

Scoring scale:

- **5 = excellent**
- **4 = strong**
- **3 = usable with caveats**
- **2 = limited**
- **1 = poor or high-risk**

For legal constraints, a high score means easier permitted use. A low score means restrictive, unclear, or sensitive use rules.

## Matrix

| Source | Main Use | Completeness | Geography | Update Lag | Cost | Legal Ease | Overall | Notes |
|---|---|---:|---:|---:|---:|---:|---:|---|
| State election offices / certified returns | Official results | 5 | 4 | 2 | 5 | 5 | 4.2 | Best authority, but formats vary and precinct availability differs. |
| County election offices | Precinct and local results | 4 | 5 | 2 | 5 | 4 | 4.0 | Essential for local and judicial races; high scraping/normalization burden. |
| MIT Election Data and Science Lab | Standardized historical results | 4 | 4 | 3 | 5 | 5 | 4.2 | Strong public-good source; lag and coverage vary by office/year. |
| OpenElections | Standardized official results | 3 | 4 | 2 | 5 | 5 | 3.8 | Useful but uneven by state and year. Validate against official totals. |
| VEST precinct returns | Precinct returns and election geography | 4 | 5 | 3 | 4 | 4 | 4.0 | Excellent for redistricting-era analysis; confirm license and vintage. |
| Redistricting Data Hub | Shapefiles, election data, crosswalks | 4 | 5 | 3 | 5 | 4 | 4.2 | Strong for district/precinct geospatial work; account registration may be required. |
| Census ACS | Demographics and socioeconomic features | 5 | 5 | 3 | 5 | 5 | 4.6 | Standard demographic source; margins of error matter for small geography. |
| Census TIGER/Line | Boundaries and GEOIDs | 5 | 5 | 4 | 5 | 5 | 4.8 | Core geography source; no demographics in shapefiles. |
| Census P.L. 94-171 redistricting data | Population and race data for redistricting | 5 | 5 | 2 | 5 | 5 | 4.4 | Strong legal/redistricting use; decennial update cadence. |
| FEC campaign finance | Federal fundraising/spending | 5 | 3 | 4 | 5 | 3 | 4.0 | Excellent federal coverage; contributor-use restrictions apply. |
| State campaign-finance portals | State, local, judicial fundraising | 3 | 4 | 3 | 5 | 3 | 3.6 | Crucial for governor/state leg/judicial races; formats and rules vary. |
| Pollster releases | Vote intention | 3 | 3 | 5 | 4 | 4 | 3.8 | Valuable where available; sparse for House/state/judicial races. |
| Poll aggregators | Poll averages and metadata | 4 | 3 | 5 | 4 | 3 | 3.8 | Check redistribution rules and pollster metadata completeness. |
| Race ratings: Cook/Sabato/Inside Elections/Split Ticket | Expert priors | 4 | 3 | 4 | 3 | 4 | 3.6 | Useful ordinal signal; not a substitute for model probabilities. |
| AP live results | Election-night results and race calls | 5 | 4 | 5 | 2 | 3 | 3.8 | High quality; licensing/cost may limit use. |
| Decision Desk HQ live results | Election-night results | 4 | 4 | 5 | 2 | 3 | 3.6 | API-friendly in some contexts; validate calls and remaining-vote assumptions. |
| NEP / Voter Poll / AP VoteCast | Voter composition and issue analysis | 4 | 3 | 4 | 2 | 3 | 3.2 | Useful for post-election composition; methods and access vary. |
| Cast Vote Records | Ballot-level analysis where public | 3 | 5 | 2 | 5 | 3 | 3.6 | Very granular; availability and privacy treatment vary by jurisdiction. |
| State voter files | Turnout, registration, voter history | 4 | 5 | 4 | 3 | 2 | 3.6 | Powerful but legally fragmented and sensitive. Never publish individual records. |
| Licensed national voter files: L2/TargetSmart/Catalist/DataTrust | Voter-level modeling | 5 | 5 | 4 | 1 | 1 | 3.2 | High analytical value; high cost, contract, privacy, and use restrictions. |
| Campaign CRM/VAN/WinRed/ActBlue/internal exports | Contact, support, donor, field data | 4 | 5 | 5 | 2 | 1 | 3.4 | Operationally sensitive; exclude from public repo. |
| Ballotpedia | Candidate, judicial, office context | 3 | 3 | 4 | 5 | 4 | 3.8 | Useful starter context; verify against official sources. |
| State court / judicial performance sites | Judicial retention and evaluations | 4 | 3 | 3 | 5 | 4 | 3.8 | Important for retention races; availability differs by state. |
| AdImpact / media-spend vendors | Advertising volume and spend | 4 | 4 | 5 | 1 | 2 | 3.2 | High value for campaign intensity; expensive and licensed. |
| Meta Ad Library / Google political ads | Digital advertising | 3 | 3 | 4 | 5 | 4 | 3.8 | Public and useful; incomplete spend/targeting visibility. |
| NewsGuard / Ad Fontes / MBFC | Source-quality coding for media analysis | 3 | 2 | 3 | 3 | 4 | 3.0 | Useful if modeling local media reliability; not election-result data. |
| Wikipedia | Entity lookup and historical context | 2 | 3 | 4 | 5 | 4 | 3.2 | Good discovery layer; not authoritative for model inputs. |

## Recommended Trust Tiers

### Tier A: Model-Primary Sources

Use as direct model inputs after validation:

- certified state/county returns;
- MIT Election Data and Science Lab;
- Census ACS;
- Census TIGER/Line;
- FEC data;
- official state campaign-finance data;
- official district shapefiles.

### Tier B: Model-Useful Sources

Use as inputs with caveats or as priors:

- OpenElections;
- VEST;
- Redistricting Data Hub;
- pollster releases;
- race ratings;
- AP/DDHQ live returns when licensed;
- cast vote records;
- judicial performance commission data.

### Tier C: Contextual Sources

Use for research, entity resolution, and report writing, not as sole quantitative truth:

- Ballotpedia;
- Wikipedia;
- local news;
- campaign websites;
- social media;
- public endorsements;
- media-source reliability products.

### Tier D: Restricted Sources

Use only in private, governed environments:

- state voter files;
- licensed national voter files;
- campaign CRM exports;
- consumer append data;
- respondent-level survey data;
- donor-level records beyond aggregate analysis.

## Dataset Acceptance Criteria

A dataset is accepted into the modeling layer only if it has:

- source owner;
- acquisition timestamp;
- license or permitted-use note;
- schema description;
- geography coverage;
- office coverage;
- cycle coverage;
- row count and unique-key checks;
- checksum;
- validation report;
- known caveats;
- privacy tier;
- downstream tables that use it.

## Reliability Questions to Ask

For every source:

1. Is this official, standardized, licensed, scraped, or inferred?
2. What is the smallest geography?
3. Does it include all candidates or only major parties?
4. Does it include uncontested races?
5. Does it include write-ins and minor parties?
6. Are candidate names stable across years?
7. Are precinct names stable across years?
8. Does the source distinguish absentee, early, Election Day, provisional, and mail?
9. Does the source expose personal data?
10. Are there restrictions on redistribution or commercial use?
11. Can results be reconciled to certified totals?
12. Is the source updated after certification?
13. Can the data be reproduced by another analyst?

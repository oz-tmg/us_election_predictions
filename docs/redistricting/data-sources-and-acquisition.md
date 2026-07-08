# Redistricting Data Sources and Acquisition

## Summary

Redistricting analysis requires combining geography, population, election results, legal constraints, and sometimes voter-file or campaign data.

The fundamental data challenge is that each source uses different units:

- Census data uses blocks, block groups, tracts, counties, and districts.
- Election returns often use precincts, wards, townships, counties, or reporting units.
- Voter files use individual addresses and precinct assignments.
- Legal plans use district boundary shapefiles.
- Communities of interest may use school districts, tribal lands, municipalities, commuting zones, media markets, or qualitative submissions.

## Core public data sources

| Source | Data | Geographic detail | Acquisition notes | Use |
|---|---|---:|---|---|
| U.S. Census P.L. 94-171 Redistricting Data | Total population, race, Hispanic origin, voting-age population, group quarters, housing occupancy | Census block and above | Download from Census FTP or data.census.gov | Equal population, race/VAP, redistricting baseline |
| Census TIGER/Line Shapefiles | Block, tract, county, district, road, water, and other geography | Geometry files | Download from Census web interface or FTP | Map geometries and adjacency graph |
| Census Block Assignment Files | Block-to-geography assignment files | Census block | Download from Census geographic support products | Joining blocks to districts and administrative geographies |
| Census Block Relationship Files / crosswalks | Relationship between 2010 and 2020 blocks | Census block | Download from Census support products | Time-series comparison and backcasting |
| ACS 5-year | Socioeconomic data | Block group / tract and above | Census API or data.census.gov | Education, income, language, housing, commuting context |
| ACS CVAP special tabulation | Citizen voting-age population by race/ethnicity | Block group and above | Census CVAP files | Voting Rights Act and eligible-voter context |
| MIT Election Data and Science Lab | Election returns | State, county, precinct depending on dataset | Public downloads | Historical election outcomes |
| OpenElections | Election returns and source files | County / precinct depending on state | GitHub repositories | Official returns and provenance |
| Redistricting Data Hub | Boundaries, election returns, voter files where available, processing metadata | Precinct/VTD/block depending on state | Public downloads; check terms | Standardized redistricting inputs |
| Dave's Redistricting data ecosystem | Election and Census data used in DRA | Block/VTD/district depending on state | GitHub/app exports where available | Map inspection and public comparison |
| State redistricting portals | Enacted/proposed plans, public submissions, shapefiles | District/block assignment | State websites | Official plans and legal records |
| State election offices | Precinct returns, voter registration summaries, turnout reports | Precinct/county | State websites, public records, APIs | Validation and current election context |
| Legislative GIS offices | District shapefiles and block equivalency files | District/block | State legislature websites | Official enacted boundaries |

## Licensed or restricted sources

| Source | Data | Value | Risk / limitation |
|---|---|---|---|
| State voter files | Individual registration and vote history | Turnout modeling, geography validation, party registration where available | State-by-state restrictions; PII controls required |
| Commercial voter files | Enhanced voter file, modeled partisanship, turnout, demographics | More complete campaign-grade scoring | Expensive, licensed, sensitive, cannot be freely redistributed |
| Campaign CRM / VAN / call / canvass data | Contact history, support IDs, responses | Ground-truth persuasion and turnout operations | Highly sensitive and campaign-specific |
| Commercial demographic append data | Consumer, lifestyle, phone/email, household data | May improve turnout or contactability models | Privacy and procurement review required |
| Proprietary precinct shapefiles | Cleaned precinct boundaries | Saves processing time | License restrictions; black-box processing risk |
| Expert litigation datasets | RPV analysis, expert-drawn alternatives | Useful in court context | Usually confidential or case-specific |

## Census block data acquisition workflow

1. Identify state FIPS code.
2. Download 2020 TIGER/Line tabulation block shapefile for the state.
3. Download P.L. 94-171 redistricting data summary file for the state.
4. Parse summary file tables:
   - P1: Race.
   - P2: Hispanic or Latino, and not Hispanic or Latino by Race.
   - P3: Race for population 18 years and over.
   - P4: Hispanic or Latino, and not Hispanic or Latino by Race for population 18 years and over.
   - P5: Group quarters population.
   - H1: Housing occupancy.
5. Join data to block geometries using GEOID.
6. Validate population totals against Census state totals.
7. Add geometry quality checks:
   - invalid geometries;
   - slivers;
   - zero-area records;
   - disconnected islands;
   - water-only artifacts if relevant.
8. Build adjacency graph using shared boundaries, not just point touches unless explicitly intended.
9. Store raw files immutably and write processed Parquet/GeoParquet outputs.

## Election-return acquisition workflow

1. Download official returns from state election office where possible.
2. Prefer precinct-level returns, but preserve county-level source files where precincts are unavailable.
3. Record whether returns are:
   - official final;
   - certified;
   - unofficial election night;
   - recanvassed;
   - amended.
4. Standardize candidate names, party labels, office names, district names, and election dates.
5. Normalize reporting units:
   - precinct;
   - ward;
   - township;
   - county;
   - absentee/early vote reporting unit;
   - central-count unit.
6. Validate against official state totals.
7. Join to precinct/VTD boundaries when possible.
8. If reporting units do not have boundaries, document allocation assumptions before block-level assignment.

## Block / precinct crosswalks

The hardest part of redistricting analytics is often not modeling. It is geographic reconciliation.

Recommended crosswalk tables:

| Crosswalk | Purpose |
|---|---|
| block_to_district | Assign blocks to enacted or simulated districts |
| block_to_precinct | Allocate election returns to blocks |
| block_to_vtd | Join Census VTD geography to election data |
| block_to_county | Count county splits and aggregate demographics |
| block_to_place | Count municipality splits |
| block_to_tract | Join ACS tract attributes |
| block_to_block_group | Join ACS block-group attributes |
| block_to_school_district | Community-of-interest proxy |
| block_to_tribal_area | Tribal representation and split analysis |
| precinct_to_election_returns | Historical vote and turnout |
| district_to_incumbent | Incumbent residence and pairing analysis |

## Data quality risks

| Risk | Why it matters | Mitigation |
|---|---|---|
| Precinct boundary drift | Precincts change between elections | Version precinct geometries by election date |
| Split precincts | One reporting unit can cross proposed districts | Allocate carefully and flag uncertainty |
| Absentee / early vote aggregation | Votes may not be assigned to residential precinct | Use state-specific allocation methods and sensitivity tests |
| Candidate uncontested races | Vote totals understate party preference | Use statewide race proxies or imputation |
| Census differential privacy | Small-area counts may include disclosure-avoidance noise | Avoid over-interpreting tiny blocks; aggregate for sensitive analysis |
| CVAP granularity | CVAP is not generally block-level | Model carefully at block group/tract or allocate with caveats |
| Voter-file restrictions | State laws and vendor licenses limit use | Maintain data-use register and access controls |
| Geometry invalidity | Bad geometries break adjacency and compactness metrics | Validate and repair geometries deterministically |
| Water adjacency / islands | Can distort contiguity and compactness | Apply state-specific geography rules |

## Storage conventions

```text
data/
  raw/
    census/pl94171/{year}/{state}/
    census/tiger/{year}/{state}/
    census/cvap/{year}/{state}/
    elections/returns/{state}/{year}/
    elections/precinct_boundaries/{state}/{year}/
    redistricting/enacted_plans/{state}/{plan_id}/
    redistricting/proposed_plans/{state}/{plan_id}/
  interim/
    geocrosswalks/{state}/{year}/
    cleaned_returns/{state}/{year}/
  processed/
    blocks/{state}/{year}.parquet
    precincts/{state}/{year}.parquet
    plans/{state}/{plan_id}.parquet
    district_scores/{state}/{plan_id}.parquet
  metadata/
    source_inventory.yml
    data_dictionary.yml
    license_register.yml
```

## Minimum metadata fields

Each dataset should have:

- source name;
- source URL;
- acquisition date;
- source owner;
- release version;
- geographic unit;
- election date, if applicable;
- file format;
- license or terms of use;
- allowed use;
- redistribution status;
- known quality issues;
- processing script;
- validation checks;
- row count;
- checksum.

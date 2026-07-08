# Dataset Registry

_Last updated: 2026-07-08_

This registry is the control document for every dataset acquired, downloaded, licensed, scraped, requested, or generated for the U.S. election analytics project. Populate this before or during ingestion so the project does not become an undocumented folder of CSVs.

---

## Status values

| Status | Meaning |
|---|---|
| `identified` | Source identified but not acquired |
| `requested` | Public-records/licensing request submitted |
| `acquired_raw` | Raw data downloaded/received, not validated |
| `profiled` | Basic row counts, fields, date ranges, geography assessed |
| `validated` | Totals and keys checked against source documentation or official benchmarks |
| `modeled` | Used in features/models |
| `published` | Used in public/client-facing outputs |
| `deprecated` | Replaced or no longer suitable |

---

## Sensitivity levels

| Sensitivity | Examples | Handling |
|---|---|---|
| `public_aggregate` | County returns, ACS tables, FEC candidate totals | Standard project storage |
| `public_microdata` | CES/Pew public-use survey files | Respect terms; no re-identification |
| `public_pii_restricted` | State voter files, donor names/addresses | Access controls, encryption, no unnecessary exports |
| `licensed_confidential` | Vendor voter files, ad intelligence, polling microdata | Contract-specific controls |
| `client_confidential` | Campaign CRM, canvass/call/text/donor data | Strict separation by client; least-privilege access |
| `derived_safe` | Aggregated features, district-level estimates | Check minimum cell sizes and license terms |

---

## Registry schema

| Field | Description |
|---|---|
| `dataset_id` | Stable snake_case identifier |
| `dataset_name` | Human-readable dataset name |
| `provider` | Organization/vendor/source |
| `source_url` | Landing page/API/public-records source |
| `access_type` | Open, free account, public-records request, licensed, client-provided, derived |
| `status` | One of the status values above |
| `sensitivity` | One of the sensitivity levels above |
| `geography` | Finest reliable geography |
| `unit_of_observation` | Row meaning: voter, respondent, precinct, county, candidate, contribution, ad, etc. |
| `time_coverage` | Years/dates covered |
| `update_cadence` | Static, annual, biennial, daily, live, election-cycle, unknown |
| `format` | CSV, Parquet, JSON, API, PDF, shapefile, GeoJSON, database, etc. |
| `raw_storage_path` | Location of immutable raw data |
| `processed_storage_path` | Location of cleaned/standardized data |
| `license_terms` | Link or short summary of permitted use |
| `primary_keys` | Candidate keys / composite keys |
| `join_keys` | Geography, candidate ID, FEC ID, precinct ID, GEOID, etc. |
| `validation_checks` | Totals, row counts, official benchmarks, schema tests |
| `known_limitations` | Missing states, lag, sample bias, nonrepresentative cells, etc. |
| `owner` | Person responsible |
| `next_action` | Next step |

---

## Initial registry table

> **P0/P1 ingestion note (2026-07-08):** The MEDSL president/senate/house ingestion
> (`data/medsl.py`), Census ACS (`data/acs.py`), and TIGER/Line (`geography/tiger.py`)
> pipelines are implemented and tested against the real source schemas, running raw →
> bronze → silver → gold with manifest, validation, and reports. A P1 baseline stack
> (presidential fundamentals, House partisanship, correlated simulation, calibration
> evaluation) is built on top. In the current sandbox, outbound access to Harvard
> Dataverse / GitHub-raw / the Census API is blocked, so the end-to-end builds were
> exercised with **synthetic fixtures** that match the real schemas (fictional data,
> clearly labelled with a SYNTHETIC banner on every report/model card). Re-run
> `ep-build-p0` and `ep-build-p1` (without `--offline`) in a networked environment to
> land the real certified snapshots and flip these rows to `validated`.

| dataset_id | dataset_name | provider | access_type | status | sensitivity | geography | unit_of_observation | time_coverage | priority | next_action |
|---|---|---|---|---|---|---|---|---|---:|---|
| `mit_us_president_returns` | U.S. President 1976-2020 Returns (`medsl_president_1976_2020`) | MIT Election Data and Science Lab | Open (Harvard Dataverse doi:10.7910/DVN/42MVDX) | profiled (pipeline built; live pull pending network) | public_aggregate | State | Race/candidate result | 1976-2020 | High | Run `ep-build-p0` in a networked env to land the real snapshot |
| `mit_us_senate_returns` | U.S. Senate 1976-2020 Returns (`medsl_senate_1976_2020`) | MIT Election Data and Science Lab | Open (Harvard Dataverse doi:10.7910/DVN/PEJ5QU) | profiled (pipeline built; live pull pending network) | public_aggregate | State | Race/candidate result | 1976-2020 | High | Run `ep-build-p0` in a networked env to land the real snapshot |
| `mit_us_house_returns` | U.S. House 1976-2022 Returns (`medsl_house_1976_2022`) | MIT Election Data and Science Lab | Open (Harvard Dataverse doi:10.7910/DVN/IG0UN2) | profiled (pipeline built; live pull pending network) | public_aggregate | Congressional district | Race/candidate result | 1976-2022 | High | Run `ep-build-p0` in a networked env to land the real snapshot |
| `mit_precinct_project` | Precinct-Level Election Results | MIT Election Data and Science Lab | Open | identified | public_aggregate | Precinct / county / state | Precinct result | Varies by state/year | High | Identify target states and available cycles |
| `openelections_results` | OpenElections Results | OpenElections | Open | identified | public_aggregate | State/county/precinct depending repo | Race result | Varies | High | Clone target-state repos |
| `census_acs_5yr` | ACS 5-Year Estimates | U.S. Census Bureau | Open API | profiled (pipeline built; live pull pending network) | public_aggregate | Block group and above (state ingested first) | Geography-variable estimate | Rolling 5-year | High | Run `ep-build-p1` in a networked env to land real ACS; extend below state |
| `census_cvap` | Citizen Voting Age Population Special Tabulation | U.S. Census Bureau | Open | identified | public_aggregate | Block group and above | Geography-race/ethnicity estimate | ACS 5-year vintages | High | Download latest and target-cycle vintages |
| `census_tiger_cd` | Congressional District / State / County TIGER Boundaries | U.S. Census Bureau | Open | profiled (pipeline built; live pull pending network) | public_aggregate | State / county / congressional district | Geometry | By Congress/year | High | Run TIGER download in a networked env; add county/CD vintages + crosswalks |
| `rdh_precinct_boundaries` | Precinct Boundaries and Election Results | Redistricting Data Hub | Open with account/terms | identified | public_aggregate | Precinct | Geometry/result | Varies | High | Register/review terms and download target states |
| `fec_api` | FEC API Data | Federal Election Commission | Open API | identified | public_aggregate/public_pii_restricted | Candidate/committee/contributor geography | Contribution, disbursement, filing | Current + historical | High | Create API key and ingestion scripts |
| `fec_bulk` | FEC Bulk Data / Raw .FEC Files | Federal Election Commission | Open | identified | public_aggregate/public_pii_restricted | Candidate/committee/contributor geography | Filing/transaction | Historical/current | Medium | Decide API vs bulk warehouse strategy |
| `ces_cumulative` | CES Cumulative File | Cooperative Election Study | Free account / Dataverse | identified | public_microdata | State/CD/ZIP/imputed county FIPS depending file | Respondent | 2006–2024 | High | Download and profile geography variables |
| `ces_current_cycle` | CES Current Election-Year File | Cooperative Election Study | Free account / Dataverse | identified | public_microdata | State/CD/ZIP depending release | Respondent | Current cycle | High | Monitor release schedule |
| `pew_atp` | American Trends Panel Datasets | Pew Research Center | Free account | identified | public_microdata | Public detailed geography masked | Respondent | 2014+ | Medium | Download election/validated-voter waves |
| `ap_votecast_puf` | AP VoteCast Public-Use Files | AP-NORC | Registration/terms | identified | public_microdata | State/national depending release | Respondent | 2017–2024 | Medium | Download latest PUF and codebook |
| `anes_public` | ANES Public-Use Data | ANES | Open | identified | public_microdata | State/CD/region typical | Respondent | Long historical | Medium | Download 2020/2024 and time-series files |
| `anes_restricted_geocodes` | ANES Restricted Geocode Files | ANES/ICPSR | Restricted application | identified | licensed_confidential | County/ZIP/tract depending study | Respondent geocode | Study-specific | Low-Medium | Decide whether restricted access is worth application |
| `nationscape` | Democracy Fund + UCLA Nationscape | Voter Study Group/UCLA | Free account/terms | identified | public_microdata | County/CD/city broad coverage | Respondent | 2019–2021 | Medium | Download for 2020 validation/MRP experiments |
| `prri_ava` | American Values Atlas / Religion Estimates | PRRI | Open/tools/data varies | identified | public_aggregate | State/county modeled | Geography estimate | Multi-year | Medium | Identify downloadable datasets and terms |
| `eac_eavs` | Election Administration and Voting Survey | U.S. Election Assistance Commission | Open | identified | public_aggregate | State/local jurisdiction | Election admin record | Biennial federal cycles | Medium | Download latest CSV/codebook |
| `uf_early_vote` | Early Vote / Turnout Data | UF Election Lab | Open | identified | public_aggregate | State/county/party/demographic where available | Aggregate count | Current/historical election cycle | Medium | Review current-cycle availability and fields |
| `voteview_nominate` | Voteview NOMINATE Data | Voteview | Open | identified | public_aggregate | Legislator/roll call | Member-vote/score | Historical/current Congress | Medium | Download members, votes, scores |
| `dime_cfscores` | DIME / CFscores | Stanford | Open/academic | identified | public_aggregate/public_microdata | Candidate/donor/committee | Contribution/network score | Historical | Medium | Download latest version and documentation |
| `meta_ad_library` | Meta Ad Library API | Meta | API/terms | identified | public_aggregate | Ad/page/location demographics ranges | Ad | Current + archive subject to retention | Medium | Create app/access and test query volume |
| `google_political_ads` | Google Political Ads Transparency Dataset | Google | Open / BigQuery | identified | public_aggregate | Advertiser/ad/region | Ad | Archive window | Medium | Connect BigQuery and inspect U.S. fields |
| `fcc_political_files` | FCC Political Files | FCC | Open web/PDF | identified | public_aggregate | Station/order/file | PDF/order record | Current + historical depending station | Medium | Build scraper/parser only after target races selected |
| `campaignview` | CampaignView House Candidate Websites | Academic dataset | Open | identified | public_microdata | Candidate/district | Platform point/biography | 2018–2022 | Medium | Download and map candidate IDs to FEC/results |
| `web_scores` | WEB-Scores | GitHub | Open | identified | public_aggregate | Candidate/district | Ideology/position score | 2018–2022 | Medium | Validate methodology and merge to CampaignView |
| `state_voter_file_target_state` | Target-State Official Voter File | State election authority | Public-records request / restricted | identified | public_pii_restricted | Individual voter/precinct/address | Registered voter | Current + vote history | High | Pick target state and review legal requirements |
| `ap_elections_api` | AP Elections API | Associated Press | Licensed | identified | licensed_confidential | Race/reporting unit | Live result | Live/certification | Medium | Defer until live newsroom product is justified |
| `commercial_voter_file` | Commercial National Voter File | L2/Catalist/TargetSmart/Data Trust/i360 | Licensed | identified | licensed_confidential | Individual voter/household | Voter | Current + historical snapshots depending vendor | Medium-High | Choose vendor based on client segment and budget |
| `adimpact` | AdImpact Political Ad Intelligence | AdImpact | Licensed | identified | licensed_confidential | Ad/market/race/sponsor | Ad occurrence/spend/creative | Current + historical | Medium | Defer until paid-media analytics is in scope |
| `statcast_public` | MLB Statcast Search CSV | MLB Baseball Savant | Open web CSV | identified | public_aggregate | Pitch/play/player/game | Pitch/event | 2008+ with feature caveats | Low | Keep as cross-domain pipeline reference, not election input |

---

## Dataset profile template

Copy this section for each acquired dataset.

```markdown
## <dataset_id>

- **Dataset name:**
- **Provider:**
- **Source URL:**
- **Access type:**
- **Status:**
- **Sensitivity:**
- **Raw storage path:**
- **Processed storage path:**
- **Date acquired:**
- **Time coverage:**
- **Geography:**
- **Unit of observation:**
- **File formats:**
- **Primary keys:**
- **Join keys:**
- **Core fields:**
- **License / permitted use:**
- **PII present?**
- **Validation checks completed:**
- **Known limitations:**
- **Downstream tables/models:**
- **Owner:**
- **Next action:**
```

---

## Validation checklist

Before a dataset moves from `acquired_raw` to `validated`, run these checks where applicable:

- Row count and column count recorded.
- Schema saved.
- Source documentation downloaded or linked.
- Geographic keys checked for valid FIPS/GEOID/district codes.
- Election totals reconciled to official certified totals.
- Candidate names and parties standardized.
- Dates parsed and timezone handled.
- Duplicate records identified and explained.
- Missingness profile generated.
- Suppressed/small-cell values documented.
- License and terms recorded.
- PII classification assigned.
- Raw file preserved immutably.
- Processed file generated reproducibly.

---

## Storage convention

Recommended local/project layout:

```text
data/
  raw/
    <provider>/<dataset_id>/<version_or_acquired_date>/
  interim/
    <dataset_id>/
  processed/
    <dataset_id>/
  external/
    documentation/
    codebooks/
    licenses/
  derived/
    features/
    modeling_tables/
    aggregates/
```

Recommended filename convention:

```text
<dataset_id>__<geography_or_unit>__<year_or_cycle>__<version>.<ext>
```

Example:

```text
ces_cumulative__respondent__2006_2024__v1.parquet
fec_api__candidate_summary__2026_cycle__2026-07-04.parquet
census_cvap__block_group__2018_2022__raw.csv
```

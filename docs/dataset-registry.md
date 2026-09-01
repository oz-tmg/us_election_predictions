# Dataset Registry

_Last updated: 2026-08-31_

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

> **Live-acquisition status (2026-08-25).** The earlier note here claimed the real
> snapshots would land by re-running the builds in a networked environment "with no code
> changes". That was **wrong**, and the actual state is recorded below. Every endpoint was
> re-verified against the live sources on 2026-07-31; the fixes are in `data/acquire.py`,
> `data/medsl.py`, `data/acs.py`, and `geography/tiger.py`.
>
> - **All three MEDSL series now cover 1976-2024** (previously 1976-2020 / 1976-2022), so
>   the 2024 presidential cycle is available for backtesting.
> - **MEDSL Senate is validated** (3,749 silver rows, 860 races, 1976-2024,
>   **0/860 vote-total reconciliation mismatches**). Its 2022 Alabama, Arizona, and Ohio
>   general-election totals also match the FEC's certified-results workbook exactly.
> - **MEDSL President and House are behind a Harvard Dataverse guestbook** that the access
>   API refuses. They are a documented, checksum-verified **one-time manual download**
>   (`pipelines/README.md`), not an automated pull. **Both landed 2026-08-31** — president
>   md5-verified against the published checksum, house size-verified — so no source is
>   synthetic any more and the SYNTHETIC banner no longer appears in any report.
> - **The house file is comma-separated despite its `.tab` name.** Dataverse serves both an
>   original and an ingested representation; `expected_size` was recorded from the original.
>   The parser now confirms the delimiter from the file's header rather than its extension.
> - **34 races (0.274%) are quarantined** for failing vote-total reconciliation, with a
>   documented exclusion, a per-race reason in `data/silver/quarantined_races.csv`, and a
>   sensitivity test in the forecast report (presidential MAE moves +0.000089). Causes are
>   heterogeneous and state-specific (Louisiana's all-party primary, New York's inconsistent
>   `BLANK` ballot rows), so no cause-specific correction is applied.
> - **MEDSL's `-1` is a 'not reported' sentinel, not zero.** It marks unopposed candidates in
>   states that elect without placing the race on the ballot. Those races keep their winner
>   and are flagged uncontested; the vote counts are null.
> - **Census ACS is validated** (key supplied 2026-08-03; vintage 2023, 52 state rows,
>   0 nulls). California, New York, and Texas population estimates match published
>   B01003 values exactly.
>   A keyless request returns HTTP 200 with an HTML "Missing Key" page, so response bodies
>   are validated before landing in `data/raw`.
> - **A Dataverse API token does not unlock the guestbook.** Verified 2026-08-03 with a
>   valid authenticated token, including `gbrecs=true`: still HTTP 400. The president and
>   house files require a browser guestbook response, once.
> - **TIGER is validated** for vintage 2024: 56 state/territory features, 3,235
>   counties/equivalents, and 440 congressional districts, with valid geometry, CRS,
>   present/unique GEOIDs, raw archive inventories, and manifests. Congressional
>   districts ship one zip per state, not as a national file.
>
> Use **`ep-build-p0 --require-live` / `ep-build-p1 --require-live`** for any run whose
> numbers will be published: it fails loudly instead of silently substituting synthetic
> fixtures. Flip a row to `validated` only after a `--require-live` run covers it.

| dataset_id | dataset_name | provider | access_type | status | sensitivity | geography | unit_of_observation | time_coverage | priority | next_action |
|---|---|---|---|---|---|---|---|---|---:|---|
| `mit_us_president_returns` | U.S. President 1976-2024 Returns (`medsl_president_1976_2024`) | MIT Election Data and Science Lab | Open, **guestbook-gated** (Harvard Dataverse doi:10.7910/DVN/42MVDX) | **validated** (manual snapshot 2026-08-31, md5-verified; 4,775 silver rows; reconciles after quarantine) | public_aggregate | State | Race/candidate result | 1976-2024 | High | One-time manual download per `pipelines/README.md`, then `ep-build-p0 --require-live` |
| `mit_us_senate_returns` | U.S. Senate 1976-2024 Returns (`medsl_senate_1976_2024`) | MIT Election Data and Science Lab | Open (Harvard Dataverse doi:10.7910/DVN/PEJ5QU) | **validated** (3,749 rows / 860 races; totals reconcile 860/860; AL/AZ/OH 2022 totals match FEC) | public_aggregate | State | Race/candidate result | 1976-2024 | High | Extend official spot-checks across cycles during model validation |
| `mit_us_house_returns` | U.S. House 1976-2024 Returns (`medsl_house_1976_2024`) | MIT Election Data and Science Lab | Open, **guestbook-gated** (Harvard Dataverse doi:10.7910/DVN/IG0UN2) | **validated** (manual snapshot 2026-08-31, size-verified; 32,148 silver rows; reconciles after quarantine) | public_aggregate | Congressional district | Race/candidate result | 1976-2024 | High | One-time manual download (tab-separated) per `pipelines/README.md`, then `ep-build-p0 --require-live` |
| `mit_precinct_project` | Precinct-Level Election Results | MIT Election Data and Science Lab | Open | identified | public_aggregate | Precinct / county / state | Precinct result | Varies by state/year | High | Identify target states and available cycles |
| `openelections_results` | OpenElections Results | OpenElections | Open | identified | public_aggregate | State/county/precinct depending repo | Race result | Varies | High | Clone target-state repos |
| `census_acs_5yr` | ACS 5-Year Estimates | U.S. Census Bureau | Open API, **key required** | **validated** (vintage 2023; 52 rows, 0 nulls; CA/NY/TX match B01003) | public_aggregate | Block group and above (state ingested first) | Geography-variable estimate | Rolling 5-year (default vintage 2023) | High | Extend below state and carry margins of error |
| `census_cvap` | Citizen Voting Age Population Special Tabulation | U.S. Census Bureau | Open | identified | public_aggregate | Block group and above | Geography-race/ethnicity estimate | ACS 5-year vintages | High | Download latest and target-cycle vintages |
| `census_tiger_cd` | Congressional District / State / County TIGER Boundaries | U.S. Census Bureau | Open | **validated** (2024: 56 state/territory, 3,235 county, 440 CD features; geometry/CRS/GEOIDs pass) | public_aggregate | State / county / congressional district | Geometry | By Congress/year | High | Add vintage-aware district crosswalks |
| `fec_federal_elections_2022` | Federal Elections 2022 certified-results workbook | Federal Election Commission | Open | **validated** (validation-only benchmark; AL/AZ/OH Senate totals extracted) | public_aggregate | State | Candidate/race result | 2022 | High | Retain as an independent benchmark and extend sampled states/cycles |
| `public_poll_toplines` | Governed public presidential poll toplines | Mixed public pollster releases | Manual public-release collection | profiled (schema, validation, averaging, and lineage built; no real snapshot registered) | public_aggregate | State (v0) | One poll/race topline | Historical/current | High | Register row-level sources and terms, then run `ep-build-p2 --polls <csv>` on held-out historical cycles |
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

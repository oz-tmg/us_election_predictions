# Ingestion Playbook

This playbook describes how to acquire, validate, store, version, and document datasets for the US Election Prediction project.

## Ingestion Principles

1. Raw data is immutable.
2. Every source has a manifest.
3. Every transformation is reproducible.
4. Every model input is traceable to raw data snapshots.
5. Sensitive data never enters the public repository.
6. Official sources override secondary sources when they conflict.
7. Live unofficial data must be clearly separated from certified results.

## Storage Layers

| Layer | Purpose | Example Path |
|---|---|---|
| raw | Exact downloaded/source snapshot | `data/raw/source=medsl/dataset=pres_county/cycle=2024/snapshot=2026-07-07/` |
| bronze | Parsed to tables with minimal cleaning | `data/bronze/medsl/pres_county/` |
| silver | Standardized schema, keys, types, geography | `data/silver/election_returns/` |
| gold | Modeling-ready features and marts | `data/gold/model_features/` |
| manifests | Source metadata, checksums, licenses, validation | `data/manifests/` |

## Required Manifest Fields

```yaml
source_id:
dataset_name:
source_owner:
source_url:
acquisition_method:
acquired_at:
snapshot_date:
election_cycle:
office_coverage:
geography_coverage:
file_format:
raw_path:
checksum_sha256:
license_or_terms:
permitted_use:
prohibited_use:
privacy_tier:
contains_personal_data:
contains_sensitive_data:
redistribution_allowed:
update_cadence:
validation_status:
known_caveats:
owner:
review_date:
```

## Standard Ingestion Workflow

### Step 1: Source Review

- Confirm source owner.
- Confirm whether the source is official, academic, vendor, scraped, or inferred.
- Read license and terms.
- Assign privacy tier.
- Confirm whether redistribution is allowed.
- Add source to `dataset-registry.md`.

### Step 2: Acquire Raw Snapshot

- Download or export source files.
- Save to `data/raw/` with source, dataset, cycle, and snapshot date.
- Do not edit raw files.
- Compute checksum.
- Save fetch logs.
- Create manifest.

### Step 3: Parse to Bronze

- Convert CSV, Excel, JSON, shapefile, PDF-derived table, or API response into a tabular or geospatial format.
- Preserve source columns where possible.
- Add ingestion metadata columns:
  - `source_id`
  - `source_file`
  - `snapshot_date`
  - `ingested_at`
  - `row_hash`

### Step 4: Validate Bronze

Checks:

- file opens;
- row count matches expectation;
- required columns exist;
- numeric columns parse;
- dates parse;
- no duplicate natural keys unless expected;
- candidate totals are nonnegative;
- geography IDs are valid;
- source totals reconcile if provided.

### Step 5: Transform to Silver

Standardize:

- state postal code;
- state FIPS;
- county FIPS;
- district ID;
- precinct ID;
- office type;
- election type;
- party;
- candidate name;
- incumbent flag;
- vote totals;
- vote share;
- two-party vote share;
- uncontested flag;
- certified/unofficial flag.

### Step 6: Validate Silver

Checks:

- unique key constraints;
- vote totals by race reconcile to source;
- no impossible vote shares;
- geography joins successfully;
- candidate-party mapping is stable;
- district boundaries match cycle;
- known special cases documented.

### Step 7: Build Gold Tables

Gold tables should be model-ready.

Examples:

- `gold_race_results`
- `gold_geography_features`
- `gold_candidate_features`
- `gold_polling_features`
- `gold_campaign_finance_features`
- `gold_turnout_features`
- `gold_judicial_features`
- `gold_forecast_training_rows`

### Step 8: Version and Publish

- Version raw snapshots with date and checksum.
- Version transformed datasets by build ID.
- Tag model runs with data snapshot IDs.
- Publish only permitted aggregate data.
- Keep restricted manifests private if they reveal sensitive vendor or campaign details.

## Dataset-Specific Playbooks

## MIT Election Data and Science Lab

Use for historical standardized returns.

Acquisition:

- Download from MIT Election Lab / Harvard Dataverse where available.
- Store each dataset by office, geography, and cycle range.

Validation:

- Check state/county/district keys.
- Confirm office and year coverage.
- Reconcile candidate totals where source totals exist.
- Compare a sample of rows to official state results.

Transform:

- Map to canonical office names.
- Standardize party labels.
- Standardize candidate names.
- Derive two-party vote share.
- Flag uncontested or missing-opposition races.

Known caveats:

- Coverage and update lag vary by office and geography.
- Precinct datasets can be incomplete or updated after initial release.

## Official State and County Election Returns

Use as the highest-authority source for final certified results.

Acquisition:

- Prefer official CSV/API downloads.
- If PDF or HTML is the only option, store original file and extraction script.
- Snapshot certified and unofficial results separately.

Validation:

- Reconcile county totals to statewide totals.
- Check candidate names and write-ins.
- Distinguish election-night unofficial from certified final.
- Identify recounts and amended certifications.

Transform:

- Standardize offices and candidate names.
- Preserve original office labels.
- Add certification status.

## Precinct Returns and Precinct Geography

Use for geospatial analysis, district profiles, redistricting crosswalks, and election-night models.

Acquisition:

- Collect precinct returns and precinct shapefiles for the same election cycle where possible.
- Store shapefiles as raw zip files and convert to GeoParquet in bronze/silver.

Validation:

- Check geometry validity.
- Confirm CRS.
- Confirm precinct names/codes join to returns.
- Compare sum of precinct votes to county/state totals.
- Identify split precincts and missing precincts.

Transform:

- Create stable precinct IDs when official IDs are absent.
- Build district assignment using spatial joins.
- Add county and district GEOIDs.

## Census ACS

Use for demographic and socioeconomic features.

Acquisition:

- Use Census API or downloaded ACS tables.
- Prefer ACS 5-year for small geographies.
- Store variable metadata with table IDs.

Validation:

- Check estimate and margin-of-error fields.
- Confirm geography universe.
- Confirm year and vintage.
- Avoid mixing 1-year and 5-year ACS without explicit reason.

Transform:

- Build derived rates: college share, income, age groups, race/ethnicity shares, homeownership, poverty, commute, language, etc.
- Carry margins of error where relevant.
- Join to district boundaries through GEOID or crosswalk.

## Census TIGER/Line

Use for official geography and boundaries.

Acquisition:

- Download current and historical shapefiles by geography type.
- Store zip files raw.
- Convert to GeoParquet for processing.

Validation:

- Check CRS and geometry validity.
- Confirm boundary vintage.
- Confirm GEOIDs match ACS and election returns.

Transform:

- Simplify geometries for web maps only, not for analysis.
- Preserve original geometries for spatial operations.

## FEC Campaign Finance

Use for federal candidates, committees, receipts, disbursements, cash, debt, and independent expenditures.

Acquisition:

- Use FEC bulk data or OpenFEC API.
- Store raw API responses or bulk files.

Validation:

- Confirm committee-candidate linkage.
- Confirm reporting period coverage.
- Check duplicates in amendments.
- Distinguish receipts, disbursements, independent expenditures, and cash-on-hand.

Transform:

- Aggregate to candidate/race/reporting-period.
- Create cumulative receipts, disbursements, cash, debt, outside spending.
- Aggregate donor geography only when allowed and necessary.

Legal note:

- Do not use contributor information for solicitation or commercial purposes.

## State Campaign Finance

Use for governor, state legislative, judicial, and other state races.

Acquisition:

- Source from state campaign-finance portals.
- Document state-specific reporting schedules and formats.

Validation:

- Confirm candidate IDs.
- Handle amended reports.
- Reconcile totals to candidate summary pages.

Transform:

- Standardize receipts, expenditures, cash, debt, independent expenditures.
- Create state-specific mapping notes.

## Polls

Use for pre-election vote intention, approval, issue salience, and favorability.

Acquisition:

- Prefer pollster releases and methodology PDFs.
- Store poll toplines and metadata.
- Avoid scraping sources that prohibit it.

Validation:

- Required fields: pollster, sponsor, field dates, sample size, population, mode, geography, question wording, candidate list.
- Check whether results are registered voter, likely voter, adult, all adults, primary electorate, or unknown.
- Record partisan sponsor or internal poll flag.

Transform:

- Standardize candidate names.
- Normalize toplines to two-party where appropriate.
- Estimate poll midpoint date.
- Add time-to-election.

## Race Ratings

Use as expert priors or comparison benchmarks.

Acquisition:

- Manually capture or scrape only where permitted.
- Store source, date, office, race, rating, and notes.

Validation:

- Ensure rating dates are correct.
- Preserve forecaster-specific categories.
- Map to common ordinal scale only in silver/gold.

Transform:

Suggested ordinal scale:

| Common Rating | Score |
|---|---:|
| Safe/Solid D | -4 |
| Likely D | -3 |
| Lean D | -2 |
| Tilt D | -1 |
| Toss-up | 0 |
| Tilt R | 1 |
| Lean R | 2 |
| Likely R | 3 |
| Safe/Solid R | 4 |

## Voter Files

Use only after legal and privacy review.

Acquisition:

- Confirm state law, vendor contract, permitted use, and retention terms.
- Store outside the public repository.
- Encrypt raw files.

Validation:

- Check field definitions.
- Confirm suppression/protected-voter handling.
- Check update date.
- Check duplicate voter IDs.
- Verify geography assignment.

Transform:

- Create private voter dimension.
- Hash internal IDs.
- Aggregate to precinct/district for public analysis.
- Do not export individual records.

## Campaign CRM Data

Use only in a restricted private environment.

Acquisition:

- Require written authorization.
- Export minimum necessary fields.
- Record data owner and deletion date.

Validation:

- Check opt-out fields.
- Check contact dates.
- Check survey response coding.
- Check duplicate people and households.

Transform:

- Separate contact history from response labels.
- Aggregate for public analysis.
- Delete raw export when no longer needed.

## Judicial Election Data

Use for partisan, nonpartisan, and retention races.

Acquisition:

- State election offices for results.
- State court sites for seat and term metadata.
- Judicial performance commissions for retention recommendations.
- Campaign-finance portals for spending.
- Ballotpedia and court pages for candidate discovery, then verify with official sources.

Validation:

- Confirm election type: partisan, nonpartisan, retention.
- Confirm court level.
- Confirm seat IDs.
- Confirm whether the race is statewide or district-based.
- Check roll-off against top-of-ticket results.

Transform:

- Create judicial race registry.
- Create retention yes/no target.
- Add appointment source and recommendation fields.

## Live Election-Night Results

Use for provisional estimates only.

Acquisition:

- Prefer licensed AP/DDHQ feeds or official state/county feeds.
- Record every update with timestamp.
- Never overwrite live snapshots.

Validation:

- Check monotonic vote totals, while allowing corrections.
- Detect duplicate batches.
- Detect candidate swaps or formatting changes.
- Compare reported precincts/expected vote to official metadata.

Transform:

- Store as event stream.
- Build latest-state table separately.
- Mark unofficial/provisional clearly.

## Quality Gates

A dataset cannot move to gold until:

- manifest complete;
- checksum stored;
- schema tests pass;
- primary key tests pass;
- geography joins pass;
- source totals reconcile or caveats documented;
- privacy tier assigned;
- legal constraints documented;
- known missingness documented.

## Recommended Tools

- Python: pandas, polars, pyarrow, geopandas, pydantic, great expectations or pandera.
- R: tidyverse, sf, arrow, targets.
- Database: Postgres/PostGIS for geospatial joins and reproducibility.
- Storage: Parquet/GeoParquet partitioned by source, office, cycle, geography.
- Orchestration: Prefect or Airflow.
- Versioning: Git for code and manifests; DVC or object-storage manifests for large data.
- Validation: dbt tests, Great Expectations, pandera, custom reconciliation scripts.

## Naming Conventions

Use lower snake case.

Examples:

```text
race_id = 2024_us_house_va_07_general
candidate_id = fec_H8VA07123
geography_id = state:51|county:059|district:cong_07
source_id = medsl_house_1976_2024
snapshot_id = medsl_house_1976_2024__2025_09_10
```

## Common Failure Modes

- treating unofficial election-night data as certified;
- mixing district boundaries across cycles;
- double-counting amended campaign-finance filings;
- ignoring uncontested races;
- assuming precinct IDs are stable;
- using ACS estimates without margins of error;
- joining county-level returns to district-level demographics incorrectly;
- underestimating correlated polling error;
- publishing sensitive derived attributes;
- using donor records or voter files outside permitted use.

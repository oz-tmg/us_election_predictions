# Pipelines

The P0 data-and-entity foundation runs as one reproducible command.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,geo]"      # package + ep-build-p0/ep-build-p1, pytest/ruff, geopandas
```

Credentials live in a **git-ignored `.env`** at the repo root; both builds load it at
start-up (existing shell variables win, so CI secrets override the file). Nothing
secret is written to a manifest, report, or log — only variable *names* are printed.

```ini
# .env  — never commit
CENSUS_API_KEY=...          # required for ACS
DATAVERSE_API_TOKEN=...     # optional; does NOT unlock the guestbook-gated files
```

## Build the P0 foundation

```bash
ep-build-p0                 # attempt live download, else synthetic fallback
ep-build-p0 --require-live  # FAIL if any source cannot be acquired for real
ep-build-p0 --offline       # force the synthetic MEDSL-schema fixture (no network)
ep-build-p0 --base /path/to/repo
```

Use **`--require-live` for any run whose numbers will be published.** The default mode
falls back to clearly-labelled synthetic fixtures so the pipeline is always exercised,
but that means a default run can "pass" on fictional data; `--require-live` exits
non-zero instead.

The build runs the medallion flow and writes to the data lake + `reports/`:

```
raw (download or synthetic) -> manifest (sha256 + privacy tier)
  -> bronze parse -> validate -> silver election_returns
  -> canonical geography spine -> gold race_results
  -> validate -> reports/data_quality_report.md
```

Outputs: `data/silver/election_returns.{parquet,csv}`, `data/silver/geography.parquet`,
`data/gold/race_results.{parquet,csv}`, per-source manifests in `data/manifests/`, and
the Markdown data-quality report. Bulk data under `data/` is git-ignored; manifests and
the report are tracked.

## Build the P1 baselines

```bash
ep-build-p1                # runs P0, then the baseline forecasting stack
ep-build-p1 --require-live # FAIL unless MEDSL, ACS, and TIGER are all real
ep-build-p1 --offline      # synthetic fixtures (no network)
```

Adds ACS (P0-006) + TIGER (P0-007) ingestion, a presidential fundamentals panel and
OLS baseline (P1-001), a House district partisanship score (P1-002), a correlated
simulation (P1-005), and calibration evaluation (P1-006). Writes
`data/gold/{presidential_panel,house_partisanship_score,acs_state_features}.parquet`,
`data/silver/tiger_{state,county,cd}_2024.parquet`, raw TIGER archive inventories,
source manifests, `reports/source_validation_report.md`,
`reports/forecast_backtest_report.md`, and `reports/model_cards/`. The strict build
also checks sampled MEDSL Senate totals against certified FEC results and ACS population
features against published B01003 values. Historical backtest only — no live forecast
is published.

## Governance guard

```bash
python pipelines/validate/check_no_restricted_data.py --all   # CI / pre-commit
pre-commit install                                            # enable on every commit
```

Blocks Tier 3-5 personal/operational data and bulk data from entering the public repo
(CLAUDE.md §5).

## Credentials

| Source | Requirement | How |
|---|---|---|
| Census ACS | **API key required.** A keyless request returns HTTP 200 with an HTML "Missing Key" page, not data. | Request at <https://api.census.gov/data/key_signup.html>, set `CENSUS_API_KEY` |
| Harvard Dataverse | Optional account token. **Verified 2026-08-03: a valid token does _not_ unlock the guestbook-gated MEDSL files** (`gbrecs=true` and authenticated requests both return HTTP 400). It is kept only for ungated files and future use. | Set `DATAVERSE_API_TOKEN` |

## Live acquisition, per source

All three MEDSL series now run **1976-2024** (they previously ended 2020/2022).

| Source | Acquisition | Notes |
|---|---|---|
| MEDSL Senate | automatic ✅ landed | Downloads via the Dataverse datafile API. |
| MEDSL President | **one-time manual** | Behind a Dataverse guestbook; the API refuses it even when authenticated. |
| MEDSL House | **one-time manual** | Same guestbook. Ships tab-separated, not CSV. |
| Census ACS | automatic ✅ landed | 5-year estimates, state level; vintage 2023 by default. |
| Census TIGER | automatic ✅ landed | 2024 state/county/CD GeoParquet validated; **congressional districts ship one zip per state**. |

### Guestbook-gated sources (president, house)

The build prints exactly what to do, including the drop path and the published
checksum. In short: open the dataset page, accept the guestbook, and save the file
unmodified to

```
data/raw/source=medsl/dataset=<office>/manual/<published-filename>
```

Re-run the build. The file's size/checksum is verified against the source's published
metadata before it is used, so a truncated or edited manual download cannot reach
silver. Manual snapshots are picked up automatically on every later run.

## Standardization the live schema requires

The real MEDSL files need transforms the synthetic fixtures never exercised. Each is
reported in `reports/data_quality_report.md` rather than applied silently:

- **Primaries dropped** — files mix `gen`/`GEN` with `pre` (primary) and runoff rows;
  comparing a primary to a general breaks like-for-like (CLAUDE.md §6).
- **Per-mode rows collapsed** — some rows are broken out by voting mode; a published
  `total` row is preferred, otherwise breakdowns are summed. Mixing them double-counts.
- **Fusion voting summed** — NY-style fusion puts one candidate on several party lines.
  Votes are summed per candidate and the major-party label kept, so a candidate's own
  vote is not split (verified against 1976 NY Senate: Moynihan 3,422,594 / Buckley
  2,836,633).
- **Specials keyed separately** — a special and a regular race in the same state-year
  are distinct races.
- **Write-ins excluded from the contender count** — a safe seat with scattered write-ins
  is still uncontested.

## Tests

```bash
pytest -q                            # 53 unit + integration tests
ruff check src pipelines tests
ruff format --check src pipelines tests
mypy src
```

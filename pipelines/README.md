# Pipelines

The P0 data-and-entity foundation runs as one reproducible command.

## Build the P0 foundation

```bash
pip install -e .            # installs the `election_prediction` package + `ep-build-p0`

ep-build-p0                 # attempt live MEDSL download, else synthetic fallback
ep-build-p0 --offline      # force the synthetic MEDSL-schema fixture (no network)
ep-build-p0 --base /path/to/repo
```

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
ep-build-p1              # runs P0, then the baseline forecasting stack
ep-build-p1 --offline    # synthetic fixtures (no network)
```

Adds ACS (P0-006) + TIGER (P0-007) ingestion, a presidential fundamentals panel and
OLS baseline (P1-001), a House district partisanship score (P1-002), a correlated
simulation (P1-005), and calibration evaluation (P1-006). Writes
`data/gold/{presidential_panel,house_partisanship_score,acs_state_features}.parquet`,
`reports/forecast_backtest_report.md`, and `reports/model_cards/`. Historical backtest
only — no live forecast is published.

## Governance guard

```bash
python pipelines/validate/check_no_restricted_data.py --all   # CI / pre-commit
pre-commit install                                            # enable on every commit
```

Blocks Tier 3-5 personal/operational data and bulk data from entering the public repo
(CLAUDE.md §5).

## Live vs. synthetic

`src/election_prediction/data/medsl.py` carries the real Harvard Dataverse endpoints and
MEDSL column layouts for president (1976-2020), senate (1976-2020), and house
(1976-2022). Where outbound access is blocked, the build falls back to a **synthetic
fixture that matches the MEDSL schema** (fictional data, clearly labelled) so the
pipeline is always exercised. Run without `--offline` in a networked environment to land
the real certified snapshots — no code changes needed.

## Tests

```bash
pytest -q                  # 15 unit + integration tests
ruff check src pipelines tests
```

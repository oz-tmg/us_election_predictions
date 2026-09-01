# Data-Quality Report — P0 Foundation

_Generated: 2026-09-01T19:37:17+00:00Z_

> Scope: loaded MEDSL federal returns (silver), model-ready race table (gold),
> and the canonical geography spine. Nonpartisan; historical/certified returns.

## Acquisition mode

- `president`: verified manual download
- `us_house`: verified manual download
- `us_senate`: live download

## Coverage

- Returns rows: **40,502**
- Distinct races: **12,358**
- Cycles: 1976, 1978, 1980, 1982, 1984, 1986, 1988, 1990, 1992, 1994, 1996, 1998, 2000, 2002, 2004, 2006, 2008, 2010, 2012, 2014, 2016, 2018, 2020, 2021, 2022, 2024
- Offices: president, us_house, us_senate
- States covered: 51
- Geography spine rows: 558

## Duplicate keys

- `returns_race_candidate_party`: 0 OK
- `race_table_race_id`: 0 OK
- `geography_geography_id`: 0 OK

## Vote-total reconciliation

- Races checked (totalvotes populated): 12,354
- Races where candidate sum ≠ reported total: **0** (0.0%, tolerance 0.5%)

## Quarantined races (excluded from the modeling layer)

- Races excluded: **34** of 12,392 (0.274%)

These races' candidate votes do not sum to the jurisdiction's reported total. The causes are heterogeneous and state-specific, so they are excluded uniformly and retained at `data/silver/quarantined_races.csv` with a reason, rather than corrected by cause-specific rules (CLAUDE.md §6). The reason labels below are descriptive: confirming why any given race fails requires the state's certified return, not an inference from the discrepancy.

- 28 — candidate_sum_exceeds_total
- 3 — rounding_or_transcription (<=10 votes)
- 2 — candidate_sum_below_total
- 1 — multi_round_contest_suspected (candidate sum ~2x total)

## Standardization decisions

What the raw → silver transform dropped or merged, per source:

- `president` — dropped non general: 0, mode rows collapsed: 0, fusion candidates merged: 42, unreported vote races: 0, rows: 4,775
- `us_house` — dropped non general: 60, mode rows collapsed: 107, fusion candidates merged: 1,134, unreported vote races: 3, rows: 32,148
- `us_senate` — dropped non general: 9, mode rows collapsed: 129, fusion candidates merged: 41, unreported vote races: 0, rows: 3,749

Primaries and other non-general stages are excluded so comparisons stay like-for-like; fusion-voting lines are summed per candidate so a candidate's own vote is not split across party lines.

## Contest flags

- Uncontested races: 687 (5.56%) — handled explicitly, never as 100–0 truth (CLAUDE.md §6).
- Uncertified races: 25

## Missingness (columns with any nulls)

- `district_num`: 20.99%
- `vote_share`: 0.01%
- `candidatevotes`: 0.01%
- `totalvotes`: 0.01%

## Source freshness

- `medsl_house_1976_2024` — snapshot 2026-09-01 (0 days, fresh)
- `medsl_president_1976_2024` — snapshot 2026-09-01 (0 days, fresh)
- `medsl_senate_1976_2024` — snapshot 2026-09-01 (0 days, fresh)

## Overall

**PASS** — keys unique and vote totals reconcile.

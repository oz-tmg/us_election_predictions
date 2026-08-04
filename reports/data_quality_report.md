# Data-Quality Report — P0 Foundation

_Generated: 2026-08-04T05:24:48+00:00Z_

> Scope: loaded MEDSL federal returns (silver), model-ready race table (gold),
> and the canonical geography spine. Nonpartisan; historical/certified returns.

> ⚠️ **SYNTHETIC DATA IN THIS RUN.** Sources acquired as synthetic fixtures: president, us_house. Numbers below describe the *pipeline*, not real elections.

## Acquisition mode

- `president`: SYNTHETIC fixture
- `us_house`: SYNTHETIC fixture
- `us_senate`: live download

## Coverage

- Returns rows: **5,910**
- Distinct races: **1,823**
- Cycles: 1976, 1978, 1980, 1982, 1984, 1986, 1988, 1990, 1992, 1994, 1996, 1998, 2000, 2002, 2004, 2006, 2008, 2010, 2012, 2014, 2016, 2018, 2020, 2021, 2022, 2024
- Offices: president, us_house, us_senate
- States covered: 51
- Geography spine rows: 230

## Duplicate keys

- `returns_race_candidate`: 0 OK
- `race_table_race_id`: 0 OK
- `geography_geography_id`: 0 OK

## Vote-total reconciliation

- Races checked (totalvotes populated): 1,823
- Races where candidate sum ≠ reported total: **0** (0.0%, tolerance 0.5%)

## Standardization decisions

What the raw → silver transform dropped or merged, per source:

- `president` — dropped non general: 0, mode rows collapsed: 0, fusion candidates merged: 0, rows: 765
- `us_house` — dropped non general: 0, mode rows collapsed: 0, fusion candidates merged: 0, rows: 1,396
- `us_senate` — dropped non general: 9, mode rows collapsed: 129, fusion candidates merged: 41, rows: 3,749

Primaries and other non-general stages are excluded so comparisons stay like-for-like; fusion-voting lines are summed per candidate so a candidate's own vote is not split across party lines.

## Contest flags

- Uncontested races: 32 (1.76%) — handled explicitly, never as 100–0 truth (CLAUDE.md §6).
- Uncertified races: 9

## Missingness (columns with any nulls)

- `district_num`: 76.38%

## Source freshness

- `medsl_house_1976_2024` — snapshot 2026-08-03 (0 days, fresh)
- `medsl_president_1976_2024` — snapshot 2026-08-03 (0 days, fresh)
- `medsl_senate_1976_2024` — snapshot 2026-08-03 (0 days, fresh)

## Overall

**PASS** — keys unique and vote totals reconcile.

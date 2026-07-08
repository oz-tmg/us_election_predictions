# Data-Quality Report — P0 Foundation

_Generated: 2026-07-08T09:27:47Z_

> Scope: loaded MEDSL federal returns (silver), model-ready race table (gold),
> and the canonical geography spine. Nonpartisan; historical/certified returns.

## Coverage

- Returns rows: **2,365**
- Distinct races: **1,031**
- Cycles: 2008, 2012, 2016, 2018, 2020, 2022, 2024
- Offices: president, us_house, us_senate
- States covered: 51
- Geography spine rows: 230

## Duplicate keys

- `returns_race_candidate`: 0 OK
- `race_table_race_id`: 0 OK
- `geography_geography_id`: 0 OK

## Vote-total reconciliation

- Races checked (totalvotes populated): 1,031
- Races where candidate sum ≠ reported total: **0**

## Contest flags

- Uncontested races: 20 (1.94%) — handled explicitly, never as 100–0 truth (CLAUDE.md §6).
- Uncertified races: 0

## Missingness (columns with any nulls)

- `district_num`: 40.97%

## Source freshness

- `medsl_house_1976_2022` — snapshot 2026-07-08 (0 days, fresh)
- `medsl_president_1976_2020` — snapshot 2026-07-08 (0 days, fresh)
- `medsl_senate_1976_2020` — snapshot 2026-07-08 (0 days, fresh)

## Overall

**PASS** — keys unique and vote totals reconcile.

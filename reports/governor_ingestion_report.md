# Governor Ingestion Report

> Tier 0 public aggregate (MEDSL). Historical returns only — no forecast is published.

## Coverage

| Cycle | Level | Governor states | Counties | Status |
|---:|---|---:|---:|---|
| 2016 | state_office | 12 | 0 | ok |
| 2018 | precinct | 34 | 1,974 | ok |
| 2020 | precinct | 11 | 528 | ok |
| 2022 | precinct | 34 | 2,053 | ok |
| 2024 | precinct | 11 | 565 | ok |

## County-level governor vs president (presidential cycles)

`ticket_split` is the governor's two-party Democratic share minus the president's in the same county; `roll_off` is the share of presidential voters who cast no gubernatorial vote. Both are **descriptive associations**, not evidence that presidential turnout caused a gubernatorial result.

| Cycle | Counties | Mean ticket split | Mean roll-off |
|---:|---:|---:|---:|
| 2020 | 528 | -0.0013 | +0.0104 |
| 2024 | 565 | +0.0186 | +0.0179 |

> ⚠️ **82 counties across 4 state-cycles are flagged `two_party_suspect`** and are excluded from the means above. A major party shows zero votes there because the nominee ran on a fusion or joint ticket that MEDSL's `party_simplified` records as OTHER — not because nobody ran. Affected: ND 2020, VT 2020, IN 2024, VT 2024. Two-party share and `ticket_split` are meaningless for these rows; Vermont 2024 otherwise computes a -0.66 'split' that is pure artefact. Fixing this needs the candidate/party alias crosswalk (backlog P0-003), not a substring rule.

## Known limitations

- Only ~11 states elect governors in presidential years, and that set skews small and rural, so on-cycle vs off-cycle comparisons rest on a small, non-random sample.
- Counties are matched on `county_fips` within a cycle; no cross-cycle county boundary crosswalk is applied.
- Coverage depends on which precinct drops have been downloaded; see the table above.

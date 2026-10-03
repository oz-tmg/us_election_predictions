# Findings against the sealed pre-registration of 2026-11-03

**This file does not amend the registration.** The seal at
`reports/preregistration_2026-11-03.json` is fixed; a changed forecast is a *new*
registration under a new date, never an edit (PROJECT_CONTEXT.md §13). This is the
record of things learned after sealing that bear on how it should be scored.

- Registration: `2026-09-30` · election `2026-11-03`
- `predictions_sha256`: `4de09ecf82f218ee807edc6d4eaae9b50d51968d0957177f33b762fad4100882`
- Commit at registration: `9e4e512e6ede498f4e04afa5b17a556dbaec8529`

---

## F-1 (2026-10-02) — the special-election baselines moved, by less than five thousandths

**What changed.** `features/cd_baseline` was discarding county-level early and absentee
ballots wherever the reporting county spanned two congressional districts. Those ballots
are now allocated within their county. Every one of the ten specials the registration
scores takes its `baseline_dem_share` from
`data/gold/cd_presidential_baseline_2024.parquet`, so the fix moves the denominator of
each overperformance calculation that feeds the sealed national-environment band.

**How much.** Re-derived per district and diffed against the sealed values:

| special | sealed | re-derived | delta | allocated share | quality | scored |
|---|---:|---:|---:|---:|---|:--:|
| `2026-ga-cd13` | 0.716404 | 0.709589 | -0.006815 | 0.0462 | ok | N |
| `2025-tn-cd07` | 0.376359 | 0.380947 | +0.004588 | 0.0316 | ok | Y |
| `2025-fl-cd01` | 0.315095 | 0.312064 | -0.003031 | 0.0259 | ok | Y |
| `2026-ga-cd14-r1` | 0.309471 | 0.312403 | +0.002932 | 0.0109 | ok | N |
| `2026-ga-cd14-runoff` | 0.309471 | 0.312403 | +0.002932 | 0.0109 | ok | Y |
| `2025-va-cd11` | 0.678638 | 0.676548 | -0.002090 | 0.0250 | ok | Y |
| `2026-nj-cd11` | 0.547419 | 0.547439 | +0.000020 | 0.0001 | ok | Y |
| `2025-fl-cd06` | 0.348756 | 0.348741 | -0.000015 | 0.0073 | ok | Y |
| `2026-ca-cd14` | 0.684424 | 0.684424 | +0.000000 | 0.0000 | ok | Y |
| `2025-tx-cd18` | 0.701937 | 0.701937 | -0.000000 | 0.0000 | ok | Y |
| `2026-ca-cd01` | 0.371887 | 0.371887 | +0.000000 | 0.0000 | ok | N |

Largest absolute movement across all eleven rows: **0.006815** (`2026-ga-cd13`, which the registration excludes from the metric).
Largest among the **scored** rows: **0.004588** (`2025-tn-cd07`). Five rows move by less than 0.0001.

**What it means for scoring.** The direction of the error was predictable and the
magnitude is not material. None of the ten districts is in a state where county-level
reporting dominates: the largest `allocated_share` among them is 0.046, and the measured
allocation error below a 10% allocated share is an MAE of 0.0001 across 48 districts
(`reports/cd_allocation_backtest.json`). Every district stays `baseline_quality = ok`.
A 0.0046 shift in one district's baseline moves that district's overperformance by the
same amount and the ten-district mean by roughly a tenth of that, which is two orders of
magnitude smaller than the 0.25–1.00 shrinkage sweep the band already reports as its
dominant uncertainty.

**Disposition: score the registration as sealed.** The sealed baselines are what was
predicted from, and re-deriving them now would be the forking path the pre-registration
exists to prevent. This finding is the audit trail: a reader can see that the inputs
moved, by how much, and why it does not change the verdict — rather than discovering
later that a dependency was quietly corrected underneath a sealed claim.

**Re-verified 2026-10-02 against the final baselines.** The table above was computed before
two further fixes landed (fusion lines, and the at-large district label). Re-running it
against the rebuilt `cd_presidential_baseline_2024.parquet` reproduces every figure
unchanged — neither fix touches a state holding one of these specials — and adds an
independent check the earlier run could not make. Each district's recovered presidential
vote now carries `coverage_vs_house_vote`, its ratio against its own certified House
return:

| special | coverage vs House vote |
|---|---:|
| `2025-fl-cd01` | 1.0049 |
| `2025-fl-cd06` | 1.0134 |
| `2025-tn-cd07` | 1.0036 |
| `2025-va-cd11` | 0.9855 |
| `2025-tx-cd18` | 1.0074 |
| `2026-ca-cd01` | 0.9933 |
| `2026-ca-cd14` | 1.0105 |
| `2026-ga-cd13` | 1.0328 |
| `2026-ga-cd14-r1` | 1.0008 |
| `2026-ga-cd14-runoff` | 1.0008 |
| `2026-nj-cd11` | 1.0241 |

The range is **0.9855 to 1.0328** against a national median of 1.0021, so none of these ten districts is missing presidential vote. That is the thing a baseline has to be right about, and it is now measured against a comparator outside the precinct file rather than inferred from the file's own internal consistency.

**What would have changed the disposition.** Had any scored district sat in New Jersey
or Washington — where 2020-style county-level reporting puts `allocated_share` above
0.5 and measured MAE above 0.039 — the baseline would have been materially wrong and
the honest response would be a new registration, not a note. `2026-nj-cd11` is the near
miss, and it is safe because New Jersey's *2024* file reports at precinct level
(`allocated_share` 0.0001); it is only the 2020 file that does not.


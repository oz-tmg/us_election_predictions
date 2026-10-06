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

---

## F-2 (2026-10-05) — New York's 26 seats are priced off 2022, because its 2024 returns were quarantined

**Found while answering "what should we do next", not by looking for it.** This is a
material defect that the registration's `declared_defects` does not list, recorded here
before the outcome is known.

**What happened.** All **26** of New York's 2024 U.S. House races are in
`data/silver/quarantined_races.csv`, every one for `candidate_sum_exceeds_total` by 6-10%.
`data/quarantine.py` requires candidate votes to equal the reported total *exactly*, and New
York's returns carry fusion tickets — MEDSL's own `fusion_ticket` column marks 36 of 158 New
York 2024 rows TRUE — so a candidate's Democratic and Working Families lines sum against a
`totalvotes` that counts each voter once. The cause is an accounting convention, not bad
data. The consequence is that New York has **no 2024 House result anywhere in silver**, so
the House model's `lag_dem_share` for its 2026 seats falls back to **2022**.

2022 was New York's Republican high-water mark. 2024 swung back.

**How much.** The sealed forecast's New York seats, against what 2024 actually returned
(computed from the raw MEDSL file, which is intact — only the gate rejected it):

| seat | sealed mean | sealed P(Dem) | 2024 actual | error |
|---|---:|---:|---:|---:|
| NY-01 | 0.4132 | 0.214 | 0.4478 | -0.0347 |
| NY-02 | 0.3850 | 0.150 | 0.4023 | -0.0173 |
| NY-03 | 0.4226 | 0.243 | 0.5179 | -0.0953 |
| NY-04 | 0.4332 | 0.275 | 0.5115 | -0.0783 |
| NY-05 | 0.7378 | 0.983 | 0.7482 | -0.0104 |
| NY-06 | 0.6770 | 0.941 | 0.6172 | +0.0598 |
| NY-07 | 0.7673 | 0.992 | 0.7811 | -0.0137 |
| NY-08 | 0.7189 | 0.973 | 0.7539 | -0.0349 |
| NY-09 | 0.8716 | 0.999 | 0.7425 | +0.1290 |
| NY-10 | 0.7889 | 0.996 | 0.8459 | -0.0571 |
| NY-11 | 0.3794 | 0.144 | 0.3590 | +0.0204 |
| NY-12 | 0.7743 | 0.993 | 0.8051 | -0.0308 |
| NY-13 | 0.8716 | 1.000 | 0.8354 | +0.0362 |
| NY-14 | 0.7209 | 0.974 | 0.6920 | +0.0289 |
| NY-15 | 0.7787 | 0.993 | 0.7836 | -0.0049 |
| NY-16 | 0.6789 | 0.946 | 0.7158 | -0.0370 |
| NY-17 | 0.4412 | 0.297 | 0.4678 | -0.0266 |
| NY-18 | 0.6053 | 0.829 | 0.5717 | +0.0336 |
| NY-19 | 0.4387 | 0.290 | 0.5111 | -0.0724 |
| NY-20 | 0.6291 | 0.876 | 0.6113 | +0.0178 |
| NY-21 | 0.3892 | 0.159 | 0.3801 | +0.0091 |
| NY-22 | 0.4403 | 0.292 | 0.5456 | -0.1053 |
| NY-23 | 0.3624 | 0.108 | 0.3421 | +0.0203 |
| NY-24 | 0.3582 | 0.102 | 0.3433 | +0.0148 |
| NY-25 | 0.6226 | 0.865 | 0.6082 | +0.0144 |
| NY-26 | 0.6771 | 0.942 | 0.6517 | +0.0254 |

Mean absolute error against 2024: **0.0396**. Nine of 26 seats are priced
more than three points too Republican. The mean signed error is only -0.0080,
so this is not a clean uniform bias — it is error concentrated in the competitive suburban
seats that flipped back to Democrats in 2024, with compensating error elsewhere.

**The sharp end.** Four seats are priced **below 50%** Democratic in a sealed forecast when
Democrats won them in 2024:

- **NY-03** — sealed P(Dem) **0.243**, 2024 actual 0.5179
- **NY-04** — sealed P(Dem) **0.275**, 2024 actual 0.5115
- **NY-19** — sealed P(Dem) **0.290**, 2024 actual 0.5111
- **NY-22** — sealed P(Dem) **0.292**, 2024 actual 0.5456

Each is given roughly a one-in-four chance in a seat the party held going in.

**Disposition: the seal stands, and this becomes a pre-declared expectation.** Editing the
registration is not available — a changed forecast is a new registration. What is available,
and is the point of recording this 29 days before the election, is a **directional
prediction made before the outcome**: New York's seats should score visibly worse than the
chamber, and the four seats above are the specific places to look. If they do, this finding
explains it and the scorer should not be credited with having anticipated it; if they do not,
that is evidence the 2022 prior was not as costly as it looks. Either way the claim is on
the record first.

**What this says about the quarantine rule.** F-1 and this finding are the same defect seen
twice: exact-equality reconciliation against a total that excludes fusion lines. In the CD
baselines it cost New York 8% of its presidential vote (fixed 2026-10-02 by resolving fusion
by candidate). In the certified returns it costs New York its entire 2024 House result and,
through that, 26 seats of the 2026 forecast. The uniform-exclusion principle is right; exact
equality against an inconsistent `totalvotes` is the wrong way to operationalise it. This
moves the threshold question in `PROJECT_CONTEXT.md` §15 from an open question to a known
cost with a number attached.

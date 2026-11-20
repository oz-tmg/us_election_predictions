# Interim scorecard, as of 2026-11-20

Scores on seats certified by the as-of date only. Not a verdict on any run: the certified subset is not a random sample of seats, and chamber-level error and the registered failure condition are not evaluable until every House seat is scoreable.

Seats observed: 209 in 24 states. **Certified and scoreable: 3** (VT, WY). Ledger snapshots used: 5.

## preregistration_2026-11-03

scored holdout (sealed 2026-09-30). sealed registration: digest verified.

| Assumption | Seats | MAE (share) | Brier | Log score | 90% coverage | Winner accuracy |
|---|---:|---:|---:|---:|---:|---:|
| shrinkage=0.25 | 3 | 0.0410 | 0.0029 | 0.0532 | 1.000 | 1.000 |
| shrinkage=0.33 | 3 | 0.0385 | 0.0034 | 0.0564 | 1.000 | 1.000 |
| shrinkage=0.5 | 3 | 0.0332 | 0.0051 | 0.0661 | 1.000 | 1.000 |
| shrinkage=0.75 | 3 | 0.0368 | 0.0094 | 0.0870 | 1.000 | 1.000 |
| shrinkage=1 | 3 | 0.0446 | 0.0167 | 0.1156 | 1.000 | 1.000 |

Chamber-level failure condition: `not_evaluable_incomplete_chamber`.

## refresh_2026-10-22

comparison: last refresh before the Senate specification change. frozen run: file SHA-256 verified against the comparison set.

| Assumption | Seats | MAE (share) | Brier | Log score | 90% coverage | Winner accuracy |
|---|---:|---:|---:|---:|---:|---:|
| shrinkage=0.25 | 3 | 0.0576 | 0.0279 | 0.1385 | 1.000 | 1.000 |
| shrinkage=0.33 | 3 | 0.0604 | 0.0323 | 0.1490 | 1.000 | 1.000 |
| shrinkage=0.5 | 3 | 0.0664 | 0.0447 | 0.1788 | 1.000 | 1.000 |
| shrinkage=0.75 | 3 | 0.0752 | 0.0676 | 0.2326 | 1.000 | 1.000 |
| shrinkage=1 | 3 | 0.0841 | 0.0972 | 0.2992 | 1.000 | 0.667 |

Chamber-level failure condition: `not_evaluable_incomplete_chamber`.

## refresh_2026-10-29

comparison: final pre-election refresh (v1_open_seat_holder). frozen run: file SHA-256 verified against the comparison set.

| Assumption | Seats | MAE (share) | Brier | Log score | 90% coverage | Winner accuracy |
|---|---:|---:|---:|---:|---:|---:|
| shrinkage=0.25 | 3 | 0.0434 | 0.0115 | 0.0923 | 1.000 | 1.000 |
| shrinkage=0.33 | 3 | 0.0463 | 0.0138 | 0.0996 | 1.000 | 1.000 |
| shrinkage=0.5 | 3 | 0.0523 | 0.0205 | 0.1211 | 1.000 | 1.000 |
| shrinkage=0.75 | 3 | 0.0611 | 0.0350 | 0.1626 | 1.000 | 1.000 |
| shrinkage=1 | 3 | 0.0700 | 0.0568 | 0.2172 | 1.000 | 1.000 |

Chamber-level failure condition: `not_evaluable_incomplete_chamber`.

## scenario_south_texas_2026-10-29

scenario, scored for information only (not a forecast). frozen run: file SHA-256 verified against the comparison set.

| Assumption | Seats | MAE (share) | Brier | Log score | 90% coverage | Winner accuracy |
|---|---:|---:|---:|---:|---:|---:|
| shrinkage=0.25 | 3 | 0.0434 | 0.0115 | 0.0923 | 1.000 | 1.000 |
| shrinkage=0.33 | 3 | 0.0463 | 0.0138 | 0.0996 | 1.000 | 1.000 |
| shrinkage=0.5 | 3 | 0.0523 | 0.0205 | 0.1211 | 1.000 | 1.000 |
| shrinkage=0.75 | 3 | 0.0611 | 0.0350 | 0.1626 | 1.000 | 1.000 |
| shrinkage=1 | 3 | 0.0700 | 0.0568 | 0.2172 | 1.000 | 1.000 |

Chamber-level failure condition: `not_evaluable_incomplete_chamber`.


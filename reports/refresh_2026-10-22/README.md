# 2026 Forecast Refresh - 2026-10-22

Internal model scenarios; no live forecast published. The original registration is preserved and remains the scored holdout.

Pre-election execution, tested capabilities and remaining blockers:
[implementation report](IMPLEMENTATION.md). Source review: [evidence review](evidence_review.md).
The final local quality result is `verification_final.json`; this is not the future
November 1-2 freeze or a deployed 50-state results feed.

## Changes

| Shrinkage | House mean: sealed -> current | House P(D): sealed -> current | Senate P(D): sealed -> current |
|---:|---:|---:|---:|
| 0.25 | 228.2 -> 234.7 | 0.536 -> 0.584 | 0.272 -> 0.545 |
| 0.33 | 233.1 -> 240.3 | 0.562 -> 0.616 | 0.298 -> 0.580 |
| 0.50 | 243.6 -> 252.3 | 0.620 -> 0.681 | 0.357 -> 0.651 |
| 0.75 | 259.3 -> 270.0 | 0.701 -> 0.762 | 0.450 -> 0.751 |
| 1.00 | 275.1 -> 287.8 | 0.770 -> 0.832 | 0.545 -> 0.832 |

## Coverage and limitations

```json
{
  "seats_projected": 35,
  "holdovers": 65,
  "democratic_holdovers": 34,
  "republican_holdovers": 31,
  "current_democratic_caucus": 47,
  "current_republican_caucus": 53,
  "reconciled": true
}
```

Candidacy evidence: {'verified': 203, 'unknown': 267, 'known_not_running': 52, 'by_office': {'us_house': 187, 'us_senate': 16}}. Missing evidence remains an assumption.
House prior sources: {'fallback_state_lean': 135, 'model': 262, 'model_transferred': 38}.
Each prior's national reference now matches its source election. The previous run incorrectly subtracted the 2022 national input from 2024 priors.
The sealed 33-race Senate universe is unchanged; this new run includes FL/OH specials and uses current official holders/caucuses.
Historical ACS is still a single vintage: excluded from the chronological benchmark. Historical candidate availability is reconstructed, not an archived as-of input.

## National baseline definitions

```json
{
  "all_races_ratio_of_two_party_votes": 0.48692578326424485,
  "contested_ratio_of_two_party_votes": 0.49532207062872,
  "contested_total_vote_weighted_model_input": 0.49744898673350363
}
```

The October 11 findings compared the all-race aggregate (0.4869) with the model's contested-race, total-vote-weighted input (0.4974). These are different quantities; the latter is labelled as the model input rather than an aggregate two-party national vote.

## Chronological evaluation

| Office | Cycles | MAE | Persistence MAE | 90% coverage |
|---|---:|---:|---:|---:|
| presidential | 8 | 0.0467 | 0.0321 | 0.887 |
| house | 15 | 0.0654 | 0.0796 | 0.913 |
| senate | 21 | 0.0645 | 0.0838 | 0.935 |

## Correlated error

house: retained asserted split: full-universe chronological gate not met. Selected variance shares: {'national': 0.45, 'regional': 0.25, 'state': 0.3}.
Held-out interval evaluation: {'asserted': {'coverage_90': 1.0, 'mean_interval_score': 131.5545454545455}, 'estimated': {'coverage_90': 0.9090909090909091, 'mean_interval_score': 124.09545454545456}}. Universe: covered contested seats only; fallback and unopposed seats are not validated.

senate: retained asserted split: full-universe chronological gate not met. Selected variance shares: {'national': 0.45, 'regional': 0.25, 'state': 0.3}.
Held-out interval evaluation: {'asserted': {'coverage_90': 1.0, 'mean_interval_score': 18.94411764705882}, 'estimated': {'coverage_90': 0.8235294117647058, 'mean_interval_score': 11.176470588235293}}. Universe: covered contested seats only; fallback and unopposed seats are not validated.

## Experimental cross-checks

Economic, polling and full-chamber diagnostics are linked in `refresh_summary.json`. They are not precision-blended into this band and do not authorize changing the seal. Their model cards describe failed promotion gates and incomplete source coverage.

## Operational follow-up

See `docs/refresh-2026-status.md`, `docs/results-2026-runbook.md` and the dated model card for source gaps, candidacy limits, release gates and the macroeconomic cross-check specification.
Source freshness is per row, not the report date. See `special_source_refresh.json` for any newly reverified counts and exclusions; other retrieval dates remain unchanged. Economic and polling cross-checks remain separate, unpromoted diagnostics.

## Reproduction

`python scripts/refresh_2026.py --as-of 2026-10-22`
Requires registered cached live inputs/P0 and CD-baseline builds, not just an empty checkout.

Full input checksums, source snapshots, model evaluations and seal verification are in `refresh_summary.json`. Per-seat and band differences are adjacent CSV files.

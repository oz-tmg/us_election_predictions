# 2024 Senate Coverage and Polling Data Guide

Owner: Alex Oswald. Review date: October 25, 2026, America/Vancouver.
Research only; no estimator promotion or change to the September forecast/registration.

## File Review and Correct Acquisition

The supplied `senate_polls(1).csv` contains 40 answer rows for 20 hypothetical 2026
questions, fieldwork through March 1, 2025. It does not supply 2024 history or current
October 2026 polling. The original is unchanged and not ingested. Its inspection
receipt is `reports/senate_poll_replacement_review_2026-10-25.json`.

The Internet Archive availability endpoint identified an older capture. The actual
[November 29, 2024 Senate CSV](https://web.archive.org/web/20241129175751if_/https://projects.fivethirtyeight.com/polls-page/data/senate_polls.csv)
was downloaded, checked and preserved: 2,628 candidate-answer rows, 1,142 questions,
32 states, exclusively 2024-cycle polling, with fieldwork through November 4, 2024.
Receipt: `reports/senate_poll_2024_acquisition_2026-10-25.json`. Its exact HTTP retrieval
was October 26 UTC, still October 25 Vancouver, not the November 2024 archive date.
No owner download is now needed for this file gap.

The study uses the two original House files, Senate history and the directly acquired
2024 Senate file. It omits the redundant November 2021 current-Senate capture rather
than allowing older metadata to conflict with the newer historical compilation.
No respondent, voter or donor records are acquired.

## Study and Boundaries

The fixed horizon, weighting, controls, earlier-cycle-only training, coefficient
uncertainty and correlated simulation are unchanged. No article coefficient is copied
and no model is tuned to the new 2024 fold. The four candidate inputs contain 13,548
answer rows and 5,784 questions before screening. The combined normalized research panel
has 8,809 pre-horizon questions, 2,979 eligible questions and 918 race-cycles including
training. Question/round/feature exclusions remain explicit in `study.json`.

Held-out coverage is 420 House races across seven cycles and 241 Senate races across
ten cycles, including 30 House and 18 Senate races in 2024. Raw coverage in 32 Senate
states is not equivalent to 32 accepted test races, much less a full chamber. Ambiguous
specials, unverified rounds, uncertified targets, unavailable priors, hypothetical
matchups and date cutoffs still apply. No complete chamber-control probability or
numerical 2026 polling correction is produced.

| Office | Blend MAE, share points | Lean-adjusted MAE | Blend Brier | Adjusted Brier | Decision |
|---|---:|---:|---:|---:|---|
| House | 3.215 | 3.272 | 0.1295 | 0.1331 | Metrics and vintage gates fail |
| Senate | 2.400 | 2.255 | 0.0520 | 0.0493 | Preliminary metrics pass; vintage gate fails |

Senate log loss improves from 0.1692 to 0.1603, with 90% coverage from 91.7% to 93.5%.
This is retrospective research, not independent prospective confirmation. Historical
publication, nominees, map/roster and fundamentals vintages remain unverified. House
still uses a lagged House-share proxy rather than presidential district lean. Neither
office's estimator is promoted and the sealed forecast remains the untouched holdout.

## Documentation and Reporting Fixes

[`docs/polling-data-guide.md`](../../docs/polling-data-guide.md) is the new consolidated
guide: actual sources, underlying pollsters, dates/counts, survey/question/answer/race
units, national/state/district detail, fields/normalization, provenance, licensing and
privacy boundaries, model-use status, storage and remaining limitations. It distinguishes
available raw presidential polling from the unpopulated real P2 pipeline and separates
national generic ballot from race polling.

The report renderer now derives 2024 House/Senate coverage from the actual eligible
panel. Its file inventory checks explicitly supplied candidate paths outside the
ratings directory. This fixes documentation/inventory claims, not numerical methods.
Three synthetic regression tests cover these cases. Existing reports remain preserved;
the previous same-input staging report predates these reporting fixes.

Current code references: `build_polling_lean.py`, `data/polling_archive.py`,
`tests/unit/test_polling_lean.py`. Source compilations, forecast parameters, external
context symlinks and unrelated edits were not modified. The earlier full verification
with 697 tests is not claimed as a new full run after these narrow reporting changes;
current focused checks are saved in `focused_verification.json`.

## Reproduction

Use the registered cached raw snapshots and existing chronological prior outputs:

```python
import json
from pathlib import Path

from election_prediction.build_polling_lean import build

manual = json.loads(Path("reports/polling_archive_intake_2026-10-25.json").read_text())["files"]
senate = json.loads(Path("reports/senate_poll_2024_acquisition_2026-10-25.json").read_text())
paths = [Path(f["raw_path"]) for f in manual if f["filename"] != "senate_polls.csv"]
paths.append(Path(senate["raw_path"]))
build(
    archive=Path("data/raw/source=538_race_poll_history/snapshot=2026-10-24/raw_polls.csv"),
    candidate_archives=paths,
    output=Path("reports/polling_lean_NEW_REVIEW"),
    review_date="YYYY-MM-DD",
)
```

Choose a new output directory; do not overwrite earlier studies or raw releases.
Attribution: FiveThirtyEight, CC BY 4.0; certified targets: registered MEDSL returns.

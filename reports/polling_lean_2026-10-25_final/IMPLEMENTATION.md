# October 25 Manual Polling Archive Integration

Owner: Alex Oswald. Review date: October 25, 2026, America/Vancouver.
Research only. No forecast promotion, publication, commit or production-results capture.

## Delivery and Provenance

All four user-supplied Downloads files are preserved unchanged under
`data/raw/source=538_race_poll_history/manual/sha256=.../`. The originals were not moved
or edited. Exact raw paths, SHA-256 hashes, manifests and Wayback URLs are in
[`../polling_archive_intake_2026-10-25.json`](../polling_archive_intake_2026-10-25.json).
Browser download metadata supplied the exact archive URLs; this does not independently
authenticate archive-server bytes. Archive capture time, actual project ingestion and
unknown original browser retrieval are explicitly separate. Retrieval is not backdated.

| File | Answer rows | Coverage | Finding |
|---|---:|---|---|
| `house_polls.csv` | 683 | 2024 plus 2023 | November 29, 2024 capture; fills part of House 2024 gap |
| `house_polls_historical.csv` | 3,579 | 2018/2020/2022 plus off-cycle races | November 29, 2024 capture |
| `senate_polls_historical.csv` | 6,658 | 2018/2020/2022 | November 29, 2024 capture |
| `senate_polls.csv` | 168 | Early 2022-cycle matchups | November 2, 2021 capture; no 2024 polling |

The intake is 11,088 candidate-answer rows and 4,642 distinct questions after combining
overlap. There are 3,317 candidate questions eligible before the fixed horizon; all
question exclusions are saved in `study.json`. Field/date/round and feature gates are
not waived to maximize coverage. Six surviving pre-horizon questions reference the old
current Senate file; none is inside the fixed election-week window.

## Implementation

- `data/candidate_polls.py`: immutable manual import; both party-column schemas;
  question-level metadata/answer conflict checks; duplicate-answer collapse; unique
  D/R pairs; ordinary November general elections; field dates, positive samples and
  percentage checks; explicit hypothetical/RCV/Louisiana exclusions.
- `data/polling_archive.py`: shared structural certified-target and strictly lagged
  feature joins. Candidate toplines are not given fabricated archived actual outcomes.
  Ambiguous regular/special keys remain excluded rather than chosen using outcomes.
- `polling/lean.py`: known field-end and database-entry-date exclusions at the fixed
  cutoff. Database entry is not a verified publication timestamp. Blank question IDs
  now fail validation. Core model, controls, horizon, simulation and gates are unchanged.
- `build_polling_lean.py`: manual-import CLI and repeated `--candidate-archive` inputs;
  candidate provenance/input hashes, normalized poll panel and updated research reports.

Candidate-covered office-cycles replace all overlapping ratings questions, rather than
double count surveys or backfill questions excluded using richer date metadata. Earlier
ratings cycles remain retrospective. The House feature still lacks usable within-era
lags in 2002/2012/2022; none is carried across a reset map.

The combined panel has 7,964 pre-horizon questions, 2,878 fixed-window questions and 900
race-cycles including training. Held-out evaluation covers 420 House races across seven
cycles and 223 Senate races across nine cycles. Thirty House races in 2024 are supported
by 39 eligible questions. This is a polled subset, not a full chamber replay.

## Findings

Equal-cycle held-out errors, Democratic two-party share points (MAE multiplied by 100):

| Office | Blend MAE | Lean-Adjusted MAE | Blend Brier | Adjusted Brier | Decision |
|---|---:|---:|---:|---:|---|
| House | 3.215 | 3.272 | 0.1295 | 0.1331 | Metrics gate fails |
| Senate | 2.393 | 2.244 | 0.0493 | 0.0477 | Preliminary metrics pass; vintage gate fails |

House 90% interval coverage falls from 85.4% to 84.5%; log loss worsens. Senate log loss
and coverage improve, including the predefined competitive subset. Neither is promoted.
The 2024 House subset alone has a negligible MAE improvement (2.507 to 2.502 points),
which does not overturn the multi-cycle House failure. No coefficient is tuned to this
new fold. Source mix/coverage changes prevent attributing differences from the October
23 study solely to the correction. The historical hypothesis is not prospectively new.

## Verification

[`intake_quality.json`](intake_quality.json) records raw-copy equality, disjoint source
office-cycles, unique questions, candidate field/entry cutoff enforcement, chronological
held-out fitting and hashes for all sealed files. The shared-code refactor reproduces
all 867 original ratings-only race averages to 1e-14 tolerance. A final rerun produces
identical held-out predictions. The final model's implementation hashes match the code.

Full repository quality checks are saved separately in
`reports/polling_archive_verification_2026-10-25.json`: all eight checks passed, including
697 tests in 280.61 seconds, Ruff lint/format, mypy on 84 source files, privacy filename
guard, cached-data preflight, historical scoring rehearsal and results CLI smoke test.
Code/reference fingerprints were unchanged during verification; the seal also passed.
The rehearsal uses historical fixtures, not 2026 forecast outcomes, and does not prove
unattended capture or runner deployment. Context files symlinked outside this workspace were left
unchanged; local status, registry, specification, backlog and download guidance are updated.

## Remaining Work

1. Obtain **`senate_polls.csv`, the 2024-cycle version**, from a late-2024/early-2025
   capture with actual October/November 2024 fieldwork. Preserve its exact archive URL.
   No replacement is needed for the other three files. Do not overwrite the 2021 capture.
2. Establish original poll publication availability and independently verified historical
   ballot identities; modern archive/database dates do not establish those facts.
3. Obtain prior presidential district results on each historical target map, with plan
   IDs/vintages, instead of treating the House-share proxy as presidential lean.
4. Validate historical fundamentals/roster/map input vintages. Then revisit the gated
   research decision, not the sealed September registration.
5. Numerical 2026 sensitivity still requires reviewed 2026 race polls and round/nominee
   identities. National generic ballot and sparse-seat simulations are not substitutes
   for complete chamber coverage or calibration.

## Reproduction

Use the registered raw snapshots and existing October 22 chronological prior files:

```python
import json
from pathlib import Path
from election_prediction.build_polling_lean import build

files = json.loads(Path("reports/polling_archive_intake_2026-10-25.json").read_text())["files"]
build(
    archive=Path("data/raw/source=538_race_poll_history/snapshot=2026-10-24/raw_polls.csv"),
    candidate_archives=[Path(f["raw_path"]) for f in files],
    output=Path("reports/polling_lean_NEW_REVIEW"),
    review_date="YYYY-MM-DD",
)
```

Choose a new output directory; existing studies and raw captures are never overwritten.
Attribution: FiveThirtyEight, CC BY 4.0; target returns: registered certified MEDSL data.

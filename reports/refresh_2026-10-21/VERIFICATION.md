# October 21 Verification

## Checks Run

- Full `pytest -q`: **620 passed**, including 74 live-data reconciliation cases, before
  the final complete-universe regression was added. No failures or skips.
- Final `pytest -q tests/unit tests/integration`: **547 passed**, including the new
  missing-share-seat/delegate regression and all 25 new intake tests. Together with
  the unchanged live-data suite this covers **621 distinct current tests** across runs.
- `ruff check .`: passed. `ruff format --check .`: passed for all Python files.
- `mypy src/election_prediction`: passed, 79 source files.
- `git diff --check`: passed. Restricted/bulk-data guard: passed.
- Historical House/Senate capture/scoring rehearsal: passed; its numerical scores are
  not forecast-performance evidence and no synthetic general results were captured.
- Read-only live-runner local data preflight: passed. This is not runner registration
  or a GitHub Actions execution; deployment still requires operator authorization.
- All 89 source/script fingerprints, four linked guidance fingerprints and diagnostic
  hashes match `refresh_summary.json`. Input provenance and runtime versions retained.
- Sealed prediction digest verified:
  `4de09ecf82f218ee807edc6d4eaae9b50d51968d0957177f33b762fad4100882`.
  All three sealed registration artifacts remain unchanged; nothing committed/pushed.

## Negative Gates Are Expected Findings

Kansas parsing covers 105 counties but is short 17 D/27 R votes, so the repair command
returns nonzero and no CD prior is admitted. All eight additional map-transfer audits
remain unadmitted; 135 fallback seats persist. No source exception was widened to make
these pass. Only 182 candidacies are verified; 288 unknown includes ten identity reviews.

Income regression fails its held-out benchmarks; two month-old generic-ballot polls
and reconstructed historical averages do not identify real-time calibration or house
effects. Five complete-House held-out folds improve retrospective error-split metrics,
but historical ballot/map vintages and independent/caucus coverage remain incomplete.
None of these findings authorizes replacing the live band, changing the seal, or claiming
all eight workstreams complete. See `docs/refresh-2026-status.md` for acceptance status.

The active daily results-capture follow-up is installed for 22:00 Vancouver. It requires
the computer/app running and readable official sources; no complete capture is guaranteed.

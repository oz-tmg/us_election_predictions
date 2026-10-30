# October 23 Polling-Lean Execution

Owner: Alex Oswald. Internal, nonpartisan research. Review date uses America/Vancouver;
actual source retrieval occurred October 24 UTC and retains that timestamp. No live
forecast, September seal, source compilation, registered parameter or unrelated edit
was changed. No estimator was promoted, no results captured and no publication made.

## Delivered

- Registered historical race-poll source and fixed the research specification before
  the first fit. Acquired 538's 20,466-row aggregate ratings archive, codebooks and license.
- Reconciled embedded source vote shares against the certified canonical race table;
  excluded ambiguous regular/special keys rather than choosing by eventual outcome.
- Explicitly screened office, stage/date, D/R candidates, unresolved/RCV rounds, missing
  priors, unmapped lean and certified-share discrepancies. Exclusion counts reconcile
  to all 20,466 input rows. No malformed rows were skipped to make a file parse.
- Fixed seven-day median-date horizon, 21-day window, survey-question deweighting,
  race-level averaging, and equal-cycle/race fitting weights. Publication timestamps
  are not inferred from a field-date median or a modern file creation timestamp.
- Compared polling-only, fundamentals blend, and a post-blend residual correction.
  Controls use cycle intercepts and weighted pollster/sponsor/mode/horizon exposures.
  Bootstrap resamples whole elections; predictions fit strictly earlier cycles.
- Simulated one shared uncertain lean coefficient per election alongside the existing
  asserted national/regional/unit errors. No independent per-state corrections and no
  estimated chamber-control probabilities from a sparse polled-seat sample.
- Saved all/competitive/lean-band calibration and proper scores, by-cycle fits,
  bootstrap intervals, coverage, model card, code/data/source hashes and seal hashes.

## Results and Limits

The window contains 2,916 poll questions representing 867 race-cycles, including training
history. Actual chronological holdouts contain **221 Senate races over nine cycles** and
**389 House races over six cycles**, not 867 held-out races. All three pipelines use the
same respective holdouts. These are retrospective diagnostics, not verified real-time
historical replays and not evidence that any specified 2026 race will change leader.
The article-inspired hypothesis was selected after historical outcomes were known;
earlier-cycle parameter fitting does not make these folds independent prospective
confirmation. The original 2026 registration is not rewritten to test the new hypothesis.

Equal-cycle MAE: Senate blend **0.02392** versus lean-adjusted **0.02263**; House blend
**0.03330** versus lean-adjusted **0.03400**. Senate Brier/log loss and coverage also
improve in this archive, including the fixed competitive subset. House scores worsen
and coverage misses the gate. Senate passes the preliminary metrics gate but fails
the vintage gate. House fails both. Neither is a promoted model.

The Senate uses lagged state presidential lean. House uses a separately labeled lagged
House proxy; the source join lacks usable same-era lags in 2002/2012/2022 and the accepted
House history ends in 2020. That is not the article's presidential-district-lean design.
The archive lacks 2024 congressional polls. Coefficient bootstrap uncertainty is not a
measured distribution of future-cycle slope heterogeneity. Blend independence and the
asserted correlation split remain assumptions, with coverage tested rather than assured.

## Blocked / Manual Files

All four publisher candidate-poll CSV endpoints returned HTML, not data; exact attempts
are in `../polling_lean_2026-10-23_acquisition.json`. The full request with original URLs,
required archive vintages and provenance instructions is
[`polling-lean-downloads.md`](../../docs/polling-lean-downloads.md):

1. `senate_polls_historical.csv`
2. `senate_polls.csv` from the archived 2024 cycle
3. `house_polls_historical.csv`
4. `house_polls.csv` from the archived 2024 cycle

The already acquired `raw_polls.csv`, codebooks and license need not be downloaded again.
The four candidate CSVs will not by themselves establish historical House presidential
lean on the right maps, archived input/publication vintages, or complete chamber replay.
Their exact schema/round/availability review and adapter remain pending the actual files.
Reviewed 2026 race polls are separately needed for numerical 2026 sensitivity; national
generic-ballot polls are not a substitute. No specific comprehensive historical district
presidential-lean download has been verified, so no imaginary publisher filename is given.

## Verification

`verification.json` is the saved full-suite/quality result; inspect its command return
codes rather than treating the existence of this document as a passed check. The focused
new/existing polling tests passed 39/39 before that final run. A read-only comparison
against the October 22 acceptance fingerprints found **zero changed paths among 152
previously fingerprinted existing code/reference files**. New research files are separate.
The full verifier also checks code/reference stability during its run and the September
seal hashes. The initial study remains at `../polling_lean_2026-10-23/`; the sibling
`study.json`, `model_card.md` and derived CSVs here are the final implementation run.

Final verification completed: **678 tests passed**, Ruff check/format and mypy (83 source
files) passed, tracked-file privacy filename guard (261 files), local read-only data
preflight and historical scoring rehearsal passed. Code/reference hashes were unchanged
during verification; all September seal hashes match. Production results snapshots remain
empty, as expected before Election Night. The filename guard is not a comprehensive
personal-data content audit and local checks do not claim CI runner deployment.

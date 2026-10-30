# Historical Polling Files Needed

Owner: Alex Oswald. Updated October 25, 2026, America/Vancouver. Archive capture,
project ingestion and original browser retrieval are distinct timestamps.

Consolidated sources, coverage, geographic granularity, row definitions and current
model-use status: [Polling Data Guide](polling-data-guide.md).

## 2024 Senate File Gap Filled Later October 25

The agent directly downloaded and preserved the correct November 29, 2024 capture:
[verified Senate CSV](https://web.archive.org/web/20241129175751if_/https://projects.fivethirtyeight.com/polls-page/data/senate_polls.csv).
It contains 2,628 candidate-answer rows, 1,142 questions, 32 states, and exclusively
`cycle=2024` rows, with fieldwork through November 4, 2024. Exact raw path, SHA-256,
manifest and actual HTTP retrieval time are in
`reports/senate_poll_2024_acquisition_2026-10-25.json`. Retrieval is October 26 UTC,
still October 25 Vancouver; the archive timestamp is not substituted for retrieval.
**No further owner download is needed for the missing 2024 Senate file.** Historical
publication/feature-vintage and current-race coverage gates remain separate.

## Replacement Reviewed Later October 25

`senate_polls(1).csv` is a March 6, 2025 Wayback capture, but all 40 answer rows
(20 questions) have `cycle=2026` and `hypothetical=true`; fieldwork ends March 1,
2025. It neither supplies 2024 Senate polls nor current October 2026 polling, and
was not admitted. The exact checksum/URL are in
`reports/senate_poll_replacement_review_2026-10-25.json`. The original remains unmodified.

For future historical inputs, prefer a calendar capture matching the needed cycle and confirm
the CSV's **cycle column is 2024** and its late fieldwork is actually October/November
2024. Alternatively a newer `senate_polls_historical.csv` can fill the gap if it contains
those 2024 rows. The direct acquisition above now fills this request. Archive date alone is not
enough, because the publisher's current-cycle file can roll forward to the next election.

## October 25 Delivery

All four supplied CSVs were preserved unchanged, with SHA-256, exact Wayback URLs from
browser download metadata and actual project-ingestion timestamps. Original browser
retrieval timestamps are unknown, not filled from file times. Intake receipts:
`reports/polling_archive_intake_2026-10-25.json`.

| File | Candidate-answer rows | Actual coverage | Archive capture UTC |
|---|---:|---|---|
| `house_polls.csv` | 683 | 2024 (678 rows), plus 2023 | 2024-11-29 17:57:37 |
| `house_polls_historical.csv` | 3,579 | 2018, 2020, 2022, plus off-cycle races | 2024-11-29 17:59:09 |
| `senate_polls_historical.csv` | 6,658 | 2018, 2020, 2022 | 2024-11-29 17:57:56 |
| `senate_polls.csv` | 168 | Early 2022-cycle matchups; fieldwork ends 2021-10-27 | 2021-11-02 00:02:29 |

**Original remaining request, now filled: `senate_polls.csv`, the 2024-cycle version.**
Use a capture actually containing 2024-cycle fieldwork through October/
November 2024, preferably the final pre-election file. A capture from November 2021 is
not that version even though the download filename is identical. Retain its exact
Wayback URL. No replacement is needed for the other three files. These four deliveries
do not include standalone presidential poll files.

## Original Request and Publisher Links

These are the four exact filenames documented by FiveThirtyEight. The current endpoints
were attempted and returned HTML rather than CSV. The original request was an unmodified historical
download, preferably a publisher/Internet Archive snapshot from after the 2024 election
and before the March 2025 closure. A complete equivalent archive with documented original
provenance is also useful; it does not have to be four separate files if it combines them.

| Exact original filename | Original publisher download | Required coverage |
|---|---|---|
| `senate_polls_historical.csv` | https://projects.fivethirtyeight.com/polls-page/data/senate_polls_historical.csv | All available earlier Senate general-election cycles, not just 2022 |
| `senate_polls.csv` | https://projects.fivethirtyeight.com/polls-page/data/senate_polls.csv | The archived 2024-cycle version; a present-day file of 2026 polls is not a substitute |
| `house_polls_historical.csv` | https://projects.fivethirtyeight.com/polls-page/data/house_polls_historical.csv | All available earlier House general-election cycles |
| `house_polls.csv` | https://projects.fivethirtyeight.com/polls-page/data/house_polls.csv | The archived 2024-cycle version, including district identifiers |

Publisher file index: https://github.com/fivethirtyeight/data/blob/master/polls/README.md

The files should contain individual candidate-answer toplines within a poll/question,
not forecast probabilities, a polling-average export, screenshots or generic-ballot
polls. Useful original fields include poll/question/race/candidate IDs, candidate party,
percent, state/district, cycle, stage, field start/end, sample size/population, pollster,
sponsor/partisan flag, methodology, source URL and created/publication timestamps.
Do not edit headers, delete rows, select a favored matchup or pre-normalize percentages.
Do not download respondent microdata, voter files or donor records.

For each download, retain the actual download URL (including the archive URL if used),
actual retrieval date/time and archive/version date separately. A timestamp saying when
an archive was created is not automatically the poll's publication date. Place unmodified
downloads in `data/raw/source=538_race_poll_history/manual/` with that provenance, or tell
the agent their existing local paths. They remain unvalidated until checksum registration,
schema/duplicate/round review, and comparison with certified results.

## Already Acquired: Do Not Download Again

- `pollster-ratings/raw_polls.csv`: 20,466 rows, congressional history through 2022.
- `pollster-ratings/README.md`, `polls/README.md` and repository `LICENSE` (CC BY 4.0).
- Certified MEDSL House/Senate and state presidential returns through 2024.
- Existing chronological fundamentals predictions, with documented vintage limitations.

The ratings CSV supports a retrospective diagnostic but lacks publication/field-end
timestamps and 2024 congressional polls. It is not a full real-time backtest archive.
Do not download `pollster-ratings-combined.csv` as a predictor: its retrospective ratings
would leak later election information into earlier-cycle forecasts.

## Other Gates, Not Solved by Those Four Downloads

- **House presidential lean:** prior presidential results tabulated on each target
  election's actual congressional map, with plan IDs and source/vintage evidence. No
  single comprehensive publisher file has been verified. The current House experiment
  uses a clearly labeled previous-House-share proxy; it cannot validate the article's
  exact presidential-lean claim. Do not acquire an arbitrary current-PVI table as a
  historical substitute. Candidate files alone will not remove this blocker.
- **Real-time availability:** original poll releases or contemporaneous archive evidence
  of publication at each cutoff, plus archived fundamentals/roster/map inputs. A modern
  retrospective database's creation timestamp alone may not establish this.
- **2026 numerical sensitivity:** reviewed current general-election House/Senate race
  polls and candidate/round identities are needed. Our two national generic-ballot polls
  cannot substitute for state/district polls. No person-level records are needed.
- **Exact article replication (optional):** the Economist's original aggregate chart
  data and codebook would settle its lean definition, units, weighting and exclusions.
  No specific downloadable filename was verified; this is not required to run our
  independent experiment. Article prose and chart images are not a numeric archive.

## Reproduce the Work Already Possible

```bash
.venv/bin/python -m election_prediction.build_polling_lean study \
  --archive data/raw/source=538_race_poll_history/snapshot=2026-10-24/raw_polls.csv \
  --out reports/polling_lean_NEW_REVIEW --review-date YYYY-MM-DD
```

Choose a new report directory; existing studies are not overwritten. Candidate ingestion
now supports both the older `candidate_party` schema and newer `party` schema. To import
a replacement without overwriting the old capture:

```bash
.venv/bin/python -m election_prediction.build_polling_lean preserve-candidate \
  --file /path/to/senate_polls.csv --archive-url EXACT_WAYBACK_CAPTURE_URL
```

For the expanded study add one `--candidate-archive PRESERVED_RAW_PATH` argument per
file. The four exact preserved paths and provenance are in the intake receipts above.
Overlapping office-cycles replace ratings data; they are never stacked as independent
polls or used to backfill date-rejected questions. No source becomes promoted or changes
the sealed September forecast by being downloaded.

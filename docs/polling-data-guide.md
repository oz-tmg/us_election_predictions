# Polling Data Guide

Owner/data steward: Alex Oswald. Inventory reviewed October 25, 2026,
America/Vancouver. This describes files actually inspected in this checkout, not every
source listed in the project's broader research catalog. Counts are snapshot-specific.

## Summary

Our acquired polling comes from **FiveThirtyEight's public compilations** and **two
hand-compiled original national releases from Marist and Emerson College**. Internet
Archive/Wayback preserves older publisher files; it did not conduct the surveys.
FiveThirtyEight is also an aggregator, not the pollster behind every row. Underlying
pollsters in the historical files include SurveyUSA, Quinnipiac, Ipsos, Emerson, Marist,
Public Policy Polling, YouGov and many others.

The finest electoral geography in the acquired poll files is a **congressional district
for House polls**. Senate polls are **statewide**; presidential polling includes
**national and state** questions. Generic-ballot polls measure **national congressional
vote intention**. These are aggregate survey estimates, not individual responses,
precinct polls or voter records. Coverage is selective and varies sharply by race/year.

Acquisition is not model promotion. The House/Senate lean experiment and national
generic-ballot cross-check remain **research-only**. The sealed September forecast is
unchanged. The presidential P2 pipeline has no registered real poll snapshot in this
checkout; its ability to run synthetic examples is not observed polling coverage.

## 1. Acquired Sources

### FiveThirtyEight Pollster-Ratings Archive

Publisher: [FiveThirtyEight pollster-ratings repository](https://github.com/fivethirtyeight/data/tree/master/pollster-ratings).
Downloaded source: `raw_polls.csv`, with its publisher README and repository license.
The canonical research copy is
`data/raw/source=538_race_poll_history/snapshot=2026-10-24/raw_polls.csv`.

There are **20,466 question records from 14,590 distinct publisher poll IDs**, with
**593 distinct pollster-name labels**. Labels are not necessarily 593 independently
deduplicated organizations. A poll can ask several questions, cover multiple races or
offer multiple matchups. Therefore 20,466 is not a count of independent surveys.

| Publisher category | Question records | Actual cycle coverage | Geography |
|---|---:|---|---|
| Presidential general (`Pres-G`) | 5,867 | 2000, 2004, 2008, 2012, 2016, 2020 | National/state |
| Senate general (`Sen-G`) | 5,006 | 1998-2022, including some off-cycle contests | State |
| House general (`House-G`) | 2,957 | 1998-2022, including some off-cycle contests | Congressional district |
| Governor general (`Gov-G`) | 3,537 | 1998-2022, including odd-year elections | State |
| National generic House (`House-G-US`) | 883 | Even cycles 1998-2022 | National |
| All primary categories combined | 2,216 | Office-dependent; includes a few governor-primary records in 2023 | Office-dependent |

The primary total includes 2,035 presidential records. Primary, gubernatorial and
generic-ballot records are not silently mixed into the House/Senate general-election
lean experiment. Governor data is acquired but not fitted by that experiment.

Important limitations in the publisher's codebook:

- The two named candidates are the election's eventual top two finishers, not necessarily
  the poll's leading candidates. This is retrospective selection, not an as-of ballot archive.
- `polldate` is a median field date, not verified publication or field completion.
- Some `samplesize` values were approximated by the publisher when originals were absent.
- Embedded `cand*_actual` outcomes are checked against registered certified targets,
  never used as polling predictors. Retrospective grades and poll scores are not predictors.
- It is a curated ratings archive, not a complete census of every published poll.
- Congressional general history ends in 2022. It contains **no 2024 presidential polls**.

There is an earlier local copy with identical bytes. Copies of one snapshot are not
additional surveys. Exact input hashes and manifests are recorded in the study report.

### FiveThirtyEight Candidate-Answer CSVs via Wayback

Publisher file index: [FiveThirtyEight polls README](https://github.com/fivethirtyeight/data/blob/master/polls/README.md).
These CSVs originate at `projects.fivethirtyeight.com/polls-page/data/`; the index points
to downloads rather than storing the complete CSVs in that GitHub directory.

| Delivered file | Candidate-answer rows | Questions in that file | Coverage | Archive capture UTC |
|---|---:|---:|---|---|
| `house_polls.csv` | 683 | 299 | 678 answer rows for 2024, plus 2023 contests | 2024-11-29 17:57:37 |
| `house_polls_historical.csv` | 3,579 | 1,562 | 2018/2020/2022 plus off-cycle House races | 2024-11-29 17:59:09 |
| `senate_polls_historical.csv` | 6,658 | 2,781 | 2018/2020/2022 | 2024-11-29 17:57:56 |
| First `senate_polls.csv` | 168 | 81 | Early 2022-cycle polling; fieldwork ends 2021-10-27 | 2021-11-02 00:02:29 |
| Correct 2024 `senate_polls.csv`, acquired directly later October 25 | 2,628 | 1,142 | 2024, 32 states; fieldwork through 2024-11-04 | 2024-11-29 17:57:51 |

The four files total **11,088 answer rows and 4,642 distinct question IDs** after
recognizing overlap. The file-level question counts must not simply be added and called
independent polls. The old current Senate file overlaps Senate history and contributes
no eligible questions at the study's fixed seven-day horizon.

One row is **one candidate's reported percentage in one poll question**. A question
typically has a Democrat, Republican and possibly third-party answers on separate rows.
An older schema calls the party field `candidate_party`; newer files use `party`.
Both schemas are supported. A candidate-answer row is not a survey respondent.

Raw files preserve poll/question/candidate/race IDs, names and party, percentages,
state, district or Senate seat/class, stage, field dates, sample and population,
pollster, sponsor, mode, source URLs and available round/hypothetical flags. Some raw
columns are intentionally omitted from the normalized research panel. A URL pointing
to crosstabs does not mean those crosstabs or respondent records have been ingested.

The first four delivered files are the original manual intake, not the complete current
acquisition total. The correct 2024 Senate file was subsequently downloaded directly
from [this verified Wayback capture](https://web.archive.org/web/20241129175751if_/https://projects.fivethirtyeight.com/polls-page/data/senate_polls.csv).
The current study inputs use it **instead of** the redundant old 2021 capture, together
with the two House files and Senate history: 13,548 answer rows, 5,784 questions before
screening. The 2024 file is not proof of complete Senate coverage: it covers 32 states,
and eligibility/certified-target/round gates remove additional questions and contests.

Preserved manual copies live under
`data/raw/source=538_race_poll_history/manual/sha256=.../`. Exact URLs, hashes and paths
are in [the intake receipts](../reports/polling_archive_intake_2026-10-25.json).
The directly acquired 2024 copy and actual HTTP retrieval timestamp are recorded in
[its acquisition receipt](../reports/senate_poll_2024_acquisition_2026-10-25.json).
Retrieval was October 26 UTC, still October 25 in Vancouver; no timestamp is backdated.

### Additional Senate File Inspected October 25

The user's `senate_polls(1).csv` is from a **March 6, 2025 Wayback capture**, but its
rows are for the **2026 election**, not 2024:

- 40 candidate-answer rows representing 20 questions.
- All 40 rows have `cycle=2026`, `stage=general`, and `hypothetical=true`.
- Fieldwork runs from April 2023 through March 1, 2025. These are early prospective
  matchups, not current October 2026 polling.
- Seven states: Alaska, Georgia, Massachusetts, Michigan, New Hampshire, North Carolina
  and Virginia. This is not all Senate contests or all 50 states.

It **does not supply 2024 Senate data** and is not admitted to the historical
study or current forecast. The original remains in Downloads; an inspection receipt is
saved in [the replacement-file review](../reports/senate_poll_replacement_review_2026-10-25.json).
The browser's `(1)` suffix is not an election-year indicator. The separate direct
November 2024 acquisition above fills the file gap; no further replacement download
is requested from the owner for that gap.

### Original 2026 National Generic-Ballot Releases

The accepted hand-compiled reference is `data/reference/generic_ballot_2026.csv`.
There are **two surveys**, not a complete current polling feed:

| Pollster / sponsor | Field dates | Published | Sample/population | Mode |
|---|---|---|---|---|
| [Marist / NPR-PBS News](https://maristpoll.marist.edu/polls/2026-midterm-elections-september-2026/) | 2026-09-14 to 09-15 | 2026-09-23 | 1,280 registered voters | Live phone/text/online |
| [Emerson College](https://emersoncollegepolling.com/september-2026-national-poll-democrats/) | 2026-09-21 to 09-22 | 2026-09-24 | 1,000 likely voters | Text-to-web/panel |

Original HTML and derived facts were preserved in dated snapshots; the most recent saved
cross-check is October 22. This guide inventories those acquisitions and does not claim
these are the latest releases available on October 25. No new release was fetched for
this documentation review. A newer chamber-control-preference question was excluded
because preferred control and intended district vote are different constructs.

Both rows use `office=us_house_generic`, `geography_id=nation:us`, `state_po=US` and no
district number. National intended vote cannot be substituted for Texas Senate polling,
for a particular House district, or for a chamber-control probability.

### Historical National Generic-Ballot Averages

Source: [FiveThirtyEight congress-generic-ballot repository](https://github.com/fivethirtyeight/data/tree/master/congress-generic-ballot).
The acquired `generic_topline_historical.csv` contains **7,669 dated aggregate estimates**
from November 9, 1995 through November 6, 2016. These are publisher averages, **not
7,669 polls**. Our fixed October 20 diagnostic uses eleven election cycles, 1996-2016.
Publisher rebuild timestamps in 2020 prevent treating it as an independently verified
real-time replay. It cannot supply individual samples or identify pollster house effects.

A separate DataHub-hosted `generic_polllist.csv` was acquired but is **quarantined for
inconsistent CSV field counts**. No bad rows are silently skipped. The 883 national
generic-ballot questions in the ratings archive are another available research source;
they are not the input to the currently saved generic-ballot cross-check and should not
be counted again as independent observations alongside overlapping source compilations.

## 2. Geographic Granularity

| Data | Finest relevant geography actually acquired | What it does not provide |
|---|---|---|
| House candidate polling | Congressional district for that cycle's map | No representative precinct/county polling or complete 435-seat coverage |
| Senate candidate polling | Statewide contest | No district or county estimates from the statewide topline |
| Presidential questions in ratings archive | National or state, depending on the question | No 2024 presidential polls, no current live P2 input |
| Governor questions in ratings archive | Statewide contest | Not incorporated into the lean experiment |
| Generic congressional ballot | National | No local race or seat-control probabilities |

Precinct returns, county context, Census demographics and district shapes elsewhere in
the project are **different datasets**, not finer-grained polls. Combining a statewide
poll with precinct demographics does not turn it into measured precinct opinion.
No survey respondent microdata or individual voter predictions are present in these
polling inputs. An MRP/turnout module would require a separate governed data/modeling project.

Senate `seat_number` can encode a seat/class; it must not be interpreted as a congressional
district. House district numbers are meaningful only with state, cycle and map vintage.
The adapter normalizes at-large House district 1 to canonical 0 only when appropriate;
simultaneous regular/special races with ambiguous structural keys are not guessed.

## 3. Counts and Units

Distinguish four units: **survey (`poll_id`)**, **question (`question_id`)**, **candidate
answer**, and **race**. Multiple matchups or candidate answers are not independent
samples. The same survey may appear in more than one file or archived version.

Source `pct` values are percentages. The modeling target is Democratic two-party share:

```text
two_party_dem_share = dem_pct / (dem_pct + rep_pct)
```

For D=48 and R=46, the normalized share is 0.5106, not 0.48. A value of 0.01 is one
two-party share point, not one point of D-minus-R margin and not a win-probability point.
Third-party and undecided responses are not secretly assigned to a major party.
The default D/R normalization does not make independent, same-party or RCV contests
ordinary two-party races. A sample size describes the publisher's survey/question
population; it is not a count of respondent rows available in this repository.

## 4. What Is Actually Used

### House/Senate Lean Experiment

Current saved run: [October 25 study including Senate 2024](../reports/polling_lean_2026-10-25_senate2024_final/README.md).
It uses earlier ratings history plus screened candidate questions for covered later
office-cycles. Candidate-covered office-cycles **replace** ratings questions; they are
not appended as independent repeats and rejected questions are not backfilled from
the archive with poorer date metadata.

- Fixed seven-day horizon and preceding 21-day lookback; 21-day decay half-life and
  square-root sample-size weights. Repeated questions divide their survey's influence.
- Ratings use median field dates; candidate files use a field-midpoint proxy, with
  field-end and database-entry-date exclusions at the cutoff.
- D/R general-election screening; reject malformed samples/percentages, conflicting
  answers/metadata, explicit hypothetical matchups and unverified runoff/RCV rounds.
- Structural joins to registered certified targets, strictly earlier fundamentals and
  lagged lean. Independent/same-party, uncertified/uncontested or ambiguous races are
  excluded with explicit reasons. No election outcome is fabricated from a poll.
- Senate lean uses lagged presidential state results. House uses a **lagged House-share
  proxy**, not presidential district lean; this remains promotion-ineligible.
- Three pipelines: polls alone, fundamentals blend, and a lean-adjusted blend. Fits are
  office-specific, earlier-cycle-only, with at least four training cycles.
- National/regional/unit error is correlated. A single uncertain lean slope is shared
  within each simulated election, not independently drawn for every district/state.

The panel contains 8,809 pre-horizon questions and 2,979 eligible questions across 918
race-cycles including training. Held-out evaluation covers **420 House races in seven
cycles** and **241 Senate races in ten cycles**. It includes **30 polled House races and
18 polled Senate races in 2024**, not a complete chamber replay. House reset-map cycles 2002/2012/2022 lack usable
within-era lags; they are not quietly carried across incompatible maps.

The Senate correction passes preliminary metrics but not vintage gates. The House
proxy correction fails the multi-cycle metrics gate. Neither is promoted; neither
establishes complete-chamber calibration or a numerical 2026 polling correction.

### National Generic-Ballot Cross-Check

This separately uses the two original national releases and historical publisher-average
diagnostic. Its averaging code uses 21-day decay, square-root sample size and population
weights LV=1.0, RV=0.85, adults=0.65, plus sampling/between-poll variance and a nonzero
error floor. Fieldwork and publication must be complete by the as-of date. Pollster house
effects remain **unidentified**, not proven to be zero. This is not the congressional
lean experiment's weighting specification and is not a promoted national estimator.

### Presidential P2 Pipeline

`ep-build-p2` implements standardized aggregate toplines, averaging, blending and correlated
Electoral College simulation. In this checkout there is **no** real
`data/silver/poll_toplines.parquet`, `data/gold/polling_averages.parquet` or registered
real P2 polling run. Without supplied governed polls it can generate clearly labeled
synthetic fixtures. Acquired presidential records inside the ratings archive have not
automatically become a validated presidential polling model.

## 5. Provenance, Dates and Privacy

These timestamps answer different questions:

| Field | Meaning |
|---|---|
| `start_date/end_date` or `field_start/field_end` | When interviewing took place |
| `polldate` | Ratings archive's median field date |
| `published_on` | Sourced release/publication date, where established |
| Candidate CSV `created_at` | When the record entered the publisher database; not proof of publication |
| Wayback capture timestamp | When that URL was archived; not the poll's fieldwork or publication date |
| `project_ingested_at` / manual-import manifest `acquired_at` | Actual project import time |
| `browser_retrieved_at` | Original browser download time; unknown for these deliveries, explicitly null |

Never substitute archive time or filesystem modification time for unknown publication
or retrieval dates. Candidate field-end availability does not remove the separate
publication gate. Same-day database entry cannot establish intraday availability.
Modern retrospective files do not establish historical nominee, geography, roster or
fundamentals input vintages.

All acquired polling here is public aggregate toplines, with professional candidate
identities where needed. No respondent, voter-file, donor or campaign CRM records enter
these polling tables. The recorded governance route allows attributed FiveThirtyEight
CC BY 4.0 compilation research and individually cited original-release facts; it does
not authorize unrestricted copying of every linked source document. Original source
HTML is retained locally and is not blanket-licensed for redistribution. Direct new
YouGov collection/modeling remains subject to the unresolved permission gate recorded
in the project's terms review; historical presence in an approved compilation does
not authorize automated collection of additional YouGov data.

## 6. Storage and Reproduction

| Layer/artifact | Location and meaning |
|---|---|
| Raw source | `data/raw/source=538_race_poll_history/`, `source=538_generic_ballot_archive/`, `source=pollster_generic_ballot_compiled/`; immutable original bytes |
| Source manifests | `data/manifests/`; URLs, actual acquisition/import times, terms, privacy and SHA-256 |
| Manual import receipts | `reports/polling_archive_intake_2026-10-25.json`; exact raw paths and separate archive/import timestamps |
| Direct 2024 Senate acquisition | `reports/senate_poll_2024_acquisition_2026-10-25.json`; raw path, checksum, exact archive URL and actual HTTP retrieval timestamp |
| Hand-compiled national facts | `data/reference/generic_ballot_2026.csv`; one sourced national survey per row |
| Research question panel | `reports/polling_lean_2026-10-25_senate2024_final/poll_questions.csv`; normalized accepted questions before horizon |
| Race averages | Same report directory, `race_averages.csv`; fixed-window race estimates |
| Historical evaluation | Same directory, `held_out_predictions.csv`, `study.json`, `model_card.md`, `intake_quality.json` |
| Generic-ballot cross-check | `reports/refresh_2026-10-22/generic_ballot_cross_check.json` and `generic_ballot_polls.csv` |

Read manifests for actual source coverage and hashes; a file's existence or pending
manifest validation flag is not approval to deploy a model. Some research eligibility
checks are recorded in `study.json`, while promotion gates remain explicitly false.
The earlier October 25 full repository verification recorded 697 passing tests; that is software
validation, not evidence that all sources, vintages or forecasts pass scientific gates.

Reproduce the candidate-extended study using the receipt paths and a **new** report
directory as shown in [the implementation report](../reports/polling_lean_2026-10-25_senate2024_final/IMPLEMENTATION.md#reproduction).
No build, re-ingestion or forecast refresh is needed just to read this guide.

## 7. What Still Needs Downloading or Verification

1. **2024 Senate file gap: filled.** The directly acquired November 29, 2024 capture
   contains the required 2024-cycle polling. No additional owner download is needed for
   that input. For future acquisitions, inspect the cycle and field dates, not just the
   archive year or browser filename. A later historical file is also useful if its
   contents actually cover a needed cycle. Preserve the unedited file and exact URL.
2. **Presidential polling:** we have general questions through 2020 in the ratings
   archive, but no standalone `president_polls.csv`/`president_polls_historical.csv`
   intake and no 2024 presidential polls. Those are optional additional historical
   coverage, not a substitute for the missing 2024 Senate input.
3. **Real-time promotion:** establish historical publication, nominees, map/roster and
   fundamentals vintages. Obtain presidential district baselines on each actual map.
4. **Current 2026 races:** acquire reviewed current race polls, with nominee/round identities
   and original field/publication evidence. The March 2025 hypothetical file and two
   September national generic-ballot polls do not provide this coverage.

To inspect a candidate file without editing it:

```python
import pandas as pd

polls = pd.read_csv("/path/to/senate_polls.csv", dtype=str)
print(polls["cycle"].value_counts())
print(pd.to_datetime(polls["end_date"], format="mixed").max())
print(polls.get("hypothetical", pd.Series(dtype=str)).value_counts())
```

## Related Documentation

- [Dataset registry](dataset-registry.md): dataset ownership, intake and governance.
- [Download checklist](polling-lean-downloads.md): exact remaining file request.
- [Lean experiment specification](polling-lean-experiment.md): fixed statistical design.
- [Polling terms review](terms_and_conditions/poll-topline-redistribution-terms.md): recorded source-specific permissions and unresolved gates.
- [Ingestion playbook](ingestion-playbook.md): source manifests and medallion conventions.
- [Public-data catalog](public-data-sources.md): possible sources, not proof of acquisition.
- [Methodology](methodology.md): model architecture, not an inventory of loaded polls.

Code: `data/polling_archive.py`, `data/candidate_polls.py`, `polling/schema.py`,
`polling/average.py`, `polling/generic.py`, `polling/lean.py`, `build_generic_ballot.py`,
`build_polling_lean.py` and `build_p2.py` under `src/election_prediction/`.

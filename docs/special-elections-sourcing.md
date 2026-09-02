# Special-Election Sourcing

_Researched 2026-09-01. Every claim below was checked against the live source; the
"could not verify" section at the end records what was not._

## Why this document exists

Special-election overperformance is one of the few ways to estimate a **national
political environment without polls**. That matters for two concrete blockers in this
project, not as general interest:

- `national_dem_share` carries the largest coefficient in the House baseline (**+0.884**),
  and its backtest *conditions on the true value*. A live cycle needs that number from
  somewhere.
- P1-004's swing ratio is **unidentified** for the current (2022) redistricting era — one
  cycle of swings yields no slope — and a poll-based national estimate remains blocked on
  the unresolved poll-redistribution question (`dataset-registry.md`).

The consuming code is `src/election_prediction/data/special_elections.py`; the
compilation table is `data/reference/special_elections_2025_2026.csv`.

## MEDSL cannot serve this need

Verified by enumerating all **55 datasets** in MEDSL's Dataverse:

- **No special-election dataset exists**, for any period.
- Their newest release is **2022 precinct data, published 2026-06-10** — roughly a
  two-year lag. Nothing for 2025 or 2026 will appear in time for this cycle.
- Our own federal returns carry only ~2 specials per cycle (6 U.S. House, 29 U.S. Senate
  across 1976–2024), and the informative signal sits in *state legislative* specials,
  which this project has no source for.

Harvard Dataverse more broadly does not have it either. A relevance-ranked search for
`title:"special election" AND (results OR returns OR margin)` returns **five hits, all
one-off exit polls and surveys** — a 2003 California exit poll, two UMass Lowell
Massachusetts Senate polls, a Venezuela study. No returns compilation.

## The four working sources

### 1. State Secretaries of State / election boards — the authority

The only sources of record. Certified, current, and free. Use these for the **result**
side of every row.

- **Strength:** authoritative. Nothing else is the actual return.
- **Cost:** free.
- **Friction:** every state differs in format, URL structure, and posting cadence, and
  specials happen on scattered dates in scattered states. There is no national index.
- **Use it for:** `dem_votes`, `rep_votes`, `other_votes`, `source_url`.

### 2. The Downballot / Split Ticket — the compiled trackers

Both maintain running special-election tallies **with presidential baselines already
computed**, which is the expensive half of the work.

- Reachability confirmed 2026-09-01: `the-downballot.com` and `split-ticket.org` both
  return HTTP 200.
- **Strength:** they solve the baseline problem. Computing a 2024 presidential share for
  a state-legislative district is not something this repo can currently do (see the gap
  below), and these outlets publish it.
- **Cost:** free to read. The Downballot has a paid tier for some content.
- **Friction:** published as articles and spreadsheets, not APIs. No stable schema.
- **Use it for:** `baseline_dem_share` + `baseline_source`. **Cite them per row** — the
  schema requires it.

### 3. Ballotpedia — most complete, and the only one with a real API

- **The developer portal is real and documented**: `developer.ballotpedia.org` publishes
  geographic APIs (`/districts`, `/officeholders`, `/election_dates`,
  `/elections_by_point`, `/elections_by_state`), a Ballot Measures API, bulk data
  download via client portal or API, and data dictionaries for Candidates, Officeholders,
  Endorsements, Campaign themes, and Candidate survey responses.
- **It publishes no pricing.** There is no rate card, no tier list, no free-tier
  description. It is a "Data Client" model — quote on request.
- **`ballotpedia.org` actively blocks automated access.** Every request returned
  **HTTP 202 with a zero-byte body** (bot protection). Scraping is therefore off the
  table both technically and as a matter of terms — and `docs/data-governance-and-privacy.md`
  already lists scraping sites with restrictive terms as a review trigger. **If we use
  Ballotpedia, it is through the paid API under a signed agreement, or not at all.**
- **Use it for:** complete national coverage of specials and candidate/nominee data —
  which would also close the separate "who won the primary" gap.

### 4. OpenElections — free and open, but thin for recent cycles

53 per-state data repositories at `github.com/openelections/openelections-data-<st>`.
Coverage verified 2026-09-01 across 16 major states:

| Cycle | States with a directory |
|---|---|
| 2025 | **GA, PA** only |
| 2026 | **PA, TX** only |

Pennsylvania does carry real 2026 primary results at county *and* precinct level
(`2026/20260519__pa__primary__county.csv` and per-county precinct files), so the data is
genuine where it exists — there just is not much of it yet. Coverage for older cycles is
much better (MI and PA hold every year 2004–2024).

- **Use it for:** backfilling historical specials to calibrate the metric, and for the
  handful of 2025–26 states already covered.

## Recommended workflow

Per special, one row in `data/reference/special_elections_2025_2026.csv`:

1. **Result** from the state election board → `dem_votes` / `rep_votes` / `other_votes`,
   `source_url`, `retrieved_on`.
2. **Baseline** from a published tracker → `baseline_dem_share`, `baseline_source`,
   `baseline_cycle`.
3. Run validation. Rows missing either citation are **rejected**, not warned about —
   hand-entered data has no upstream checksum, so provenance carries the whole burden.

A cycle is a few dozen rows. This is deliberately manual: it is auditable, it needs no
licensing decision, and it is faster than building 50 state scrapers for a table this
small.

## The real gap: no district-level presidential baseline

This project has no presidential baseline below the congressional district, so
state-legislative rows depend entirely on a third-party tracker for `baseline_dem_share`.

The one Dataverse dataset that would fix this is **`Presidential Vote within Legislative
Districts`** (`doi:10.7910/DVN/24655`, Michael P. McDonald, **CC0**). It tabulates
presidential vote within state legislative districts with identifiers designed to merge
against the State Legislative Elections Returns Database.

**It was released 2014-02-04.** State legislative lines were redrawn after 2010 *and*
2020, so it cannot serve as a 2024 baseline for 2025–26 specials. It remains useful for
**historical calibration** — validating that the overperformance metric behaves sensibly
on past cycles — and is registered on that basis.

## Could not verify

Stated plainly so nobody treats these as settled:

- **Ballotpedia pricing.** Not published anywhere public; requires contacting them.
- **Ballotpedia's Terms of Use content.** The page exists at
  `developer.ballotpedia.org/terms-of-use` but is a GitBook single-page app whose text is
  JavaScript-rendered, so it could not be read programmatically. **A human must read it
  before any commitment**, particularly on redistribution and commercial use.
- **Whether The Downballot or Split Ticket publish structured, downloadable data.** Only
  homepage reachability was confirmed; their tracker formats were not inspected.
- **Coverage of `doi:10.7910/DVN/24655`** — which cycles and which redistricting vintages
  it actually spans. Its files were not downloaded.

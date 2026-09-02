# Special-Election Compilation Worklist — 2025–2026

> ⚠️ **THIS IS NOT DATA.** It is a research aid identifying *which* special elections to
> compile and roughly *when* they occurred. Nothing here may be entered into
> `data/reference/special_elections_2025_2026.csv` as-is.
>
> Contests and dates were located via the Wikipedia API on 2026-09-02. Wikipedia is a
> **tertiary source** and ranks below the trust tiers this project models on
> (`docs/source-reliability-matrix.md`). Every row you compile must take its vote counts
> from the **state election board** and its baseline from a **published tracker**, each
> cited per row. See `docs/special-elections-sourcing.md`.

## How to read the dates

Dates were extracted from article introductions, which mix several kinds of date in one
paragraph: the **general** special, the **primary**, any **runoff**, the date the vacancy
arose, and sometimes the term-start date. They are listed here unfiltered.

**You must confirm which date is the general special before compiling.** Where more than
one date appears, the first is usually — but not reliably — the general.

## U.S. House specials (11 identified)

| Contest | Dates appearing in the article intro |
|---|---|
| AZ-07 | Sep 23 2025 · Jul 15 2025 · Mar 13 2025 |
| FL-01 | Apr 1 2025 · Nov 13 2024 |
| FL-06 | Apr 1 2025 |
| TN-07 | Dec 2 2025 · Oct 7 2025 · Jan 3 2027 |
| VA-11 | Sep 9 2025 · May 21 2025 |
| TX-18 | Nov 4 2025 · Mar 5 2025 · Jan 31 2026 |
| CA-01 | Jun 2 2026 · Jan 3 2027 |
| CA-14 | Jun 16 2026 |
| GA-13 | Jul 28 2026 · Apr 22 2026 |
| GA-14 | Mar 10 2026 · Jan 5 2026 · Apr 7 2026 |
| NJ-11 | Apr 16 2026 · Nov 20 2025 · Feb 5 2026 |

These are the **highest-value rows**: congressional districts, so the baseline is more
readily available from published trackers than for state-legislative seats, and turnout
is high enough that the result is not dominated by noise.

## U.S. Senate specials — exclude these from the metric

| Contest | Date |
|---|---|
| Florida (U.S. Senate special) | **Nov 3 2026** |
| Ohio (U.S. Senate special) | **Nov 3 2026** |

**Both fall on general-election day.** They are "special" only in the legal sense that
they fill an unexpired term — they are contested before a normal midterm electorate, so
they carry **no turnout differential**, which is the entire mechanism the overperformance
metric relies on. Including them would dilute the signal with two high-profile races run
under ordinary conditions.

Compile them if you want the results for other purposes, but mark them so they are
excluded from `national_environment_estimate`.

## State-legislative specials (~17 identified, list incomplete)

| State | Count | Notes from article intro |
|---|---:|---|
| Florida 2025 | 7 | Driven by Florida's resign-to-run law |
| New Hampshire 2025–26 | 2 | Both NH House; as of Jul 3 2025 |
| Alabama 2026 | 3 | Held during 2026 |
| Arkansas 2026 | 3 | 1 Senate (D26) + 2 House; as of Aug 7 2026 |
| Connecticut 2026 | 2 | As of Oct 27 2025 |

⚠️ **This list is incomplete.** These are only the states with a dedicated Wikipedia
page. States that hold specials regularly and are almost certainly missing include
Minnesota, Iowa, Georgia, Pennsylvania and Virginia — Wikipedia maintains
*List of special elections to the Minnesota House of Representatives*, *…Minnesota
Senate*, *…Iowa Senate* and *…Alabama Senate* as standing lists rather than per-year
pages, so they did not surface in a year-scoped search.

Before treating the compilation as complete, sweep those standing lists and each state
board's election calendar.

## Viability check

~28 contests are identified so far, against `national_environment_estimate`'s minimum of
**5**. So the metric is comfortably viable on volume — the constraint is per-row
baselines, not contest count.

## Suggested order of work

1. **The 11 U.S. House specials first.** Best baseline availability, largest turnout,
   least ambiguity. If the metric is going to show anything, it shows there.
2. **Then the ~17 state-legislative rows**, which is where most published analysis finds
   the signal, but where each row needs a tracker-supplied district baseline.
3. **Sweep the standing per-chamber lists** for the states missing above.
4. Leave the two Senate specials flagged and excluded.

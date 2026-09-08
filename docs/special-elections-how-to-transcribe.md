# How to Transcribe Special-Election Results

Ten rows are already pre-filled in `data/reference/special_elections_2025_2026.csv`.
**You fill three numbers and two provenance fields per row.** Everything else — district,
baseline, baseline source — is done.

Automated acquisition is not possible here; every results platform is a JavaScript app or
bot-protected (`docs/special-elections-worklist.md` records the failed attempts). This is
browser work.

## Per row, you supply five fields

| Field | What to enter |
|---|---|
| `dem_votes` | Democratic candidate's total votes |
| `rep_votes` | Republican candidate's total votes |
| `other_votes` | Everyone else combined (`0` if none) |
| `source_url` | The **exact page you read the numbers from** |
| `retrieved_on` | Today's date, `YYYY-MM-DD` |

Leave every other column alone. Validation **rejects** any row missing `source_url` or
`retrieved_on` — for hand-entered data the citation is the only quality control there is.

## Where to open each one

| Row | Where |
|---|---|
| **VA-11** | `https://enr.elections.virginia.gov/results/public/virginia/2025-September-9-Special` ← exact page, verified |
| FL-01, FL-06 | `https://results.elections.myflorida.com/` |
| TX-18 | `https://www.sos.state.tx.us/elections/historical/index.shtml` |
| CA-01, CA-14 | `https://electionresults.sos.ca.gov/` |
| GA-13, GA-14 | `https://results.sos.ga.gov/` |
| NJ-11 | `https://www.nj.gov/state/elections/election-results.shtml` |
| TN-07 | ⚠️ URL not located — search the Tennessee Secretary of State's results archive |

All verified reachable 2026-09-05 except TN.

## Four things that will bite you

**1. Confirm the date.** Every pre-filled `election_date` came from Wikipedia and is
**unverified** — the article intros mixed generals, primaries, runoffs and term-start
dates in one paragraph. The results page states the real date. Fix it if it differs, then
delete the `CONFIRM DATE` text from `notes`.

**2. Under an all-party ballot, compile round ONE — not the deciding round.**
An earlier version of this document said "use the deciding round." That is right for a
D-vs-R runoff and **wrong** for an all-party ("jungle") special.

Texas, Georgia and Louisiana run specials with every candidate on one ballot, and
California uses top-two. If nobody clears 50%, the top two advance — and in a safe seat
they are usually **from the same party**. TX-18's runoff was D-vs-D.

A same-party runoff is unusable. One party's vote is zero because nobody from that party
was on the ballot, not because voters abandoned it, so the two-party margin is +/-1 no
matter what. TX-18's runoff scores **+59.6 points** of Democratic overperformance against
a +0.404 baseline margin. Pure artefact.

**The rule: compile the last round in which both parties ran.** For an all-party contest
that is round one. Record `contest_format` accordingly, and **aggregate by party** — sum
every Democratic candidate into `dem_votes` and every Republican into `rep_votes`.

**3. A special held alongside another election is not usable either.** CA-01 fell on
California's statewide primary day. The metric works off the turnout *differential*
between a special and a regular election; when they are the same election there is no
differential. Its turnout ratio is 0.62 against a standalone-special norm of 0.33-0.45,
and its overperformance is ~0 while every standalone special in the table sits between
+11 and +29. Same rule already applied to the two general-election-day Senate specials.

**4. Two-party only for the majors.** `dem_votes` and `rep_votes` must hold *only*
major-party candidates. Independents, write-ins and minor parties go in `other_votes` —
they do not affect the metric, which runs on the two-party margin, but they belong in the
total.

## Recording an unusable contest

Do not delete it. Set `include_in_metric` to `N` and write an `exclusion_reason`.
Validation **rejects an exclusion with no reason**, so a dropped row can never be
confused with an oversight. Excluded rows are exempted from the vote and provenance
gates, which is what lets a not-yet-compiled placeholder sit in the table.

Validation also **rejects any included row where one major party polled zero**
(`votes.both_parties_contested`). That single rule catches same-party runoffs,
uncontested specials, and the transcription slip of missing a party.

## Check your work

```bash
./scripts/check_specials.sh
```

While rows are incomplete it exits non-zero and names the failing gates — that is the
gate working, not an error. Once every row is filled it prints each contest's
overperformance and the national-environment estimate.

## Current state (2026-09-08)

Nine of ten rows are compiled and the table **validates**. Seven feed the metric; three
are recorded and excluded:

| Row | Why excluded |
|---|---|
| GA-13 | Runoff, turnout 6% of presidential. Compile the 2026-04-22 first round instead. |
| CA-01 | Held on the statewide primary day — no turnout differential. |
| CA-14 | Not yet compiled. |

`national_environment_estimate` requires **five**, so seven clears the bar. The two
outstanding jobs are CA-14's results and GA-13's April first round.

## What happens after

The metric returns Democratic overperformance against each district's 2024 presidential
baseline, plus a standard error and explicit caveats. Treat it as an **association** with
the national environment, not a measurement of it — specials are a non-random sample of
seats and their turnout composition differs from a general electorate.

AZ-07 is deliberately absent: its baseline is flagged `under_covered` (26% of Arizona's
median district vote), so it would need a tracker-supplied baseline instead.

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

## Three things that will bite you

**1. Confirm the date.** Every pre-filled `election_date` came from Wikipedia and is
**unverified** — the article intros mixed generals, primaries, runoffs and term-start
dates in one paragraph. The results page states the real date. Fix it if it differs, then
delete the `CONFIRM DATE` text from `notes`.

**2. TX-18 had a runoff.** The general was 2025-11-04 and a runoff followed on
2026-01-31. **Use the deciding round**, and set `election_date` to match it. Texas runoffs
determine the winner, so the November round is not the result.

**3. Two-party only for the majors.** `dem_votes` and `rep_votes` must be the *major-party
nominees*. Independents, write-ins and minor parties all go in `other_votes` — they do not
affect the metric, which is computed on the two-party margin, but they belong in the total.

## Check your work

```bash
./scripts/check_specials.sh
```

While rows are incomplete it exits non-zero and names the failing gates — that is the
gate working, not an error. Once every row is filled it prints each contest's
overperformance and the national-environment estimate.

## You do not need all ten

`national_environment_estimate` requires **five**. Five good rows produce a real estimate;
ten produce a better one. Start with VA-11, since its page is verified and linked
directly.

## What happens after

The metric returns Democratic overperformance against each district's 2024 presidential
baseline, plus a standard error and explicit caveats. Treat it as an **association** with
the national environment, not a measurement of it — specials are a non-random sample of
seats and their turnout composition differs from a general electorate.

AZ-07 is deliberately absent: its baseline is flagged `under_covered` (26% of Arizona's
median district vote), so it would need a tracker-supplied baseline instead.

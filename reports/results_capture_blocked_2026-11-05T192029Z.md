# November 5 Results Capture: Blocked Checkout

Heartbeat: 2026-11-05T19:20:29.440Z, or 12:20:29 America/Vancouver.
This is an operational failure report, not a results observation or forecast score.
No daily compiled snapshot was saved.

## New Material Blocker

The requested working directory is on branch `post-poll-closing-updates` at
`1369168389aef38fbd45bcfe3c9aead93f9e2ebf`. It was clean at the start of this run,
but does not contain the validated capture workflow reviewed before Election Night.
The following required files are absent:

- `docs/results-2026-runbook.md`
- `docs/pre-election-2026-checklist.md`
- `data/reference/results_sources_2026.csv`
- `src/election_prediction/data/results_sources.py`
- `reports/comparison_set_2026-11-03.json`
- `scripts/verify_pre_election.py`

The installed module CLI was checked in this directory. Its help exposes only
`capture` and `actual`; its source has neither `preserve-source` nor
`capture --source-evidence`. Do not bypass the required evidence safeguards by
using this older capture command. The prior as-of, certification-revocation and
unresolved-round acceptance checks cannot be assumed to apply to this checkout.

## Guidance Recovery and Limited Source Review

Read the current `AGENTS.md` and `PROJECT_CONTEXT.md`. The missing runbook,
checklist and 50-state catalog were read without restoration using `git show`
from locally available commit `eee9c5e1f2b31d42e0ce5dfd082810ecf143118e`, the commit
recorded by the November 1 successful verification. Local refs
`feat/fec-candidate-layer` and `origin/feat/fec-candidate-layer` contain that commit.
This identifies an available workflow version; no branch was switched, merged,
reset or otherwise changed, and no historical code was substituted for execution.

Four catalog-derived official portals were reviewed on the web during this run:

| State | Official URL | Observed limitation |
|---|---|---|
| VA | https://www.elections.virginia.gov/results/ | Lists November 3, 2026 General and Special Elections as unofficial. Its linked reporting application supplied no readable count table through this tool. |
| NC | https://er.ncsbe.gov/ | Contest portal and downloads page require an election selection; no November federal aggregate download was verified. |
| CA | https://electionresults.sos.ca.gov/ | The landing page exposes an iframe; following it returned an Imperva security check, not aggregate results. |
| LA | https://voterportal.sos.la.gov/static/2026-11-03/resultsRace/ | Inaccessible through the web tool. This is not proof of a site-wide outage. |

Virginia's linked reporting application is
https://enr.elections.virginia.gov/results/public/virginia/elections/2026-November-General;
North Carolina's downloads page is https://er.ncsbe.gov/downloads.html.
These are portal-level checks, not validated feeds or preserved raw releases.
No aggregate count file was downloaded, ingested or passed to a preservation command.
The other 46 states were not checked live in this run. No earlier manual-download
or historical-parser status is represented as a fresh November 5 validation.

## Capture and Scoring Status

No `data/raw/source=state_canvass/**/snapshot=*.csv` production observation was found,
and no `*.source.json` source-evidence receipt was found under `data/raw`.
Thus all 50 states are missing from validated production observations in this
checkout, not necessarily missing from the authorities' own reporting systems:

AL, AK, AZ, AR, CA, CO, CT, DE, FL, GA, HI, ID, IL, IN, IA, KS, KY, LA, ME, MD,
MA, MI, MN, MS, MO, MT, NE, NV, NH, NJ, NM, NY, NC, ND, OH, OK, OR, PA, RI, SC,
SD, TN, TX, UT, VT, VA, WA, WV, WI, WY.

No daily observation, certified subset, actual-results table or forecast score was
created. There is no claim of complete capture, unattended success, zero forecast
error or final certification. Missing election-night observations were not backdated
or reconstructed from later information.

All four September sealed-file hashes match their previously recorded values:
registration JSON, registration Markdown, seat CSV and findings Markdown.
No forecast parameters, source compilations, candidate inputs, branch configuration
or unrelated content were changed. Only this new failure report was added.

## Required Action and Remaining Work

1. Align the automation's working directory with the validated capture implementation
   and its source catalog, or deliberately integrate that implementation into this
   branch. Review the chosen branch/worktree before changing it; do not regenerate
   the sealed forecast or replace the frozen comparison set.
2. Resume official aggregate retrieval immediately once the governed workflow is
   available. Preserve raw releases using `preserve-source`, with actual retrieval
   timestamps, URLs and SHA-256, and explicitly sourced status, round, resolution
   and winner identity. Manual browser saves remain a fallback for inaccessible
   official sources. Report every missing state rather than substituting results.
3. Append a new UTC-dated observation with `capture --source-evidence`; do not create
   empty or invented counts to make the daily capture appear successful. Build and
   score only certified, resolved subsets under the validated as-of rules.
4. Keep Louisiana House first rounds separate from any December 12 runoff. A
   certified but unresolved first round is unscoreable. Follow recounts, certification
   revocation and recertification; never use media calls as certification evidence.
5. Today's trigger at 12:20:29 Vancouver is not the intended 22:00 execution. Retain
   manual invocation until actual timing is confirmed. The automation remains useful
   through certification/runoffs; it was not deleted or rescheduled by this run.

Continue until final resolution or January 4, 2027, requesting an extension if needed.

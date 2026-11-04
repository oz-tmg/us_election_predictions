# October 22 Evidence Review

Owner: Alex Oswald. Nonpartisan public aggregate research only. This is not a new
estimator, a complete poll census, a legal opinion or a November results capture.

## Polling

Original Marist September 23 and Emerson September 24 national district-vote-intention
releases were saved again in dated raw snapshots; manifests retain their actual retrieval
and SHA-256. Survey field dates remain September 14-15 and September 21-22. A newer
retrieval is not a newer survey. The current cross-check still has only two surveys and
unidentified house effects, and remains unpromotable.

Catalogs reviewed October 22:

- [Marist latest polls](https://maristpoll.marist.edu/latest-polls/): October releases
  reviewed concern individual states, not a replacement national generic ballot.
- [Emerson national archive](https://emersoncollegepolling.com/category/national-poll/):
  latest national generic-ballot release found was September 24.
- [Quinnipiac September 29 national release](https://poll.qu.edu/Poll-Release?releaseid=3968):
  September 24-27, n=1,032 registered voters, live landline/cell phone. The 51/39 question
  asks which party respondents want to control the House, not their district's intended
  vote. It is excluded from the district vote-intention average on construct grounds,
  irrespective of the observed party margin. State polls are not substituted nationally.

This review does not prove that no eligible poll exists elsewhere. No YouGov ingestion,
respondent records, prohibited scraping or precision blending was performed.

## Precinct Sources

- Kansas fresh official workbook again reconciles neither major party: 544,836 versus
  544,853 D, and 758,775 versus 758,802 R. Suppression/blank cells are not reversed.
- NCSBE original administrative-precinct ZIPs reconcile each major party exactly for
  2020 and 2024. Archived October 18, 2020 / July 23, 2024 precinct polygons were acquired
  and tested with county-qualified identifiers. Multipart polygons were dissolved only
  within the same published identifier. The 2020 audit places all offered votes (including
  county allocations) and its 2020->2022 diagnostic covers 14 districts, MAE 0.0175 versus
  fallback 0.1086. The 2024 polygons still produce ambiguous block assignments and are
  refused. See `priority_transfers/`; no live prior or sigma has been admitted.
- NCSBE explains that its separate precinct-sorted releases contain privacy noise and
  are not official totals. No attempt was made to undo that noise or reconstruct cells.
  [NCSBE source documentation](https://www.ncsbe.gov/results-data/election-results/historical-election-results-data)
- Florida's officially linked 2024 ZIP returned HTTP 403 from the acquisition client:
  `https://dos.fl.gov/media/708761/2024-gen-outputofficial1.zip`. No replacement was
  substituted. Indiana/Louisiana/Oklahoma/New Jersey flagged sources remain excluded.

## Special Elections

The October 21 GA/NJ verification remains in force with its actual retrieval dates.
Florida's outer page was a frameset; following its federal-results link established both
April 1 congressional specials and all D/R/other totals. FL01 is 72,375/97,370/1,503;
FL06 is 83,580/110,980/1,240. Counts are unchanged; URL/retrieval metadata now point to
the actual table and October 22. See `special_source_refresh.json`. Tennessee's cited
certified PDF returned HTTP 403. Other compilation retrieval dates remain unchanged.

## Map and Calendar Review

[NCSBE's current map page](https://www.ncsbe.gov/results-data/voting-maps-redistricting)
identifies the October 2025 congressional map for 2026. This does not settle later
litigation in every state. The nine redrawn states and Missouri still need an official
legal-status review before release. No plan-register dates were falsely refreshed.

[Louisiana SOS](https://www.sos.la.gov/elections-voting/types-of-elections) identifies
November 3 as the House first round and December 12 as its possible final round. The
Senate uses the November general. Capture records round identity and resolved status;
certification of an unresolved first round is not an elected-member outcome.

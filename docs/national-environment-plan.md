# National Environment: Architecture Plan

_Drafted 2026-09-09; Track D added 2026-09-15. Supersedes the implicit design in which
`shrinkage` was a number to be estimated later._

## The decision this document records

`shrinkage` is not estimable from what this project has, and the attempt to estimate it
has been shaping the architecture. One cycle of specials cannot identify it; four
historical cycles cannot either, in the sense of yielding a point estimate anyone should
condition on. The change is to **stop treating shrinkage as a parameter and start
treating the sensitivity band as the output**, then reorganize the national-environment
layer around an estimator that is identified — the generic ballot — with specials demoted
to a cross-check.

Three consequences follow, and they are the first three tracks below. A fourth track adds
the estimator that none of the others supply: the one available a year out, when there are
no specials and no generic ballot worth averaging.

| Track | Item | What it changes | Gated on |
|---|---|---|---|
| A | NE-001 | The band becomes the contract, not a diagnostic printout | nothing |
| B | NE-002 | Four historical pairs bound the band; they never fit it | hand compilation |
| C | NE-003 | Generic ballot becomes primary; specials become a cross-check | NE-000 (legal) |
| D | NE-004 | Economic fundamentals become a third estimator — a cross-check in midterms, the far-out estimator in presidential years | FRED/BEA/BLS registered; NE-001's contract |
| — | NE-000 | Poll redistribution terms answered | a human reading terms |

---

## Track A — Keep reporting the band (NE-001)

### The claim

`shrinkage_sensitivity` across 0.25–1.0 already answers the question a consumer actually
has. From `reports/projection_2026.txt`: Democrats are favored for the House at every
factor in the band (`house_p_dem` 0.518 → 0.792), and the Senate is out of reach except at
the top (`sen_p_dem` 0.272 → 0.545, crossing 0.5 only at shrinkage = 1.0). A point
estimate would not change either conclusion; it would only misrepresent their support.

That is a *finding about the band's usefulness*, and it is currently buried in a script's
stdout. It should be a returned object with a validated schema.

### Architecture

Add `src/election_prediction/models/baseline/national_environment.py`. It owns the
estimator contract; `data/special_elections.py` keeps the specials measurement but stops
being the thing a projection reaches for.

Every estimator returns the same shape:

```
{
  "estimator": str,            # "specials_band" | "generic_ballot" | "scenario"
  "status": str,               # "band" | "point" | "unavailable"
  "national_dem_share": float | None,   # None when status == "band"
  "band": DataFrame | None,    # the sweep, when status == "band"
  "identified": bool,          # False whenever a free parameter was assumed
  "assumptions": list[str],
  "caveats": list[str],
  "provenance": dict,          # source_id, snapshot_date, n
}
```

`identified` is the field that does the work. It is `False` for the specials band by
construction and must stay `False` — a validator should fail the build if a specials-derived
estimate ever reports `True`, in the same spirit as `filings.validate_filings` refusing to
emit `nominated`.

### Changes to existing code

- `scripts/project_2026.py` stops calling `se.shrinkage_sensitivity` directly and consumes
  `national_environment.estimate(...)`. The loop over the sweep stays; it is now iterating
  a contract rather than a specials-specific DataFrame.
- `implied_national_dem_share`'s `shrinkage` default (`SHRINKAGE_UNCALIBRATED = 0.5`)
  should be **removed, not re-pointed**. A default is what lets a caller obtain a bare
  number without choosing; making it a required keyword is the same discipline
  `generic_ballot.apply_national_swing` already applies to `national_swing`.
- The projection report gains a machine-readable sibling
  (`reports/national_environment_<date>.json`) so the band can be diffed across runs
  rather than re-read from formatted text.

### Acceptance criteria

- A projection cannot be produced from an unidentified estimator without the band, and a
  test asserts that.
- Every row of the emitted band carries the assumption that generated it.
- `reports/projection_2026.txt` states the two band-level conclusions (House favored
  throughout; Senate only at the top) as text, not as a table the reader must infer from.
- No public function returns a national share with a silently defaulted free parameter.

### What would falsify this track

If the House control conclusion flips sign somewhere inside 0.25–1.0, the band is no
longer a sufficient output and a point estimate becomes necessary rather than merely
desirable. Re-check this whenever the specials mean or the seat roster changes.

---

## Track B — Four historical pairs as a bound, not a fit (NE-002)

### The claim, stated carefully

Compile the specials window and the following November general for four cycles —
**2017→2018, 2019→2020, 2021→2022, 2023→2024** — and compute the realized ratio
(general swing ÷ specials-window mean overperformance) for each. If all four land near
0.4, that is evidence the plausible band is narrower than 0.25–1.0, and narrowing it is a
real gain: at shrinkage ≈ 0.4 the Senate conclusion is unambiguous rather than
conditional.

What it is **not** is a fitted parameter. n = 4, drawn from two redistricting eras and
both presidential-party configurations. Four ratios can bound a band; they cannot support
a point estimate or a standard error anyone should propagate. The plan must encode that
distinction structurally, or the number will get used as a point the first time someone is
in a hurry.

### Architecture

- Extend `data/reference/` with `special_elections_historical.csv`, same schema as
  `special_elections_2025_2026.csv` (`read_compiled` and `validate_specials` are reused
  unchanged — every row still needs `source_url` + `retrieved_on`).
- Add `calibration_pairs(specials, generals) -> DataFrame` to `data/special_elections.py`:
  one row per cycle pair with `specials_mean`, `general_swing`, `realized_ratio`, `n_specials`,
  `plan_era`, `president_party`.
- Add `band_from_pairs(pairs) -> dict` returning **an interval and a refusal**: the
  min/max of the observed ratios, widened by the spread, plus `"status": "bound"` and
  never a mean. If a caller wants a central value they must pass it themselves.
- The band constant becomes derived: `SHRINKAGE_SENSITIVITY` is replaced by the bound when
  one exists, and stays at the current tuple otherwise.

### The measurement trap to avoid

Overperformance here is measured against a **presidential** baseline and applied to a
**House** basis (already in `implied_national_dem_share`'s caveats). The historical pairs
must replicate that exact construction — same baseline office, same halving of the margin,
same exclusions (`include_in_metric`, Senate specials dropped) — or they will calibrate a
different quantity than the one being shrunk. This is the single highest-risk detail in
the track. A test should assert that the historical and live paths share the same
`compute_overperformance` code path rather than reimplementing it.

### Cost

Roughly four times the 2025–26 compilation, which `docs/special-elections-worklist.md`
sizes at ~28 contests with per-row baselines as the binding constraint. Pre-2024 baselines
are worse, not better: `data/gold/cd_presidential_baseline_2024.parquet` covers one cycle,
and the tracker sources that solve the baseline problem (The Downballot, Split Ticket)
have thinner archives the further back you go. Budget the state-legislative rows as the
expensive half, and consider House-only pairs as the first deliverable.

### Acceptance criteria

- Four `realized_ratio` values, each traceable to per-row sources.
- A returned interval, explicitly not a point, with `status == "bound"`.
- A test that fails if `band_from_pairs` ever returns a scalar shrinkage.
- `SHRINKAGE_SENSITIVITY` derived from the bound, with the old tuple as the documented
  fallback.

### What would falsify this track

If the four ratios span more than ~0.3 in width, the band does not narrow and the
compilation has bought nothing but an honest negative result — which should be written up
and the track closed rather than extended to more cycles in search of a tighter answer.
Decide that threshold **before** looking at the fourth pair.

---

## Track C — Generic ballot primary, specials as cross-check (NE-003)

### The claim

A generic-ballot average is a direct estimate of the quantity the House model needs.
`national_dem_share` carries the largest coefficient in the House baseline (+0.884), and
the backtest conditions on its true value — so a live cycle needs it from somewhere, and
the generic ballot is what it is for. Specials overperformance is an *association* with
the national environment (its own docstring says so); a generic ballot is a measurement of
it. Making the measurement primary and the association a cross-check is the correct
ordering, independent of how the licensing question resolves.

### What actually sits behind the gate

The licensing answer is one decision, and it is plausibly faster to obtain than four
cycles of hand compilation. But it unblocks the *right to store toplines*, not a working
estimator. Behind it:

1. **Schema.** `polling/schema.py` requires `geography_id` and `state_po` per row, and
   `geography/reference.py` exposes only `StateRef` / `by_postal`. A national generic-ballot
   row has no state. Needs a national geography entry and an `office` value
   (`us_house_generic`) that the validator accepts.
2. **Manifest.** `build_p2.py` sets `redistribution_allowed=synthetic` — i.e. `False` for
   any real poll. That flag is the licensing question made concrete, and NE-000's answer
   is what sets it.
3. **House effects.** P2-003 is `todo`. A generic-ballot average across mixed pollsters
   without house-effect handling inherits whatever the field's composition happens to be
   that month. `house_effect_dem` exists in `POLL_COLUMNS` as an optional externally
   estimated field, so v0 can carry published estimates rather than fitting its own.
4. **Backtest.** No historical generic-ballot archive is registered. Without one there is
   no held-out test, and an unbacktested primary estimator is a downgrade from an honest
   band — see the decision gate below.

### Architecture

- `national_environment.from_generic_ballot(polls, *, as_of, swing_ratio)` produces a
  `status: "point"` estimate with `identified: True`, using the existing
  `polling.average_polls` machinery.
- Specials move to `cross_check(primary, specials_band) -> dict`, reporting whether the
  point estimate falls inside the specials band and how far from its centre. Disagreement
  is **reported, never reconciled** — no blending of a measurement with an association.
- `generic_ballot.apply_national_swing` is already the right seam and needs no change; it
  requires `national_swing` explicitly, which is exactly the contract this feeds.

### The separate blocker this does not fix

The 2022-era **swing ratio** is unidentified (`estimate_by_plan_era` returns
`"unidentified"` — one cycle of swings gives no slope), and no national estimator fixes
that. 2026's own returns would be the second cycle, which arrives too late to forecast
2026. So a live projection must either adopt the pooled cross-era ratio with its deviation
from uniform reported, or state uniform swing (β = 1) as an assumption. Whichever is
chosen, it belongs in `assumptions` on the estimator contract, so the projection carries
two named assumptions rather than one hidden one.

### Acceptance criteria

- NE-000 answered in writing and recorded in `docs/dataset-registry.md` with the terms
  cited, before any topline is stored.
- A national geography row and `us_house_generic` office accepted by `validate_polls`.
- At least one historical cycle backtested: generic-ballot average as of ~60 days out
  versus realized national House share.
- `cross_check` output present in every projection report, including when the two agree.

### Decision gate

**Do not promote the generic ballot to primary until it has beaten the band midpoint on at
least one held-out cycle.** Until then it is a second cross-check. A point estimate that
has never been tested is more dangerous than a band that is honest about being one,
because it invites exactly the false precision this plan exists to remove.

---

## Track D — Economic fundamentals as a third estimator (NE-004)

### The claim

The economy's effect on the national vote is the best-established regularity in election
forecasting, and this project does not model it. `docs/methodology.md` lists "GDP/income,
inflation, consumer sentiment, party tenure" in one bullet; nothing in `src/` reads an
economic series, no BEA/BLS/FRED source is registered, and the presidential baseline
conditions on the *true* `national_dem_share` — the national vote is never forecast.

The regularity is worth stating precisely, because the precise version is what the
estimator should encode. Election-year growth in real income (and GDP), measured over the
first half of the year, predicts the **incumbent president's party's** two-party share;
the effect is stronger when the president is on the ballot, and weakens with the number
of consecutive terms the party has held the White House (Fair; Abramowitz's "Time for
Change"; Hibbs's "Bread and Peace"). In midterms, the economy's effect runs mostly
through presidential approval and is smaller than the midterm penalty the House and
Senate baselines already carry (Tufte).

### What this track is not

It is not a narrative fitted to the cycles everyone remembers. Two of the cases most
often cited for the economy-decides-elections story are famous misses of exactly this
class of model: **1992** (the recession ended in March 1991; Q2–Q3 1992 real growth was
~4%; Fair's model predicted a Bush win) and **2000** (strong Q2 growth; fundamentals models
predicted a comfortable Gore popular-vote win; he won it by half a point and lost the
Electoral College). 2008 is the clean case. 2020 held the sign but not the magnitude:
Q2 GDP fell ~31% annualized, rebounded ~33% in Q3, and the incumbent lost the two-party
vote by ~4.5 points while raising his own vote share over 2016.

The honest picture is a robust *direction*, an uncertain *magnitude*, and a sample of
**13 presidential cycles in this project's own returns** (1976–2024) — nineteen if a
pre-1976 national-vote source is registered. That is the same shape of problem as
shrinkage: a parameter that n cannot pin down and that a story will pin down for you if
the architecture lets it. The guards below exist for that reason.

### Architecture

**Ingestion.** Add `data/fred.py`: FRED API (`FRED_API_KEY`, same `.env` discipline as
Census and FEC), pulling a fixed, documented series list into `data/raw/` with query
date in the filename and a manifest. Register each series in `docs/dataset-registry.md`
before use (CLAUDE.md §7) — all Tier 0. First-pass series:

| Series | Source via FRED | Role |
|---|---|---|
| Real disposable personal income per capita (`A229RX0`) | BEA | Primary growth measure (Hibbs; Fair's "growth") |
| Real GDP (`GDPC1`) | BEA | Secondary growth measure |
| Unemployment rate (`UNRATE`) | BLS | Change over the election year |
| CPI-U (`CPIAUCSL`) | BLS | Election-year inflation |
| Consumer sentiment (`UMCSENT`) | U. Michigan | Perceived economy — the 1992 lesson |

Presidential approval is deliberately **not** in the first pass: it is the strongest
midterm predictor, but its redistribution terms are the same question as NE-000 and it
should be gated the same way.

**Vintages are the measurement trap.** Q2 GDP's advance estimate is released in late July
and revised for years; a forecast issued in September should use the number that existed
in September, not the one revised in 2028. FRED's ALFRED endpoint serves as-of vintages.
Every panel row must carry `data_vintage`, and the backtest must be run on real-time
vintages, or it is measuring a quantity no forecaster could have used. Record the vintage
policy in the registry row.

**Panel.** Add `features/national_fundamentals.py` building one row per presidential
cycle (and, separately, per midterm):

```
cycle, incumbent_party, president_on_ballot, consecutive_terms,
h1_rdi_growth, h1_gdp_growth, unemployment_change_12m, cpi_yoy, sentiment_q2,
data_vintage, incumbent_party_two_party_share
```

The target is the **incumbent party's** share, not the Democratic share. The estimator is
sign-agnostic by construction: no feature is defined by party, and the mapping to
`national_dem_share` happens once, at the end, through `_white_house_party` (already in
`models/baseline/senate.py`). This is the nonpartisanship rule (CLAUDE.md §2.1) made
structural rather than asserted.

**Estimator.** `national_environment.from_fundamentals(panel, *, cycle, as_of)` returns the
Track A contract with `status: "point"`, `identified: True`, and `sigma` taken from the
leave-one-cycle-out residuals — which will be wide, and which is reported, not tuned.
Specification is fixed in advance and small: one growth term, `president_on_ballot`,
`consecutive_terms`. Adding indicators is a *new* specification requiring a *new*
held-out comparison, not a refinement.

**Pre-registered decisions (2026-09-15, before any backtest has run):**

- *Growth term:* **H1 real disposable personal income per capita**, annualized. Q2 real
  GDP is the one documented sensitivity. The reason is 1992: headline output had recovered
  while real income had not, and income is the quantity a voter experiences.
- *Panel depth:* extend **before 1976, but only as far back as a real-time vintage of the
  growth term exists** — the boundary is set by data honesty, not by preference. The
  Philadelphia Fed Real-Time Data Set for Macroeconomists carries real-output vintages
  from 1965Q4, which would make **1968 the earliest cycle** (n = 15); if real-time
  disposable-income vintages do not reach that far, the pre-1976 rows carry the GDP
  sensitivity term only and say so. 1948 is explicitly out: revised-data rows would
  measure a quantity no forecaster could have used. The pre-1976 national two-party vote
  needs its own registered source (MEDSL starts in 1976; ICPSR's historical constituency
  totals are the candidate), registered before use like everything else.

**Role by cycle type.** In a **midterm** (2026) it is a third cross-check through the
existing `cross_check(primary, ...)` — never blended with specials or the generic ballot,
disagreement reported. In a **presidential** year it is the only national estimator
available before polls mean anything, which is the reason the track exists: 2028 is
where this earns its keep, and 2026 is where it gets backtested in public.

### Acceptance criteria

- FRED series registered (license, vintage policy, attribution) before any pull; pulls
  land with manifests and query-dated filenames.
- A panel with real-time vintages for every cycle 1976–2024, and a test that fails if any
  row lacks `data_vintage`.
- Leave-one-cycle-out MAE and 90% coverage reported against **two** comparators: naive
  persistence (last cycle's national two-party share) and, for midterms, the midterm
  penalty alone.
- The estimator's output is the incumbent-party share; a test asserts that flipping the
  White House party in the panel flips the sign of the Democratic mapping and nothing else.
- `cross_check` output for 2026 includes the fundamentals estimate alongside specials.

### Decision gate

**It is a cross-check until it beats persistence on held-out cycles, and it is never the
primary estimator in a midterm.** In a presidential year it may be primary only until
the generic ballot or a poll average is available and has itself been backtested, at
which point it becomes the cross-check. A fundamentals estimate that has beaten
persistence on 13 cycles is still a 13-cycle result; its sigma says so.

### What would falsify this track

If leave-one-cycle-out MAE is not better than persistence — or is better only under a
specification chosen after looking at the residuals — the track closes with the negative
result written up, and the fundamentals estimate stays in the report as a labelled
cross-check with its honest sigma. Do not add series, lags, or interaction terms in search
of a fit; with n = 13 the garden of forking paths is the whole garden. Decide the
comparison metric and the specification **before** the first backtest runs, and record
both in this document.

### Cost

Small in compute and data: the FRED API is free with a key, the panel is a few dozen
rows, and the backtest runs in seconds. The cost is discipline — the vintage handling and
the pre-registered specification are what separate this from a curve-fit to five
memorable elections.

---

## Sequencing

1. **NE-000 (legal) and NE-001 (band contract) start immediately and in parallel.** NE-001
   depends on nothing and is the piece that makes the current output defensible.
2. **NE-002 begins with House-only pairs.** They have the best baseline availability, and
   four House-only ratios are a usable bound. State-legislative rows are a later extension,
   not a prerequisite.
3. **NE-003 begins when NE-000 returns.** If the answer permits storage, the schema and
   manifest work is small; the backtest is the long pole.
4. **NE-004 begins after NE-001 lands** — it needs the contract to return into — and
   after its FRED series are registered. Its 2026 role is cross-check only, so it is not
   on the critical path for the current projection; its 2028 role is why it should not
   wait until 2028.
5. **None of B, C, and D are competitors.** If the generic ballot becomes primary, the
   historical pairs still bound the specials cross-check and the fundamentals estimate
   still appears beside it — the band does not stop being reported just because
   something better exists next to it.

## Open questions

- Which central value, if any, the narrowed band gets when it is quoted in a single
  sentence. Current position: none — quote the interval.
- Whether House-only calibration pairs are sufficient, or whether the state-legislative
  rows are load-bearing for the ratio. Unknown until the House-only pairs are in hand.
- Whether a pooled cross-era swing ratio or uniform swing is the better interim
  assumption for the 2022 plan era. Both are assumptions; the choice should be made on
  which is easier for a reader to reason about, since neither is estimable.
- ~~Panel depth and growth term for NE-004~~ — decided 2026-09-15; see Track D
  "Pre-registered decisions". Remaining sub-question: whether real-time disposable-income
  vintages exist before 1976, which determines whether the 1968–1972 rows carry the
  primary term or only the sensitivity term.

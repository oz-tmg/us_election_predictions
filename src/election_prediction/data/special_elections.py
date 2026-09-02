"""Hand-compiled special-election results and the overperformance metric.

Special elections are the one practical way to estimate a national environment without
polls. That matters here for two specific reasons:

* ``national_dem_share`` carries the largest coefficient in the House baseline (+0.884),
  and its backtest *conditions on the true value*. For a live cycle that number has to
  come from somewhere.
* P1-004's swing ratio is **unidentified** for the current (2022) redistricting era —
  one cycle of swings gives no slope — so the usual route into district-level effects
  is unavailable, and a poll-based national estimate is still blocked on the unresolved
  poll-redistribution question (``docs/dataset-registry.md``).

No open structured source exists. MEDSL publishes nothing on specials, Harvard Dataverse
carries only one-off exit surveys, and our own federal returns hold ~2 specials a cycle
while the informative signal sits in *state legislative* specials. So this module accepts
a **hand-compiled** table instead — a few dozen rows a cycle, which is tractable — and
compensates for the lack of an upstream publisher with strict provenance:

**Every row must cite a source URL and a retrieval date, or it is rejected.** For manually
entered data the citation *is* the quality control; there is no upstream checksum to fall
back on. Validation is deliberately unforgiving for the same reason.

The metric is margin-based rather than share-based. Special elections have erratic and
usually low turnout, so comparing a special's *margin* against the seat's presidential
*margin* controls for the turnout level in a way raw share does not. It does not control
for turnout *composition*, which is the metric's main known weakness and is recorded as
such in the outputs rather than argued away.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

# The compiled input schema. `baseline_dem_share` is supplied by the compiler rather
# than derived: state-legislative districts do not map cleanly onto counties, and this
# project has no district-level presidential baseline below the congressional district.
# Supplying it explicitly (with its own citation) is honest about where it came from.
SPECIAL_COLUMNS = [
    "special_id",
    "election_date",
    "state_po",
    "office",  # us_house | us_senate | state_house | state_senate | other
    "district",
    "dem_votes",
    "rep_votes",
    "other_votes",
    "baseline_dem_share",  # two-party presidential Dem share for the same geography
    "baseline_source",
    "baseline_cycle",
    "source_url",
    "retrieved_on",
    "notes",
]

OUTPUT_COLUMNS = SPECIAL_COLUMNS + [
    "total_votes",
    "two_party_votes",
    "special_dem_share",
    "special_margin",
    "baseline_margin",
    "overperformance",
]

VALID_OFFICES = frozenset({"us_house", "us_senate", "state_house", "state_senate", "governor", "other"})

# A special with almost no votes is noise, not signal, and hand-entry typos land here.
MIN_PLAUSIBLE_VOTES = 100


def empty_frame() -> pd.DataFrame:
    """An empty, correctly-typed compilation table — the starting point for entry."""
    return pd.DataFrame(columns=SPECIAL_COLUMNS)


def read_compiled(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str, comment="#")
    df.columns = [c.strip().lower() for c in df.columns]
    for col in ("dem_votes", "rep_votes", "other_votes", "baseline_dem_share", "baseline_cycle"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def validate_specials(df: pd.DataFrame) -> dict:
    """Hard gates on a hand-compiled table. Returns a report; never mutates the input.

    Deliberately strict. This is the only dataset in the project with no upstream
    publisher, checksum, or manifest to verify against, so the citation and internal
    consistency of each row carry the whole burden of trust (CLAUDE.md §4).
    """
    checks: dict[str, object] = {}
    missing = [c for c in SPECIAL_COLUMNS if c not in df.columns]
    checks["schema.required_columns"] = not missing
    checks["schema.missing"] = missing
    if missing:
        checks["ok"] = False
        return checks

    checks["rows"] = int(len(df))
    checks["keys.unique_special_id"] = int(df["special_id"].duplicated().sum()) == 0

    # Provenance: a row without a citation cannot be audited and is not usable.
    no_source = df["source_url"].isna() | (df["source_url"].astype(str).str.strip() == "")
    checks["provenance.source_url_present"] = int(no_source.sum()) == 0
    checks["provenance.rows_without_source"] = int(no_source.sum())
    no_retrieved = df["retrieved_on"].isna() | (df["retrieved_on"].astype(str).str.strip() == "")
    checks["provenance.retrieved_on_present"] = int(no_retrieved.sum()) == 0

    no_baseline_src = df["baseline_source"].isna() | (df["baseline_source"].astype(str).str.strip() == "")
    checks["provenance.baseline_source_present"] = int(no_baseline_src.sum()) == 0

    dates = pd.to_datetime(df["election_date"], errors="coerce")
    checks["dates.parse"] = int(dates.isna().sum()) == 0
    checks["dates.not_future"] = bool((dates.dropna() <= pd.Timestamp(date.today())).all())

    checks["office.known"] = bool(df["office"].str.strip().str.lower().isin(VALID_OFFICES).all())

    votes = df[["dem_votes", "rep_votes"]].fillna(0)
    checks["votes.nonnegative"] = bool((votes >= 0).all().all())
    total = votes.sum(axis=1) + df["other_votes"].fillna(0)
    checks["votes.plausible_total"] = bool((total >= MIN_PLAUSIBLE_VOTES).all())

    base = df["baseline_dem_share"]
    checks["baseline.in_unit_interval"] = bool(base.dropna().between(0, 1).all())
    checks["baseline.present"] = int(base.isna().sum()) == 0

    # Only boolean entries are gates. Keys like ``schema.missing`` and
    # ``provenance.rows_without_source`` are diagnostics carried alongside them, and
    # folding those into the verdict made an otherwise-clean table fail.
    checks["ok"] = all(v for v in checks.values() if isinstance(v, bool))
    return checks


def compute_overperformance(df: pd.DataFrame) -> pd.DataFrame:
    """Add two-party shares, margins, and Democratic overperformance per special.

    ``overperformance`` is the special's two-party Democratic *margin* minus the
    geography's presidential two-party Democratic margin. Positive means Democrats ran
    ahead of the seat's presidential baseline.
    """
    out = df.copy()
    dem = out["dem_votes"].fillna(0)
    rep = out["rep_votes"].fillna(0)
    out["total_votes"] = dem + rep + out["other_votes"].fillna(0)
    out["two_party_votes"] = dem + rep
    two = out["two_party_votes"].where(out["two_party_votes"] > 0)
    out["special_dem_share"] = dem / two
    # Margin on a two-party basis: +1 = unopposed D, -1 = unopposed R.
    out["special_margin"] = (dem - rep) / two
    out["baseline_margin"] = 2 * out["baseline_dem_share"] - 1
    out["overperformance"] = out["special_margin"] - out["baseline_margin"]
    return out.reindex(columns=OUTPUT_COLUMNS)


def national_environment_estimate(df: pd.DataFrame, *, weight: str = "equal", min_specials: int = 5) -> dict:
    """Summarise Democratic overperformance across specials into an environment signal.

    ``weight='equal'`` treats every special alike, which is what most public trackers
    report. ``weight='votes'`` weights by two-party turnout, which lets a single
    high-turnout congressional special dominate a dozen state-legislative ones — usually
    not what you want from a *national* indicator, so it is offered but not the default.

    The returned ``std_error`` is the standard error of the mean across specials. It
    describes sampling spread only. It does **not** capture the metric's real weaknesses:
    specials are a non-random set of seats, turnout composition differs from a general
    electorate, and overperformance is an association with the national environment, not
    a measurement of it.
    """
    d = df.dropna(subset=["overperformance"])
    n = len(d)
    if n < min_specials:
        return {
            "status": "insufficient_data",
            "n": int(n),
            "min_specials": min_specials,
            "reason": f"{n} specials is too few to average; need at least {min_specials}",
        }

    if weight == "votes":
        w = d["two_party_votes"].fillna(0)
        mean = float((d["overperformance"] * w).sum() / w.sum()) if w.sum() > 0 else float("nan")
    else:
        mean = float(d["overperformance"].mean())

    sd = float(d["overperformance"].std(ddof=1)) if n > 1 else float("nan")
    return {
        "status": "ok",
        "n": int(n),
        "weighting": weight,
        "mean_overperformance": mean,
        "median_overperformance": float(d["overperformance"].median()),
        "std_dev": sd,
        "std_error": (sd / (n**0.5)) if n > 1 else float("nan"),
        "by_office": d.groupby("office")["overperformance"].mean().round(4).to_dict(),
        "date_range": [str(d["election_date"].min()), str(d["election_date"].max())],
        "caveats": [
            "Specials are a non-random sample of seats; they occur where a vacancy happened.",
            "Special-election turnout composition differs from a general electorate.",
            "Overperformance is an association with the national environment, not a measure of it.",
            "Margin-based, so it controls for turnout level but not turnout composition.",
        ],
    }

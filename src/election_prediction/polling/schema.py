"""Canonical public poll-topline schema (P2-001).

The schema is deliberately poll-level and aggregate. It stores no respondent records,
contact fields, or inferred personal attributes. Each row is one race topline with the
field dates, sample, population, mode, sponsor, source URL, and optional externally
estimated pollster house effect needed for a reproducible average.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from ..geography import reference as geography_reference

POLL_COLUMNS = [
    "poll_id",
    "pollster",
    "sponsor",
    "sponsor_partisan",
    "internal",
    "office",
    "cycle",
    "geography_id",
    "state_po",
    "district_num",
    "field_start",
    "field_end",
    "sample_size",
    "population",
    "mode",
    "dem_pct",
    "rep_pct",
    "other_pct",
    "undecided_pct",
    "two_party_dem_share",
    "house_effect_dem",
    "source_url",
    "source_id",
    "snapshot_date",
]

REQUIRED_INPUT_COLUMNS = {
    "poll_id",
    "pollster",
    "office",
    "cycle",
    "geography_id",
    "state_po",
    "field_start",
    "field_end",
    "sample_size",
    "population",
    "mode",
    "dem_pct",
    "rep_pct",
    "source_url",
}

ALIASES = {
    "start_date": "field_start",
    "end_date": "field_end",
    "sample": "sample_size",
    "dem": "dem_pct",
    "rep": "rep_pct",
    "democratic_pct": "dem_pct",
    "republican_pct": "rep_pct",
    "partisan_sponsor": "sponsor_partisan",
    "is_internal": "internal",
}

POPULATION_ALIASES = {
    "LIKELY VOTERS": "LV",
    "LIKELY VOTER": "LV",
    "LV": "LV",
    "REGISTERED VOTERS": "RV",
    "REGISTERED VOTER": "RV",
    "RV": "RV",
    "ADULTS": "A",
    "ADULT": "A",
    "A": "A",
}


def _share(series: pd.Series) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    return values.where(values.abs() <= 1, values / 100)


def _boolean(series: pd.Series) -> pd.Series:
    truthy = {"1", "true", "t", "yes", "y"}
    return series.fillna(False).astype(str).str.strip().str.lower().isin(truthy)


def _string(series: pd.Series) -> pd.Series:
    """Trim text without converting missing values into the literal string ``nan``."""
    return series.astype("string").str.strip()


def standardize_polls(
    raw: pd.DataFrame,
    *,
    source_id: str,
    snapshot_date: str | date,
) -> pd.DataFrame:
    """Normalize a wide public-poll topline frame to ``POLL_COLUMNS``."""
    df = raw.copy()
    df.columns = [ALIASES.get(str(col).strip().lower(), str(col).strip().lower()) for col in df.columns]
    missing = sorted(REQUIRED_INPUT_COLUMNS - set(df.columns))
    if missing:
        raise ValueError(f"Poll input is missing required columns: {missing}")

    for column, default in {
        "sponsor": "",
        "sponsor_partisan": "NONE",
        "internal": False,
        "district_num": pd.NA,
        "other_pct": np.nan,
        "undecided_pct": np.nan,
        "house_effect_dem": 0.0,
    }.items():
        if column not in df:
            df[column] = default

    for column in ("dem_pct", "rep_pct", "other_pct", "undecided_pct", "house_effect_dem"):
        df[column] = _share(df[column])

    df["poll_id"] = _string(df["poll_id"])
    df["pollster"] = _string(df["pollster"])
    df["sponsor"] = _string(df["sponsor"]).fillna("")
    df["sponsor_partisan"] = (
        df["sponsor_partisan"].fillna("NONE").astype(str).str.strip().str.upper().replace("", "NONE")
    )
    df["internal"] = _boolean(df["internal"])
    df["office"] = _string(df["office"]).str.lower()
    df["cycle"] = pd.to_numeric(df["cycle"], errors="coerce").astype("Int64")
    df["geography_id"] = _string(df["geography_id"])
    df["state_po"] = _string(df["state_po"]).str.upper()
    df["district_num"] = pd.to_numeric(df["district_num"], errors="coerce").astype("Int64")
    df["field_start"] = pd.to_datetime(df["field_start"], errors="coerce").dt.normalize()
    df["field_end"] = pd.to_datetime(df["field_end"], errors="coerce").dt.normalize()
    df["sample_size"] = pd.to_numeric(df["sample_size"], errors="coerce").astype("Int64")
    population = _string(df["population"]).str.upper()
    df["population"] = population.map(POPULATION_ALIASES).fillna(population)
    df["mode"] = _string(df["mode"]).str.lower()
    df["source_url"] = _string(df["source_url"])
    df["source_id"] = source_id
    df["snapshot_date"] = pd.Timestamp(snapshot_date).date().isoformat()

    major_total = df["dem_pct"] + df["rep_pct"]
    df["two_party_dem_share"] = (df["dem_pct"] / major_total).where(major_total > 0)
    return (
        df[POLL_COLUMNS].sort_values(["cycle", "geography_id", "field_end", "poll_id"]).reset_index(drop=True)
    )


def validate_polls(polls: pd.DataFrame) -> dict[str, bool | int]:
    """Validate keys, dates, ranges, source lineage, and aggregate-only structure."""
    required_present = set(POLL_COLUMNS).issubset(polls.columns)
    known_states = {state.postal for state in geography_reference.STATES.values()}
    nonblank = ["poll_id", "pollster", "office", "geography_id", "population", "mode", "source_url"]
    checks: dict[str, bool | int] = {
        "required_columns": required_present,
        "poll_id_unique": bool(polls["poll_id"].is_unique) if "poll_id" in polls else False,
        "required_values_present": (
            bool(polls[nonblank].notna().all().all())
            and bool((polls[nonblank].astype(str).apply(lambda col: col.str.strip()) != "").all().all())
            if set(nonblank).issubset(polls.columns)
            else False
        ),
        "dates_valid": (
            bool(polls[["field_start", "field_end"]].notna().all().all())
            and bool((polls["field_start"] <= polls["field_end"]).all())
            if {"field_start", "field_end"}.issubset(polls.columns)
            else False
        ),
        "sample_size_positive": (bool((polls["sample_size"] > 0).all()) if "sample_size" in polls else False),
        "major_shares_valid": (
            bool(polls[["dem_pct", "rep_pct", "two_party_dem_share"]].notna().all().all())
            and bool(
                polls[["dem_pct", "rep_pct", "two_party_dem_share"]]
                .apply(lambda col: col.between(0, 1))
                .all()
                .all()
            )
            and bool(((polls["dem_pct"] + polls["rep_pct"]) > 0).all())
            if {"dem_pct", "rep_pct", "two_party_dem_share"}.issubset(polls.columns)
            else False
        ),
        "house_effect_valid": (
            bool(polls["house_effect_dem"].between(-0.20, 0.20).all())
            if "house_effect_dem" in polls
            else False
        ),
        "population_known": (
            bool(polls["population"].isin(POPULATION_ALIASES.values()).all())
            if "population" in polls
            else False
        ),
        "state_known": bool(polls["state_po"].isin(known_states).all()) if "state_po" in polls else False,
        "source_urls_present": (
            bool(polls["source_url"].str.match(r"^https?://", na=False).all())
            if "source_url" in polls
            else False
        ),
        "n_polls": int(len(polls)),
    }
    checks["ok"] = all(value for value in checks.values() if isinstance(value, bool))
    return checks


def build_synthetic_poll_fixture(
    fundamentals: pd.DataFrame,
    *,
    cycle: int,
    reference_date: str | date,
    polls_per_state: int = 3,
    seed: int = 23,
) -> pd.DataFrame:
    """Deterministic fictional poll toplines for offline end-to-end tests.

    ``fundamentals`` must contain ``state_po`` and ``pred_dem_share``. The generated
    values are explicitly synthetic and must never be presented as observed polls.
    """
    required = {"state_po", "pred_dem_share"}
    if not required.issubset(fundamentals.columns):
        raise ValueError(f"Synthetic polls require columns {sorted(required)}")
    as_of = pd.Timestamp(reference_date).date()
    rng = np.random.default_rng(seed)
    pollsters = ["Synthetic Research A", "Synthetic Research B", "Synthetic Research C"]
    modes = ["online", "phone", "mixed"]
    populations = ["LV", "RV", "LV"]
    rows = []
    for _, fundamental in fundamentals.sort_values("state_po").iterrows():
        state_po = str(fundamental["state_po"])
        prior = float(fundamental["pred_dem_share"])
        for index in range(polls_per_state):
            age = 4 + index * 9
            field_end = as_of - timedelta(days=age)
            field_start = field_end - timedelta(days=3 + index)
            two_party = float(np.clip(prior + rng.normal(0, 0.012), 0.30, 0.70))
            undecided = float(0.04 + 0.01 * index)
            decided = 1 - undecided
            rows.append(
                {
                    "poll_id": f"synthetic-{cycle}-{state_po}-{index + 1}",
                    "pollster": pollsters[index % len(pollsters)],
                    "sponsor": "Synthetic fixture",
                    "sponsor_partisan": "NONE",
                    "internal": False,
                    "office": "president",
                    "cycle": cycle,
                    "geography_id": f"state:{geography_reference.by_postal(state_po).fips}",
                    "state_po": state_po,
                    "district_num": pd.NA,
                    "field_start": field_start.isoformat(),
                    "field_end": field_end.isoformat(),
                    "sample_size": 600 + index * 250,
                    "population": populations[index % len(populations)],
                    "mode": modes[index % len(modes)],
                    "dem_pct": two_party * decided,
                    "rep_pct": (1 - two_party) * decided,
                    "other_pct": 0.0,
                    "undecided_pct": undecided,
                    "house_effect_dem": 0.0,
                    "source_url": "https://example.invalid/synthetic-poll-fixture",
                }
            )
    return pd.DataFrame(rows)


def read_poll_csv(path: str | Path) -> pd.DataFrame:
    """Read a UTF-8 public topline CSV without inferring personal-data semantics."""
    return pd.read_csv(path, low_memory=False)

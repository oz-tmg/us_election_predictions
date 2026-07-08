"""Canonical geography table (P0-002).

One conformed geography spine keyed on FIPS/GEOID so returns, demographics, and
boundaries join without name-matching. Prevents the FIPS/GEOID/district mismatch
that CLAUDE.md §3 and PROJECT_CONTEXT.md §13 call out as a foundational risk.

``geography_id`` follows the naming convention in docs/ingestion-playbook.md, e.g.
``state:51`` , ``state:51|county:059`` , ``state:51|district:cong_07``.
"""
from __future__ import annotations

import pandas as pd

from . import reference as ref

GEOG_LEVELS = ("nation", "state", "county", "cong_district")

# Canonical column contract for the geography spine.
GEOGRAPHY_COLUMNS = [
    "geography_id", "geog_level", "state_po", "state_fips", "state_name",
    "county_fips", "district_num", "geoid", "census_region", "census_division",
]


def geography_id(level: str, *, state_fips: str | None = None,
                 county_fips: str | None = None, district_num: str | int | None = None) -> str:
    """Build a stable, human-readable geography_id."""
    if level == "nation":
        return "nation:us"
    if state_fips is None:
        raise ValueError(f"state_fips required for level {level!r}")
    sid = f"state:{state_fips}"
    if level == "state":
        return sid
    if level == "county":
        if county_fips is None:
            raise ValueError("county_fips required for county level")
        return f"{sid}|county:{str(county_fips).zfill(3)}"
    if level == "cong_district":
        if district_num is None:
            raise ValueError("district_num required for cong_district level")
        return f"{sid}|district:cong_{str(district_num).zfill(2)}"
    raise ValueError(f"Unknown geog_level {level!r}")


def build_state_table() -> pd.DataFrame:
    """The 50 states + DC (+ territories present in reference data) as the base spine."""
    rows = []
    for s in ref.STATES.values():
        rows.append({
            "geography_id": geography_id("state", state_fips=s.fips),
            "geog_level": "state",
            "state_po": s.postal,
            "state_fips": s.fips,
            "state_name": s.name,
            "county_fips": None,
            "district_num": None,
            "geoid": s.fips,  # state GEOID == state FIPS
            "census_region": s.census_region,
            "census_division": s.census_division,
        })
    df = pd.DataFrame(rows, columns=GEOGRAPHY_COLUMNS)
    return df.sort_values("state_fips").reset_index(drop=True)


def counties_from_returns(returns: pd.DataFrame) -> pd.DataFrame:
    """Derive the county layer of the spine from observed county FIPS in returns.

    Until TIGER county boundaries are ingested (P0-007), the county spine is
    seeded from the geography actually present in the returns so joins are exact.
    Expects columns: state_fips, county_fips (may be absent -> empty frame).
    """
    if "county_fips" not in returns.columns:
        return pd.DataFrame(columns=GEOGRAPHY_COLUMNS)
    cols = returns[["state_fips", "county_fips"]].dropna().drop_duplicates()
    rows = []
    for _, r in cols.iterrows():
        sf = str(r["state_fips"]).zfill(2)
        cf = str(r["county_fips"]).zfill(3)
        s = ref.by_fips(sf)
        rows.append({
            "geography_id": geography_id("county", state_fips=sf, county_fips=cf),
            "geog_level": "county",
            "state_po": s.postal,
            "state_fips": sf,
            "state_name": s.name,
            "county_fips": cf,
            "district_num": None,
            "geoid": f"{sf}{cf}",  # 5-digit county GEOID
            "census_region": s.census_region,
            "census_division": s.census_division,
        })
    return pd.DataFrame(rows, columns=GEOGRAPHY_COLUMNS)


def cong_districts_from_returns(returns: pd.DataFrame) -> pd.DataFrame:
    """Derive the congressional-district layer from observed districts in House returns.

    Expects columns: state_fips, district_num. At-large districts are stored as 0
    (Census convention: at-large CDs use 00 in GEOID).
    """
    if "district_num" not in returns.columns:
        return pd.DataFrame(columns=GEOGRAPHY_COLUMNS)
    cols = returns[["state_fips", "district_num"]].dropna().drop_duplicates()
    rows = []
    for _, r in cols.iterrows():
        sf = str(r["state_fips"]).zfill(2)
        dnum = int(r["district_num"])
        s = ref.by_fips(sf)
        rows.append({
            "geography_id": geography_id("cong_district", state_fips=sf, district_num=dnum),
            "geog_level": "cong_district",
            "state_po": s.postal,
            "state_fips": sf,
            "state_name": s.name,
            "county_fips": None,
            "district_num": dnum,
            "geoid": f"{sf}{str(dnum).zfill(2)}",  # 4-digit CD GEOID
            "census_region": s.census_region,
            "census_division": s.census_division,
        })
    return pd.DataFrame(rows, columns=GEOGRAPHY_COLUMNS)


def build_geography_table(returns: pd.DataFrame | None = None) -> pd.DataFrame:
    """Assemble the canonical geography spine (nation + states + observed county/CD).

    ``returns`` (silver election returns) is optional; when provided, county and
    congressional-district rows are seeded from the geography present in the data.
    """
    nation = pd.DataFrame([{
        "geography_id": "nation:us", "geog_level": "nation", "state_po": None,
        "state_fips": None, "state_name": "United States", "county_fips": None,
        "district_num": None, "geoid": "US", "census_region": None,
        "census_division": None,
    }], columns=GEOGRAPHY_COLUMNS)

    parts = [nation, build_state_table()]
    if returns is not None:
        parts.append(counties_from_returns(returns))
        parts.append(cong_districts_from_returns(returns))
    out = pd.concat(parts, ignore_index=True)
    out = out.drop_duplicates("geography_id").reset_index(drop=True)
    return out

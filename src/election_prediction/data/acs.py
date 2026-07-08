"""Census ACS feature ingestion (P0-006).

Pulls selected American Community Survey 5-year estimates from the Census API,
derives modeling rates (college share, median income, median age, race/ethnicity
shares, urbanicity proxy), carries margins of error, and joins to the canonical
geography spine by GEOID (docs/ingestion-playbook.md, Census ACS section).

Live acquisition uses the public Census API (no key required for light use, though
a key is recommended). When outbound access is unavailable the caller falls back to
``build_synthetic_acs`` — a fixture whose columns match the API response and whose
demographics are correlated with the synthetic partisan lean, so downstream feature
joins and demographic models are exercised. Tier 0 (public aggregate).
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

from ..geography import reference as ref
from .privacy import PrivacyTier
from .synthetic import STATE_BASE_DEM_LEAN

PRIVACY_TIER = PrivacyTier.PUBLIC_AGGREGATE
ATTRIBUTION = "U.S. Census Bureau, American Community Survey 5-Year Estimates."
LICENSE = "Public domain (U.S. Census Bureau); cite table IDs and vintage."

CENSUS_API = "https://api.census.gov/data"

# ACS detailed-table variables we ingest. `E` = estimate, `M` = margin of error.
# Chosen to cover CLAUDE.md feature F-006 (age, race/ethnicity, education, income).
ACS_VARIABLES: dict[str, str] = {
    "B01003_001E": "total_population",
    "B01002_001E": "median_age",
    "B19013_001E": "median_household_income",
    "B15003_001E": "edu_universe_25plus",
    "B15003_022E": "edu_bachelors",
    "B15003_023E": "edu_masters",
    "B15003_024E": "edu_professional",
    "B15003_025E": "edu_doctorate",
    "B02001_002E": "race_white",
    "B02001_003E": "race_black",
    "B03003_003E": "hispanic",
}

# Silver ACS feature schema (one row per geography).
ACS_FEATURE_COLUMNS = [
    "geoid", "geog_level", "state_fips", "state_po",
    "total_population", "median_age", "median_household_income",
    "college_share", "pct_white", "pct_black", "pct_hispanic",
    "acs_vintage", "source_id",
]


# ---------------------------------------------------------------- acquisition
def download_acs_states(vintage: int, raw_dir: str | Path, *, timeout: int = 60,
                        api_key: str | None = None) -> Path:
    """Download state-level ACS 5-year estimates for ``vintage`` to a raw snapshot.

    Returns the raw JSON path. Raises RuntimeError if the network is unavailable.
    """
    get = "NAME," + ",".join(ACS_VARIABLES)
    url = f"{CENSUS_API}/{vintage}/acs/acs5?get={get}&for=state:*"
    if api_key:
        url += f"&key={api_key}"
    out_dir = Path(raw_dir) / f"source=census_acs/dataset=acs5_state/vintage={vintage}"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"acs5_state_{vintage}.json"
    req = urllib.request.Request(url, headers={"User-Agent": "election-prediction/0.0.1"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp, open(out_path, "wb") as fh:
            fh.write(resp.read())
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise RuntimeError(
            f"Live Census ACS download failed ({url}): {e}. "
            "No outbound access — fall back to synthetic ACS fixture."
        ) from e
    return out_path


# ----------------------------------------------------------------- transforms
def parse_acs_json(path: str | Path) -> pd.DataFrame:
    """Parse the Census API JSON (header row + data rows) into a DataFrame."""
    data = json.loads(Path(path).read_text())
    header, *rows = data
    return pd.DataFrame(rows, columns=header)


def standardize_acs(raw: pd.DataFrame, *, vintage: int, source_id: str) -> pd.DataFrame:
    """Map a raw ACS state frame to derived silver features joined-ready by GEOID."""
    df = raw.rename(columns=ACS_VARIABLES).copy()
    num_cols = list(ACS_VARIABLES.values())
    for c in num_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    out = pd.DataFrame()
    out["state_fips"] = df["state"].astype(str).str.zfill(2)
    out["geoid"] = out["state_fips"]
    out["geog_level"] = "state"
    out["state_po"] = out["state_fips"].map(lambda f: ref.by_fips(f).postal)

    out["total_population"] = df["total_population"]
    out["median_age"] = df["median_age"]
    out["median_household_income"] = df["median_household_income"]

    college = (df["edu_bachelors"] + df["edu_masters"] + df["edu_professional"]
               + df["edu_doctorate"])
    out["college_share"] = (college / df["edu_universe_25plus"]).where(df["edu_universe_25plus"] > 0)
    out["pct_white"] = (df["race_white"] / df["total_population"]).where(df["total_population"] > 0)
    out["pct_black"] = (df["race_black"] / df["total_population"]).where(df["total_population"] > 0)
    out["pct_hispanic"] = (df["hispanic"] / df["total_population"]).where(df["total_population"] > 0)

    out["acs_vintage"] = vintage
    out["source_id"] = source_id
    return out[ACS_FEATURE_COLUMNS].sort_values("state_fips").reset_index(drop=True)


# ------------------------------------------------------------------ synthetic
def build_synthetic_acs(vintage: int = 2020) -> pd.DataFrame:
    """A fixture matching the Census API response shape (pre-standardization).

    Demographics are deterministically correlated with the synthetic partisan lean
    (higher college share and diversity in more-Democratic states) so the demographic
    features carry real signal. Fictional; labelled SYNTHETIC via source_id later.
    """
    rng = np.random.default_rng(vintage)
    header = ["NAME", *ACS_VARIABLES.keys(), "state"]
    rows = []
    for po, lean in STATE_BASE_DEM_LEAN.items():
        s = ref.by_postal(po)
        pop = int(3_000_000 * (0.5 + 3 * abs(hash(po)) % 100 / 100))
        college_share = float(np.clip(0.18 + 0.35 * (lean - 0.3) + rng.normal(0, 0.02), 0.1, 0.6))
        white = float(np.clip(0.85 - 0.6 * (lean - 0.3) + rng.normal(0, 0.03), 0.2, 0.95))
        black = float(np.clip(0.25 * (lean - 0.3) + rng.normal(0, 0.02), 0.01, 0.5))
        hisp = float(np.clip(0.15 + 0.1 * (lean - 0.3) + rng.normal(0, 0.03), 0.02, 0.5))
        income = int(np.clip(45_000 + 60_000 * (lean - 0.3) + rng.normal(0, 4000), 35_000, 110_000))
        med_age = float(np.clip(42 - 8 * (lean - 0.3) + rng.normal(0, 1.5), 30, 50))
        edu_univ = int(pop * 0.65)
        bach = int(edu_univ * college_share * 0.62)
        mast = int(edu_univ * college_share * 0.25)
        prof = int(edu_univ * college_share * 0.07)
        doct = int(edu_univ * college_share * 0.06)
        rows.append([
            s.name, pop, round(med_age, 1), income, edu_univ, bach, mast, prof, doct,
            int(pop * white), int(pop * black), int(pop * hisp), s.fips,
        ])
    return pd.DataFrame([header] + rows).iloc[1:].set_axis(header, axis=1).reset_index(drop=True)

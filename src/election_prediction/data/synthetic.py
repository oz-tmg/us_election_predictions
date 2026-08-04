"""Synthetic MEDSL-schema fixtures with realistic partisan structure.

Generates small, deterministic CSVs that match the *real* MEDSL raw column layout
for president / senate / house, so the ingestion AND modeling stacks can be
exercised end-to-end and reproducibly when live download is unavailable (a
locked-down sandbox).

The data are fictional but *structured*: each state has a latent Democratic
two-party lean, each cycle a national environment shift, plus incumbency effects
and noise. That structure gives the P1 baselines, correlated simulation, and
calibration evaluation genuine signal to learn — the same code runs unchanged on
the real MEDSL snapshots. Values are NOT real returns and are labelled SYNTHETIC.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from ..geography import reference as ref

_RNG = np.random.default_rng(20260708)

# Latent Democratic two-party lean per state (approx. modern baseline; used only as
# a generative parameter for fictional data). DC intentionally very Dem.
STATE_BASE_DEM_LEAN: dict[str, float] = {
    "AL": .37, "AK": .44, "AZ": .50, "AR": .35, "CA": .65, "CO": .57, "CT": .60,
    "DE": .59, "DC": .93, "FL": .48, "GA": .50, "HI": .65, "ID": .34, "IL": .58,
    "IN": .42, "IA": .45, "KS": .42, "KY": .37, "LA": .40, "ME": .55, "MD": .66,
    "MA": .67, "MI": .51, "MN": .53, "MS": .41, "MO": .43, "MT": .41, "NE": .40,
    "NV": .51, "NH": .53, "NJ": .58, "NM": .55, "NY": .62, "NC": .49, "ND": .33,
    "OH": .46, "OK": .33, "OR": .58, "PA": .50, "RI": .60, "SC": .44, "SD": .36,
    "TN": .38, "TX": .47, "UT": .39, "VT": .68, "VA": .55, "WA": .60, "WV": .30,
    "WI": .50, "WY": .27,
}

# National environment: Democratic share of the two-party presidential vote by cycle.
NATIONAL_ENV = {2008: .540, 2012: .520, 2016: .512, 2020: .522, 2024: .495}
PRES_CYCLES = [2008, 2012, 2016, 2020, 2024]
HOUSE_CYCLES = [2016, 2018, 2020, 2022]
SENATE_CYCLES = [2012, 2016, 2018, 2020]

# Approx apportionment (fictional-friendly): districts per state for the House fixture.
_DISTRICTS = {
    "CA": 12, "TX": 10, "FL": 8, "NY": 8, "PA": 6, "IL": 6, "OH": 6, "GA": 5,
    "NC": 5, "MI": 5, "NJ": 5, "VA": 4, "WA": 4, "AZ": 4, "MA": 4, "TN": 4,
    "IN": 4, "MO": 4, "MD": 4, "WI": 4, "CO": 4, "MN": 4, "SC": 3, "AL": 3,
    "LA": 3, "KY": 3, "OR": 3, "OK": 3, "CT": 3, "IA": 2, "MS": 2, "AR": 2,
    "KS": 2, "NV": 3, "UT": 2, "NM": 2, "NE": 2, "WV": 2, "ID": 2, "HI": 2,
    "ME": 2, "NH": 2, "RI": 2, "MT": 1, "DE": 1, "SD": 1, "ND": 1, "AK": 1,
    "VT": 1, "WY": 1,
}

# Named after the real published files so a synthetic snapshot is obviously the
# stand-in for a specific source (the SYNTHETIC_ prefix is added on write).
_FILENAMES = {
    "president": "1976-2024-president.csv",
    "us_senate": "1976-2024-senate-state.csv",
    "us_house": "1976-2024-house.tab",
}


def _states() -> list[str]:
    return list(STATE_BASE_DEM_LEAN.keys())


def _split_votes(total: int, dem_share: float, other_share: float = 0.02) -> tuple[int, int, int]:
    other = int(total * other_share)
    remaining = total - other
    dem = int(round(remaining * dem_share))
    rep = remaining - dem
    return dem, rep, other


def _state_size(po: str) -> int:
    # deterministic pseudo electorate size, larger for big states
    base = {"CA": 14e6, "TX": 11e6, "FL": 11e6, "NY": 8e6, "PA": 7e6}.get(po, 2.5e6)
    return int(base * (1 + _RNG.normal(0, 0.05)))


def _president_rows() -> list[dict]:
    rows = []
    for year in PRES_CYCLES:
        shift = NATIONAL_ENV[year] - 0.515
        for po in _states():
            s = ref.by_postal(po)
            lean = float(np.clip(STATE_BASE_DEM_LEAN[po] + shift + _RNG.normal(0, 0.02), 0.03, 0.97))
            total = _state_size(po)
            dem, rep, oth = _split_votes(total, lean)
            for cand, pd_, ps_, v in [
                ("DEMOCRAT CANDIDATE", "DEMOCRAT", "DEMOCRAT", dem),
                ("REPUBLICAN CANDIDATE", "REPUBLICAN", "REPUBLICAN", rep),
                ("OTHER", "LIBERTARIAN", "OTHER", oth),
            ]:
                rows.append(dict(
                    year=year, state=s.name.upper(), state_po=po, state_fips=s.fips,
                    office="US PRESIDENT", candidate=cand, party_detailed=pd_,
                    party_simplified=ps_, writein="FALSE",
                    candidatevotes=v, totalvotes=dem + rep + oth,
                ))
    return rows


def _senate_rows() -> list[dict]:
    rows = []
    states = _states()
    for year in SENATE_CYCLES:
        for i, po in enumerate(states):
            if (i % 3) != (SENATE_CYCLES.index(year) % 3):
                continue  # staggered classes
            s = ref.by_postal(po)
            shift = (NATIONAL_ENV.get(year, 0.51) - 0.515)
            incumbent_dem = STATE_BASE_DEM_LEAN[po] >= 0.5
            inc_boost = 0.03 if incumbent_dem else -0.03
            lean = float(np.clip(STATE_BASE_DEM_LEAN[po] + shift + inc_boost + _RNG.normal(0, 0.03),
                                 0.03, 0.97))
            total = int(_state_size(po) * 0.9)
            dem, rep, oth = _split_votes(total, lean, other_share=0.015)
            for cand, pd_, ps_, v in [
                ("DEMOCRAT CANDIDATE", "DEMOCRAT", "DEMOCRAT", dem),
                ("REPUBLICAN CANDIDATE", "REPUBLICAN", "REPUBLICAN", rep),
                ("OTHER", "LIBERTARIAN", "OTHER", oth),
            ]:
                rows.append(dict(
                    year=year, state=s.name.upper(), state_po=po, state_fips=s.fips,
                    office="US SENATE", candidate=cand, party_detailed=pd_,
                    party_simplified=ps_, writein="FALSE",
                    candidatevotes=v, totalvotes=dem + rep + oth,
                    stage="GEN", special="FALSE", unofficial="FALSE",
                ))
    return rows


def _house_rows() -> list[dict]:
    rows = []
    for year in HOUSE_CYCLES:
        midterm = year % 4 != 0
        # presidential penalty: party holding WH (Dem 2016/2020 era assumption) loses ground in midterms
        penalty = -0.02 if midterm else 0.0
        for po in _states():
            if po not in _DISTRICTS:  # e.g. DC has no voting House seat
                continue
            s = ref.by_postal(po)
            for d in range(1, _DISTRICTS[po] + 1):
                offset = _RNG.normal(0, 0.08)  # district heterogeneity within state
                lean = float(np.clip(STATE_BASE_DEM_LEAN[po] + penalty + offset
                                     + _RNG.normal(0, 0.02), 0.03, 0.97))
                total = int(250_000 * (1 + _RNG.normal(0, 0.1)))
                uncontested = (d == 1 and STATE_BASE_DEM_LEAN[po] > 0.62)  # a few safe seats
                if uncontested:
                    dem, rep, oth = total, 0, 0
                else:
                    dem, rep, oth = _split_votes(total, lean, other_share=0.0)
                cands = [("DEMOCRAT CANDIDATE", "DEMOCRAT", dem)]
                if not uncontested:
                    cands.append(("REPUBLICAN CANDIDATE", "REPUBLICAN", rep))
                for cand, party, v in cands:
                    rows.append(dict(
                        year=year, state=s.name.upper(), state_po=po, state_fips=s.fips,
                        office="US HOUSE", district=d, candidate=cand, party=party,
                        writein="FALSE", candidatevotes=v, totalvotes=dem + rep + oth,
                        stage="GEN", special="FALSE", unofficial="FALSE", runoff="FALSE",
                    ))
    return rows


_BUILDERS = {
    "president": _president_rows,
    "us_senate": _senate_rows,
    "us_house": _house_rows,
}


def build_fixture(office: str) -> pd.DataFrame:
    return pd.DataFrame(_BUILDERS[office]())


def write_fixture(office: str, out_dir: str | Path) -> Path:
    """Write a single office's synthetic fixture and return its path.

    The fixture is written with the *same delimiter* as the real published file for
    that office (House ships tab-separated), so the parser is exercised exactly as it
    will be against the live source rather than against a friendlier format.
    """
    from .medsl import MEDSL_SOURCES

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    p = out / f"SYNTHETIC_{_FILENAMES[office]}"
    sep = MEDSL_SOURCES[office].sep if office in MEDSL_SOURCES else ","
    build_fixture(office).to_csv(p, index=False, sep=sep)
    return p


def write_fixtures(out_dir: str | Path) -> dict[str, Path]:
    """Write all three synthetic CSVs and return {office: path}."""
    return {office: write_fixture(office, out_dir) for office in _FILENAMES}

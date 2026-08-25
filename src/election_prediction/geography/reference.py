"""State reference data: postal code <-> FIPS <-> Census region/division.

Small, static, authoritative lookup used to conform geography keys across every
source (CLAUDE.md §3: standardize on FIPS/GEOID keys). Values follow Census /
FIPS 5-2 and the Census statistical regions. 50 states + DC (+ common territories).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StateRef:
    postal: str
    fips: str  # 2-digit state FIPS as string (preserves leading zero)
    name: str
    census_region: str  # Northeast | Midwest | South | West | Territory
    census_division: str


# name, postal, fips, region, division
_ROWS = [
    ("Alabama", "AL", "01", "South", "East South Central"),
    ("Alaska", "AK", "02", "West", "Pacific"),
    ("Arizona", "AZ", "04", "West", "Mountain"),
    ("Arkansas", "AR", "05", "South", "West South Central"),
    ("California", "CA", "06", "West", "Pacific"),
    ("Colorado", "CO", "08", "West", "Mountain"),
    ("Connecticut", "CT", "09", "Northeast", "New England"),
    ("Delaware", "DE", "10", "South", "South Atlantic"),
    ("District of Columbia", "DC", "11", "South", "South Atlantic"),
    ("Florida", "FL", "12", "South", "South Atlantic"),
    ("Georgia", "GA", "13", "South", "South Atlantic"),
    ("Hawaii", "HI", "15", "West", "Pacific"),
    ("Idaho", "ID", "16", "West", "Mountain"),
    ("Illinois", "IL", "17", "Midwest", "East North Central"),
    ("Indiana", "IN", "18", "Midwest", "East North Central"),
    ("Iowa", "IA", "19", "Midwest", "West North Central"),
    ("Kansas", "KS", "20", "Midwest", "West North Central"),
    ("Kentucky", "KY", "21", "South", "East South Central"),
    ("Louisiana", "LA", "22", "South", "West South Central"),
    ("Maine", "ME", "23", "Northeast", "New England"),
    ("Maryland", "MD", "24", "South", "South Atlantic"),
    ("Massachusetts", "MA", "25", "Northeast", "New England"),
    ("Michigan", "MI", "26", "Midwest", "East North Central"),
    ("Minnesota", "MN", "27", "Midwest", "West North Central"),
    ("Mississippi", "MS", "28", "South", "East South Central"),
    ("Missouri", "MO", "29", "Midwest", "West North Central"),
    ("Montana", "MT", "30", "West", "Mountain"),
    ("Nebraska", "NE", "31", "Midwest", "West North Central"),
    ("Nevada", "NV", "32", "West", "Mountain"),
    ("New Hampshire", "NH", "33", "Northeast", "New England"),
    ("New Jersey", "NJ", "34", "Northeast", "Middle Atlantic"),
    ("New Mexico", "NM", "35", "West", "Mountain"),
    ("New York", "NY", "36", "Northeast", "Middle Atlantic"),
    ("North Carolina", "NC", "37", "South", "South Atlantic"),
    ("North Dakota", "ND", "38", "Midwest", "West North Central"),
    ("Ohio", "OH", "39", "Midwest", "East North Central"),
    ("Oklahoma", "OK", "40", "South", "West South Central"),
    ("Oregon", "OR", "41", "West", "Pacific"),
    ("Pennsylvania", "PA", "42", "Northeast", "Middle Atlantic"),
    ("Rhode Island", "RI", "44", "Northeast", "New England"),
    ("South Carolina", "SC", "45", "South", "South Atlantic"),
    ("South Dakota", "SD", "46", "Midwest", "West North Central"),
    ("Tennessee", "TN", "47", "South", "East South Central"),
    ("Texas", "TX", "48", "South", "West South Central"),
    ("Utah", "UT", "49", "West", "Mountain"),
    ("Vermont", "VT", "50", "Northeast", "New England"),
    ("Virginia", "VA", "51", "South", "South Atlantic"),
    ("Washington", "WA", "53", "West", "Pacific"),
    ("West Virginia", "WV", "54", "South", "South Atlantic"),
    ("Wisconsin", "WI", "55", "Midwest", "East North Central"),
    ("Wyoming", "WY", "56", "West", "Mountain"),
    # Common territories (Tier 0 geography; coverage varies by source)
    ("Puerto Rico", "PR", "72", "Territory", "Territory"),
]

STATES: dict[str, StateRef] = {
    postal: StateRef(postal=postal, fips=fips, name=name, census_region=region, census_division=division)
    for (name, postal, fips, region, division) in _ROWS
}

_BY_FIPS: dict[str, StateRef] = {s.fips: s for s in STATES.values()}
_BY_NAME: dict[str, StateRef] = {s.name.upper(): s for s in STATES.values()}


def by_postal(postal: str) -> StateRef:
    return STATES[postal.strip().upper()]


def by_fips(fips: str | int) -> StateRef:
    key = str(fips).zfill(2)
    return _BY_FIPS[key]


def normalize_state(value: str) -> StateRef:
    """Resolve a state given a postal code, 2-digit FIPS, or full name."""
    v = str(value).strip()
    if v.upper() in STATES:
        return STATES[v.upper()]
    if v.isdigit():
        return by_fips(v)
    if v.upper() in _BY_NAME:
        return _BY_NAME[v.upper()]
    raise KeyError(f"Unrecognized state identifier: {value!r}")

"""Regional reversion: part of a region's *excess* swing between two elections reverses.

Used for the South Texas scenario (2026-10-29). Between 2020 and 2024 the Texas border
counties moved toward the Republican presidential candidate far more than the state did.
The 2026 House priors for Texas rest on 2024 presidential votes, so they carry that
region-specific move in full; the national environment then shifts every seat uniformly.
The scenario asks what happens if a stated fraction of the region's *excess* swing (its
swing minus the statewide swing) reverses, weighted by how much of each seat's 2024 vote
the region cast.

Everything here is measured from registered data except the reversion fraction, which is
the scenario's one assumption and is recorded with it. Results are county aggregates:
nothing here says how any group of voters moved (PROJECT_CONTEXT.md §16: ecological fallacy).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass

import pandas as pd

# Rio Grande Valley, Laredo and the Maverick/Zavala/Dimmit border counties.
SOUTH_TEXAS_BORDER_FIPS: dict[str, str] = {
    "48061": "Cameron",
    "48127": "Dimmit",
    "48215": "Hidalgo",
    "48247": "Jim Hogg",
    "48323": "Maverick",
    "48427": "Starr",
    "48479": "Webb",
    "48489": "Willacy",
    "48505": "Zapata",
    "48507": "Zavala",
}


@dataclass(frozen=True)
class RegionalSwing:
    region_from: float
    region_to: float
    state_from: float
    state_to: float
    from_cycle: int
    to_cycle: int

    @property
    def region_swing(self) -> float:
        return self.region_to - self.region_from

    @property
    def state_swing(self) -> float:
        return self.state_to - self.state_from

    @property
    def excess_swing(self) -> float:
        """Region swing beyond the statewide swing, in two-party Democratic share."""
        return self.region_swing - self.state_swing

    def to_dict(self) -> dict:
        return {
            **asdict(self),
            "region_swing": self.region_swing,
            "state_swing": self.state_swing,
            "excess_swing": self.excess_swing,
        }


def _two_party(df: pd.DataFrame) -> float:
    return float(df["dem_votes"].sum() / (df["dem_votes"].sum() + df["rep_votes"].sum()))


def measure_swing(
    county_votes: pd.DataFrame, region_fips: Iterable[str], *, from_cycle: int, to_cycle: int
) -> RegionalSwing:
    """``county_votes``: one row per (cycle, county_fips) with ``dem_votes``/``rep_votes``."""
    region = set(region_fips)
    out = {}
    for label, cycle in (("from", from_cycle), ("to", to_cycle)):
        year = county_votes[county_votes["cycle"] == cycle]
        if year.empty:
            raise ValueError(f"no county votes for {cycle}")
        in_region = year[year["county_fips"].isin(region)]
        missing = region - set(in_region["county_fips"])
        if missing:
            raise ValueError(f"{cycle}: region counties missing from county votes: {sorted(missing)}")
        out[f"region_{label}"] = _two_party(in_region)
        out[f"state_{label}"] = _two_party(year)
    return RegionalSwing(from_cycle=from_cycle, to_cycle=to_cycle, **out)


def district_region_share(at_block: pd.DataFrame, region_fips: Iterable[str]) -> pd.DataFrame:
    """Share of each new district's two-party votes cast in the region.

    ``at_block`` is the block-level vote table a plan transfer rests on (``block_id``
    GEOID, ``new_district``, ``dem_votes``, ``rep_votes``), so the weights use exactly the
    allocation behind the transferred prior.
    """
    region = set(region_fips)
    b = at_block.dropna(subset=["new_district"]).copy()
    b["county_fips"] = b["block_id"].astype(str).str[:5]
    b["two_party"] = b["dem_votes"] + b["rep_votes"]
    b["in_region"] = b["county_fips"].isin(region)
    g = b.groupby("new_district")
    out = pd.DataFrame(
        {
            "two_party_votes": g["two_party"].sum(),
            "region_votes": g.apply(lambda x: x.loc[x["in_region"], "two_party"].sum(), include_groups=False),
            "dem_share": g["dem_votes"].sum() / g["two_party"].sum(),
        }
    ).reset_index()
    out["region_share"] = out["region_votes"] / out["two_party_votes"]
    out["new_district"] = out["new_district"].astype(int)
    return out


def statewide_region_share(at_block: pd.DataFrame, region_fips: Iterable[str]) -> float:
    region = set(region_fips)
    two_party = at_block["dem_votes"] + at_block["rep_votes"]
    in_region = at_block["block_id"].astype(str).str[:5].isin(region)
    return float(two_party[in_region].sum() / two_party.sum())


def reversion_adjustment(
    *,
    state_po: str,
    district_shares: pd.DataFrame,
    statewide_share: float,
    excess_swing: float,
    fraction: float,
) -> Callable[[pd.DataFrame, str], pd.DataFrame]:
    """A ``seat_adjustment`` for ``project_2026.main``.

    Each House seat in ``state_po`` moves by ``-fraction * excess_swing * region_share``;
    a statewide Senate contest moves by the same with the state's region share. Seats in
    other states are returned unchanged. Shares stay inside [0, 1].
    """
    if not 0.0 <= fraction <= 1.0:
        raise ValueError("reversion fraction must be in [0, 1]")
    per_district = district_shares.set_index("new_district")["region_share"]

    def adjust(proj: pd.DataFrame, office: str) -> pd.DataFrame:
        out = proj.copy()
        in_state = out["state_po"] == state_po
        if office == "us_house":
            weight = out.loc[in_state, "district_num"].astype(int).map(per_district)
            if weight.isna().any():
                raise ValueError(
                    f"{state_po} House seats without a region share: {weight[weight.isna()].index}"
                )
        else:
            weight = pd.Series(statewide_share, index=out.index[in_state])
        out.loc[in_state, "mean_dem_share"] = (
            out.loc[in_state, "mean_dem_share"] - fraction * excess_swing * weight
        ).clip(0.0, 1.0)
        return out

    return adjust

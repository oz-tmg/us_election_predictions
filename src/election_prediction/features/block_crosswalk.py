"""Census-block crosswalks for old-to-new vote transfer (RD-003, collection step).

``features/plan_transfer`` takes three conformed block-level tables and will not invent
them. This module builds them from registered public-domain sources, and it exists because
the obvious route — digitise precinct boundaries, geocode them against blocks — is not
needed. Census already publishes the precinct-to-block link:

    BlockAssign_ST<ff>_<XX>_VTD.txt   block -> voting district (precinct)
    BlockAssign_ST<ff>_<XX>_CD.txt    block -> congressional district, as apportioned
    tl_<yyyy>_<ff>_tabblock20         block polygons, interior points, POP20
    tl_<yyyy>_<ff>_cd118              the 2022-round congressional districts

So the chain runs **precinct → block → new district** on published tables and one
point-in-polygon join, with no digitising and no commercial boundary file. That matters
beyond convenience: a Block Assignment File is an *authoritative* assignment, not an
estimate, so the only modelled step left is dividing a split precinct's votes.

**Census publishes no Block Assignment File for the 2022 round.** ``baf2020/`` carries the
116th Congress (2010-era lines on 2020 blocks); there is no ``cd118`` BAF. The 2022-round
assignment is therefore derived here, by locating each block's Census-published interior
point inside a TIGER congressional-district polygon. An interior point is guaranteed to lie
within its block, and blocks nest inside districts by construction in a plan drawn on 2020
blocks, so the join is exact wherever the point lands — the residual is blocks whose point
falls outside every polygon (coastal and water blocks), which are counted and reported
rather than assigned to a neighbour.

Attribution, required on any published output: "U.S. Census Bureau Block Assignment Files."
and "U.S. Census Bureau, TIGER/Line Shapefiles."
"""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

import pandas as pd

#: Census writes these files with either ``|`` (2020 vintage) or ``,`` (2010 vintage).
_BAF_SEPARATORS = ("|", ",")


def _read_baf(zip_path: Path, suffix: str) -> pd.DataFrame:
    """One member of a Block Assignment File package, whatever its delimiter."""
    with zipfile.ZipFile(zip_path) as zf:
        names = [n for n in zf.namelist() if n.upper().endswith(f"_{suffix.upper()}.TXT")]
        if not names:
            raise FileNotFoundError(f"{zip_path.name} has no _{suffix}.txt member")
        raw = zf.read(names[0])
    for sep in _BAF_SEPARATORS:
        df = pd.read_csv(io.BytesIO(raw), sep=sep, dtype=str)
        if len(df.columns) > 1:
            return df
    raise ValueError(f"{zip_path.name}:{names[0]} parsed to a single column")


def _vtd_code(county_fp: str, district: str) -> str | None:
    """The precinct identifier inside a Census VTD code, normalised to a string.

    The ``DISTRICT`` field is not one format, in two separate ways.

    **It is not always a number.** North Carolina's VTD codes are alphanumeric -- ``00012W``,
    ``00000C``, ``00000H`` -- and parsing them as integers collapsed ``00012W`` and
    ``000012`` onto one value while discarding the letter. Only 1,126 of North Carolina's
    3,065 precincts matched and 55% of its votes went unplaced, which read as a failure of
    the transfer method and was a failure to parse an identifier.

    **Some counties embed their own FIPS.** Accomack County, Virginia writes precinct 101 as
    ``000101``; Alleghany writes it as ``005101``. Reading the field whole matches the first
    and misses the second, which dropped twelve Alleghany precincts.

    So the code is normalised as a *string*: strip an embedded county prefix, strip leading
    zeros, upper-case. ``000101`` and ``005101`` both become ``101``; ``00012W`` becomes
    ``12W`` and stays distinct from ``000012``'s ``12``.
    """
    if not isinstance(district, str) or not district.strip():
        return None
    code = district.strip().upper()
    if county_fp and code.startswith(county_fp) and len(code) > len(county_fp):
        code = code[len(county_fp) :]
    code = code.lstrip("0")
    return code or "0"


def normalise_precinct_code(value: object) -> str | None:
    """Normalise a state's own precinct identifier onto the same footing as a VTD code.

    The returns side needs identical treatment to the crosswalk side or the join is a coin
    flip: North Carolina writes ``0001`` where Census writes ``000001``, and Virginia writes
    ``101 - CHINCOTEAGUE`` where Census writes ``000101``.
    """
    if value is None:
        return None
    text = str(value).strip().upper()
    if not text:
        return None
    # A state may append a name after the code ("101 - CHINCOTEAGUE"); take the leading token.
    head = re.split(r"[\s\-_]", text, maxsplit=1)[0]
    candidate = head if re.fullmatch(r"[0-9A-Z]+", head or "") else text
    candidate = candidate.lstrip("0")
    return candidate or "0"


def block_to_vtd(baf_zip: Path, state_fips: str) -> pd.DataFrame:
    """``block_id, county_fips, vtd_code, vtd_number`` from a BAF package.

    ``vtd_key`` is the normalised string a state's own returns use to name the precinct,
    which is what makes the join to election results possible without a name match. Use
    ``normalise_precinct_code`` on the returns side so both sides normalise identically.
    """
    df = _read_baf(baf_zip, "VTD")
    cols = {c.upper(): c for c in df.columns}
    out = pd.DataFrame(
        {
            "block_id": df[cols["BLOCKID"]].astype(str).str.strip(),
            "county_fp": df[cols["COUNTYFP"]].astype(str).str.strip().str.zfill(3),
            "vtd_code": df[cols["DISTRICT"]].astype(str).str.strip(),
        }
    )
    out["county_fips"] = str(state_fips).zfill(2) + out["county_fp"]
    out["vtd_key"] = [_vtd_code(c, d) for c, d in zip(out["county_fp"], out["vtd_code"], strict=True)]
    return out.drop(columns=["county_fp"])


def block_to_old_district(baf_zip: Path) -> pd.DataFrame:
    """``block_id, old_district`` from a BAF package's congressional-district member.

    This is the plan *as apportioned at that Census*, which for the 2020 package means the
    116th Congress — 2010-era lines expressed in 2020 blocks. That is precisely the "old"
    side of a 2020→2022 transfer, so it is read rather than derived.
    """
    df = _read_baf(baf_zip, "CD")
    cols = {c.upper(): c for c in df.columns}
    district = pd.to_numeric(df[cols["DISTRICT"]], errors="coerce")
    return pd.DataFrame(
        {"block_id": df[cols["BLOCKID"]].astype(str).str.strip(), "old_district": district}
    ).dropna(subset=["old_district"])


def block_to_new_district(
    block_zip: Path, district_zip: Path, *, district_column: str | None = None
) -> tuple[pd.DataFrame, dict]:
    """``block_id, new_district, pop`` by locating each block's interior point in a plan.

    Census has no Block Assignment File for the 2022 round, so this is the derived step. It
    uses the interior point TIGER publishes per block (``INTPTLAT``/``INTPTLON``), which is
    guaranteed to lie inside the block, rather than a computed centroid, which for a
    crescent-shaped block need not.

    Blocks whose point falls inside no district are **reported, never nearest-matched**: in
    Virginia they are water and coastal blocks, and a nearest-neighbour fill would put real
    votes in a district on the strength of a tie-break.
    """
    import geopandas as gpd

    plan = gpd.read_file(district_zip)
    if district_column is None:
        candidates = [c for c in plan.columns if re.fullmatch(r"CD\d+FP", c)]
        if not candidates:
            raise ValueError(f"{district_zip.name} has no CD<nnn>FP column: {list(plan.columns)}")
        district_column = candidates[0]

    blocks = gpd.read_file(block_zip, columns=["GEOID20", "INTPTLAT20", "INTPTLON20", "POP20", "ALAND20"])
    points = gpd.GeoDataFrame(
        {
            "block_id": blocks["GEOID20"].astype(str),
            "pop": pd.to_numeric(blocks["POP20"], errors="coerce").fillna(0),
            "land_area": pd.to_numeric(blocks["ALAND20"], errors="coerce").fillna(0),
        },
        geometry=gpd.points_from_xy(
            pd.to_numeric(blocks["INTPTLON20"], errors="coerce"),
            pd.to_numeric(blocks["INTPTLAT20"], errors="coerce"),
        ),
        crs=blocks.crs,
    ).to_crs(plan.crs)

    joined = gpd.sjoin(points, plan[[district_column, "geometry"]], how="left", predicate="within")
    joined = joined.drop_duplicates("block_id")
    out = pd.DataFrame(
        {
            "block_id": joined["block_id"].to_numpy(),
            "new_district": pd.to_numeric(joined[district_column], errors="coerce").to_numpy(),
            "pop": joined["pop"].to_numpy(),
            "land_area": joined["land_area"].to_numpy(),
        }
    )
    unplaced = out["new_district"].isna()
    stats = {
        "blocks": int(len(out)),
        "blocks_unplaced": int(unplaced.sum()),
        "population_unplaced": int(out.loc[unplaced, "pop"].sum()),
        # Land area distinguishes a water block (no voters, expected) from a real hole.
        "unplaced_blocks_with_land": int((unplaced & (out["land_area"] > 0)).sum()),
        "districts": sorted(out["new_district"].dropna().unique().astype(int).tolist()),
    }
    return out.drop(columns=["land_area"]), stats

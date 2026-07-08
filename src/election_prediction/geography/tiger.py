"""Census TIGER/Line boundary ingestion (P0-007).

Downloads official TIGER/Line shapefiles (state / county / congressional district),
converts them to GeoParquet, validates CRS and geometry, and confirms GEOIDs match
the returns/ACS spine (docs/ingestion-playbook.md, TIGER section). Geometry is
preserved for analysis; simplify only for web maps.

Live acquisition uses the public census.gov TIGER endpoints. When outbound access is
unavailable, ``build_synthetic_boundaries`` produces a valid GeoDataFrame with correct
GEOIDs and simple placeholder geometries so geometry-validity checks, GEOID joins, and
GeoParquet round-trips are exercised. Tier 0 (public aggregate).
"""
from __future__ import annotations

import urllib.error
import urllib.request
import zipfile
from pathlib import Path

from ..data.privacy import PrivacyTier
from . import reference as ref

PRIVACY_TIER = PrivacyTier.PUBLIC_AGGREGATE
ATTRIBUTION = "U.S. Census Bureau, TIGER/Line Shapefiles."
LICENSE = "Public domain (U.S. Census Bureau); record vintage/Congress."
TIGER_BASE = "https://www2.census.gov/geo/tiger"

# Analysis CRS: TIGER ships in NAD83 (EPSG:4269).
TIGER_CRS = "EPSG:4269"


def tiger_url(vintage: int, layer: str) -> str:
    """Build the TIGER zip URL for a layer: 'state' | 'county' | 'cd'."""
    if layer == "state":
        return f"{TIGER_BASE}/TIGER{vintage}/STATE/tl_{vintage}_us_state.zip"
    if layer == "county":
        return f"{TIGER_BASE}/TIGER{vintage}/COUNTY/tl_{vintage}_us_county.zip"
    if layer == "cd":
        # congressional-district file name encodes the Congress number
        congress = {2022: "cd118", 2020: "cd116", 2018: "cd116"}.get(vintage, "cd118")
        return f"{TIGER_BASE}/TIGER{vintage}/CD/tl_{vintage}_us_{congress}.zip"
    raise ValueError(f"Unknown TIGER layer {layer!r}")


# ---------------------------------------------------------------- acquisition
def download_tiger(vintage: int, layer: str, raw_dir: str | Path, *, timeout: int = 120) -> Path:
    """Download and unzip a TIGER shapefile; return the extracted .shp path."""
    url = tiger_url(vintage, layer)
    out_dir = Path(raw_dir) / f"source=tiger/dataset={layer}/vintage={vintage}"
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_path = out_dir / Path(url).name
    req = urllib.request.Request(url, headers={"User-Agent": "election-prediction/0.0.1"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp, open(zip_path, "wb") as fh:
            fh.write(resp.read())
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise RuntimeError(
            f"Live TIGER download failed ({url}): {e}. "
            "No outbound access — fall back to synthetic boundaries."
        ) from e
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(out_dir)
    shp = next(out_dir.glob("*.shp"))
    return shp


# ----------------------------------------------------------------- transforms
def to_geoparquet(shp_path: str | Path, out_path: str | Path):
    """Load a TIGER shapefile, ensure CRS, write GeoParquet. Returns the GeoDataFrame."""
    import geopandas as gpd

    gdf = gpd.read_file(shp_path)
    if gdf.crs is None:
        gdf = gdf.set_crs(TIGER_CRS)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    gdf.to_parquet(out_path)
    return gdf


def validate_boundaries(gdf, *, geoid_col: str = "GEOID") -> dict:
    """Geometry/CRS/GEOID checks (docs/ingestion-playbook.md TIGER validation)."""
    checks = {
        "has_crs": gdf.crs is not None,
        "geometry_valid": bool(gdf.geometry.is_valid.all()),
        "geoid_present": geoid_col in gdf.columns,
        "geoid_unique": bool(gdf[geoid_col].is_unique) if geoid_col in gdf.columns else False,
        "n_features": int(len(gdf)),
    }
    checks["ok"] = all(v for k, v in checks.items() if isinstance(v, bool))
    return checks


# ------------------------------------------------------------------ synthetic
def build_synthetic_boundaries(layer: str = "state"):
    """A valid GeoDataFrame with correct state GEOIDs and placeholder box geometries.

    Enough to exercise geometry validity, GEOID joins, and GeoParquet round-trips
    without downloading ~100 MB shapefiles. Geometries are schematic, not real.
    """
    import geopandas as gpd
    from shapely.geometry import box

    rows = []
    for i, (po, s) in enumerate(ref.STATES.items()):
        col, row = i % 10, i // 10
        rows.append({
            "GEOID": s.fips, "STUSPS": po, "NAME": s.name,
            "geometry": box(col, row, col + 0.9, row + 0.9),
        })
    gdf = gpd.GeoDataFrame(rows, crs=TIGER_CRS)
    return gdf

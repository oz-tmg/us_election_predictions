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

import json
import zipfile
from pathlib import Path

import pandas as pd

from ..data import acquire
from ..data.privacy import PrivacyTier
from . import reference as ref

PRIVACY_TIER = PrivacyTier.PUBLIC_AGGREGATE
ATTRIBUTION = "U.S. Census Bureau, TIGER/Line Shapefiles."
LICENSE = "Public domain (U.S. Census Bureau); record vintage/Congress."
TIGER_BASE = "https://www2.census.gov/geo/tiger"
DEFAULT_TIGER_VINTAGE = 2024

# Analysis CRS: TIGER ships in NAD83 (EPSG:4269).
TIGER_CRS = "EPSG:4269"


# Congress number by TIGER vintage. Congressional-district filenames encode the
# Congress, not the year, and a new Congress reshapes the layer — so this mapping is
# also the record of which district plan a snapshot represents.
CD_CONGRESS = {2024: "cd119", 2023: "cd118", 2022: "cd118"}

# Layers published as a single national file. Congressional districts are NOT one of
# them: TIGER ships CD as one zip per state (tl_2024_01_cd119.zip, ...).
NATIONAL_LAYERS = {"state": "STATE", "county": "COUNTY"}


def congress_for_vintage(vintage: int) -> str:
    if vintage not in CD_CONGRESS:
        raise ValueError(
            f"No congressional-district mapping for TIGER vintage {vintage}. "
            f"Known vintages: {sorted(CD_CONGRESS)}. Check "
            f"{TIGER_BASE}/TIGER{vintage}/CD/ and add the Congress number."
        )
    return CD_CONGRESS[vintage]


def tiger_url(vintage: int, layer: str, state_fips: str | None = None) -> str:
    """Build the TIGER zip URL for 'state' | 'county' | 'cd'.

    ``cd`` requires ``state_fips`` because the Census publishes congressional
    districts per state rather than as a national file.
    """
    if layer in NATIONAL_LAYERS:
        directory = NATIONAL_LAYERS[layer]
        return f"{TIGER_BASE}/TIGER{vintage}/{directory}/tl_{vintage}_us_{layer}.zip"
    if layer == "cd":
        if not state_fips:
            raise ValueError(
                "TIGER congressional districts are published per state; pass state_fips "
                "(use download_tiger_cd to fetch every state)."
            )
        congress = congress_for_vintage(vintage)
        return f"{TIGER_BASE}/TIGER{vintage}/CD/tl_{vintage}_{state_fips}_{congress}.zip"
    raise ValueError(f"Unknown TIGER layer {layer!r}")


# ---------------------------------------------------------------- acquisition
def _download_and_extract(url: str, out_dir: Path, *, timeout: int) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_path = acquire.fetch(url, out_dir / Path(url).name.split("?")[0], expect="zip", timeout=timeout)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(out_dir)
    try:
        return next(out_dir.glob("*.shp"))
    except StopIteration as exc:
        raise acquire.InvalidResponse(f"TIGER archive {zip_path} did not contain a shapefile") from exc


def download_tiger(
    vintage: int, layer: str, raw_dir: str | Path, *, state_fips: str | None = None, timeout: int = 300
) -> Path:
    """Download and unzip one TIGER shapefile; return the extracted .shp path."""
    url = tiger_url(vintage, layer, state_fips)
    suffix = f"/state={state_fips}" if state_fips else ""
    out_dir = Path(raw_dir) / f"source=tiger/dataset={layer}/vintage={vintage}{suffix}"
    return _download_and_extract(url, out_dir, timeout=timeout)


def download_tiger_cd(
    vintage: int,
    raw_dir: str | Path,
    *,
    state_fips: list[str] | None = None,
    timeout: int = 300,
    require_all: bool = False,
) -> dict[str, Path]:
    """Download congressional-district shapefiles for every requested state.

    Returns ``{state_fips: shp_path}``. States are fetched independently so one
    missing state (e.g. a territory without CDs) does not abort the whole layer;
    failures are raised only if *every* state fails unless ``require_all`` is set.
    """
    targets = state_fips or [s.fips for s in ref.STATES.values()]
    out: dict[str, Path] = {}
    errors: list[str] = []
    for fips in targets:
        try:
            out[fips] = download_tiger(vintage, "cd", raw_dir, state_fips=fips, timeout=timeout)
        except acquire.AcquisitionError as e:
            errors.append(f"{fips}: {e}")
    if not out:
        raise acquire.NetworkUnavailable(
            f"No TIGER congressional-district files could be downloaded: {errors[:3]}"
        )
    if require_all and errors:
        raise acquire.AcquisitionError(
            "Publication-grade TIGER acquisition requires every requested state; "
            f"{len(errors)} failed: {errors[:5]}"
        )
    return out


def write_inventory(
    vintage: int,
    layer: str,
    shapefiles: dict[str, Path],
    raw_dir: str | Path,
) -> Path:
    """Write a deterministic inventory of raw TIGER archives and checksums.

    Congressional districts arrive as one archive per state. The inventory is the
    checksummed lineage payload used by the source manifest, so every constituent
    archive remains auditable without committing dozens of redundant manifests.
    """
    files = []
    for key, shp_path in sorted(shapefiles.items()):
        archives = sorted(shp_path.parent.glob("*.zip"))
        if len(archives) != 1:
            raise acquire.AcquisitionError(
                f"Expected one TIGER archive beside {shp_path}, found {len(archives)}"
            )
        archive = archives[0]
        files.append(
            {
                "key": key,
                "url": tiger_url(vintage, layer, key if layer == "cd" else None),
                "path": str(archive),
                "size_bytes": archive.stat().st_size,
                "sha256": acquire.sha256_file(archive),
            }
        )

    inventory = {
        "provider": "U.S. Census Bureau",
        "dataset": "TIGER/Line Shapefiles",
        "vintage": vintage,
        "layer": layer,
        "files": files,
    }
    out_path = Path(raw_dir) / f"source=tiger/dataset={layer}/vintage={vintage}/archive_inventory.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(inventory, indent=2, sort_keys=True) + "\n")
    return out_path


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


def to_geoparquet_many(shp_paths: list[str | Path], out_path: str | Path):
    """Combine same-schema TIGER shapefiles and write one GeoParquet layer."""
    import geopandas as gpd

    parts = [gpd.read_file(path) for path in shp_paths]
    if not parts:
        raise ValueError("At least one TIGER shapefile is required")
    crs = parts[0].crs or TIGER_CRS
    for part in parts:
        if part.crs is not None and part.crs != crs:
            raise ValueError(f"TIGER CRS mismatch: expected {crs}, got {part.crs}")
    combined = gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), crs=crs)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    combined.to_parquet(out_path)
    return combined


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

    if layer not in {"state", "county", "cd"}:
        raise ValueError(f"Unknown synthetic TIGER layer {layer!r}")

    rows = []
    for i, (po, s) in enumerate(ref.STATES.items()):
        col, row = i % 10, i // 10
        geoid = s.fips if layer == "state" else f"{s.fips}{'001' if layer == 'county' else '00'}"
        rows.append(
            {
                "GEOID": geoid,
                "STATEFP": s.fips,
                "STUSPS": po,
                "NAME": s.name,
                "geometry": box(col, row, col + 0.9, row + 0.9),
            }
        )
    gdf = gpd.GeoDataFrame(rows, crs=TIGER_CRS)
    return gdf

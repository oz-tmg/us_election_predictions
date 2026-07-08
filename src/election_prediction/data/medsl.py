"""MEDSL federal returns ingestion (P0-005).

Ingests the MIT Election Data & Science Lab canonical federal return datasets —
president, U.S. House, U.S. Senate — through raw -> bronze -> silver, standardizing
to one conformed election-returns schema (docs/ingestion-playbook.md, MEDSL section).

Live acquisition uses the published Harvard Dataverse file endpoints. When the
environment has no outbound access (e.g. a locked-down sandbox), ``download_medsl``
raises a clear error and the caller falls back to a synthetic fixture that matches
the real schema, so the pipeline is exercised end-to-end and reproducibly.

Source (Tier 0, public aggregate; attribution required):
  President 1976-2020  doi:10.7910/DVN/42MVDX
  Senate    1976-2020  doi:10.7910/DVN/PEJ5QU
  House     1976-2022  doi:10.7910/DVN/IG0UN2
"""
from __future__ import annotations

import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from ..geography import reference as ref
from .privacy import PrivacyTier

DATAVERSE = "https://dataverse.harvard.edu/api/access/datafile/:persistentId?persistentId="

# Canonical silver schema every office maps into.
SILVER_COLUMNS = [
    "race_id", "cycle", "office", "state_po", "state_fips", "district_num",
    "geography_id", "geog_level", "candidate", "party", "party_simplified",
    "candidatevotes", "totalvotes", "vote_share", "writein",
    "uncontested_flag", "certified_flag", "stage", "special",
    "source_id", "snapshot_date",
]

OFFICE_CANON = {
    "US PRESIDENT": "president",
    "PRESIDENT": "president",
    "US HOUSE": "us_house",
    "US SENATE": "us_senate",
}


@dataclass(frozen=True)
class MedslSource:
    office: str                 # canonical office name
    source_id: str
    dataset_name: str
    doi: str
    filename: str               # the CSV as published
    election_cycle: str
    geog_level: str             # "state" (pres/sen) | "cong_district" (house)
    # columns expected in the raw file (real MEDSL layout)
    raw_columns: tuple[str, ...]

    @property
    def url(self) -> str:
        return DATAVERSE + self.doi


MEDSL_SOURCES: dict[str, MedslSource] = {
    "president": MedslSource(
        office="president",
        source_id="medsl_president_1976_2020",
        dataset_name="MEDSL U.S. President 1976-2020",
        doi="doi:10.7910/DVN/42MVDX",
        filename="1976-2020-president.csv",
        election_cycle="1976-2020",
        geog_level="state",
        raw_columns=("year", "state", "state_po", "state_fips", "office",
                     "candidate", "party_detailed", "party_simplified",
                     "writein", "candidatevotes", "totalvotes"),
    ),
    "us_senate": MedslSource(
        office="us_senate",
        source_id="medsl_senate_1976_2020",
        dataset_name="MEDSL U.S. Senate 1976-2020",
        doi="doi:10.7910/DVN/PEJ5QU",
        filename="1976-2020-senate.csv",
        election_cycle="1976-2020",
        geog_level="state",
        raw_columns=("year", "state", "state_po", "state_fips", "office",
                     "candidate", "party_detailed", "party_simplified", "writein",
                     "candidatevotes", "totalvotes", "stage", "special", "unofficial"),
    ),
    "us_house": MedslSource(
        office="us_house",
        source_id="medsl_house_1976_2022",
        dataset_name="MEDSL U.S. House 1976-2022",
        doi="doi:10.7910/DVN/IG0UN2",
        filename="1976-2022-house.csv",
        election_cycle="1976-2022",
        geog_level="cong_district",
        raw_columns=("year", "state", "state_po", "state_fips", "office", "district",
                     "candidate", "party", "writein", "candidatevotes", "totalvotes",
                     "stage", "special", "unofficial", "runoff"),
    ),
}


# ---------------------------------------------------------------- acquisition
def download_medsl(office: str, raw_dir: str | Path, *, timeout: int = 120) -> Path:
    """Download the MEDSL CSV for ``office`` into a raw snapshot dir. Returns the path.

    Raises RuntimeError with a clear message if the network is unavailable so the
    caller can fall back to the synthetic fixture.
    """
    src = MEDSL_SOURCES[office]
    out_dir = Path(raw_dir) / f"source=medsl/dataset={office}/snapshot={pd.Timestamp.today():%Y-%m-%d}"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / src.filename
    req = urllib.request.Request(src.url, headers={"User-Agent": "election-prediction/0.0.1"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp, open(out_path, "wb") as fh:
            fh.write(resp.read())
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise RuntimeError(
            f"Live MEDSL download failed for {office} ({src.url}): {e}. "
            "No outbound access in this environment — fall back to synthetic fixture."
        ) from e
    return out_path


# ----------------------------------------------------------------- transforms
def _canon_party(row: pd.Series) -> tuple[str, str]:
    """Return (party, party_simplified) standardized to D/R/OTHER family."""
    detailed = str(row.get("party_detailed") or row.get("party") or "").strip().upper()
    simple = str(row.get("party_simplified") or "").strip().upper()
    if not simple:
        if "DEMOCRAT" in detailed:
            simple = "DEMOCRAT"
        elif "REPUBLICAN" in detailed:
            simple = "REPUBLICAN"
        elif detailed in {"", "NAN", "NONE"}:
            simple = "OTHER"
        else:
            simple = "OTHER"
    return (detailed or "OTHER", simple or "OTHER")


def parse_bronze(csv_path: str | Path, office: str, *, source_id: str,
                 snapshot_date: str) -> pd.DataFrame:
    """Parse a raw MEDSL CSV to a bronze frame with ingestion metadata columns."""
    df = pd.read_csv(csv_path, dtype=str)
    df.columns = [c.strip().lower() for c in df.columns]
    df["source_id"] = source_id
    df["source_file"] = str(Path(csv_path).name)
    df["snapshot_date"] = snapshot_date
    df["ingested_at"] = pd.Timestamp.utcnow().isoformat()
    return df


def standardize_silver(bronze: pd.DataFrame, office: str) -> pd.DataFrame:
    """Map a bronze MEDSL frame to the conformed silver election-returns schema."""
    from ..geography.canonical import geography_id

    src = MEDSL_SOURCES[office]
    out = pd.DataFrame()
    b = bronze.copy()

    out["cycle"] = b["year"].astype(int)
    out["office"] = office
    # conform state via reference (handles postal or fips present in file)
    state = b["state_po"].fillna(b.get("state"))
    refs = state.map(lambda v: ref.normalize_state(v))
    out["state_po"] = refs.map(lambda s: s.postal)
    out["state_fips"] = refs.map(lambda s: s.fips)

    if office == "us_house":
        out["district_num"] = pd.to_numeric(b["district"], errors="coerce").fillna(0).astype(int)
        out["geog_level"] = "cong_district"
        out["geography_id"] = [
            geography_id("cong_district", state_fips=sf, district_num=d)
            for sf, d in zip(out["state_fips"], out["district_num"], strict=True)
        ]
    else:
        out["district_num"] = pd.NA
        out["geog_level"] = "state"
        out["geography_id"] = [geography_id("state", state_fips=sf) for sf in out["state_fips"]]

    def col(name: str, default: str) -> pd.Series:
        """Return column ``name`` as a Series, or a same-length default Series."""
        if name in b.columns:
            return b[name]
        return pd.Series([default] * len(b), index=b.index)

    def truthy(name: str) -> pd.Series:
        return col(name, "FALSE").astype(str).str.upper().isin({"TRUE", "1", "YES"})

    parties = b.apply(_canon_party, axis=1, result_type="expand")
    out["candidate"] = b["candidate"].fillna("").str.strip().str.upper()
    out["party"] = parties[0]
    out["party_simplified"] = parties[1]
    out["candidatevotes"] = pd.to_numeric(b["candidatevotes"], errors="coerce").fillna(0).astype(int)
    out["totalvotes"] = pd.to_numeric(b["totalvotes"], errors="coerce").fillna(0).astype(int)
    out["writein"] = truthy("writein")
    out["stage"] = col("stage", "GEN").fillna("GEN")
    out["special"] = truthy("special")
    # MEDSL historical returns are certified unless an 'unofficial' flag says otherwise
    out["certified_flag"] = ~truthy("unofficial")

    out["source_id"] = src.source_id
    out["snapshot_date"] = b["snapshot_date"]

    # race grain + derived shares
    out["race_id"] = _race_id(out)
    out["vote_share"] = _vote_share(out)
    out["uncontested_flag"] = _uncontested(out)

    return out[SILVER_COLUMNS].sort_values(["cycle", "state_po", "race_id"]).reset_index(drop=True)


def _race_id(df: pd.DataFrame) -> pd.Series:
    def mk(r):
        base = f"{r['cycle']}_{r['office']}_{r['state_po']}".lower()
        if r["office"] == "us_house":
            base += f"_{int(r['district_num']):02d}"
        stage = str(r.get("stage") or "gen").lower()
        return f"{base}_{stage}"
    return df.apply(mk, axis=1)


def _vote_share(df: pd.DataFrame) -> pd.Series:
    tot = df.groupby("race_id")["candidatevotes"].transform("sum")
    return (df["candidatevotes"] / tot.where(tot > 0)).fillna(0.0)


def _uncontested(df: pd.DataFrame) -> pd.Series:
    """A race is uncontested if fewer than 2 candidates poll >0 votes."""
    n_contenders = (
        df[df["candidatevotes"] > 0].groupby("race_id")["candidate"].nunique()
    )
    return df["race_id"].map(n_contenders).fillna(0) < 2


PRIVACY_TIER = PrivacyTier.PUBLIC_AGGREGATE
LICENSE = "MEDSL data are released for research use; cite MIT Election Data and Science Lab."
ATTRIBUTION = "MIT Election Data and Science Lab (MEDSL), Harvard Dataverse."

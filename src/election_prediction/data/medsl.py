"""MEDSL federal returns ingestion (P0-005).

Ingests the MIT Election Data & Science Lab canonical federal return datasets —
president, U.S. House, U.S. Senate — through raw -> bronze -> silver, standardizing
to one conformed election-returns schema (docs/ingestion-playbook.md, MEDSL section).

Acquisition notes (verified against the live endpoints, 2026-07-31):

* The Dataverse *datafile* access API needs a numeric file id or a **file** PID.
  The dataset DOI is not a datafile PID, so it cannot be used here.
* All three series now run **1976-2024** (they previously ended 2020/2022).
* Senate and House are Dataverse-*ingested* tabular files, so the default download
  is a re-serialized ``.tab``. We request ``format=original`` and record the
  original separator per source rather than assuming CSV.
* The president and House datasets sit behind a Dataverse **guestbook**, which the
  access API refuses to satisfy. Those are handled as a documented, checksum-verified
  manual acquisition (see ``acquire.ManualAcquisitionRequired``) rather than by
  silently substituting synthetic data.

Source (Tier 0, public aggregate; attribution required):
  President 1976-2024  doi:10.7910/DVN/42MVDX
  Senate    1976-2024  doi:10.7910/DVN/PEJ5QU
  House     1976-2024  doi:10.7910/DVN/IG0UN2
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from ..geography import reference as ref
from . import acquire
from .privacy import PrivacyTier

DATAVERSE_ACCESS = "https://dataverse.harvard.edu/api/access/datafile"
DATAVERSE_PAGE = "https://dataverse.harvard.edu/dataset.xhtml?persistentId="
DATAVERSE_TOKEN_ENV = "DATAVERSE_API_TOKEN"

# Canonical silver schema every office maps into.
SILVER_COLUMNS = [
    "race_id", "cycle", "office", "state_po", "state_fips", "district_num",
    "geography_id", "geog_level", "candidate", "party", "party_simplified",
    "candidatevotes", "totalvotes", "vote_share", "writein",
    "fusion_flag", "uncontested_flag", "certified_flag", "stage", "special",
    "source_id", "snapshot_date",
]

OFFICE_CANON = {
    "US PRESIDENT": "president",
    "PRESIDENT": "president",
    "US HOUSE": "us_house",
    "US SENATE": "us_senate",
}

# Stages that represent a general election. MEDSL mixes case and includes primaries
# ('pre'/'pri') in some series; modelling like-for-like requires general only
# (CLAUDE.md §6 "equivalent election type").
GENERAL_STAGES = {"gen", "gen runoff", "runoff", "general"}


@dataclass(frozen=True)
class MedslSource:
    office: str                 # canonical office name
    source_id: str
    dataset_name: str
    doi: str                    # dataset DOI (for citation + the human landing page)
    datafile_id: int            # Dataverse numeric datafile id (for the access API)
    filename: str               # the file as published in its original format
    sep: str                    # separator of the *original* file
    election_cycle: str
    geog_level: str             # "state" (pres/sen) | "cong_district" (house)
    guestbook: bool = False     # True -> access API is gated, manual download required
    expected_md5: str | None = None
    expected_size: int | None = None
    raw_columns: tuple[str, ...] = field(default=())

    @property
    def url(self) -> str:
        """Programmatic download URL (original format)."""
        return f"{DATAVERSE_ACCESS}/{self.datafile_id}?format=original"

    @property
    def landing_page(self) -> str:
        """Human-facing dataset page — where a guestbook can be accepted."""
        return DATAVERSE_PAGE + self.doi


MEDSL_SOURCES: dict[str, MedslSource] = {
    "president": MedslSource(
        office="president",
        source_id="medsl_president_1976_2024",
        dataset_name="MEDSL U.S. President 1976-2024",
        doi="doi:10.7910/DVN/42MVDX",
        datafile_id=13887042,
        filename="1976-2024-president.csv",
        sep=",",
        election_cycle="1976-2024",
        geog_level="state",
        guestbook=True,
        expected_md5="405af83db7625cb35d8c19a5ebe029ff",
        expected_size=514108,
        raw_columns=("year", "state", "state_po", "state_fips", "office",
                     "candidate", "party_detailed", "party_simplified",
                     "writein", "candidatevotes", "totalvotes"),
    ),
    "us_senate": MedslSource(
        office="us_senate",
        source_id="medsl_senate_1976_2024",
        dataset_name="MEDSL U.S. Senate 1976-2024",
        doi="doi:10.7910/DVN/PEJ5QU",
        datafile_id=13887039,
        filename="1976-2024-senate-state.csv",
        sep=",",
        election_cycle="1976-2024",
        geog_level="state",
        guestbook=False,
        expected_size=530501,
        raw_columns=("year", "state", "state_po", "state_fips", "state_cen", "state_ic",
                     "office", "district", "stage", "special", "candidate",
                     "party_detailed", "writein", "mode", "candidatevotes",
                     "totalvotes", "unofficial", "version", "party_simplified"),
    ),
    "us_house": MedslSource(
        office="us_house",
        source_id="medsl_house_1976_2024",
        dataset_name="MEDSL U.S. House 1976-2024",
        doi="doi:10.7910/DVN/IG0UN2",
        datafile_id=13592823,
        filename="1976-2024-house.tab",
        sep="\t",
        election_cycle="1976-2024",
        geog_level="cong_district",
        guestbook=True,
        expected_size=4156562,
        raw_columns=("year", "state", "state_po", "state_fips", "office", "district",
                     "stage", "special", "candidate", "party", "writein", "mode",
                     "candidatevotes", "totalvotes", "unofficial", "runoff"),
    ),
}


# ---------------------------------------------------------------- acquisition
def manual_drop_dir(office: str, raw_dir: str | Path) -> Path:
    """Stable location where an operator places a guestbook-gated source file."""
    return Path(raw_dir) / f"source=medsl/dataset={office}/manual"


def find_manual_snapshot(office: str, raw_dir: str | Path) -> Path | None:
    """Return a verified, manually-placed snapshot for ``office`` if one exists.

    The file must match the published size/checksum; an unverifiable file raises
    rather than being used, so a corrupted manual download cannot reach silver.
    """
    src = MEDSL_SOURCES[office]
    candidate = manual_drop_dir(office, raw_dir) / src.filename
    if not candidate.exists():
        return None
    acquire.verify_file(candidate, expected_md5=src.expected_md5,
                        expected_size=src.expected_size, url=src.landing_page)
    return candidate


def download_medsl(office: str, raw_dir: str | Path, *, timeout: int = 180) -> Path:
    """Acquire the MEDSL file for ``office`` into a raw snapshot dir; return the path.

    Resolution order:
      1. a previously verified manual download (guestbook-gated sources);
      2. the Dataverse access API (ungated sources).

    Raises ``acquire.ManualAcquisitionRequired`` for gated sources that have not been
    downloaded yet, ``acquire.NetworkUnavailable`` when offline, and
    ``acquire.InvalidResponse`` if the endpoint answers with something that is not
    the dataset.
    """
    src = MEDSL_SOURCES[office]

    if (manual := find_manual_snapshot(office, raw_dir)) is not None:
        return manual

    out_dir = Path(raw_dir) / f"source=medsl/dataset={office}/snapshot={pd.Timestamp.today():%Y-%m-%d}"
    expect = "tsv" if src.sep == "\t" else "csv"
    headers = {}
    if token := os.environ.get(DATAVERSE_TOKEN_ENV, "").strip():
        # An account token satisfies the guestbook on some Dataverse installations.
        headers["X-Dataverse-key"] = token

    if src.guestbook and not headers:
        raise _guestbook_error(src, raw_dir)

    try:
        return acquire.fetch(src.url, out_dir / src.filename, expect=expect, timeout=timeout,
                             expected_md5=src.expected_md5, expected_size=src.expected_size,
                             headers=headers)
    except acquire.InvalidResponse as e:
        if "guestbook" in str(e).lower():
            raise _guestbook_error(src, raw_dir) from e
        raise


def _guestbook_error(src: MedslSource, raw_dir: str | Path) -> acquire.ManualAcquisitionRequired:
    drop = manual_drop_dir(src.office, raw_dir)
    drop.mkdir(parents=True, exist_ok=True)
    return acquire.ManualAcquisitionRequired(
        f"{src.dataset_name} is behind a Harvard Dataverse guestbook, so it cannot be "
        f"downloaded programmatically. A valid ${DATAVERSE_TOKEN_ENV} does NOT satisfy "
        "this guestbook (verified 2026-08-03) — the response must be given in a browser, "
        "once.",
        url=src.landing_page, filename=src.filename, drop_dir=drop,
        expected_md5=src.expected_md5, expected_size=src.expected_size,
    )


# ----------------------------------------------------------------- transforms
def _canon_party(row: pd.Series) -> tuple[str, str]:
    """Return (party, party_simplified) standardized to the D/R/OTHER family."""
    detailed = str(row.get("party_detailed") or row.get("party") or "").strip().upper()
    simple = str(row.get("party_simplified") or "").strip().upper()
    if not simple or simple in {"NAN", "NONE"}:
        if "DEMOCRAT" in detailed:
            simple = "DEMOCRAT"
        elif "REPUBLICAN" in detailed:
            simple = "REPUBLICAN"
        else:
            simple = "OTHER"
    return (detailed or "OTHER", simple)


def parse_bronze(csv_path: str | Path, office: str, *, source_id: str,
                 snapshot_date: str) -> pd.DataFrame:
    """Parse a raw MEDSL file to a bronze frame with ingestion metadata columns.

    The separator comes from the source definition — senate/house ship as ingested
    tabular files and reading them as CSV silently produces a single-column frame.
    """
    sep = MEDSL_SOURCES[office].sep if office in MEDSL_SOURCES else ","
    df = pd.read_csv(csv_path, dtype=str, sep=sep, low_memory=False)
    if df.shape[1] == 1:
        raise ValueError(
            f"{Path(csv_path).name} parsed to a single column with sep={sep!r}. "
            "The source's file format has probably changed."
        )
    df.columns = [c.strip().lower() for c in df.columns]
    df["source_id"] = source_id
    df["source_file"] = str(Path(csv_path).name)
    df["snapshot_date"] = snapshot_date
    df["ingested_at"] = pd.Timestamp.now(tz="UTC").isoformat()
    return df


def filter_general_election(bronze: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Keep general-election rows only; return (frame, counts of what was dropped).

    Real MEDSL files mix case ('gen' vs 'GEN') and include primary rows in some
    series. Comparing a primary to a general would violate the like-for-like rule
    in CLAUDE.md §6, so primaries are dropped here and reported.
    """
    if "stage" not in bronze.columns:
        return bronze, {"dropped_non_general": 0}
    stage = bronze["stage"].fillna("gen").astype(str).str.strip().str.lower()
    keep = stage.isin(GENERAL_STAGES)
    return bronze[keep].copy(), {"dropped_non_general": int((~keep).sum())}


def collapse_vote_modes(bronze: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Reduce per-voting-mode rows to one row per candidate line.

    Some MEDSL rows are broken out by ``mode`` (election day / absentee / total).
    Mixing a 'total' row with mode breakdowns double-counts votes. Where a race has
    any non-total modes we sum them; where it already reports totals we keep those.
    """
    if "mode" not in bronze.columns:
        return bronze, {"mode_rows_collapsed": 0}

    key = [c for c in ("year", "state_po", "office", "district", "stage", "special",
                       "candidate", "party_detailed", "party", "writein")
           if c in bronze.columns]
    if not key:
        return bronze, {"mode_rows_collapsed": 0}

    df = bronze.copy()
    n_before = len(df)
    df["_mode"] = df["mode"].fillna("total").astype(str).str.strip().str.lower()
    df["_key"] = df[key].fillna("").astype(str).agg("|".join, axis=1)
    df["candidatevotes"] = pd.to_numeric(df["candidatevotes"], errors="coerce").fillna(0)

    # Where a candidate line publishes a 'total' row, keep it and drop the breakdown
    # rows; otherwise the breakdowns *are* the total and get summed below.
    is_total = df["_mode"].eq("total")
    has_total = is_total.groupby(df["_key"]).transform("any")
    df = df[is_total | ~has_total].copy()

    if df["_key"].duplicated().any():
        df["candidatevotes"] = df.groupby("_key")["candidatevotes"].transform("sum")
        df = df.drop_duplicates("_key")

    df = df.drop(columns=["_mode", "_key"]).reset_index(drop=True)
    return df, {"mode_rows_collapsed": int(n_before - len(df))}


def _collapse_fusion(out: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Sum a candidate's votes across party lines (fusion voting).

    New York and a few other states let one candidate appear on several party lines
    (e.g. Democratic *and* Working Families). MEDSL reports one row per line, so a
    naive winner/two-party calculation would split a candidate's own vote. We sum
    the lines and keep the major-party label where one exists.
    docs/methodology.md lists fusion voting as requiring explicit handling.
    """
    key = ["race_id", "candidate"]
    dup_mask = out.duplicated(key, keep=False) & out["candidate"].ne("")
    n_fusion_rows = int(dup_mask.sum())
    if not n_fusion_rows:
        out["fusion_flag"] = False
        return out, 0

    def pick_party(group: pd.DataFrame) -> pd.Series:
        major = group[group["party_simplified"].isin({"DEMOCRAT", "REPUBLICAN"})]
        source = major if len(major) else group
        return source.sort_values("candidatevotes", ascending=False).iloc[0]

    parts = []
    for _, group in out[dup_mask].groupby(key, sort=False):
        row = pick_party(group).copy()
        row["candidatevotes"] = group["candidatevotes"].sum()
        row["fusion_flag"] = True
        parts.append(row)

    merged = pd.DataFrame(parts)
    kept = out[~dup_mask].copy()
    kept["fusion_flag"] = False
    combined = pd.concat([kept, merged], ignore_index=True)
    # Row-wise assembly of the merged lines can widen dtypes to object; restore them
    # so the downstream share/uncontested maths stays numeric.
    combined["candidatevotes"] = pd.to_numeric(combined["candidatevotes"]).astype("int64")
    combined["totalvotes"] = pd.to_numeric(combined["totalvotes"]).astype("int64")
    for flag in ("writein", "special", "certified_flag", "fusion_flag"):
        combined[flag] = combined[flag].astype(bool)
    return combined, len(merged)


def standardize_silver(bronze: pd.DataFrame, office: str) -> pd.DataFrame:
    """Map a bronze MEDSL frame to the conformed silver election-returns schema."""
    df, _ = standardize_silver_with_stats(bronze, office)
    return df


def standardize_silver_with_stats(bronze: pd.DataFrame, office: str) -> tuple[pd.DataFrame, dict]:
    """As ``standardize_silver``, also returning what the transform dropped/merged.

    The stats feed the data-quality report so that filtering decisions (primaries
    removed, fusion lines merged) are visible rather than silent.
    """
    from ..geography.canonical import geography_id

    src = MEDSL_SOURCES[office]
    b, stats = filter_general_election(bronze)
    b, mode_stats = collapse_vote_modes(b)
    stats.update(mode_stats)
    b = b.reset_index(drop=True)

    out = pd.DataFrame(index=b.index)
    out["cycle"] = pd.to_numeric(b["year"], errors="coerce").astype("Int64")
    out["office"] = office

    state = b["state_po"].fillna(b["state"]) if "state" in b.columns else b["state_po"]
    refs = state.map(ref.normalize_state)
    out["state_po"] = refs.map(lambda s: s.postal)
    out["state_fips"] = refs.map(lambda s: s.fips)

    def col(name: str, default: str) -> pd.Series:
        if name in b.columns:
            return b[name]
        return pd.Series([default] * len(b), index=b.index)

    def truthy(name: str) -> pd.Series:
        return col(name, "FALSE").astype(str).str.strip().str.upper().isin({"TRUE", "1", "YES", "T"})

    if office == "us_house":
        district = pd.to_numeric(b["district"], errors="coerce").fillna(0).astype(int)
        out["district_num"] = district
        out["geog_level"] = "cong_district"
        out["geography_id"] = [
            geography_id("cong_district", state_fips=sf, district_num=d)
            for sf, d in zip(out["state_fips"], district, strict=True)
        ]
    else:
        out["district_num"] = pd.NA
        out["geog_level"] = "state"
        out["geography_id"] = [geography_id("state", state_fips=sf) for sf in out["state_fips"]]

    parties = b.apply(_canon_party, axis=1, result_type="expand")
    out["candidate"] = b["candidate"].fillna("").astype(str).str.strip().str.upper()
    out["party"] = parties[0]
    out["party_simplified"] = parties[1]
    out["candidatevotes"] = pd.to_numeric(b["candidatevotes"], errors="coerce").fillna(0).astype("int64")
    out["totalvotes"] = pd.to_numeric(b["totalvotes"], errors="coerce").fillna(0).astype("int64")
    out["writein"] = truthy("writein")
    out["stage"] = col("stage", "gen").fillna("gen").astype(str).str.strip().str.lower()
    out["special"] = truthy("special")
    # MEDSL historical returns are certified unless an 'unofficial' flag says otherwise.
    out["certified_flag"] = ~truthy("unofficial")

    out["source_id"] = src.source_id
    out["snapshot_date"] = b["snapshot_date"] if "snapshot_date" in b.columns else pd.NaT

    out["race_id"] = _race_id(out)
    out, n_fusion = _collapse_fusion(out)
    stats["fusion_candidates_merged"] = n_fusion

    out["vote_share"] = _vote_share(out)
    out["uncontested_flag"] = _uncontested(out)

    out = (out[SILVER_COLUMNS]
           .sort_values(["cycle", "state_po", "race_id", "candidatevotes"],
                        ascending=[True, True, True, False])
           .reset_index(drop=True))
    stats["rows"] = len(out)
    return out, stats


def _race_id(df: pd.DataFrame) -> pd.Series:
    """Stable race key. Specials and runoffs are distinct races from the regular one."""
    def mk(r):
        base = f"{r['cycle']}_{r['office']}_{r['state_po']}".lower()
        if r["office"] == "us_house":
            district = r["district_num"]
            base += f"_{int(district):02d}" if pd.notna(district) else "_na"
        stage = str(r.get("stage") or "gen").strip().lower().replace(" ", "_")
        base += f"_{stage}"
        if bool(r.get("special")):
            base += "_special"
        return base
    return df.apply(mk, axis=1)


def _vote_share(df: pd.DataFrame) -> pd.Series:
    tot = df.groupby("race_id")["candidatevotes"].transform("sum")
    return (df["candidatevotes"] / tot.where(tot > 0)).fillna(0.0)


def _uncontested(df: pd.DataFrame) -> pd.Series:
    """Uncontested if fewer than 2 non-write-in candidates poll >0 votes.

    Write-ins are excluded from the contender count so a safe seat with a handful of
    write-in votes is still recorded as uncontested (CLAUDE.md §6 — uncontested races
    are handled explicitly, never as 100-0 truth).
    """
    real = df[(df["candidatevotes"] > 0) & (~df["writein"]) & (df["candidate"] != "")]
    n_contenders = real.groupby("race_id")["candidate"].nunique()
    return df["race_id"].map(n_contenders).fillna(0) < 2


PRIVACY_TIER = PrivacyTier.PUBLIC_AGGREGATE
LICENSE = "MEDSL data are released for research use; cite MIT Election Data and Science Lab."
ATTRIBUTION = "MIT Election Data and Science Lab (MEDSL), Harvard Dataverse."

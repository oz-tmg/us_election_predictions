"""Source manifest schema (P0-004).

Every raw snapshot that enters ``data/raw/`` carries a manifest recording source,
date, checksum, license, and privacy tier — the minimum for reproducibility and
legal review (CLAUDE.md §4/§5, docs/ingestion-playbook.md "Required Manifest Fields").

The manifest is the unit of lineage: raw source -> snapshot -> transform ->
model version -> evaluation report all trace back to a ``source_id`` + ``snapshot_id``.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path

from .privacy import PrivacyTier, assert_public_safe

MANIFEST_SCHEMA_VERSION = "1.0"


def sha256_file(path: str | Path, *, chunk: int = 1 << 20) -> str:
    """Streaming SHA-256 of a file (works on large precinct/CVR files)."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def _utcnow_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


@dataclass
class SourceManifest:
    """A complete manifest for one raw source snapshot.

    Field set mirrors docs/ingestion-playbook.md "Required Manifest Fields" plus
    the row/key checks and checksum required before a dataset enters silver.
    """

    # --- identity ---------------------------------------------------------
    source_id: str  # e.g. "medsl_president_1976_2020"
    dataset_name: str  # human name
    source_owner: str  # e.g. "MIT Election Data and Science Lab"
    source_url: str
    acquisition_method: str  # "http_download" | "api" | "manual_export" | ...

    # --- timing / coverage ------------------------------------------------
    acquired_at: str  # ISO timestamp of the fetch
    snapshot_date: str  # logical snapshot date (YYYY-MM-DD)
    election_cycle: str  # "1976-2020" | "2024" | "multi"
    office_coverage: list[str]  # ["president","us_house","us_senate"]
    geography_coverage: list[str]  # ["state","county","district"]

    # --- payload ----------------------------------------------------------
    file_format: str  # "csv" | "parquet" | "shp_zip" | ...
    raw_path: str  # path under data/raw/
    checksum_sha256: str

    # --- governance -------------------------------------------------------
    license_or_terms: str
    permitted_use: str
    prohibited_use: str
    privacy_tier: int  # PrivacyTier value
    contains_personal_data: bool
    contains_sensitive_data: bool
    redistribution_allowed: bool
    update_cadence: str  # "static" | "per_cycle" | "live" | ...
    owner: str  # responsible person (data steward)
    review_date: str  # next governance review (YYYY-MM-DD)

    # --- quality / notes --------------------------------------------------
    validation_status: str = "pending"  # pending | passed | failed
    known_caveats: str = ""
    required_attribution: str = ""
    row_count: int | None = None
    unique_key: list[str] = field(default_factory=list)

    # --- bookkeeping ------------------------------------------------------
    schema_version: str = MANIFEST_SCHEMA_VERSION

    # ---------------------------------------------------------------- checks
    def __post_init__(self) -> None:
        # Enforce the public-repo tier boundary at construction time.
        tier = PrivacyTier(self.privacy_tier)
        assert_public_safe(tier, context=f"manifest for {self.source_id}")

    @property
    def snapshot_id(self) -> str:
        return f"{self.source_id}__{self.snapshot_date.replace('-', '_')}"

    def to_dict(self) -> dict:
        return asdict(self)

    def write(self, manifests_dir: str | Path = "data/manifests") -> Path:
        """Persist as ``data/manifests/<snapshot_id>.json`` and return the path."""
        out_dir = Path(manifests_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{self.snapshot_id}.json"
        out_path.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n")
        return out_path

    @classmethod
    def load(cls, path: str | Path) -> SourceManifest:
        data = json.loads(Path(path).read_text())
        return cls(**data)

    @classmethod
    def for_snapshot(
        cls,
        *,
        raw_path: str | Path,
        source_id: str,
        dataset_name: str,
        source_owner: str,
        source_url: str,
        privacy_tier: PrivacyTier,
        license_or_terms: str,
        permitted_use: str,
        prohibited_use: str,
        office_coverage: list[str],
        geography_coverage: list[str],
        election_cycle: str,
        owner: str,
        acquisition_method: str = "http_download",
        file_format: str = "csv",
        redistribution_allowed: bool = True,
        contains_personal_data: bool = False,
        contains_sensitive_data: bool = False,
        update_cadence: str = "per_cycle",
        required_attribution: str = "",
        known_caveats: str = "",
        review_months: int = 12,
    ) -> SourceManifest:
        """Build a manifest for a freshly downloaded snapshot, checksumming the file."""
        raw_path = Path(raw_path)
        checksum = sha256_file(raw_path)
        today = date.today()
        review = today.replace(year=today.year + (review_months // 12))
        return cls(
            source_id=source_id,
            dataset_name=dataset_name,
            source_owner=source_owner,
            source_url=source_url,
            acquisition_method=acquisition_method,
            acquired_at=_utcnow_iso(),
            snapshot_date=today.isoformat(),
            election_cycle=election_cycle,
            office_coverage=office_coverage,
            geography_coverage=geography_coverage,
            file_format=file_format,
            raw_path=str(raw_path),
            checksum_sha256=checksum,
            license_or_terms=license_or_terms,
            permitted_use=permitted_use,
            prohibited_use=prohibited_use,
            privacy_tier=int(privacy_tier),
            contains_personal_data=contains_personal_data,
            contains_sensitive_data=contains_sensitive_data,
            redistribution_allowed=redistribution_allowed,
            update_cadence=update_cadence,
            owner=owner,
            review_date=review.isoformat(),
            required_attribution=required_attribution,
            known_caveats=known_caveats,
        )


def json_schema() -> dict:
    """Return a JSON Schema (draft 2020-12) describing a manifest document.

    Useful for CI validation of committed manifests and for documenting the
    contract to non-Python agents.
    """
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "SourceManifest",
        "type": "object",
        "required": [
            "source_id",
            "dataset_name",
            "source_owner",
            "source_url",
            "acquisition_method",
            "acquired_at",
            "snapshot_date",
            "election_cycle",
            "office_coverage",
            "geography_coverage",
            "file_format",
            "raw_path",
            "checksum_sha256",
            "license_or_terms",
            "permitted_use",
            "prohibited_use",
            "privacy_tier",
            "contains_personal_data",
            "contains_sensitive_data",
            "redistribution_allowed",
            "update_cadence",
            "owner",
            "review_date",
        ],
        "properties": {
            "source_id": {"type": "string", "pattern": "^[a-z0-9_]+$"},
            "checksum_sha256": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
            "privacy_tier": {
                "type": "integer",
                "minimum": 0,
                "maximum": 2,
                "description": "Public repo accepts tiers 0-2 only (CLAUDE.md §5).",
            },
            "snapshot_date": {"type": "string", "format": "date"},
            "office_coverage": {"type": "array", "items": {"type": "string"}},
            "geography_coverage": {"type": "array", "items": {"type": "string"}},
            "validation_status": {"enum": ["pending", "passed", "failed"]},
        },
        "additionalProperties": True,
    }

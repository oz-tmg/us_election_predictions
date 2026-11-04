"""Immutable snapshots for individually registered public research sources."""

from datetime import UTC, datetime
from pathlib import Path

from . import acquire
from .manifest import SourceManifest, sha256_file
from .privacy import PrivacyTier


def snapshot(
    url: str,
    path: Path,
    *,
    source_id: str,
    owner: str,
    expect: str,
    cycle: str = "2026",
    tier: PrivacyTier = PrivacyTier.PUBLIC_AGGREGATE,
    redistribution_allowed: bool = False,
) -> Path:
    if not path.is_file():
        acquire.fetch(url, path, expect=expect)
    with path.open("rb") as handle:
        head = handle.read(4096)
    acquire._validate_body(head, expect=expect, url=url)
    if expect == "pdf" and not head.startswith(b"%PDF"):
        raise acquire.InvalidResponse("official PDF endpoint did not return a PDF")
    digest = sha256_file(path)
    for candidate in Path("data/manifests").glob(f"{source_id}_*__*.json"):
        previous = SourceManifest.load(candidate)
        if Path(previous.raw_path).resolve() != path.resolve():
            continue
        if previous.checksum_sha256 != digest or previous.source_url != url:
            raise acquire.InvalidResponse(f"registered source bytes or URL changed: {path}")
        return path
    manifest = SourceManifest.for_snapshot(
        raw_path=path,
        source_id=f"{source_id}_{digest[:12]}",
        dataset_name=path.name,
        source_owner=owner,
        source_url=url,
        privacy_tier=tier,
        license_or_terms="Registered public factual research use; cite provider and source URL.",
        permitted_use="Nonpartisan aggregate research; no contact fields in modeling tables.",
        prohibited_use="No solicitation, personal targeting, respondent records or advocacy optimization.",
        office_coverage=["us_house", "us_senate"],
        geography_coverage=["state", "district"],
        election_cycle=cycle,
        owner="Alex Oswald (data steward)",
        file_format=expect,
        redistribution_allowed=redistribution_allowed,
        contains_personal_data=tier == PrivacyTier.PUBLIC_PERSONAL,
        known_caveats="Checksum/integrity recorded at intake; substantive validation is a separate gate.",
        required_attribution=owner,
    )
    # Cached bytes were retrieved at their saved file time, not at this rebuild's time.
    acquired = datetime.fromtimestamp(path.stat().st_mtime, UTC)
    manifest.acquired_at = acquired.isoformat()
    manifest.snapshot_date = acquired.date().isoformat()
    manifest.write()
    return path

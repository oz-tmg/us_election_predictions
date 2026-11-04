"""Auditable source preservation and reachability checks, never a results scraper."""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

import pandas as pd

from ..geography.reference import STATES
from . import acquire
from .manifest import sha256_file

CATALOG = Path("data/reference/results_sources_2026.csv")
SOURCE_DIR = Path("data/raw/source=state_canvass_evidence")

#: ``extraction_status`` moves off ``manual_review_pending`` only when a parser reproduced
#: a past certified result from that state's own release (``state_extraction.reconcile``),
#: and the row then names the reconciliation report. Reachability is never enough.
EXTRACTION_STATUSES = {"manual_review_pending", "parser_tested_2024"}
#: How the release can be fetched, recorded apart from extraction so that a blocked site
#: never reads as a reviewed one.
DOWNLOAD_ACCESS = {"untested", "automated_ok", "blocked_manual_download"}


def load_catalog(path: Path = CATALOG) -> pd.DataFrame:
    frame = pd.read_csv(path, dtype=str).fillna("")
    required = {"state_po", "primary_url", "fallback_url", "extraction_status", "certification_evidence"}
    if not required.issubset(frame) or frame[list(required)].eq("").any().any():
        raise ValueError("results source inventory needs complete provenance and status")
    if frame.state_po.duplicated().any() or set(frame.state_po) != set(STATES) - {"DC", "PR"}:
        raise ValueError("results source inventory must contain exactly the 50 states")
    for column in ("primary_url", "fallback_url"):
        if (
            not frame[column]
            .map(lambda u: urlsplit(u).scheme == "https" and bool(urlsplit(u).hostname))
            .all()
        ):
            raise ValueError("official source URLs must be absolute HTTPS links")
    if "download_access" not in frame:
        frame["download_access"] = "untested"
    if "extraction_evidence" not in frame:
        frame["extraction_evidence"] = ""
    frame["download_access"] = frame["download_access"].replace("", "untested")
    if not frame.extraction_status.isin(EXTRACTION_STATUSES).all():
        raise ValueError(f"extraction_status must be one of {sorted(EXTRACTION_STATUSES)}")
    if not frame.download_access.isin(DOWNLOAD_ACCESS).all():
        raise ValueError(f"download_access must be one of {sorted(DOWNLOAD_ACCESS)}")
    tested = frame.extraction_status.eq("parser_tested_2024")
    if (frame.loc[tested, "extraction_evidence"] == "").any():
        raise ValueError("a parser_tested_2024 row must name its reconciliation report")
    return frame


def preserve_source(
    path: Path, *, state: str, url: str, retrieved_at: str, directory: Path = SOURCE_DIR
) -> Path:
    """Copy a reviewed public aggregate release, recording its actual retrieval time.

    The caller attests to the timestamp and aggregate-only review. This records evidence;
    it does not establish certification or that the file contains a particular contest.
    """
    timestamp = datetime.fromisoformat(retrieved_at.replace("Z", "+00:00"))
    if timestamp.tzinfo is None or timestamp > datetime.now(UTC):
        raise ValueError("retrieved_at needs an explicit timezone and cannot be in the future")
    if state not in set(STATES) - {"DC", "PR"}:
        raise ValueError("source state must be a voting congressional state")
    if urlsplit(url).scheme != "https" or not urlsplit(url).hostname:
        raise ValueError("source_url must be an absolute HTTPS URL")
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError("source release must be a nonempty local file")
    digest = sha256_file(path)
    stamp = timestamp.astimezone(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    target = directory / f"state={state}" / f"retrieved={stamp}" / f"sha256={digest}" / path.name
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("xb") as handle, path.open("rb") as source:
        shutil.copyfileobj(source, handle)
    evidence = {
        "state_po": state,
        "source_url": url,
        "retrieved_at": timestamp.isoformat(),
        "retrieved_on": timestamp.astimezone(UTC).date().isoformat(),
        "raw_path": str(target.resolve()),
        "checksum_sha256": digest,
        "privacy_tier": 0,
        "contains_personal_data": False,
        "review": "Caller attests public aggregate release; no inferred certification",
    }
    manifest = target.with_suffix(target.suffix + ".source.json")
    with manifest.open("x") as handle:
        json.dump(evidence, handle, indent=2)
    return manifest


def verify_evidence(frame: pd.DataFrame, paths: list[Path]) -> None:
    records = []
    for path in paths:
        record = json.loads(path.read_text())
        if record.get("privacy_tier") != 0 or record.get("contains_personal_data") is not False:
            raise ValueError("capture evidence must be reviewed public aggregate data")
        if sha256_file(record["raw_path"]) != record["checksum_sha256"]:
            raise ValueError(f"raw source checksum mismatch: {path}")
        records.append(record)
    for row in frame.to_dict(orient="records"):
        if not any(
            record["state_po"] == row["state_po"]
            and record["source_url"] == row["source_url"]
            and record["retrieved_on"] == str(row["retrieved_on"])[:10]
            for record in records
        ):
            raise ValueError(f"no preserved raw source for {row['state_po']} {row['source_url']}")


def probe_catalog(*, output: Path, timeout: int = 12) -> dict:
    """Retain landing HTML and discovered links; never label reachability extraction-ready."""
    from urllib.parse import urljoin

    from bs4 import BeautifulSoup

    if output.exists():
        raise FileExistsError("preserve the earlier readiness report; choose a new output")
    frame = load_catalog()
    report: dict = {"checked_at": datetime.now(UTC).isoformat(), "states": [], "outcomes_captured": 0}
    for row in frame.to_dict(orient="records"):
        attempts = []
        for role in ("primary_url", "fallback_url"):
            url = row[role]
            now = datetime.now(UTC)
            path = (
                Path("data/raw/source=state_canvass_readiness_2026")
                / now.strftime("snapshot=%Y-%m-%d")
                / row["state_po"]
                / role
                / "page.html"
            )
            try:
                if not path.exists():
                    acquire.fetch(url, path, expect="html", timeout=timeout)
                soup = BeautifulSoup(path.read_bytes(), "html.parser")
                links = [
                    {"label": a.get_text(" ", strip=True), "url": urljoin(url, str(a["href"]))}
                    for a in soup.find_all("a", href=True)
                    if any(
                        term in (a.get_text(" ", strip=True) + " " + str(a["href"])).lower()
                        for term in ("2026", "result", "canvass", "certif", ".csv", ".xlsx")
                    )
                ]
                attempts.append(
                    {
                        "role": role,
                        "url": url,
                        "status": "reachable_unvalidated",
                        "retrieved_at": datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat(),
                        "raw_path": str(path),
                        "sha256": sha256_file(path),
                        "candidate_links": links[:80],
                    }
                )
            except acquire.AcquisitionError as exc:
                attempts.append({"role": role, "url": url, "status": "unreadable", "error": str(exc)})
            print(f"source {row['state_po']} {role}: {attempts[-1]['status']}", flush=True)
        report["states"].append({**row, "attempts": attempts, "capture_ready": False})
    report["reachable_primary_states"] = sum(
        s["attempts"][0]["status"] == "reachable_unvalidated" for s in report["states"]
    )
    report["states_without_reachable_landing"] = [
        s["state_po"] for s in report["states"] if all(a["status"] == "unreadable" for a in s["attempts"])
    ]
    report["untested_extraction_states"] = frame.state_po.tolist()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x") as handle:
        json.dump(report, handle, indent=2)
    return report

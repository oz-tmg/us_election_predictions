"""As-of ALFRED observations for the explicitly registered federal economic series."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

import pandas as pd

from . import acquire
from .manifest import SourceManifest, sha256_file
from .privacy import PrivacyTier

SERIES = {
    "A229RX0": ("fred_bea_income_vintages", "U.S. Bureau of Economic Analysis / FRED"),
    "UNRATE": ("fred_bls_unemployment_vintages", "U.S. Bureau of Labor Statistics / FRED"),
    "CPIAUCSL": ("fred_bls_cpi_vintages", "U.S. Bureau of Labor Statistics / FRED"),
}
API = "https://api.stlouisfed.org/fred/series/observations"


class VintageUnavailable(ValueError):
    """The provider has no observations for the requested historical information set."""


def download(
    series_id: str,
    *,
    vintage: str,
    raw_dir: Path = Path("data/raw"),
    api_key: str | None = None,
) -> Path:
    if series_id not in SERIES:
        raise ValueError("unregistered economic series")
    cutoff = date.fromisoformat(vintage)
    if cutoff > date.today():
        raise ValueError("an economic vintage cannot be in the future")
    retrieved = date.today().isoformat()
    path = (
        raw_dir
        / f"source=fred_alfred/series={series_id}/vintage={vintage}/retrieved={retrieved}/observations.json"
    )
    if path.is_file():
        parse(path, series_id=series_id, vintage=vintage)
        return path
    key = api_key or os.getenv("FRED_API_KEY")
    if not key:
        raise acquire.CredentialRequired(
            "FRED_API_KEY is required for historical real-time observations",
            env_var="FRED_API_KEY",
            signup_url="https://fred.stlouisfed.org/docs/api/api_key.html",
        )
    query = {
        "series_id": series_id,
        "realtime_start": vintage,
        "realtime_end": vintage,
        "observation_start": f"{cutoff.year - 2}-01-01",
        "observation_end": vintage,
        "file_type": "json",
    }
    url = API + "?" + urllib.parse.urlencode({**query, "api_key": key})
    try:
        request = urllib.request.Request(url, headers={"User-Agent": acquire.USER_AGENT})
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        try:
            message = str(json.loads(exc.read()).get("error_message", "")).replace(key, "[redacted]")
        except ValueError:
            message = "non-JSON provider error"
        if exc.code == 400 and "does not exist in ALFRED" in message:
            raise VintageUnavailable(f"ALFRED {series_id} vintage {vintage}: {message}") from None
        if exc.code == 400:
            raise acquire.InvalidResponse(f"ALFRED rejected query for {series_id}: {message}") from None
        raise acquire.NetworkUnavailable(
            f"ALFRED {series_id} vintage {vintage} failed ({exc.code})"
        ) from None
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        # Never include the keyed URL, exception body or chained request in a report.
        code = getattr(exc, "code", type(exc).__name__)
        raise acquire.NetworkUnavailable(f"ALFRED {series_id} vintage {vintage} failed ({code})") from None
    if "observations" not in payload:
        raise acquire.InvalidResponse(f"ALFRED {series_id} returned no observation array")
    document = {"endpoint": API, "query": query, "retrieved_on": retrieved, "response": payload}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as handle:
        json.dump(document, handle, indent=2)
    frame = parse(path, series_id=series_id, vintage=vintage)
    source_id, owner = SERIES[series_id]
    manifest = SourceManifest.for_snapshot(
        raw_path=path,
        source_id=f"{source_id}_{vintage.replace('-', '')}_{sha256_file(path)[:10]}",
        dataset_name=f"{series_id} as known {vintage}",
        source_owner=owner,
        source_url=API + "?" + urllib.parse.urlencode(query),
        privacy_tier=PrivacyTier.PUBLIC_AGGREGATE,
        license_or_terms="Public domain; citation requested.",
        permitted_use="Nonpartisan aggregate research with explicit real-time vintage and attribution.",
        prohibited_use="Do not replace historical vintages with today's revised values or disclose API keys.",
        office_coverage=["us_house"],
        geography_coverage=["national"],
        election_cycle=str(cutoff.year),
        owner="Alex Oswald (data steward)",
        acquisition_method="api",
        file_format="json",
        required_attribution=owner,
        known_caveats="Point-in-time intervals are clipped; exact release_date is not inferred from cutoff.",
    )
    manifest.validation_status = "passed"
    manifest.row_count = len(frame)
    manifest.write()
    return path


def parse(path: Path, *, series_id: str, vintage: str) -> pd.DataFrame:
    payload = json.loads(path.read_text())
    query = payload["query"]
    if (
        query.get("series_id") != series_id
        or query.get("realtime_start") != vintage
        or query.get("realtime_end") != vintage
    ):
        raise ValueError("ALFRED query must pin the requested series and exact historical information set")
    response = payload["response"]
    if response.get("realtime_start") != vintage or response.get("realtime_end") != vintage:
        raise ValueError("ALFRED did not honor the requested historical vintage")
    observations = response["observations"]
    rows = []
    for observation in observations:
        value = pd.to_numeric(observation["value"], errors="coerce")
        if pd.isna(value):
            continue
        observed = pd.Timestamp(observation["date"])
        if observed > pd.Timestamp(vintage):
            raise ValueError("future observation leaked into an economic vintage")
        rows.append(
            {
                "series_id": series_id,
                "observation_date": observed.date().isoformat(),
                "value": float(value),
                "data_vintage": vintage,
                "known_by_date": vintage,
                "release_date": None,
                "retrieved_on": payload["retrieved_on"],
                "source_snapshot": str(path),
            }
        )
    out = pd.DataFrame(
        rows,
        columns=[
            "series_id",
            "observation_date",
            "value",
            "data_vintage",
            "known_by_date",
            "release_date",
            "retrieved_on",
            "source_snapshot",
        ],
    )
    if not out.empty and out.observation_date.duplicated().any():
        raise ValueError("duplicate economic observation dates")
    return out

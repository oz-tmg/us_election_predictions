"""Fetch each state's official 2026 results release with an honest client.

A fetcher exists for a state only when (1) the state's own release downloads with an
honest research user agent, certificate checks on, no block evaded, and (2) the state's
parser in ``state_parsers`` reproduced the 2024 certified result exactly
(``scripts/test_state_extraction.py``). ``FETCHERS`` is therefore the list of states the
daily capture can do unattended; every other state is a manual capture.

A fetcher returns the bytes as published plus the moment they were retrieved, and what
the file itself says about its status (``labelled``): it never decides certification.
"""

from __future__ import annotations

import http.cookiejar
import re
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

USER_AGENT = "SavepointAnalytics-election-research/1.0 (nonpartisan research)"
TIMEOUT = 120


@dataclass(frozen=True)
class FetchedRelease:
    state_po: str
    path: Path
    source_url: str
    retrieved_at: str  # ISO 8601 with an explicit UTC offset
    labelled: str  # "unofficial", "official" or "unknown": what the release says of itself


Fetcher = Callable[[Path], FetchedRelease]
FETCHERS: dict[str, Fetcher] = {}


def register(state: str) -> Callable[[Fetcher], Fetcher]:
    def wrap(fn: Fetcher) -> Fetcher:
        if state in FETCHERS:
            raise ValueError(f"fetcher for {state} already registered")
        FETCHERS[state] = fn
        return fn

    return wrap


def _opener() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def _get(opener: urllib.request.OpenerDirector, url: str, data: bytes | None = None) -> bytes:
    request = urllib.request.Request(url, data=data, headers={"User-Agent": USER_AGENT})
    with opener.open(request, timeout=TIMEOUT) as response:
        if response.status != 200:
            raise RuntimeError(f"{url} -> HTTP {response.status}")
        return response.read()


def _now() -> str:
    return datetime.now(UTC).isoformat()


NC_URL = "https://dl.ncsbe.gov/ENRS/2026_11_03/results_pct_20261103.zip"


@register("NC")
def north_carolina(dest: Path) -> FetchedRelease:
    """NCSBE precinct results, updated in place until certification. The file carries no
    status label; the State Board's certification is observed separately."""
    retrieved = _now()
    body = _get(_opener(), NC_URL)
    path = dest / "NC_2026GE_results_pct_20261103.zip"
    path.write_bytes(body)
    return FetchedRelease("NC", path, NC_URL, retrieved, "unknown")


MT_URL = "https://electionresults.mt.gov/ResultsExport.aspx"


@register("MT")
def montana(dest: Path) -> FetchedRelease:
    """Montana results export: the statewide workbook is the page's own "Statewide Export"
    post-back (``__EVENTTARGET=ctl00$MainContent$Statewide``), the request a click makes.
    The workbook's first line states whether the results are unofficial."""
    opener = _opener()
    page = _get(opener, MT_URL).decode("utf-8", "replace")
    fields = dict(re.findall(r'<input type="hidden" name="([^"]+)" id="[^"]*" value="([^"]*)"', page))
    if "__VIEWSTATE" not in fields:
        raise RuntimeError("Montana export page changed: no __VIEWSTATE form field")
    fields.update({"__EVENTTARGET": "ctl00$MainContent$Statewide", "__EVENTARGUMENT": ""})
    retrieved = _now()
    body = _get(opener, MT_URL, urllib.parse.urlencode(fields).encode())
    if not body.startswith(b"PK"):
        raise RuntimeError("Montana export did not return a workbook")
    path = dest / "MT_2026GE_Statewide_Results.xlsx"
    path.write_bytes(body)
    return FetchedRelease("MT", path, MT_URL, retrieved, _montana_label(path))


def _montana_label(path: Path) -> str:
    import openpyxl

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        first = str(next(wb.worksheets[-1].iter_rows(max_row=1, values_only=True))[0] or "").upper()
    finally:
        wb.close()
    if "UNOFFICIAL" in first:
        return "unofficial"
    return "official" if "OFFICIAL" in first else "unknown"


WV_BASE = "https://results.enr.clarityelections.com/WV/127496"


@register("WV")
def west_virginia(dest: Path) -> FetchedRelease:
    """WV SOS on Clarity: the current version number, then that version's summary.zip.
    The results page states "Unofficial Results" until the canvass; the zip carries no
    status, so it is reported as unknown and certification is observed separately."""
    opener = _opener()
    version = _get(opener, f"{WV_BASE}/current_ver.txt").decode().strip()
    if not version.isdigit():
        raise RuntimeError(f"unexpected Clarity version {version!r}")
    url = f"{WV_BASE}/{version}/reports/summary.zip"
    retrieved = _now()
    body = _get(opener, url)
    path = dest / f"WV_2026GE_{version}_summary.zip"
    path.write_bytes(body)
    return FetchedRelease("WV", path, url, retrieved, "unknown")


UT_URL = "https://electionresults.utah.gov/cdn/results/Utah/export-General11032026.json"


@register("UT")
def utah(dest: Path) -> FetchedRelease:
    """Utah Lt. Governor's results export (the page's own media export path)."""
    retrieved = _now()
    body = _get(_opener(), UT_URL)
    path = dest / "UT_2026GE_export-General11032026.json"
    path.write_bytes(body)
    return FetchedRelease("UT", path, UT_URL, retrieved, "unknown")


VT_STATIC = "https://static.electionresults.vermont.gov/"
VT_INDEX = VT_STATIC + "elections/68d61e96-1d28-4210-8c1d-8e90512ae105.json"


@register("VT")
def vermont(dest: Path) -> FetchedRelease:
    """Vermont SOS: the election index names the current federal file (renamed on every
    update) and states ``isOfficial``."""
    import json

    opener = _opener()
    index = json.loads(_get(opener, VT_INDEX))
    rel = str(index["federal"]["path"]).replace("\\", "/")
    url = VT_STATIC + rel.lstrip("/")
    retrieved = _now()
    body = _get(opener, url)
    path = dest / f"VT_2026GE_{Path(rel).name}"
    path.write_bytes(body)
    official = str(index.get("electionDetails", {}).get("isOfficial", "")).lower()
    labelled = "official" if official == "true" else "unofficial" if official == "false" else "unknown"
    return FetchedRelease("VT", path, url, retrieved, labelled)


WY_URL = "https://sos.wyo.gov/Elections/Docs/2026/Results/General/2026_Wyoming_General_Results.zip"


@register("WY")
def wyoming(dest: Path) -> FetchedRelease:
    """Wyoming SOS results zip; its workbook names say OFFICIAL or not."""
    import zipfile

    retrieved = _now()
    body = _get(_opener(), WY_URL)
    path = dest / "WY_2026GE_Wyoming_General_Results.zip"
    path.write_bytes(body)
    with zipfile.ZipFile(path) as zf:
        names = " ".join(zf.namelist()).upper()
    labelled = "unofficial" if "UNOFFICIAL" in names else "official" if "OFFICIAL" in names else "unknown"
    return FetchedRelease("WY", path, WY_URL, retrieved, labelled)

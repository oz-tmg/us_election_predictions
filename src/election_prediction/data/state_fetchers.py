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
    # "results" files carry votes; "support" files (e.g. contest or party name lookups)
    # are preserved as evidence and passed alongside every results file when extracting.
    role: str = "results"


Fetcher = Callable[[Path], "FetchedRelease | list[FetchedRelease]"]
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


def _get(
    opener: urllib.request.OpenerDirector,
    url: str,
    data: bytes | None = None,
    headers: dict[str, str] | None = None,
) -> bytes:
    request = urllib.request.Request(url, data=data, headers={"User-Agent": USER_AGENT, **(headers or {})})
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


MN_BASE = "https://electionresultsfiles.sos.mn.gov/20261103/"


@register("MN")
def minnesota(dest: Path) -> list[FetchedRelease]:
    """Minnesota SOS media files: statewide U.S. House and U.S. Senate text files. The
    HTML results site rate-limits with a captcha; these files are served for media use."""
    opener = _opener()
    out = []
    for name in ("ushouse.txt", "ussenate.txt"):
        retrieved = _now()
        body = _get(opener, MN_BASE + name)
        path = dest / f"MN_2026GE_{name}"
        path.write_bytes(body)
        out.append(FetchedRelease("MN", path, MN_BASE + name, retrieved, "unknown"))
    return out


SC_BASE = "https://www.enr-scvotes.org/SC"
SC_GENERAL, SC_RECOUNTS = "127300", ("127592",)


@register("SC")
def south_carolina(dest: Path) -> list[FetchedRelease]:
    """SC Election Commission on Clarity: the general election, then each recount election
    (published separately; its races replace the general's). Versions from current_ver.txt."""
    opener = _opener()
    out = []
    for election, tag in [(SC_GENERAL, "general"), *((e, "recount") for e in SC_RECOUNTS)]:
        version = _get(opener, f"{SC_BASE}/{election}/current_ver.txt").decode().strip()
        if not version.isdigit():
            raise RuntimeError(f"unexpected Clarity version {version!r} for {election}")
        url = f"{SC_BASE}/{election}/{version}/reports/summary.zip"
        retrieved = _now()
        body = _get(opener, url)
        path = dest / f"SC_2026GE_{tag}_{election}_{version}_summary.zip"
        path.write_bytes(body)
        out.append(FetchedRelease("SC", path, url, retrieved, "unknown"))
    return out


LA_BASE = "https://voterportal.sos.la.gov/ElectionResults/ElectionResults/Data?blob=20261103/csv/"
#: Senate and CD1-CD6 race IDs for the 2026-11-03 election (voter portal ElectionRaces).
LA_RACES = ("67997", "70195", "70196", "70197", "70198", "70199", "70200")


@register("LA")
def louisiana(dest: Path) -> list[FetchedRelease]:
    """Louisiana SOS voter portal: one by-parish CSV per federal race."""
    opener = _opener()
    out = []
    for race in LA_RACES:
        url = f"{LA_BASE}ByParish_{race}.csv"
        retrieved = _now()
        body = _get(opener, url)
        path = dest / f"LA_2026GE_ByParish_{race}.csv"
        path.write_bytes(body)
        out.append(FetchedRelease("LA", path, url, retrieved, "unknown"))
    return out


GA_API = "https://results.sos.ga.gov/results/public/api/elections/Georgia/11032026GeneralAndSpecialElection"
GA_CDN = "https://results.sos.ga.gov/cdn/results/"


def _find_report(node: object, name: str) -> dict | None:
    if isinstance(node, dict):
        if node.get("reportName") == name and node.get("blobName"):
            return node
        children: list[object] = list(node.values())
    elif isinstance(node, list):
        children = list(node)
    else:
        return None
    for child in children:
        found = _find_report(child, name)
        if found:
            return found
    return None


def _published_report(
    *, state: str, api: str, cdn: str, report_name: str, filename: str, dest: Path
) -> FetchedRelease:
    """Results platforms (GA, VA) whose elections API names each public report's current
    blob (renamed on every publish) and states ``isOfficialResults``. The report is
    matched by its exact name, so an unrequested report (e.g. an absentee raw-data file,
    which may hold personal records) can never be fetched by accident."""
    import json

    opener = _opener()
    meta = json.loads(_get(opener, api))
    report = _find_report(meta, report_name)
    if report is None:
        raise RuntimeError(f"{state} API lists no {report_name!r} report")
    url = cdn + meta["jurisdictionId"] + "/" + urllib.parse.quote(report["blobName"])
    retrieved = _now()
    body = _get(opener, url)
    path = dest / filename
    path.write_bytes(body)
    official = meta.get("isOfficialResults")
    labelled = "official" if official is True else "unofficial" if official is False else "unknown"
    return FetchedRelease(state, path, url, retrieved, labelled)


@register("GA")
def georgia(dest: Path) -> FetchedRelease:
    """Georgia SOS "Total Votes Excel" report."""
    return _published_report(
        state="GA",
        api=GA_API,
        cdn=GA_CDN,
        report_name="Total Votes Excel",
        filename="GA_2026GE_TotalVotes.xlsx",
        dest=dest,
    )


VA_API = "https://enr.elections.virginia.gov/results/public/api/elections/Virginia/2026-November-General"
VA_CDN = "https://enr.elections.virginia.gov/cdn/results/"


@register("VA")
def virginia(dest: Path) -> FetchedRelease:
    """Virginia ELECT "Election Results" CSV (precinct-level aggregate results)."""
    return _published_report(
        state="VA",
        api=VA_API,
        cdn=VA_CDN,
        report_name="Election Results",
        filename="VA_2026GE_ElectionResults.csv",
        dest=dest,
    )


def _clarity(state: str, base: str, report: str, filename_prefix: str, dest: Path) -> FetchedRelease:
    """A Clarity/Scytl election: current_ver.txt gives the live version, then that
    version's report zip (``summary.zip`` or ``detailxml.zip``)."""
    opener = _opener()
    version = _get(opener, f"{base}/current_ver.txt").decode().strip()
    if not version.isdigit():
        raise RuntimeError(f"unexpected Clarity version {version!r} at {base}")
    url = f"{base}/{version}/reports/{report}"
    retrieved = _now()
    body = _get(opener, url)
    path = dest / f"{filename_prefix}_{version}_{report}"
    path.write_bytes(body)
    return FetchedRelease(state, path, url, retrieved, "unknown")


@register("CO")
def colorado(dest: Path) -> FetchedRelease:
    """Colorado SOS on Clarity (election 127407): detailxml.zip (no summary report)."""
    return _clarity(
        "CO", "https://results.enr.clarityelections.com/CO/127407", "detailxml.zip", "CO_2026GE", dest
    )


PA_REPORT = "https://www.electionreturns.pa.gov/api/Reports/GenerateReport"
#: The Report Center's own "Generate" request: 2026 General (ElectionID 117, subtype G),
#: Representative in Congress (OfficeID 11), county-level CSV. One request a day; the
#: page adds a reCAPTCHA only after 50 submissions, which this never approaches.
PA_BODY = {
    "ElectionID": 117,
    "ElectionsubType": "G",
    "OfficeIds": [11],
    "RetOfficeIds": [],
    "PartyIds": [],
    "DistrictIds": [],
    "CandidateIds": [],
    "CountyIds": [],
    "ReferendumIds": [],
    "ReferendumDetailIds": [],
    "ExportType": "C",
    "ReportType": "C",
    "FileName": "UnOfficial",
}


@register("PA")
def pennsylvania(dest: Path) -> FetchedRelease:
    """Pennsylvania DOS Report Center county CSV for U.S. House (no 2026 Senate race)."""
    import json

    retrieved = _now()
    body = _get(
        _opener(), PA_REPORT, json.dumps(PA_BODY).encode(), headers={"Content-Type": "application/json"}
    )
    if b"Office Name" not in body[:500]:
        raise RuntimeError("Pennsylvania report did not return the expected CSV")
    path = dest / "PA_2026GE_county_USC.csv"
    path.write_bytes(body)
    return FetchedRelease("PA", path, PA_REPORT, retrieved, "unknown")


AR_API = "https://enr-results-api.totalresults.com/"
AR_ELECTION = "11b07106-031e-4d7c-911a-d01fb473d6dd"


@register("AR")
def arkansas(dest: Path) -> list[FetchedRelease]:
    """Arkansas SOS results (tally-enr) JSON API: federal contest results plus the contest
    and party name lookups needed to label them; ``isOfficial`` from the election info."""
    import json

    opener = _opener()
    parts = [
        (
            "Contest/GetContestResults?cId=arkansas&electionID={e}&contestType=Federal",
            "federal_results",
            "results",
        ),
        ("Contest/GetContestSearchList?cid=arkansas&electionID={e}", "contestlist", "support"),
        ("Election/GetElectionInfo?cId=arkansas&electionID={e}", "electioninfo", "support"),
    ]
    out = []
    labelled = "unknown"
    for query, tag, role in parts:
        url = AR_API + query.format(e=AR_ELECTION)
        retrieved = _now()
        body = _get(opener, url)
        path = dest / f"AR_2026GE_{tag}.json"
        path.write_bytes(body)
        if tag == "electioninfo":
            official = json.loads(body).get("isOfficial")
            labelled = "official" if official is True else "unofficial" if official is False else "unknown"
        out.append(FetchedRelease("AR", path, url, retrieved, "unknown", role))
    return [FetchedRelease(r.state_po, r.path, r.source_url, r.retrieved_at, labelled, r.role) for r in out]


DE_URL = "https://data.delaware.gov/resource/4hbv-7brf.csv?electiondate=2026-11-03T00:00:00.000"


@register("DE")
def delaware(dest: Path) -> FetchedRelease:
    """Delaware Department of Elections results via the state open-data portal (the
    results page's own "Download CSV Report" button)."""
    retrieved = _now()
    body = _get(_opener(), DE_URL)
    path = dest / "DE_2026GE_statewide_opendata.csv"
    path.write_bytes(body)
    return FetchedRelease("DE", path, DE_URL, retrieved, "unknown")


IN_BASE = "https://enr.indianavoters.in.gov/site/"


@register("IN")
def indiana(dest: Path) -> FetchedRelease:
    """Indiana Election Division results download (``AllOfficeResults.csv``); the site's
    ``settings.json`` states whether results are certified."""
    import json

    opener = _opener()
    settings = json.loads(_get(opener, IN_BASE + "data/settings.json"))
    url = IN_BASE + "download/AllOfficeResults.csv"
    retrieved = _now()
    body = _get(opener, url)
    path = dest / "IN_2026GE_AllOfficeResults.csv"
    path.write_bytes(body)
    flag = str(settings.get("Root", settings).get("Certified", "")).upper()
    labelled = "official" if flag == "T" else "unofficial" if flag == "F" else "unknown"
    return FetchedRelease("IN", path, url, retrieved, labelled)


HI_URL = "https://elections.hawaii.gov/wp-content/results/2026%20General/summary.txt"


@register("HI")
def hawaii(dest: Path) -> FetchedRelease:
    """Hawaii Office of Elections statewide ``summary.txt``."""
    retrieved = _now()
    body = _get(_opener(), HI_URL)
    path = dest / "HI_2026GE_summary.txt"
    path.write_bytes(body)
    return FetchedRelease("HI", path, HI_URL, retrieved, "unknown")

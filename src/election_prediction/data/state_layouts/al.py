"""Alabama: 2024 certified precinct workbooks; 2026 election-night "Export Data" workbook.

Both come from the Secretary of State's reporting system and share contest titles
(``UNITED STATES REPRESENTATIVE, 6TH CONGRESSIONAL DISTRICT``) and party codes, but the
2024 certified release is one wide precinct ``.xls`` per county in a ZIP, and the 2026
release is one long county-by-candidate ``.xlsx``. Neither prints a contest total, so
both parsers sum; the 2026 sums are cross-checked against the totals the state prints on
its statewide results page.
"""

from __future__ import annotations

import io
import re
import urllib.parse
import zipfile
from collections.abc import Iterable, Sequence
from pathlib import Path

import pandas as pd

from .. import state_fetchers
from ..state_extraction import from_candidates, register, register_historical
from ..state_fetchers import FetchedRelease

_SENATE = re.compile(r"^UNITED STATES SENATOR$")
_HOUSE = re.compile(r"^UNITED STATES REPRESENTATIVE, (\d{1,2})(?:ST|ND|RD|TH) CONGRESSIONAL DISTRICT$")
_FEDERAL = re.compile(r"^UNITED STATES (SENAT|REPRESENTATIVE)")
_SPECIAL = re.compile(r"SPECIAL|UNEXPIRED|VACANCY")
_NOT_VOTES = {"OVER VOTES", "UNDER VOTES"}


def _contest(title: str) -> tuple[str, int | None] | None:
    """The race a contest title names, ``None`` for other offices and special contests."""
    text = " ".join(str(title).upper().split())
    if not _FEDERAL.match(text):
        return None
    if _SPECIAL.search(text):
        return None
    if _SENATE.match(text):
        return "us_senate", None
    if m := _HOUSE.match(text):
        return "us_house", int(m.group(1))
    raise ValueError(f"AL: unrecognized federal contest title {title!r}")


def _races(candidates: pd.DataFrame, *, source: str) -> pd.DataFrame:
    """Race rows from long rows (``office``, ``district``, ``candidate``, ``party``, ``votes``)."""
    if candidates.empty:
        raise ValueError(f"{source}: no U.S. House or Senate contest found")
    rows = []
    for (office, district), group in candidates.groupby(["office", "district"], dropna=False):
        by_candidate = group.groupby(["candidate", "party"], as_index=False)["votes"].sum()
        rows.append(
            from_candidates(
                by_candidate,
                state_po="AL",
                office=str(office),
                district_num=None if office == "us_senate" else int(district),
            )
        )
    return pd.DataFrame(rows)


def _int(value: object, *, where: str) -> int:
    text = str(value).replace(",", "").strip()
    if text in {"", "nan", "None"}:
        return 0
    number = float(text)
    if number != int(number) or number < 0:
        raise ValueError(f"{where}: vote count {value!r} is not a non-negative whole number")
    return int(number)


# --------------------------------------------------------------------------- 2024 format


def precinct_sheet_candidates(sheet: pd.DataFrame, *, source: str) -> list[dict[str, object]]:
    """Federal candidate rows of one county's ``Precinct Results`` sheet (read header-less).

    Columns are ``Contest Title``, ``Party``, ``Candidate`` and then one column per
    precinct plus ``ABSENTEE`` and ``PROVISIONAL``; there is no total column, so a
    candidate's county vote is the sum across all of them. ``Over Votes`` and ``Under
    Votes`` rows (blank party) are not votes.
    """
    header = [str(v).strip() for v in sheet.iloc[0].tolist()]
    if header[:3] != ["Contest Title", "Party", "Candidate"] or len(header) < 4:
        raise ValueError(f"{source}: expected Contest Title/Party/Candidate then precinct columns")
    out: list[dict[str, object]] = []
    for i, row in enumerate(sheet.iloc[1:].itertuples(index=False), start=2):
        contest = _contest(row[0])
        if contest is None:
            continue
        party, name = str(row[1]).strip(), str(row[2]).strip()
        party = "" if party == "nan" else party
        if name.upper() in _NOT_VOTES:
            continue
        if not party:
            raise ValueError(f"{source} row {i}: candidate {name!r} has no party code")
        votes = sum(_int(v, where=f"{source} row {i}") for v in row[3:])
        out.append(
            {"office": contest[0], "district": contest[1], "candidate": name, "party": party, "votes": votes}
        )
    return out


def _county_workbooks(paths: Sequence[Path]) -> Iterable[tuple[str, bytes]]:
    for path in paths:
        if path.suffix.lower() == ".zip":
            with zipfile.ZipFile(path) as zf:
                names = [n for n in zf.namelist() if n.lower().endswith(".xls")]
                if not names:
                    raise ValueError(f"{path.name}: no county .xls workbook inside")
                for name in sorted(names):
                    yield name, zf.read(name)
        elif path.suffix.lower() == ".xls":
            yield path.name, path.read_bytes()
        else:
            raise ValueError(f"{path.name}: expected the precinct-results ZIP or a county .xls")


@register_historical("AL")
def alabama_2024(paths: Sequence[Path]) -> pd.DataFrame:
    """2024 certified "General Precinct Level Results" ZIP: one BIFF ``.xls`` per county.

    Reading BIFF needs ``xlrd`` (not a project dependency: this format is only read to
    prove the historical path).
    """
    try:
        import xlrd  # noqa: F401
    except ImportError as exc:  # pragma: no cover - environment
        raise ImportError("AL 2024 county workbooks are BIFF .xls: install xlrd>=2.0.1") from exc
    records: list[dict[str, object]] = []
    counties = 0
    for name, raw in _county_workbooks(paths):
        sheets = pd.read_excel(io.BytesIO(raw), sheet_name=None, header=None, dtype=str, engine="xlrd")
        if list(sheets) != ["Precinct Results"]:
            raise ValueError(f"{name}: expected one sheet 'Precinct Results', found {list(sheets)}")
        found = precinct_sheet_candidates(sheets["Precinct Results"], source=name)
        if not found:
            raise ValueError(f"{name}: no federal contest in county workbook")
        records.extend(found)
        counties += 1
    if counties != 67:
        raise ValueError(f"AL: expected 67 county workbooks, read {counties}")
    return _races(pd.DataFrame(records), source="AL 2024 precinct results")


# --------------------------------------------------------------------------- 2026 format

_EXPORT_COLUMNS = [
    "Election Title",
    "County Code",
    "Contest Code",
    "Contest Title",
    "Candidate Number",
    "Candidate Name",
    "Votes",
    "Party Code",
]


def export_candidates(table: pd.DataFrame, *, source: str) -> pd.DataFrame:
    """Federal candidate rows of the export's ``AllResults`` sheet (county x candidate)."""
    missing = [c for c in _EXPORT_COLUMNS if c not in table.columns]
    if missing:
        raise ValueError(f"{source}: AllResults sheet missing columns {missing}")
    titles = {str(t).strip().upper() for t in table["Election Title"].unique()}
    if len(titles) != 1 or "GENERAL ELECTION" not in next(iter(titles)) or "SPECIAL" in next(iter(titles)):
        raise ValueError(f"{source}: expected one general election, found {sorted(titles)}")
    keys = ["County Code", "Contest Code", "Candidate Number"]
    if table.duplicated(keys).any():
        raise ValueError(f"{source}: repeated county/contest/candidate rows")
    records = []
    for i, row in enumerate(table.to_dict(orient="records"), start=2):
        contest = _contest(row["Contest Title"])
        if contest is None:
            continue
        name = str(row["Candidate Name"]).strip()
        if name.upper() in _NOT_VOTES:
            continue
        party = str(row["Party Code"]).strip()
        if not party or party == "nan":
            raise ValueError(f"{source} row {i}: candidate {name!r} has no party code")
        records.append(
            {
                "office": contest[0],
                "district": contest[1],
                "candidate": f"{row['Candidate Number']}|{name}",
                "party": party,
                "votes": _int(row["Votes"], where=f"{source} row {i}"),
                "contest_code": str(row["Contest Code"]).strip(),
            }
        )
    out = pd.DataFrame(records)
    if len(out) and (out.groupby(["office", "district"], dropna=False)["contest_code"].nunique() != 1).any():
        raise ValueError(f"{source}: one race title under several contest codes")
    return out


@register("AL")
def alabama(paths: Sequence[Path]) -> pd.DataFrame:
    """Election-night reporting "Export Data" workbook (``sosEnrExport.xlsx``).

    Sheet ``AllResults`` has one row per county, contest and candidate; a race total is
    the sum over the counties. Write-ins (party ``NON``) count as other votes.
    """
    frames = []
    for path in paths:
        sheets = pd.read_excel(path, sheet_name=None, dtype=str, engine="openpyxl")
        if "AllResults" not in sheets:
            raise ValueError(f"{path.name}: no AllResults sheet (found {list(sheets)})")
        frames.append(export_candidates(sheets["AllResults"], source=path.name))
    if len(frames) != 1:
        raise ValueError(f"AL: expected exactly one export workbook, got {len(frames)}")
    return _races(frames[0], source="AL export")


# --------------------------------------------------------------------------- fetcher

AL_URL = "https://www2.alabamavotes.gov/electionNight/statewideResultsByContest.aspx?ecode=1001305"
_HIDDEN = re.compile(r'<input type="hidden" name="([^"]+)" id="[^"]*" value="([^"]*)"')
_HEADING = re.compile(r"<h2>\s*([^<]*Results[^<]*)</h2>", re.IGNORECASE)


def page_label(page: str) -> str:
    """What the results page calls itself in its heading (``Unofficial Election Night Results``)."""
    match = _HEADING.search(page)
    heading = match.group(1).upper() if match else ""
    if "UNOFFICIAL" in heading:
        return "unofficial"
    return "official" if "OFFICIAL" in heading else "unknown"


@state_fetchers.register("AL")
def fetch_alabama(dest: Path) -> FetchedRelease:
    """The statewide results page's own "Export Data" post-back (``hlnkExportData``), the
    request a click on that link makes. The status label is the page's heading."""
    opener = state_fetchers._opener()
    page = state_fetchers._get(opener, AL_URL).decode("utf-8", "replace")
    fields = dict(_HIDDEN.findall(page))
    if "__VIEWSTATE" not in fields or "hlnkExportData" not in page:
        raise RuntimeError("Alabama results page changed: no Export Data post-back form")
    fields.update({"__EVENTTARGET": "hlnkExportData", "__EVENTARGUMENT": ""})
    retrieved = state_fetchers._now()
    body = state_fetchers._get(opener, AL_URL, urllib.parse.urlencode(fields).encode())
    if not body.startswith(b"PK"):
        raise RuntimeError("Alabama Export Data did not return a workbook")
    path = dest / "AL_2026GE_sosEnrExport.xlsx"
    path.write_bytes(body)
    return FetchedRelease("AL", path, AL_URL, retrieved, page_label(page))


_PAGE_CONTEST = re.compile(
    r'<td class="enrContestHeader">([^<]*)</td>(.*?)(?=<td class="enrContestHeader">|\Z)', re.S
)
_PAGE_CANDIDATE = re.compile(
    r'enrCandNameCol"[^>]*>([^<]*?)\(([A-Z]{2,4})\)\s*</td>.*?'
    r'enrCandVoteNumCol">\s*<div class="numberValue">\s*([\d,]+)\s*</div>',
    re.S,
)


def page_totals(page: str) -> pd.DataFrame:
    """Contest totals as printed on the statewide results page (``office``, ``district_num``,
    ``dem_votes``, ``rep_votes``): the state's own sums, used to cross-check the export."""
    rows = []
    for title, block in _PAGE_CONTEST.findall(page):
        contest = _contest(title)
        if contest is None:
            continue
        found = _PAGE_CANDIDATE.findall(block)
        if not found:
            raise ValueError(f"AL page: no candidate rows under {title.strip()!r}")
        votes = {"DEM": 0, "REP": 0}
        for _name, party, count in found:
            if party in votes:
                votes[party] += int(count.replace(",", ""))
        rows.append(
            {
                "office": contest[0],
                "district_num": contest[1],
                "dem_votes": votes["DEM"],
                "rep_votes": votes["REP"],
            }
        )
    if not rows:
        raise ValueError("AL page: no federal contest found")
    return pd.DataFrame(rows)

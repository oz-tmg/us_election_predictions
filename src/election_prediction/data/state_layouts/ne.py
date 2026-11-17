"""Nebraska: 2024 certified Canvass Book (PDF only); 2026 election-night CSV exports.

Nebraska's certified 2024 result is published only as the Board of State Canvassers'
Canvass Book, a PDF with one county-by-candidate table per contest and a printed
``Total`` row. The 2026 release is the results site's "Results Media" CSV export: one
file per contest type (``type=CG`` for congressional districts, ``type=SW`` for statewide
contests, which holds the Senate race), each row a candidate's district or statewide
total.

The 2024 parser reads the PDF's text layer and accepts a table only when its county rows
add up to the printed ``Total`` row, column by column, so nothing is taken from a
mis-read line. The Senate seat on the regular six-year term is the race; a two-year
(unexpired term) Senate contest is a special election and is skipped in both formats.
"""

from __future__ import annotations

import csv
import io
import re
from collections.abc import Sequence
from pathlib import Path

import pandas as pd

from .. import state_fetchers
from ..state_extraction import from_candidates, register, register_historical
from ..state_fetchers import FetchedRelease
from ..state_parsers import _decode

# --- 2024: Canvass Book PDF ---------------------------------------------------------

_DASH = "[–—-]"
_PDF_SENATE = re.compile(rf"^Member of the United States Senate {_DASH} (\w+) Year Term$")
_PDF_HOUSE_SECTION = "Member of the U.S. House of Representatives"
_PDF_HOUSE = re.compile(rf"^Congressional District (\d{{1,2}}) {_DASH} (\w+) Year Term$")
_PDF_PAGE = re.compile(r"^General Election .* Page \| \d+$")
_PDF_COLUMN = re.compile(r"\(([^()]+)\)|Write-In\s+Scatterings")
_PDF_NUMBERS = re.compile(r"^(?P<name>.*?)(?P<numbers>(?: +[\d,]+)+)$")


def _numbers(text: str) -> list[int]:
    return [int(n.replace(",", "")) for n in text.split()]


def canvass_lines(lines: Sequence[str], *, source: str = "") -> list[dict[str, object]]:
    """The Canvass Book text layer, one race row per U.S. Senate / House contest.

    A contest starts at its heading line (``Member of the United States Senate – Six Year
    Term``; ``Congressional District N – Two Year Term`` once the House section heading has
    been seen, which the presidential by-district tables precede).
    Its table header runs from ``County`` to the ``Total`` row: one column per candidate,
    each ending in a parenthesised party, plus an optional ``Write-In Scatterings`` column.
    County rows follow (the header repeats on a new page) until the first line that is
    neither a county row nor a header or page line.
    """
    text = [" ".join(ln.split()) for ln in lines]
    text = [ln for ln in text if ln]
    rows: list[dict[str, object]] = []
    in_house = False
    i = 0
    while i < len(text):
        line = text[i]
        i += 1
        contest: tuple[str, int | None] | None = None
        if m := _PDF_SENATE.match(line):
            in_house = False
            if m.group(1) != "Six":  # an unexpired (two-year) term: a special election
                continue
            contest = ("us_senate", None)
        elif line == _PDF_HOUSE_SECTION:
            in_house = True
        elif in_house and (m := _PDF_HOUSE.match(line)):
            if m.group(2) != "Two":
                continue
            contest = ("us_house", int(m.group(1)))
        if contest is None:
            continue
        label = f"{source}: '{line}'"
        if i >= len(text) or text[i] != "County":
            raise ValueError(f"{label} is not followed by a County table")
        header: list[str] = []
        while i < len(text) and not text[i].startswith("Total "):
            header.append(text[i])
            i += 1
        if i >= len(text):
            raise ValueError(f"{label} has no Total row")
        parties = [
            m.group(1) if m.group(1) else "Write-in" for m in _PDF_COLUMN.finditer(" ".join(header[1:]))
        ]
        totals = _numbers(text[i][len("Total ") :]) if _PDF_NUMBERS.match(text[i]) else []
        if not parties or len(totals) != len(parties):
            raise ValueError(f"{label}: {len(parties)} candidate columns, Total row '{text[i]}'")
        i += 1
        sums = [0] * len(parties)
        counties = 0
        repeated = set(header)
        while i < len(text):
            row = text[i]
            if row in repeated or _PDF_PAGE.match(row):
                i += 1
                continue
            m = _PDF_NUMBERS.match(row)
            if not m or not m.group("name") or len(_numbers(m.group("numbers"))) != len(parties):
                break
            sums = [a + b for a, b in zip(sums, _numbers(m.group("numbers")), strict=True)]
            counties += 1
            i += 1
        if sums != totals:
            raise ValueError(f"{label}: {counties} county rows sum to {sums}, printed Total {totals}")
        frame = pd.DataFrame({"party": parties, "votes": totals})
        rows.append(from_candidates(frame, state_po="NE", office=contest[0], district_num=contest[1]))
    return rows


@register_historical("NE")
def nebraska_2024(paths: Sequence[Path]) -> pd.DataFrame:
    """Board of State Canvassers' General Election Canvass Book PDF (text layer)."""
    from pypdf import PdfReader

    rows: list[dict[str, object]] = []
    for path in paths:
        lines = [ln for page in PdfReader(path).pages for ln in (page.extract_text() or "").splitlines()]
        rows.extend(canvass_lines(lines, source=path.name))
    if not rows:
        raise ValueError("NE: no U.S. House or Senate contest found in the canvass book")
    return pd.DataFrame(rows)


# --- 2026: Results Media CSV export -------------------------------------------------

_CSV_HEADER = [
    "RaceID",
    "RaceName",
    "PartyCode",
    "AreaType",
    "AreaNum",
    "OfficeSeqNo",
    "BallotOrder",
    "CandidateID",
    "CandidateName",
    "CurrentDateTime",
    "VoteFor",
    "CandidateVotes",
    "CandidatePercentage",
    "PrecinctsReporting",
]
_CSV_FEDERAL = re.compile(r"CONGRESS|UNITED STATES SENAT|U\.?S\.? (SENAT|REPRESENTATIVE|HOUSE)")
_CSV_SENATE = re.compile(r"^FOR UNITED STATES SENATOR - (\d+) YEAR TERM$")
_CSV_HOUSE = re.compile(r"^FOR REPRESENTATIVE IN CONGRESS - (\d+) YEAR TERM$")
_CSV_DISTRICT = re.compile(r"^DISTRICT 0?(\d{1,2})$")
_SPECIAL = re.compile(r"SPECIAL|UNEXPIRED|VACANCY")


def _csv_contest(race: str, area_type: str, area: str) -> tuple[str, int | None] | None:
    """The race a CSV row belongs to, ``None`` for other offices and unexpired terms."""
    text = " ".join(race.upper().split())
    if not _CSV_FEDERAL.search(text) or _SPECIAL.search(text):
        return None
    if m := _CSV_SENATE.match(text):
        if m.group(1) != "6":  # an unexpired term: a special election
            return None
        if area_type != "SW" or area.strip():
            raise ValueError(f"NE: Senate row is not a statewide total ({area_type!r}, {area!r})")
        return "us_senate", None
    if m := _CSV_HOUSE.match(text):
        if m.group(1) != "2":
            return None
        district = _CSV_DISTRICT.match(" ".join(area.upper().split()))
        if area_type != "CG" or not district:
            raise ValueError(f"NE: House row is not a district total ({area_type!r}, {area!r})")
        return "us_house", int(district.group(1))
    raise ValueError(f"NE: unrecognized federal contest name {race!r}")


@register("NE")
def nebraska(paths: Sequence[Path]) -> pd.DataFrame:
    """``electionresults.nebraska.gov`` ``resultsCSV.aspx`` exports (``type=CG`` and/or
    ``type=SW``): one row per candidate with the district or statewide total. Each data
    row ends with a comma, so it has one empty field more than the header. A candidate
    listed twice in a contest (e.g. county rows instead of totals) is refused rather
    than summed. ``PartyCode`` is ``REP``/``DEM``/…; ``PET`` (by petition) is other.
    """
    records: list[dict[str, object]] = []
    for path in paths:
        reader = csv.reader(io.StringIO(_decode(path.read_bytes())))
        header = [h.strip() for h in next(reader, [])]
        if header != _CSV_HEADER:
            raise ValueError(f"{path.name}: unexpected header {header}")
        for number, row in enumerate(reader, 2):
            if not row:
                continue
            if len(row) == len(header) + 1 and not row[-1].strip():
                row = row[:-1]
            if len(row) != len(header):
                raise ValueError(f"{path.name} line {number}: {len(row)} fields, expected {len(header)}")
            field = dict(zip(header, row, strict=True))
            contest = _csv_contest(field["RaceName"], field["AreaType"].strip(), field["AreaNum"])
            if contest is None:
                continue
            votes = field["CandidateVotes"].replace(",", "").strip()
            if not votes.isdigit() or not field["CandidateID"].strip():
                raise ValueError(f"{path.name} line {number}: bad candidate or vote count {votes!r}")
            records.append(
                {
                    "office": contest[0],
                    "district": contest[1],
                    "race_id": field["RaceID"].strip(),
                    "candidate": field["CandidateID"].strip(),
                    "party": field["PartyCode"].strip(),
                    "votes": int(votes),
                }
            )
    if not records:
        raise ValueError("NE: no U.S. House or Senate contest found")
    data = pd.DataFrame(records)
    if data.duplicated(["office", "district", "candidate"]).any():
        raise ValueError("NE: a candidate is listed more than once in a contest (not a totals file?)")
    rows = []
    for (office, district), group in data.groupby(["office", "district"], dropna=False):
        if group["race_id"].nunique() != 1:
            raise ValueError(f"NE: {office} {district} spans RaceIDs {sorted(group['race_id'].unique())}")
        rows.append(
            from_candidates(
                group[["party", "votes"]],
                state_po="NE",
                office=str(office),
                district_num=None if office == "us_senate" else int(district),
            )
        )
    return pd.DataFrame(rows)


NE_SITE = "https://electionresults.nebraska.gov/"
NE_FILES = (
    ("CG", "resultsCSV.aspx?text=All&type=CG&map=DIST"),
    ("SW", "resultsCSV.aspx?text=All&type=SW&map=CTY"),
)
_BANNER = re.compile(r">\s*((?:Unofficial|Official)) Results\s*<", re.IGNORECASE)


def banner_label(page: str) -> str:
    """What the results site's banner says of the count: ``Unofficial Results`` /
    ``Official Results`` (``unknown`` when it says neither, or both)."""
    found = {m.lower() for m in _BANNER.findall(page)}
    return found.pop() if len(found) == 1 else "unknown"


@state_fetchers.register("NE")
def fetch_nebraska(dest: Path) -> list[FetchedRelease]:
    """Nebraska SOS "Results Media" CSV exports: congressional districts (House) and
    statewide contests (Senate). The CSVs carry no status; the Results Media page that
    links them states "Unofficial Results" or "Official Results" in its banner."""
    opener = state_fetchers._opener()
    page = state_fetchers._get(opener, NE_SITE + "ResultsMedia.aspx").decode("utf-8", "replace")
    labelled = banner_label(page)
    out = []
    for tag, query in NE_FILES:
        if query.replace("&", "&amp;") not in page and query not in page:
            raise RuntimeError(f"Nebraska Results Media page no longer links {query}")
        url = NE_SITE + query
        retrieved = state_fetchers._now()
        body = state_fetchers._get(opener, url)
        if not body.lstrip(b"\xef\xbb\xbf").startswith(b"RaceID,"):
            raise RuntimeError(f"{url} did not return the results CSV")
        path = dest / f"NE_2026GE_resultsCSV_{tag}.csv"
        path.write_bytes(body)
        out.append(FetchedRelease("NE", path, url, retrieved, labelled))
    return out

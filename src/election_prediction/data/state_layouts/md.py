"""Maryland: State Board of Elections HTML results pages (the same template in 2024 and 2026).

Until the State Board posts its post-certification CSVs, the only release of the 2026
general is the results site: one page per office ("Representative in Congress", with a
``District N`` heading and a table per district; "U.S. Senator"). The 2024 general was
published on the same template and those archived pages are the certified count, so this
one parser is proven directly against 2024 certified returns and is registered as the
current parser only; no separate historical parser is needed.

Each table lists candidates (Name, Party, Early Voting, Election Day, Mail-In Ballot,
Provisional, Total, Percentage), an ``Other Write-Ins`` row and a ``Totals`` row. ``NR``
means a vote type is not yet reported; the ``Total`` column is what the state has counted.
"""

from __future__ import annotations

import re
import urllib.parse
from collections.abc import Sequence
from pathlib import Path
from typing import NamedTuple

import pandas as pd

from .. import state_fetchers
from ..state_extraction import from_candidates, party_bucket, register
from ..state_fetchers import FetchedRelease

_TITLE = re.compile(
    r"^(Official|Unofficial) (\d{4}) (Presidential|Gubernatorial) General Election Results for (.+)$"
)
_OFFICES = {"Representative in Congress": "us_house", "U.S. Senator": "us_senate"}
_DISTRICT = re.compile(r"^District (\d{1,2})$")
_SPECIAL = re.compile(r"SPECIAL|UNEXPIRED|VACANCY", re.IGNORECASE)
_COLUMNS = [
    "Name",
    "Party",
    "Early Voting",
    "Election Day",
    "Mail-In Ballot",
    "Provisional",
    "Total",
    "Percentage",
]


class Contest(NamedTuple):
    office: str
    district: int | None
    year: int
    candidates: tuple[tuple[str, str, int], ...]  # (name, party, votes)


def _text(node: object) -> str:
    return " ".join(node.get_text(" ").split())  # type: ignore[attr-defined]


def _count(text: str, *, where: str) -> int:
    digits = text.replace(",", "").strip()
    if not digits.isdigit():
        raise ValueError(f"{where}: vote count {text!r} is not a whole number")
    return int(digits)


def page_title(html: str) -> tuple[str, int, str]:
    """``(label, year, office heading)`` from the page's ``<h1>``: the state's own statement
    of whether the results are official."""
    from bs4 import BeautifulSoup

    h1 = BeautifulSoup(html, "html.parser").find("h1")
    match = _TITLE.match(_text(h1)) if h1 is not None else None
    if not match:
        raise ValueError("MD page: no '<Official|Unofficial> <year> ... General Election Results for' title")
    return match.group(1).lower(), int(match.group(2)), match.group(4)


def page_contests(html: str, *, source: str) -> list[Contest]:
    """Every contest table on one results page. The candidates must add up to the table's
    ``Totals`` row."""
    from bs4 import BeautifulSoup

    _label, year, heading = page_title(html)
    if _SPECIAL.search(heading):
        return []
    if heading not in _OFFICES:
        raise ValueError(f"{source}: page is for {heading!r}, not a U.S. House or Senate contest")
    office = _OFFICES[heading]
    soup = BeautifulSoup(html, "html.parser")
    contests: list[Contest] = []
    district: int | None = None
    current_office: str | None = None
    for node in soup.find_all(["h2", "h3", "table"]):
        if node.name == "h2":
            current_office, district = _text(node), None
            continue
        if node.name == "h3":
            match = _DISTRICT.match(_text(node))
            if not match:
                raise ValueError(f"{source}: unexpected contest heading {_text(node)!r}")
            district = int(match.group(1))
            continue
        if "table-banded" not in (node.get("class") or []):
            continue
        if current_office != heading:
            raise ValueError(
                f"{source}: results table under heading {current_office!r}, expected {heading!r}"
            )
        if (office == "us_house") != (district is not None):
            raise ValueError(f"{source}: {heading} table with district {district!r}")
        where = f"{source} {heading} {district or ''}".strip()
        rows = [[_text(c) for c in tr.find_all(["th", "td"])] for tr in node.find_all("tr")]
        if not rows or rows[0] != _COLUMNS:
            raise ValueError(f"{where}: unexpected table columns {rows[0] if rows else None}")
        candidates: list[tuple[str, str, int]] = []
        total: int | None = None
        for cells in rows[1:]:
            if len(cells) != len(_COLUMNS):
                raise ValueError(f"{where}: row with {len(cells)} cells")
            if total is not None:
                raise ValueError(f"{where}: rows after the Totals row")
            if cells[0] == "Totals":
                total = _count(cells[6], where=where)
                continue
            if not cells[0]:
                raise ValueError(f"{where}: candidate row without a name")
            candidates.append((cells[0], cells[1], _count(cells[6], where=where)))
        if total is None or not candidates:
            raise ValueError(f"{where}: table needs candidate rows and a Totals row")
        if sum(votes for _name, _party, votes in candidates) != total:
            raise ValueError(f"{where}: candidates do not add up to the Totals row ({total})")
        contests.append(Contest(office, district, year, tuple(candidates)))
        if office == "us_house":
            district = None  # every House table needs its own District heading
    if not contests:
        raise ValueError(f"{source}: no results table found")
    return contests


@register("MD")
def maryland(paths: Sequence[Path]) -> pd.DataFrame:
    """Results pages for "Representative in Congress" (all districts on one page, or one
    page per district) and "U.S. Senator". A district that appears on two pages must show
    the same count on both."""
    seen: dict[tuple[str, int | None], Contest] = {}
    for path in paths:
        html = path.read_text(encoding="utf-8", errors="replace")
        for contest in page_contests(html, source=path.name):
            key = (contest.office, contest.district)
            if key in seen and seen[key] != contest:
                raise ValueError(f"MD: {key} differs between pages")
            seen[key] = contest
    years = sorted({c.year for c in seen.values()})
    if len(years) != 1:
        raise ValueError(f"MD: pages from {years or 'no'} elections; expected one")
    rows = [
        from_candidates(
            pd.DataFrame(c.candidates, columns=["name", "party", "votes"])[["party", "votes"]],
            state_po="MD",
            office=c.office,
            district_num=c.district,
        )
        for c in seen.values()
    ]
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- fetcher

MD_BASE = "https://elections.maryland.gov/elections/2026/general_results/"
_INDEX_LINK = re.compile(r'<a[^>]*href="(gen_results_2026_\d+\.html)"[^>]*>\s*([^<]+?)\s*</a>')


def office_pages(index_html: str) -> dict[str, str]:
    """Office name -> page file, from the results index (page numbers change by year)."""
    return {name: href for href, name in _INDEX_LINK.findall(index_html)}


@state_fetchers.register("MD")
def fetch_maryland(dest: Path) -> list[FetchedRelease]:
    """The federal office pages linked from the State Board's results index, found by
    office name. Each page's title says whether the results are official."""
    opener = state_fetchers._opener()
    pages = office_pages(state_fetchers._get(opener, MD_BASE + "index.html").decode("utf-8", "replace"))
    if "Representative in Congress" not in pages:
        raise RuntimeError("Maryland results index lists no 'Representative in Congress' page")
    out = []
    for heading, token in (("Representative in Congress", "USHouse"), ("U.S. Senator", "USSenate")):
        if heading not in pages:
            continue
        url = MD_BASE + pages[heading]
        retrieved = state_fetchers._now()
        body = state_fetchers._get(opener, url)
        label, year, found = page_title(body.decode("utf-8", "replace"))
        if year != 2026 or found != heading:
            raise RuntimeError(f"Maryland page {url} is for {year} {found!r}")
        path = dest / f"MD_2026GE_{token}_{pages[heading]}"
        path.write_bytes(body)
        out.append(FetchedRelease("MD", path, url, retrieved, label))
    return out


# --------------------------------------------------------------------------- cross-check

_DETAIL_LINK = re.compile(r'href="(gen_detail_results_2026_\d+_(\d+)_District \d+\.html)"')


def detail_urls(page_html: str) -> dict[int, str]:
    """District -> URL of its "County Break Down" page, from the office page's links."""
    return {int(d): MD_BASE + urllib.parse.quote(href) for href, d in _DETAIL_LINK.findall(page_html)}


def detail_totals(html: str, *, district: int) -> dict[str, object]:
    """One district's "County Break Down" page (a column per candidate, a row per county)
    summed over the counties: a different table of the same count, used to cross-check."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    heading = soup.find("h3")
    if heading is None or _text(heading) != f"District {district}":
        raise ValueError(f"MD county break down: expected District {district}")
    sums: dict[str, int] = {}
    for table in soup.find_all("table", class_="table-banded"):
        head = table.find_all("tr")[0].find_all("th")
        if not head or _text(head[0]) != "Jurisdiction":
            raise ValueError("MD county break down: first column is not Jurisdiction")
        parties = []
        for th in head[1:]:
            lines = [" ".join(s.split()) for s in th.get_text("\n").split("\n") if s.strip()]
            parties.append(lines[-1] if len(lines) > 1 else "")
        for tr in table.find_all("tr")[1:]:
            cells = [_text(c) for c in tr.find_all("td")]
            if not cells or cells[0] == "Totals":
                continue
            if len(cells) != len(parties) + 1:
                raise ValueError("MD county break down: row width differs from header")
            for party, cell in zip(parties, cells[1:], strict=True):
                bucket = party_bucket(party)
                sums[bucket] = sums.get(bucket, 0) + _count(cell, where="MD county break down")
    if not sums:
        raise ValueError("MD county break down: no county rows")
    return {
        "office": "us_house",
        "district_num": district,
        "dem_votes": sums.get("DEMOCRAT", 0),
        "rep_votes": sums.get("REPUBLICAN", 0),
    }

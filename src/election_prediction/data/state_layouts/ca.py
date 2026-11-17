"""California: 2024 certified Statement of Vote workbook; 2026 Secretary of State media JSON.

The certified Statement of Vote "CSV Files - All Candidates" workbook is long, one row
per county, contest and candidate. During the canvass the Secretary of State publishes
``us-rep.json`` for media use: one object per district ("Districtwide Results") and per
county part of a district. California's top-two primary can send two candidates of one
party to the general election, so a race may have no Democratic or no Republican votes;
both candidates' votes then fall in the one party's column, as the certified returns
record them.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from pathlib import Path

import pandas as pd

from .. import state_fetchers
from ..state_extraction import from_candidates, register, register_historical
from ..state_fetchers import FetchedRelease

_SPECIAL = re.compile(r"PARTIAL|UNEXPIRED|SPECIAL|VACANCY", re.IGNORECASE)

# --------------------------------------------------------------------------- 2024 format

_SOV_COLUMNS = [
    "Election Name",
    "County Id",
    "Contest ID",
    "Contest Name",
    "Candidate ID",
    "Party Name",
    "Vote Total",
]
_SOV_HOUSE = re.compile(r"^United States Representative District (\d{1,2})$")
_SOV_SENATE = re.compile(r"^US Senate\b")
_SOV_FEDERAL = re.compile(r"^(US Senat|United States (Senat|Representative))", re.IGNORECASE)


def _sov_contest(name: str) -> tuple[str, int | None] | None:
    text = " ".join(str(name).split())
    if not _SOV_FEDERAL.match(text) or _SPECIAL.search(text):
        return None
    if m := _SOV_HOUSE.match(text):
        return "us_house", int(m.group(1))
    if _SOV_SENATE.match(text):
        return "us_senate", None
    raise ValueError(f"CA: unrecognized federal contest name {name!r}")


def sov_races(table: pd.DataFrame, *, source: str) -> pd.DataFrame:
    """Race rows from the Statement of Vote all-candidates table (county x candidate)."""
    missing = [c for c in _SOV_COLUMNS if c not in table.columns]
    if missing:
        raise ValueError(f"{source}: missing columns {missing}")
    elections = {str(e).strip() for e in table["Election Name"].unique()}
    if len(elections) != 1 or "General Election" not in next(iter(elections)):
        raise ValueError(f"{source}: expected one general election, found {sorted(elections)}")
    if table.duplicated(["County Id", "Contest ID", "Candidate ID"]).any():
        raise ValueError(f"{source}: repeated county/contest/candidate rows")
    contests = table["Contest Name"].map(_sov_contest)
    federal = table[contests.notna()].assign(
        office=[c[0] for c in contests.dropna()],
        district=[c[1] for c in contests.dropna()],
        votes=lambda d: pd.to_numeric(d["Vote Total"].astype(str).str.replace(",", "")),
    )
    if federal.empty:
        raise ValueError(f"{source}: no U.S. House or Senate contest found")
    if (federal["votes"] < 0).any() or (federal["votes"] % 1 != 0).any():
        raise ValueError(f"{source}: vote totals must be non-negative whole numbers")
    if (federal.groupby("Contest ID")["Contest Name"].nunique() != 1).any():
        raise ValueError(f"{source}: one contest ID under several names")
    rows = []
    for (office, contest_id), group in federal.groupby(["office", "Contest ID"]):
        if group.groupby("Candidate ID")["Party Name"].nunique().max() != 1:
            raise ValueError(f"{source}: contest {contest_id} lists a candidate under two parties")
        by_candidate = (
            group.groupby(["Candidate ID", "Party Name"], as_index=False)["votes"]
            .sum()
            .rename(columns={"Party Name": "party"})
        )
        district = group["district"].iloc[0]
        rows.append(
            from_candidates(
                by_candidate,
                state_po="CA",
                office=str(office),
                district_num=None if office == "us_senate" else int(district),
            )
        )
    return pd.DataFrame(rows)


@register_historical("CA")
def california_2024(paths: Sequence[Path]) -> pd.DataFrame:
    """Certified Statement of Vote, ``csv-all-candidates.xlsx``. The partial/unexpired-term
    Senate contest is skipped; the full-term contest is the seat's regular race."""
    if len(paths) != 1:
        raise ValueError(f"CA: expected the one all-candidates workbook, got {len(paths)} files")
    sheets = pd.read_excel(paths[0], sheet_name=None, dtype=str, engine="openpyxl")
    if len(sheets) != 1:
        raise ValueError(f"{paths[0].name}: expected one sheet, found {list(sheets)}")
    return sov_races(next(iter(sheets.values())), source=paths[0].name)


# --------------------------------------------------------------------------- 2026 format

_JSON_TITLE = re.compile(r"^United States Representative District (\d{1,2}) - (.+) Results$")
_JSON_PARTIES = {"Dem", "Rep", "NPP", "AI", "Grn", "Lib", "P&F"}


def _json_votes(value: object, *, where: str) -> int:
    text = str(value).replace(",", "").strip()
    if not text.isdigit():
        raise ValueError(f"{where}: vote count {value!r} is not a whole number")
    return int(text)


def media_races(records: object, *, source: str) -> pd.DataFrame:
    """Race rows from ``us-rep.json``.

    Each district has one "Districtwide Results" object and one object per county part.
    The districtwide object is the race total; the county parts must add up to it for
    every candidate, or the file is refused.
    """
    if not isinstance(records, list) or not records:
        raise ValueError(f"{source}: expected a non-empty JSON list of contests")
    district_totals: dict[int, dict[str, tuple[str, int]]] = {}
    county_sums: dict[int, dict[str, int]] = {}
    for record in records:
        title = str(record.get("raceTitle", "")) if isinstance(record, dict) else ""
        if _SPECIAL.search(title):
            continue
        match = _JSON_TITLE.match(title)
        if not match or not isinstance(record.get("candidates"), list) or not record["candidates"]:
            raise ValueError(f"{source}: unexpected contest entry {title!r}")
        district, scope = int(match.group(1)), match.group(2)
        entry: dict[str, tuple[str, int]] = {}
        for candidate in record["candidates"]:
            name, party = str(candidate["Name"]).strip(), str(candidate["Party"]).strip()
            if party not in _JSON_PARTIES:
                raise ValueError(f"{source}: {title!r} has unknown party label {party!r}")
            if name in entry:
                raise ValueError(f"{source}: {title!r} lists {name!r} twice")
            entry[name] = (party, _json_votes(candidate["Votes"], where=f"{source} {title!r}"))
        if scope == "Districtwide":
            if district in district_totals:
                raise ValueError(f"{source}: two districtwide entries for district {district}")
            district_totals[district] = entry
        elif scope.endswith(" County"):
            sums = county_sums.setdefault(district, {})
            for name, (_party, votes) in entry.items():
                sums[name] = sums.get(name, 0) + votes
        else:
            raise ValueError(f"{source}: unexpected result scope in {title!r}")
    if not district_totals:
        raise ValueError(f"{source}: no districtwide U.S. Representative result")
    if set(county_sums) - set(district_totals):
        raise ValueError(f"{source}: county results without a districtwide entry")
    rows = []
    for district, entry in sorted(district_totals.items()):
        if district in county_sums and county_sums[district] != {n: v for n, (_p, v) in entry.items()}:
            raise ValueError(f"{source}: district {district} county results do not add up to districtwide")
        frame = pd.DataFrame([{"party": p, "votes": v} for p, v in entry.values()])
        rows.append(from_candidates(frame, state_po="CA", office="us_house", district_num=district))
    return pd.DataFrame(rows)


@register("CA")
def california(paths: Sequence[Path]) -> pd.DataFrame:
    """Secretary of State media file ``us-rep.json`` (districtwide and county results)."""
    if len(paths) != 1:
        raise ValueError(f"CA: expected the one us-rep.json file, got {len(paths)} files")
    return media_races(json.loads(paths[0].read_text(encoding="utf-8-sig")), source=paths[0].name)


# --------------------------------------------------------------------------- fetcher

CA_URL = "https://media.sos.ca.gov/media/us-rep.json"


@state_fetchers.register("CA")
def fetch_california(dest: Path) -> FetchedRelease:
    """The U.S. Representative JSON listed in the Secretary of State's media-file index
    (``json-endpoints.csv``). The file carries a reporting time but no statement of
    whether the count is official, so its status is reported as unknown."""
    retrieved = state_fetchers._now()
    body = state_fetchers._get(state_fetchers._opener(), CA_URL)
    path = dest / "CA_2026GE_us-rep.json"
    path.write_bytes(body)
    return FetchedRelease("CA", path, CA_URL, retrieved, "unknown")


# --------------------------------------------------------------------------- cross-check

_ASCII_HOUSE = re.compile(r"^1100(\d{4})0000$")


def _ascii_messages(text: str, kind: str) -> list[list[str]]:
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if not (line.startswith("[") and line.endswith("]")):
            raise ValueError(f"CA ASCII file: malformed message {line[:40]!r}")
        fields = line[1:-1].split("|")
        if fields[0] == kind:
            out.append(fields)
    return out


def ascii_totals(votes_text: str, candidates_text: str) -> pd.DataFrame:
    """Districtwide U.S. Representative totals from the ASCII media files (``V26GG.txt``
    county-59 vote messages, parties from ``C26GG.txt`` codes 01 Democratic, 02
    Republican): a second publication of the count, used to cross-check ``us-rep.json``."""
    party = {(f[3], f[4]): f[9] for f in _ascii_messages(candidates_text, "C") if len(f) >= 11 and f[4]}
    rows = []
    for f in _ascii_messages(votes_text, "V"):
        match = _ASCII_HOUSE.match(f[3])
        if not match or f[4] != "59":
            continue
        cells = f[8:]
        if len(cells) % 4 or not cells:
            raise ValueError(f"CA V message {f[2]}: candidate fields are not groups of four")
        votes = {"01": 0, "02": 0}
        for i in range(0, len(cells), 4):
            code = party.get((f[3], cells[i]))
            if code is None:
                raise ValueError(f"CA V message {f[2]}: candidate {cells[i]} not in the candidate file")
            if code in votes:
                votes[code] += int(cells[i + 1])
        rows.append(
            {
                "office": "us_house",
                "district_num": int(match.group(1)),
                "dem_votes": votes["01"],
                "rep_votes": votes["02"],
            }
        )
    if not rows:
        raise ValueError("CA V file: no statewide U.S. Representative vote message")
    return pd.DataFrame(rows)

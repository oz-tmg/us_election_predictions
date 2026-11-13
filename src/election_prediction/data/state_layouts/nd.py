"""North Dakota: 2024 legacy "All Statewide" CSV export; 2026 tally-enr JSON API.

The 2024 certified results sit on the old ``results.sos.nd.gov`` site, whose CSV export
has one row per county, contest and candidate and prints no contest total. For 2026 the
Secretary of State moved to ``resultsnd.sos.nd.gov`` (the platform Arkansas uses): a JSON
API that gives each contest's statewide votes per choice, the contest total, and the same
votes by county. Contest names are the same in both (``Representative in Congress``, an
at-large seat numbered district 0 here; ``United States Senator``).

The 2026 parser reads the statewide votes and refuses the file unless they add up to the
printed contest total and to the county rows. Parties come from the ``partyID`` code
(``DEM``, ``REP``): the party *name* for ``DEM`` is "Democratic-NPL".
"""

from __future__ import annotations

import csv
import io
import json
import re
from collections.abc import Sequence
from pathlib import Path

import pandas as pd

from .. import state_fetchers
from ..state_extraction import from_candidates, register, register_historical
from ..state_fetchers import FetchedRelease
from ..state_parsers import _decode

_FEDERAL = re.compile(r"CONGRESS|UNITED STATES SENAT|U\.?S\.? (SENAT|REPRESENTATIVE|HOUSE)")
_SPECIAL = re.compile(r"SPECIAL|UNEXPIRED|VACANCY")


def _contest(name: object) -> tuple[str, int | None] | None:
    """The race a contest name is, ``None`` for other offices and unexpired-term contests."""
    text = " ".join(str(name).upper().split())
    if not _FEDERAL.search(text) or _SPECIAL.search(text):
        return None
    if text == "REPRESENTATIVE IN CONGRESS":
        return "us_house", 0
    if text == "UNITED STATES SENATOR":
        return "us_senate", None
    raise ValueError(f"ND: unrecognized federal contest name {name!r}")


_HEADER_2024 = [
    "ContestName",
    "PartyCode",
    "AreaNum",
    "CandidateName",
    "VoteFor",
    "CandidateVotes",
    "CandidatePercentage",
    "PrecinctsReporting",
]


@register_historical("ND")
def north_dakota_2024(paths: Sequence[Path]) -> pd.DataFrame:
    """``results.sos.nd.gov`` "All Statewide" CSV export (certified 2024 general).

    The header names eight fields but every data row carries two more: the county name
    and an empty trailing field. One row per county, contest and candidate, summed here
    over counties; a county listed twice for the same candidate is refused. The
    ``write-in`` row (party ``NON``) counts as other votes.
    """
    records: list[dict[str, object]] = []
    for path in paths:
        reader = csv.reader(io.StringIO(_decode(path.read_bytes())))
        header = [h.strip() for h in next(reader, [])]
        if header != _HEADER_2024:
            raise ValueError(f"{path.name}: unexpected header {header}")
        for number, row in enumerate(reader, 2):
            if not row:
                continue
            if len(row) != 10 or row[9].strip() or not row[8].strip():
                raise ValueError(f"{path.name} line {number}: expected 8 fields, county and an empty field")
            contest = _contest(row[0])
            if contest is None:
                continue
            records.append(
                {
                    "office": contest[0],
                    "candidate": " ".join(row[3].split()),
                    "party": row[1].strip(),
                    "county": row[8].strip(),
                    "votes": int(row[5].replace(",", "")),
                }
            )
    if not records:
        raise ValueError("ND: no U.S. House or Senate contest found")
    data = pd.DataFrame(records)
    keys = ["office", "candidate", "party", "county"]
    if data.duplicated(keys).any():
        raise ValueError(f"ND: repeated county rows {data[data.duplicated(keys)][keys].to_dict('records')}")
    rows = []
    for office, group in data.groupby("office"):
        if group.groupby(["candidate", "party"])["county"].nunique().nunique() != 1:
            raise ValueError(f"ND: {office} candidates are not listed for the same counties")
        by_candidate = group.groupby(["candidate", "party"], as_index=False)["votes"].sum()
        rows.append(
            from_candidates(
                by_candidate,
                state_po="ND",
                office=str(office),
                district_num=None if office == "us_senate" else 0,
            )
        )
    return pd.DataFrame(rows)


def _choice_votes(node: dict, *, where: str) -> dict[str, tuple[str, int]]:
    """``choiceID -> (partyID, votes)`` for a contest or one of its county locations."""
    out: dict[str, tuple[str, int]] = {}
    listed = [*(node.get("choices") or []), *(node.get("writeInChoices") or node.get("writeinChoices") or [])]
    for choice in listed:
        choice_id, votes = str(choice.get("choiceID", "")), choice.get("totalVotes")
        if not choice_id or choice_id in out or not isinstance(votes, int) or votes < 0:
            raise ValueError(f"ND: {where}: malformed choice {choice!r}")
        out[choice_id] = (str(choice.get("partyID") or ""), votes)
    return out


@register("ND")
def north_dakota(paths: Sequence[Path]) -> pd.DataFrame:
    """``resultsnd.sos.nd.gov`` tally-enr JSON: ``*statewide_results*`` (statewide contests:
    votes per choice with ``partyID``, contest total, county ``locations``) joined by
    contest ID to ``*contestlist*`` (contest names and each contest's choices).

    Every choice must be one the contest list names with the same party; choices must add
    up to the contest's ``totalVotes``; and where county results are given, each choice's
    county votes must add up to its statewide votes. The write-in line is an ordinary
    choice with party ``NON`` and counts as other votes.
    """
    by_kind: dict[str, dict] = {}
    for path in paths:
        for kind in ("contestlist", "statewide_results"):
            if kind in path.name:
                if kind in by_kind:
                    raise ValueError(f"ND: more than one {kind} file")
                by_kind[kind] = json.loads(path.read_text(encoding="utf-8-sig"))
    missing = {"contestlist", "statewide_results"} - set(by_kind)
    if missing:
        raise ValueError(f"ND needs contestlist and statewide_results files; missing {sorted(missing)}")
    try:
        listed = by_kind["contestlist"]["response"]["contests"]
        contests = by_kind["statewide_results"]["response"]["contests"]
    except (KeyError, TypeError) as exc:
        raise ValueError("ND: unexpected JSON structure (no response.contests)") from exc
    rows = []
    for contest_id, result in contests.items():
        if contest_id not in listed:
            raise ValueError(f"ND: contest {contest_id} is not in the contest list")
        name = listed[contest_id].get("contestName")
        contest = _contest(name)
        if contest is None:
            continue
        where = f"contest {contest_id} ({' '.join(str(name).split())})"
        votes = _choice_votes(result, where=where)
        known = listed[contest_id].get("choices") or {}
        for choice_id, (party, _) in votes.items():
            if choice_id not in known or str(known[choice_id].get("partyID") or "") != party:
                raise ValueError(f"ND: {where}: choice {choice_id} does not match the contest list")
        total = sum(v for _, v in votes.values())
        if not votes or total != result.get("totalVotes"):
            raise ValueError(f"ND: {where}: choices sum to {total}, contest total {result.get('totalVotes')}")
        locations = result.get("locations") or {}
        if locations:
            summed = dict.fromkeys(votes, 0)
            for location_id, location in locations.items():
                county = _choice_votes(location, where=f"{where} location {location_id}")
                if set(county) != set(votes):
                    raise ValueError(f"ND: {where}: location {location_id} lists different choices")
                for choice_id, (_, county_votes) in county.items():
                    summed[choice_id] += county_votes
            if summed != {k: v for k, (_, v) in votes.items()}:
                raise ValueError(f"ND: {where}: county votes do not add up to the statewide votes")
        frame = pd.DataFrame([{"party": party, "votes": v} for party, v in votes.values()])
        rows.append(from_candidates(frame, state_po="ND", office=contest[0], district_num=contest[1]))
    if not rows:
        raise ValueError("ND: no U.S. House or Senate contest found")
    return pd.DataFrame(rows)


ND_API = "https://api.resultsnd.sos.nd.gov/"
ND_ELECTION = "348"  # 2026 General Election (Election/GetElectionList)


@state_fetchers.register("ND")
def fetch_north_dakota(dest: Path) -> list[FetchedRelease]:
    """North Dakota SOS results API: statewide contest results (the at-large House seat is
    a statewide contest) and the contest list that names them. ``isOfficial`` is stated in
    the results response itself."""
    opener = state_fetchers._opener()
    results_url = (
        f"{ND_API}Contest/GetContestResults?cId=north-dakota&electionID={ND_ELECTION}&contestType=SW"
    )
    list_url = f"{ND_API}Contest/GetContestSearchList?cid=north-dakota&electionID={ND_ELECTION}"
    retrieved = state_fetchers._now()
    body = state_fetchers._get(opener, results_url)
    official = json.loads(body).get("isOfficial")
    labelled = "official" if official is True else "unofficial" if official is False else "unknown"
    results_path = dest / "ND_2026GE_statewide_results.json"
    results_path.write_bytes(body)
    list_retrieved = state_fetchers._now()
    list_path = dest / "ND_2026GE_contestlist.json"
    list_path.write_bytes(state_fetchers._get(opener, list_url))
    return [
        FetchedRelease("ND", results_path, results_url, retrieved, labelled),
        FetchedRelease("ND", list_path, list_url, list_retrieved, labelled, "support"),
    ]

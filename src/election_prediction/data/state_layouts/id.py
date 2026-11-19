"""Idaho: 2024 certified precinct workbook; 2026 results-application contest JSON.

In 2024 the Secretary of State published ``raw_races_general.xlsx``, one row per
precinct, race and candidate. For 2026 the state moved to a results application whose
public API lists every statewide-jurisdiction contest with its totals
(``/ballot-items``); contest names are unchanged ("United States Representative
District 1"). The API's election record states whether the results are official.
"""

from __future__ import annotations

import json
import re
import urllib.parse
from collections.abc import Sequence
from pathlib import Path

import pandas as pd

from .. import state_fetchers
from ..state_extraction import from_candidates, party_bucket, register, register_historical
from ..state_fetchers import FetchedRelease

_SENATE = re.compile(r"^United States Senator$")
_HOUSE = re.compile(r"^United States Representative District (\d{1,2})$")
_FEDERAL = re.compile(r"^United States (Senat|Representative)", re.IGNORECASE)
_SPECIAL = re.compile(r"SPECIAL|UNEXPIRED|VACANCY|PARTIAL", re.IGNORECASE)
_NOT_VOTES = {"OVERVOTES", "UNDERVOTES", "OVER VOTES", "UNDER VOTES", "BALLOTS CAST"}


def _contest(name: str) -> tuple[str, int | None] | None:
    text = " ".join(str(name).split())
    if not _FEDERAL.match(text) or _SPECIAL.search(text):
        return None
    if _SENATE.match(text):
        return "us_senate", None
    if m := _HOUSE.match(text):
        return "us_house", int(m.group(1))
    raise ValueError(f"ID: unrecognized federal contest name {name!r}")


def _blank(value: object) -> bool:
    return value is None or str(value).strip() in {"", "nan", "None"}


# --------------------------------------------------------------------------- 2024 format

_RAW_COLUMNS = ["County", "Precinct", "Race", "Party", "Candidate", "Votes"]


def raw_races(table: pd.DataFrame, *, source: str) -> pd.DataFrame:
    """Race rows from the ``raw_races`` precinct table. ``Overvotes`` and ``Undervotes``
    rows (blank party) are not votes; named write-ins carry the party they filed under."""
    missing = [c for c in _RAW_COLUMNS if c not in table.columns]
    if missing:
        raise ValueError(f"{source}: missing columns {missing}")
    contests = table["Race"].map(_contest)
    federal = table[contests.notna()].assign(
        office=[c[0] for c in contests.dropna()], district=[c[1] for c in contests.dropna()]
    )
    if federal.empty:
        raise ValueError(f"{source}: no U.S. House or Senate contest found")
    not_votes = federal["Candidate"].astype(str).str.strip().str.upper().isin(_NOT_VOTES)
    federal = federal[~not_votes]
    no_party = federal[federal["Party"].map(_blank)]
    if len(no_party):
        raise ValueError(
            f"{source}: candidates without a party: {sorted(no_party['Candidate'].astype(str).unique())}"
        )
    if federal.duplicated(["County", "Precinct", "Race", "Party", "Candidate"]).any():
        raise ValueError(f"{source}: repeated precinct/race/candidate rows")
    votes = pd.to_numeric(federal["Votes"])
    if votes.isna().any() or (votes < 0).any() or (votes % 1 != 0).any():
        raise ValueError(f"{source}: vote counts must be non-negative whole numbers")
    federal = federal.assign(votes=votes)
    rows = []
    for (office, district), group in federal.groupby(["office", "district"], dropna=False):
        by_candidate = (
            group.groupby(["Candidate", "Party"], as_index=False)["votes"]
            .sum()
            .rename(columns={"Party": "party"})
        )
        rows.append(
            from_candidates(
                by_candidate,
                state_po="ID",
                office=str(office),
                district_num=None if office == "us_senate" else int(district),
            )
        )
    return pd.DataFrame(rows)


@register_historical("ID")
def idaho_2024(paths: Sequence[Path]) -> pd.DataFrame:
    """Certified 2024 ``raw_races_general.xlsx`` (sheet ``raw_races``)."""
    if len(paths) != 1:
        raise ValueError(f"ID: expected the one raw_races workbook, got {len(paths)} files")
    sheets = pd.read_excel(paths[0], sheet_name=None, dtype=str, engine="openpyxl")
    if "raw_races" not in sheets:
        raise ValueError(f"{paths[0].name}: no raw_races sheet (found {list(sheets)})")
    return raw_races(sheets["raw_races"], source=paths[0].name)


# --------------------------------------------------------------------------- 2026 format


def _english(texts: object, *, where: str) -> str:
    if isinstance(texts, list):
        for entry in texts:
            if isinstance(entry, dict) and entry.get("languageId") == "en":
                return str(entry.get("text", "")).strip()
    raise ValueError(f"{where}: no English name")


def ballot_item_races(payload: object, *, source: str) -> pd.DataFrame:
    """Race rows from the ``/ballot-items`` response: ``data`` is the list of contests,
    each with ``summaryResults.ballotOptions`` (name, ``voteCount``, ``party``) and the
    contest's ``voteTotal``, which the options must add up to."""
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise ValueError(f"{source}: expected an object with a 'data' list of contests")
    if payload.get("totalRecordCount") != len(payload["data"]):
        raise ValueError(
            f"{source}: holds {len(payload['data'])} of {payload.get('totalRecordCount')} contests"
        )
    rows = []
    for item in payload["data"]:
        name = _english(item.get("name"), where=source)
        contest = _contest(name)
        if contest is None:
            continue
        options = (item.get("summaryResults") or {}).get("ballotOptions")
        if item.get("contestType") != "Candidate" or not isinstance(options, list) or not options:
            raise ValueError(f"{source}: {name!r} has no candidate results")
        candidates: list[dict[str, object]] = []
        counted = 0
        for option in options:
            who = _english(option.get("name"), where=f"{source} {name!r}")
            votes = option.get("voteCount")
            if isinstance(votes, bool) or not isinstance(votes, int) or votes < 0:
                raise ValueError(f"{source}: {name!r} {who!r} vote count {votes!r} is not a whole number")
            if who.upper() in _NOT_VOTES:
                continue
            party = (option.get("party") or {}).get("abbreviation")
            if _blank(party):
                if not (option.get("isWriteIn") or "write-in" in who.lower()):
                    raise ValueError(f"{source}: {name!r} candidate {who!r} has no party")
                party = "WRITE-IN"
            candidates.append({"party": party, "votes": votes})
            counted += votes
        total = item.get("voteTotal")
        if total is not None and total != counted:
            raise ValueError(f"{source}: {name!r} options do not add up to voteTotal {total}")
        rows.append(
            from_candidates(
                pd.DataFrame(candidates), state_po="ID", office=contest[0], district_num=contest[1]
            )
        )
    if not rows:
        raise ValueError(f"{source}: no U.S. House or Senate contest found")
    return pd.DataFrame(rows)


@register("ID")
def idaho(paths: Sequence[Path]) -> pd.DataFrame:
    """Results-application ``/ballot-items`` JSON. The election record fetched with it
    (``isOfficialResults``) is evidence of status only and holds no votes."""
    frames = []
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        if isinstance(payload, dict) and "isOfficialResults" in payload and "data" not in payload:
            continue
        frames.append(ballot_item_races(payload, source=path.name))
    if len(frames) != 1:
        raise ValueError(f"ID: expected exactly one ballot-items file, got {len(frames)}")
    return frames[0]


# --------------------------------------------------------------------------- fetcher

ID_API = "https://results.voteidaho.gov/results/public/api/elections/id/nov2026"
ID_CDN = "https://results.voteidaho.gov/cdn/results/"
ID_SUMMARY_REPORT = "Summary and Precinct Results Excel"


@state_fetchers.register("ID")
def fetch_idaho(dest: Path) -> list[FetchedRelease]:
    """The results application's public API: the election record, which states
    ``isOfficialResults``, and the statewide contest list with totals."""
    opener = state_fetchers._opener()
    meta_at = state_fetchers._now()
    meta_body = state_fetchers._get(opener, ID_API)
    official = json.loads(meta_body).get("isOfficialResults")
    labelled = "official" if official is True else "unofficial" if official is False else "unknown"
    url = f"{ID_API}/ballot-items"
    retrieved = state_fetchers._now()
    body = state_fetchers._get(opener, url)
    meta_path, path = dest / "ID_2026GE_election.json", dest / "ID_2026GE_ballot_items.json"
    meta_path.write_bytes(meta_body)
    path.write_bytes(body)
    return [
        FetchedRelease("ID", path, url, retrieved, labelled),
        FetchedRelease("ID", meta_path, ID_API, meta_at, labelled, role="support"),
    ]


# --------------------------------------------------------------------------- cross-check


def summary_report_url(election: dict) -> str:
    """Where the election record says the state's "Summary and Precinct Results Excel"
    report currently is (the blob is renamed on every publish)."""
    report = state_fetchers._find_report(election, ID_SUMMARY_REPORT)
    if report is None:
        raise ValueError(f"ID election record lists no {ID_SUMMARY_REPORT!r} report")
    return ID_CDN + str(election["jurisdictionId"]) + "/" + urllib.parse.quote(report["blobName"])


def summary_report_totals(table: pd.DataFrame) -> pd.DataFrame:
    """Contest totals from the report's ``Summary Results`` sheet (one row per county,
    contest and choice): ``office``, ``district_num``, ``dem_votes``, ``rep_votes``."""
    contests = table["Office Name"].map(_contest)
    federal = table[contests.notna()].assign(
        office=[c[0] for c in contests.dropna()],
        district_num=[c[1] for c in contests.dropna()],
        votes=lambda d: pd.to_numeric(d["Total"]),
    )
    if federal.empty:
        raise ValueError("ID summary report: no federal contest")
    # Counties label parties differently ("Republican", "Republican Party").
    bucket = federal["Party"].map(lambda p: "OTHER" if _blank(p) else party_bucket(p))
    federal = federal.assign(
        dem_votes=federal["votes"].where(bucket == "DEMOCRAT", 0),
        rep_votes=federal["votes"].where(bucket == "REPUBLICAN", 0),
    )
    return federal.groupby(["office", "district_num"], dropna=False, as_index=False)[
        ["dem_votes", "rep_votes"]
    ].sum()

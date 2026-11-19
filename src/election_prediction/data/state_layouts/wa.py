"""Washington: 2024 certified legacy CSV export; 2026 VoteWA "All Results Excel" workbook.

The certified 2024 general is the final export of the old ``results.vote.wa.gov`` site: a
long CSV, one row per contest and candidate with statewide totals. For 2026 the Secretary
of State moved to ``results.votewa.gov``, whose "All Results Excel" report has a
``Summary Results`` sheet of the same shape plus non-vote lines (``Ballots Cast``,
``Over Votes``, ``Under Votes``), which are dropped. Contest names are the same in both
(``Congressional District N - U.S. Representative``, ``U.S. Senator``).

Washington candidates state a party *preference* in their own words (``(Prefers GOP
Party)``, ``(Prefers MAGA Republican Party)``), and the top-two general can pit two
candidates of one party against each other. A preference naming Republican/GOP counts as
Republican and one naming Democratic/Democrat as Democratic — the reading under which the
2024 export reproduces the certified returns exactly; anything else is other.
"""

from __future__ import annotations

import io
import re
from collections.abc import Sequence
from pathlib import Path

import pandas as pd

from .. import state_fetchers
from ..state_extraction import from_candidates, register, register_historical
from ..state_fetchers import FetchedRelease
from ..state_parsers import _decode

_FEDERAL = re.compile(r"U\.?S\.? (SENAT|REPRESENTATIVE|HOUSE)|UNITED STATES (SENAT|REPRESENTATIVE)|CONGRESS")
_SPECIAL = re.compile(r"SPECIAL|UNEXPIRED|SHORT TERM|VACANCY")
_SENATE = re.compile(r"^U\.S\. SENATOR$")
_HOUSE = re.compile(r"^CONGRESSIONAL DISTRICT (\d{1,2}) - U\.S\. REPRESENTATIVE$")
_PREFERS = re.compile(r"^\(PREFERS (.+) PARTY\)$")
_REPUBLICAN = re.compile(r"\b(REPUBLICAN|GOP)\b")
_DEMOCRAT = re.compile(r"\b(DEMOCRATIC|DEMOCRAT)\b")


def _contest(name: object) -> tuple[str, int | None] | None:
    """The race a contest name is, ``None`` for other offices and short/unexpired terms."""
    text = " ".join(str(name).upper().split())
    if not _FEDERAL.search(text) or text.startswith("PRESIDENT") or _SPECIAL.search(text):
        return None
    if _SENATE.match(text):
        return "us_senate", None
    if m := _HOUSE.match(text):
        return "us_house", int(m.group(1))
    raise ValueError(f"WA: unrecognized federal contest name {name!r}")


def party_preference(label: object) -> str:
    """A candidate's stated preference as DEM / REP / OTHER. Blank is the write-in line."""
    text = " ".join(str(label if label is not None else "").upper().split())
    if not text:
        return "OTHER"
    if text == "(STATES NO PARTY PREFERENCE)":
        return "OTHER"
    match = _PREFERS.match(text)
    if not match:
        raise ValueError(f"WA: unrecognized party label {label!r}")
    republican, democrat = _REPUBLICAN.search(match.group(1)), _DEMOCRAT.search(match.group(1))
    if republican and democrat:
        raise ValueError(f"WA: party label {label!r} names both major parties")
    return "REP" if republican else "DEM" if democrat else "OTHER"


def _races(records: list[dict[str, object]]) -> pd.DataFrame:
    if not records:
        raise ValueError("WA: no U.S. House or Senate contest found")
    data = pd.DataFrame(records)
    rows = []
    for (office, district), group in data.groupby(["office", "district"], dropna=False):
        if group["contest_id"].nunique() != 1:
            raise ValueError(f"WA: {office} {district} appears as more than one contest")
        if group.duplicated("choice").any():
            raise ValueError(f"WA: {office} {district} lists a choice more than once")
        rows.append(
            from_candidates(
                group[["party", "votes"]],
                state_po="WA",
                office=str(office),
                district_num=None if office == "us_senate" else int(district),
            )
        )
    return pd.DataFrame(rows)


_HEADER_2024 = ["Race", "Candidate", "Party", "Votes", "PercentageOfTotalVotes", "JurisdictionName"]


@register_historical("WA")
def washington_2024(paths: Sequence[Path]) -> pd.DataFrame:
    """``results.vote.wa.gov`` export CSV (``<date>_Congressional.csv``): statewide totals,
    one row per contest and candidate, with a ``WRITE-IN`` row (blank party) per contest.
    Contest names vary in capitalisation (``CONGRESSIONAL DISTRICT 3 - …``)."""
    records: list[dict[str, object]] = []
    for path in paths:
        data = pd.read_csv(io.StringIO(_decode(path.read_bytes())), dtype=str, keep_default_na=False)
        if list(data.columns) != _HEADER_2024:
            raise ValueError(f"{path.name}: unexpected header {list(data.columns)}")
        for row in data.to_dict(orient="records"):
            contest = _contest(row["Race"])
            if contest is None:
                continue
            votes = row["Votes"].replace(",", "").strip()
            if not votes.isdigit():
                raise ValueError(f"{path.name}: bad vote count {row['Votes']!r} in {row['Race']!r}")
            records.append(
                {
                    "office": contest[0],
                    "district": contest[1],
                    "contest_id": f"{path.name}:{' '.join(row['Race'].upper().split())}",
                    "choice": row["Candidate"].strip(),
                    "party": party_preference(row["Party"]),
                    "votes": int(votes),
                }
            )
    return _races(records)


_HEADER_2026 = ("Office Name", "Contest ID", "Ballot Name", "Choice ID", "Party", "Total")
_NOT_VOTES = {"BALLOTS CAST", "OVER VOTES", "UNDER VOTES"}


def summary_rows(rows: Sequence[Sequence[object]], *, source: str = "") -> pd.DataFrame:
    """Race rows from the ``Summary Results`` sheet (header row first).

    Each contest lists ``Ballots Cast``, its candidates (with a choice ID and a party
    label), ``Write-in`` (a choice with no party), ``Over Votes`` and ``Under Votes``. The
    three non-vote lines carry no choice ID and are dropped; a vote line must have one.
    """
    if not rows or tuple(str(c or "").strip() for c in rows[0][:6]) != _HEADER_2026:
        raise ValueError(f"{source}: unexpected Summary Results header {list(rows[0][:6]) if rows else None}")
    records: list[dict[str, object]] = []
    for number, row in enumerate(rows[1:], 2):
        cells = [*row[:6], *([None] * (6 - len(row[:6])))]
        if all(c is None or str(c).strip() == "" for c in cells):
            continue
        office_name, contest_id, ballot_name, choice_id, party, total = cells
        contest = _contest(office_name)
        if contest is None:
            continue
        name = " ".join(str(ballot_name or "").upper().split())
        choice = str(choice_id or "").strip()
        if name in _NOT_VOTES:
            if choice:
                raise ValueError(f"{source} row {number}: non-vote line {ballot_name!r} has a choice ID")
            continue
        if isinstance(total, bool) or not isinstance(total, int | float) or total < 0 or total != int(total):
            raise ValueError(f"{source} row {number}: bad vote total {total!r}")
        if not choice or not name or not str(contest_id or "").strip():
            raise ValueError(f"{source} row {number}: vote line without contest, name or choice ID")
        blank_party = party is None or not str(party).strip()
        if blank_party != (name == "WRITE-IN"):
            raise ValueError(f"{source} row {number}: {ballot_name!r} with party {party!r}")
        records.append(
            {
                "office": contest[0],
                "district": contest[1],
                "contest_id": str(contest_id).strip(),
                "choice": choice,
                "party": party_preference(party),
                "votes": int(total),
            }
        )
    return _races(records)


@register("WA")
def washington(paths: Sequence[Path]) -> pd.DataFrame:
    """``results.votewa.gov`` "All Results Excel" workbook, ``Summary Results`` sheet
    (statewide totals per contest; the ``Precinct Results`` sheet is not read)."""
    import openpyxl

    frames = []
    for path in paths:
        workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
        try:
            if "Summary Results" not in workbook.sheetnames:
                raise ValueError(f"{path.name}: no 'Summary Results' sheet ({workbook.sheetnames})")
            rows = [row[:6] for row in workbook["Summary Results"].iter_rows(values_only=True)]
        finally:
            workbook.close()
        frames.append(summary_rows(rows, source=path.name))
    if not frames:
        raise ValueError("WA: no workbook given")
    return pd.concat(frames, ignore_index=True)


WA_API = "https://results.votewa.gov/results/public/api/elections/washington/20261103"
WA_CDN = "https://results.votewa.gov/cdn/results/"


@state_fetchers.register("WA")
def fetch_washington(dest: Path) -> FetchedRelease:
    """Washington SOS (VoteWA) "All Results Excel" report: aggregate results only. The
    elections API names the report's current blob and states ``isOfficialResults``."""
    return state_fetchers._published_report(
        state="WA",
        api=WA_API,
        cdn=WA_CDN,
        report_name="All Results Excel",
        filename="WA_2026GE_AllResults.xlsx",
        dest=dest,
    )

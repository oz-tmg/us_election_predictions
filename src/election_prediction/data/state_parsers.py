"""State parsers for official aggregate releases, registered into ``state_extraction``.

Each parser reads only the files an operator downloaded from the state's own results
site and returns one row per contest in ``state_extraction.EXTRACTED_COLUMNS``. A parser
is trusted only after ``state_extraction.reconcile`` reproduced the 2024 certified result
from that state's 2024 release (``scripts/test_state_extraction.py``).

Files that carry one contest each are named by the operator with the contest token
``SEN`` or ``CD<n>`` (e.g. ``MA_2026GE_CD4_<id>_by_town.csv``); a parser refuses a file
whose name does not say which contest it holds rather than guessing from its content.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path

import pandas as pd

from .state_extraction import from_candidates, register

_CONTEST = re.compile(r"(?:^|_)(SEN|CD(\d{1,2}))(?:_|\.|$)", re.IGNORECASE)


def contest_from_name(path: Path) -> tuple[str, int | None]:
    match = _CONTEST.search(path.stem)
    if not match:
        raise ValueError(f"{path.name}: name must carry the contest token SEN or CD<n>")
    if match.group(1).upper() == "SEN":
        return "us_senate", None
    return "us_house", int(match.group(2))


def _votes(value: object) -> int:
    text = str(value).replace(",", "").strip()
    return int(float(text)) if text not in {"", "nan"} else 0


@register("MA")
def massachusetts(paths: Sequence[Path]) -> pd.DataFrame:
    """electionstats.state.ma.us contest downloads (``precincts_include:0``, by town).

    Row 1 names candidates, then ``All Others`` (write-ins), ``Blanks`` and ``Total Votes
    Cast``; row 2 gives each candidate's party; the ``TOTALS`` row is the contest total.
    Write-ins count as other votes; blanks are not votes for anyone and are dropped.
    """
    rows = []
    for path in paths:
        office, district = contest_from_name(path)
        raw = pd.read_csv(path, header=None, dtype=str, keep_default_na=False)
        header, parties = raw.iloc[0].tolist(), raw.iloc[1].tolist()
        totals = raw[raw.iloc[:, 0].str.strip().str.upper() == "TOTALS"]
        if len(totals) != 1:
            raise ValueError(f"{path.name}: expected one TOTALS row")
        total = totals.iloc[0].tolist()
        candidates = []
        for i, name in enumerate(header):
            label = str(name).strip()
            if i < 3 or not label or label in {"Blanks", "Total Votes Cast"}:
                continue
            party = "Write-in" if label == "All Others" else (parties[i] if i < len(parties) else "")
            candidates.append({"candidate": label, "party": party, "votes": _votes(total[i])})
        frame = pd.DataFrame(candidates)
        rows.append(from_candidates(frame, state_po="MA", office=office, district_num=district))
    return pd.DataFrame(rows)


_WI_HOUSE = re.compile(r"^REPRESENTATIVE IN CONGRESS DISTRICT (\d{1,2})\b")


@register("WI")
def wisconsin(paths: Sequence[Path]) -> pd.DataFrame:
    """WEC canvass ``WardbyWard_byCD_<date>.xlsx``: one contest per sheet, title in A7.

    Row 9 holds party codes from column E, row 10 candidate names, and the ``Office
    Totals:`` row the contest total. A sheet for an unexpired term ("Term ending ...") is
    a special election, not the regular race, and is skipped: the scored universe keys
    each House seat to its regular race. Contests are found by title, never by sheet
    number, because WEC numbers sheets differently each election.
    """
    import openpyxl

    rows = []
    for path in paths:
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        try:
            for ws in wb.worksheets:
                values = list(ws.iter_rows(values_only=True))
                if len(values) < 11:
                    continue
                title = str(values[6][0] or "").strip()
                if title == "UNITED STATES SENATOR":
                    office, district = "us_senate", None
                elif (m := _WI_HOUSE.match(title)) and "TERM ENDING" not in title.upper():
                    office, district = "us_house", int(m.group(1))
                else:
                    continue
                parties = values[8]
                totals = [r for r in values if str(r[0] or "").strip() == "Office Totals:"]
                if len(totals) != 1:
                    raise ValueError(f"{path.name} / {title}: expected one 'Office Totals:' row")
                candidates = [
                    {"party": parties[i] or "", "votes": int(totals[0][i] or 0)}
                    for i in range(4, len(parties))
                    if values[9][i] is not None
                ]
                rows.append(
                    from_candidates(
                        pd.DataFrame(candidates), state_po="WI", office=office, district_num=district
                    )
                )
        finally:
            wb.close()
    return pd.DataFrame(rows)


_MT_CONTEST = re.compile(r"^UNITED STATES (SENATOR|REPRESENTATIVE (\d)(?:ST|ND|RD|TH) CONGRESSIONAL)")


@register("MT")
def montana(paths: Sequence[Path]) -> pd.DataFrame:
    """electionresults.mt.gov ``ResultsExport`` statewide workbook: one contest per sheet.

    Row 7 holds the contest title (column A, read here because sheet names truncate) and
    one ``NAME\\nParty`` header per candidate from column C; the ``TOTALS`` row (column B)
    is the contest total. The export is labelled unofficial even after the canvass, so a
    snapshot built from it must not be marked certified on the strength of this file.
    """
    import openpyxl

    rows = []
    for path in paths:
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        try:
            for ws in wb.worksheets:
                values = list(ws.iter_rows(values_only=True))
                if len(values) < 8:
                    continue
                title = str(values[6][0] or "").strip().upper()
                m = _MT_CONTEST.match(title)
                if not m:
                    continue
                office, district = (
                    ("us_senate", None) if m.group(2) is None else ("us_house", int(m.group(2)))
                )
                totals = [r for r in values if str(r[1] or "").strip().upper() == "TOTALS"]
                if len(totals) != 1:
                    raise ValueError(f"{path.name} / {title}: expected one TOTALS row")
                header = values[6]
                candidates = [
                    {"party": str(header[i]).split("\n")[-1], "votes": int(totals[0][i] or 0)}
                    for i in range(2, len(header))
                    if header[i]
                ]
                rows.append(
                    from_candidates(
                        pd.DataFrame(candidates), state_po="MT", office=office, district_num=district
                    )
                )
        finally:
            wb.close()
    return pd.DataFrame(rows)


_MO_HEAD = re.compile(r"^U\.S\. (Senator|Representative - District (\d{1,2})) \(")
_MO_CANDIDATE = re.compile(r"^(?P<name>.+) (?P<party>\S+) (?P<votes>[\d,]+) [\d.]+%$")
_MO_TOTAL = re.compile(r"^Total Votes ([\d,]+)$")


@register("MO")
def missouri(paths: Sequence[Path]) -> pd.DataFrame:
    """Missouri SOS certified canvass PDF (``<year>GeneralElection.pdf``), text layer.

    A contest starts at ``U.S. Senator (`` or ``U.S. Representative - District N (`` and
    ends at ``Total Votes N``; each candidate line ends ``<Party> <votes> <pct>%``, with a
    long name possibly wrapped onto the previous line. Candidate votes must sum exactly to
    the printed total, so a mis-read line fails loudly instead of skewing a share.
    """
    from pypdf import PdfReader

    rows = []
    for path in paths:
        lines = [
            ln.strip()
            for page in PdfReader(path).pages
            for ln in (page.extract_text() or "").splitlines()
            if ln.strip()
        ]
        rows.extend(missouri_lines(lines, source=path.name))
    return pd.DataFrame(rows)


def missouri_lines(lines: Sequence[str], *, source: str = "") -> list[dict[str, object]]:
    """The Missouri canvass text layer, one race row per U.S. House / Senate contest."""
    rows = []
    i = 0
    while i < len(lines):
        head = _MO_HEAD.match(lines[i])
        if not head:
            i += 1
            continue
        office, district = ("us_senate", None) if head.group(2) is None else ("us_house", int(head.group(2)))
        candidates: list[dict[str, object]] = []
        votes: list[int] = []
        carry = ""
        i += 1
        while i < len(lines) and not _MO_TOTAL.match(lines[i]):
            line = f"{carry} {lines[i]}".strip()
            if m := _MO_CANDIDATE.match(line):
                votes.append(int(m["votes"].replace(",", "")))
                candidates.append({"party": m["party"], "votes": votes[-1]})
                carry = ""
            else:
                carry = line
            i += 1
        total = _MO_TOTAL.match(lines[i]) if i < len(lines) else None
        if total is None:
            raise ValueError(f"{source}: contest '{head.group(0)}' has no Total Votes line")
        printed = int(total.group(1).replace(",", ""))
        if sum(votes) != printed:
            raise ValueError(f"{source}: '{head.group(0)}' candidates do not sum to {printed}")
        rows.append(
            from_candidates(pd.DataFrame(candidates), state_po="MO", office=office, district_num=district)
        )
    return rows


_NC_CONTEST = re.compile(r"^US (SENATE|HOUSE OF REPRESENTATIVES DISTRICT (\d{1,2}))$")


@register("NC")
def north_carolina(paths: Sequence[Path]) -> pd.DataFrame:
    """NCSBE ``results_pct_<date>.zip`` (tab-separated precinct results, one file inside).

    Contests ``US SENATE`` and ``US HOUSE OF REPRESENTATIVES DISTRICT NN``. Every row is
    summed, including county-level absentee/one-stop/provisional batches (``Real Precinct
    = N``): they are votes, not duplicates. ``Choice Party`` gives the party; write-ins
    carry none and count as other.
    """
    import zipfile

    frames = []
    for path in paths:
        with zipfile.ZipFile(path) as zf:
            members = [n for n in zf.namelist() if n.lower().endswith(".txt")]
            if len(members) != 1:
                raise ValueError(f"{path.name}: expected one .txt member, found {members}")
            with zf.open(members[0]) as handle:
                raw = pd.read_csv(handle, sep="\t", dtype=str, keep_default_na=False)
        frames.append(raw)
    data = pd.concat(frames, ignore_index=True)
    data["Contest Name"] = data["Contest Name"].str.strip().str.upper()
    rows = []
    for contest, group in data.groupby("Contest Name"):
        m = _NC_CONTEST.match(contest)
        if not m:
            continue
        office, district = ("us_senate", None) if m.group(2) is None else ("us_house", int(m.group(2)))
        by_choice = (
            group.assign(votes=pd.to_numeric(group["Total Votes"]))
            .groupby(["Choice", "Choice Party"], as_index=False)["votes"]
            .sum()
            .rename(columns={"Choice Party": "party"})
        )
        rows.append(from_candidates(by_choice, state_po="NC", office=office, district_num=district))
    return pd.DataFrame(rows)

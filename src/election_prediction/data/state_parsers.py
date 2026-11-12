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

import io
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


def _decode(raw: bytes) -> str:
    """UTF-8 when it is, else Windows-1252 (curly quotes in names in some state exports)."""
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("cp1252")


def clarity_summary(
    paths: Sequence[Path], *, state: str, senate: str, house: str, exclude: str = r"UNEXPIRED|SPECIAL"
) -> pd.DataFrame:
    """Clarity/Scytl ENR ``summary.zip`` (``summary.csv``: one row per contest choice).

    ``senate`` and ``house`` are regexes on ``contest name``; ``house`` must capture the
    district number. Contests matching ``exclude`` (unexpired-term specials) are skipped,
    because the scored universe keys each seat to its regular race. Duplicate lines that
    Clarity sometimes repeats for the same contest choice are collapsed, not summed.
    """
    import zipfile

    senate_re, house_re, exclude_re = (re.compile(p, re.IGNORECASE) for p in (senate, house, exclude))
    frames = []
    for path in paths:
        with zipfile.ZipFile(path) as zf:
            raw = zf.read("summary.csv")
        frames.append(pd.read_csv(io.StringIO(_decode(raw)), dtype=str, keep_default_na=False))
    data = pd.concat(frames, ignore_index=True)
    data = data.drop_duplicates(["contest name", "choice name", "party name", "total votes"])
    rows = []
    for contest, group in data.groupby("contest name"):
        if exclude_re.search(contest):
            continue
        if senate_re.search(contest):
            office, district = "us_senate", None
        elif m := house_re.search(contest):
            office, district = "us_house", int(m.group(1))
        else:
            continue
        frame = pd.DataFrame(
            {"party": group["party name"], "votes": pd.to_numeric(group["total votes"].str.replace(",", ""))}
        )
        rows.append(from_candidates(frame, state_po=state, office=office, district_num=district))
    return pd.DataFrame(rows)


@register("WV")
def west_virginia(paths: Sequence[Path]) -> pd.DataFrame:
    """West Virginia SOS Clarity ``summary.zip``."""
    return clarity_summary(
        paths,
        state="WV",
        senate=r"^U\.S\. SENATOR",
        house=r"^U\.S\. HOUSE OF REPRESENTATIVES, (\d+)(?:st|nd|rd|th) Congressional District",
    )


_UT_HOUSE = re.compile(r"^U\.S\. House(?: District)? (\d{1,2})\s*$", re.IGNORECASE)
_UT_SENATE = re.compile(r"^U\.S\. Senate\b", re.IGNORECASE)


@register("UT")
def utah(paths: Sequence[Path]) -> pd.DataFrame:
    """electionresults.utah.gov JSON export: statewide totals in ``results.ballotItems``.

    Contest names changed between cycles ("U.S. House 1 " in 2024, "U.S. House District 1"
    in 2026); the pattern accepts both. ``politicalParty`` gives the party.
    """
    import json

    rows = []
    for path in paths:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        for item in data["results"]["ballotItems"]:
            name = str(item.get("name") or "")
            if m := _UT_HOUSE.match(name):
                office, district = "us_house", int(m.group(1))
            elif _UT_SENATE.match(name) and "UNEXPIRED" not in name.upper():
                office, district = "us_senate", None
            else:
                continue
            frame = pd.DataFrame(
                {
                    "party": [o.get("politicalParty") or "" for o in item["ballotOptions"]],
                    "votes": [int(o.get("voteCount") or 0) for o in item["ballotOptions"]],
                }
            )
            rows.append(from_candidates(frame, state_po="UT", office=office, district_num=district))
    return pd.DataFrame(rows)


def _vt_sum(rows: list[dict]) -> dict[tuple[str, str], int]:
    votes: dict[tuple[str, str], int] = {}
    for town in rows:
        for r in [*town.get("rc", []), *town.get("wc", [])]:
            key = (str(r.get("cn")), str(r.get("pn") or "Write-in").split("/")[0])
            votes[key] = votes.get(key, 0) + int(r.get("vc") or 0)
    return votes


@register("VT")
def vermont(paths: Sequence[Path]) -> pd.DataFrame:
    """static.electionresults.vermont.gov federal file (``...-f-<timestamp>.json``).

    ``d[pid=0].o`` lists offices; each office's ``cs`` rows are towns with candidate votes
    in ``rc`` and write-ins in ``wc``; statewide totals are sums over towns. Blank and
    spoiled ballots (``bv``, ``sv``) are not votes and are ignored; the ``tid`` 0 row is the
    state total, used only as a cross-check. A fusion label such as
    ``REP/LBRT`` is read as its first party, the line the candidate is nominated on first.
    """
    import json

    rows = []
    for path in paths:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        block = next(b for b in data["d"] if b.get("pid") == 0)
        for office_row in block["o"]:
            name = str(office_row.get("on") or "").upper()
            if name == "REPRESENTATIVE TO CONGRESS":
                office, district = "us_house", 0
            elif name.startswith("US SENATOR") and "UNEXPIRED" not in name:
                office, district = "us_senate", None
            else:
                continue
            # A town split across representative districts appears once per district;
            # the row with tid 0 is the statewide total and must not be added again.
            towns = [t for t in office_row["cs"] if int(t.get("tid") or 0) > 0]
            totals = [t for t in office_row["cs"] if int(t.get("tid") or 0) == 0]
            votes = _vt_sum(towns)
            if totals and _vt_sum(totals) != votes:
                raise ValueError(f"{path.name} / {name}: town rows do not sum to the state total row")
            frame = pd.DataFrame([{"party": p, "votes": v} for (_, p), v in votes.items()])
            rows.append(from_candidates(frame, state_po="VT", office=office, district_num=district))
    return pd.DataFrame(rows)


_WY_PARTY = re.compile(r"\(([A-Za-z]+)\)\s*$")


@register("WY")
def wyoming(paths: Sequence[Path]) -> pd.DataFrame:
    """Wyoming SOS results zip: ``... General Results Summaries ....xlsx``, sheet
    ``Statewide Candidates``. Contest blocks sit side by side: a title row names each
    block at its first column, the next row lists candidates as ``Name (P)`` then
    ``Write-Ins``, ``Overvotes``, ``Undervotes``; the ``Total`` row holds statewide sums.
    Over- and undervotes are not votes for anyone and are dropped. Block positions move
    between cycles, so blocks are found by title, never by column letter.
    """
    import zipfile

    import openpyxl

    rows = []
    for path in paths:
        with zipfile.ZipFile(path) as zf:
            members = [n for n in zf.namelist() if "Summaries" in n and n.endswith(".xlsx")]
            if len(members) != 1:
                raise ValueError(f"{path.name}: expected one 'Summaries' workbook, found {members}")
            wb = openpyxl.load_workbook(io.BytesIO(zf.read(members[0])), read_only=True, data_only=True)
        values = list(wb["Statewide Candidates"].iter_rows(values_only=True))
        wb.close()
        head = next(
            i for i, r in enumerate(values) if "United States Representative" in [str(c).strip() for c in r]
        )
        titles = {j: str(c).strip() for j, c in enumerate(values[head]) if c}
        names = values[head + 1]
        total = next(r for r in values if str(r[0] or "").strip().lower() == "total")
        starts = sorted(titles)
        for k, start in enumerate(starts):
            title = titles[start]
            if title == "United States Senator":
                office, district = "us_senate", None
            elif title == "United States Representative":
                office, district = "us_house", 0
            else:
                continue
            end = starts[k + 1] if k + 1 < len(starts) else len(names)
            candidates = []
            for j in range(start, end):
                label = str(names[j] or "").strip()
                if not label or label in {"Overvotes", "Undervotes"}:
                    continue
                m = _WY_PARTY.search(label)
                party = m.group(1) if m else "Write-in"
                candidates.append({"party": party, "votes": int(total[j] or 0)})
            rows.append(
                from_candidates(pd.DataFrame(candidates), state_po="WY", office=office, district_num=district)
            )
    return pd.DataFrame(rows)


@register("SC")
def south_carolina(paths: Sequence[Path]) -> pd.DataFrame:
    """SC State Election Commission on Clarity: the general election's summary.zip, plus
    any recount published as a separate Clarity election (file name contains
    ``recount``). A race found in a recount file replaces the same race from the general
    file; the recount is the later official count of the same contest."""
    kwargs = {
        "state": "SC",
        "senate": r"^U\.S\.\s+Senate",
        "house": r"^U\.S\.\s+House of Representatives,\s+District\s+(\d+)",
    }
    general = [p for p in paths if "recount" not in p.name.lower()]
    recounts = [p for p in paths if "recount" in p.name.lower()]
    if not recounts:
        return clarity_summary(general, **kwargs)
    if not general:
        return clarity_summary(recounts, **kwargs)
    base = clarity_summary(general, **kwargs)
    override = clarity_summary(recounts, **kwargs)
    keys = ["office", "district_num"]
    kept = base.merge(override[keys], on=keys, how="left", indicator=True)
    kept = kept[kept["_merge"] == "left_only"].drop(columns="_merge")
    return pd.concat([kept, override], ignore_index=True)


_MN_HOUSE = re.compile(r"^U\.S\. Representative District (\d{1,2})$")


@register("MN")
def minnesota(paths: Sequence[Path]) -> pd.DataFrame:
    """Minnesota SOS media text files (``ushouse.txt``, ``ussenate.txt``): semicolon-
    delimited, no header, one row per candidate statewide. Fields used: 4 office name,
    10 party abbreviation (DFL is the Democratic party), 13 votes. County files
    (``USHouseCty.txt``) are not read."""
    rows = []
    for path in paths:
        if path.name.lower().endswith("cty.txt"):
            continue
        data = pd.read_csv(path, sep=";", header=None, dtype=str, keep_default_na=False, encoding="latin-1")
        for contest, group in data.groupby(4):
            name = str(contest).strip()
            if m := _MN_HOUSE.match(name):
                office, district = "us_house", int(m.group(1))
            elif name.startswith("U.S. Senator") and "SPECIAL" not in name.upper():
                office, district = "us_senate", None
            else:
                continue
            frame = pd.DataFrame({"party": group[10], "votes": pd.to_numeric(group[13])})
            rows.append(from_candidates(frame, state_po="MN", office=office, district_num=district))
    return pd.DataFrame(rows)


_LA_HOUSE = re.compile(r"^U\. ?S\. Representative -- (\d{1,2})(?:st|nd|rd|th) Congressional District$")
_LA_PARTY = re.compile(r"\(([A-Z]+)\)\s*$")


@register("LA")
def louisiana(paths: Sequence[Path]) -> pd.DataFrame:
    """Louisiana SOS voter portal ``ByParish_<raceId>.csv`` files, one race each: an
    ``Office`` column, a ``Parish`` column, then one column per candidate ``Name (PARTY)``.

    House races on November 3 are first rounds of Louisiana's majority system: a race is
    resolved only if its top candidate has more than half the votes; otherwise it goes to
    the December runoff and ``outcome_resolved`` is False (unscoreable until then). The
    Senate race cannot have a runoff and is an ordinary general.
    """
    rows = []
    for path in paths:
        data = pd.read_csv(path, dtype=str, keep_default_na=False)
        offices = data["Office"].str.strip().unique()
        if len(offices) != 1:
            raise ValueError(f"{path.name}: expected one race, found {list(offices)}")
        office_name = offices[0]
        candidates = []
        for column in data.columns[2:]:
            m = _LA_PARTY.search(column)
            votes = pd.to_numeric(data[column].str.replace(",", "")).sum()
            candidates.append({"party": m.group(1) if m else "", "votes": int(votes)})
        frame = pd.DataFrame(candidates)
        if m := _LA_HOUSE.match(office_name):
            row = from_candidates(frame, state_po="LA", office="us_house", district_num=int(m.group(1)))
            total = int(frame["votes"].sum())
            row["election_round"] = "first_round"
            row["outcome_resolved"] = bool(total and frame["votes"].max() * 2 > total)
            if not row["outcome_resolved"]:
                row["winner_party"] = None  # a first-round leader is not a winner
        elif office_name.replace(" ", "") == "U.S.Senator":
            row = from_candidates(frame, state_po="LA", office="us_senate", district_num=None)
            row["election_round"] = "general"
            row["outcome_resolved"] = True
        else:
            continue
        rows.append(row)
    return pd.DataFrame(rows)


_GA_HOUSE = re.compile(r"^US House of Representatives - District (\d{1,2})$")


@register("GA")
def georgia(paths: Sequence[Path]) -> pd.DataFrame:
    """Georgia SOS results ``Total Votes`` workbook: one row per contest choice (Office
    Name, Ballot Name, Party, Total) and a ``Total Votes`` row per contest, used only to
    cross-check that the choices sum to the contest total."""
    import openpyxl

    rows = []
    for path in paths:
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        values = list(wb["Total Votes"].iter_rows(values_only=True))
        wb.close()
        head = [str(c or "").strip() for c in values[0]]
        data = pd.DataFrame(values[1:], columns=head)[["Office Name", "Ballot Name", "Party", "Total"]]
        data = data.dropna(subset=["Office Name"])
        for contest, group in data.groupby("Office Name"):
            name = str(contest).strip()
            if m := _GA_HOUSE.match(name):
                office, district = "us_house", int(m.group(1))
            elif name == "US Senate":
                office, district = "us_senate", None
            else:
                continue
            is_total = group["Ballot Name"].astype(str).str.strip().eq("Total Votes")
            choices = group[~is_total]
            frame = pd.DataFrame(
                {"party": choices["Party"].fillna(""), "votes": pd.to_numeric(choices["Total"])}
            )
            if is_total.any() and int(frame["votes"].sum()) != int(
                pd.to_numeric(group[is_total]["Total"]).sum()
            ):
                raise ValueError(f"{path.name} / {name}: choices do not sum to Total Votes")
            rows.append(from_candidates(frame, state_po="GA", office=office, district_num=district))
    return pd.DataFrame(rows)


_VA_HOUSE = re.compile(r"^Member, House of Representatives \((\d{1,2})(?:st|nd|rd|th) District\)$")


@register("VA")
def virginia(paths: Sequence[Path]) -> pd.DataFrame:
    """Virginia ELECT ``Election Results`` CSV (precinct level, Windows-1252): summed per
    office over all precincts, provisional and absentee pseudo-precincts included. Write-in
    rows (``WRITE IN VOTES``) carry their count in ``WriteInVote``, not ``TOTAL_VOTES``."""
    rows = []
    for path in paths:
        data = pd.read_csv(io.StringIO(_decode(path.read_bytes())), dtype=str, keep_default_na=False)
        total = pd.to_numeric(data["TOTAL_VOTES"].str.replace(",", ""), errors="coerce")
        write_in = pd.to_numeric(data["WriteInVote"].str.replace(",", ""), errors="coerce")
        is_write_in = data["CandidateName"].str.strip().str.upper().eq("WRITE IN VOTES")
        data = data.assign(
            votes=total.where(~is_write_in, write_in).fillna(0),
            party=data["Party"].where(~is_write_in, "Write-in"),
        )
        for contest, group in data.groupby("OfficeTitle"):
            name = str(contest).strip()
            if m := _VA_HOUSE.match(name):
                office, district = "us_house", int(m.group(1))
            elif name == "Member, United States Senate":
                office, district = "us_senate", None
            else:
                continue
            frame = group.groupby(["CandidateName", "party"], as_index=False)["votes"].sum()
            rows.append(from_candidates(frame, state_po="VA", office=office, district_num=district))
    return pd.DataFrame(rows)

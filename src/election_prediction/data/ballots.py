"""Official ballot facts and the current House roster, without contact fields."""

from __future__ import annotations

import csv
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd

from ..features.candidate_crosswalk import split_name
from ..geography import reference

PARTIES = {"DEM": "DEMOCRAT", "REP": "REPUBLICAN", "D": "DEMOCRAT", "R": "REPUBLICAN"}
BALLOT_COLUMNS = ["state_po", "office", "district_num", "candidate_name", "party"]


def house_roster(path: Path) -> pd.DataFrame:
    root = ET.parse(path).getroot()
    rows = []
    for member in root.findall("./members/member"):
        key = member.findtext("statedistrict", "")
        if (
            len(key) != 4
            or key[:2] not in reference.STATES
            or key[:2] == "DC"
            or reference.by_postal(key[:2]).census_region == "Territory"
        ):
            continue
        name = member.findtext("member-info/official-name", "").strip()
        rows.append(
            {
                "state_po": key[:2],
                "district_num": int(key[2:]),
                "incumbent_name": name if name.lower() != "vacant" else "",
                "incumbent_party": PARTIES.get(member.findtext("member-info/party", ""), "OTHER"),
                "roster_published_on": root.attrib.get("publish-date", ""),
            }
        )
    out = pd.DataFrame(rows)
    if len(out) != 435 or out.duplicated(["state_po", "district_num"]).any():
        raise ValueError("House Clerk roster must contain all 435 voting districts")
    return out


def california(path: Path) -> pd.DataFrame:
    rows = []
    for line in path.read_text(encoding="cp1252").splitlines():
        if not line.startswith("[C|"):
            continue
        fields = next(csv.reader([line.strip("[]")], delimiter="|"))
        contest = fields[3]
        if not contest.startswith("110000"):
            continue
        rows.append(
            {
                "state_po": "CA",
                "office": "us_house",
                "district_num": int(contest[6:8]),
                "candidate_name": fields[10],
                "party": {"01": "DEMOCRAT", "02": "REPUBLICAN"}.get(fields[9], "OTHER"),
            }
        )
    return validate(pd.DataFrame(rows), state="CA", expected_house=52, expected_senate=0)


def texas(path: Path) -> pd.DataFrame:
    from pypdf import PdfReader

    rows = []
    contest: tuple[str, int] | None = None
    for page in PdfReader(path).pages:
        for text in (page.extract_text(extraction_mode="layout") or "").splitlines():
            line = text.strip()
            heading = re.fullmatch(r"U\.\s*S\.\s*(SENATOR|REPRESENTATIVE\s+DISTRICT\s+(\d+))", line)
            if heading:
                contest = ("us_senate", 0) if heading[1] == "SENATOR" else ("us_house", int(heading[2]))
                continue
            candidate = re.fullmatch(r"(.+?)\s+(REP|DEM|LIB|GRE|IND)", line)
            if contest and candidate:
                rows.append(
                    {
                        "state_po": "TX",
                        "office": contest[0],
                        "district_num": contest[1],
                        "candidate_name": candidate[1],
                        "party": PARTIES.get(candidate[2], "OTHER"),
                    }
                )
            elif line and line.isupper() and not line.startswith(("County ", "2026 ")):
                contest = None
    return validate(pd.DataFrame(rows).drop_duplicates(), state="TX", expected_house=38, expected_senate=1)


def north_carolina(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, usecols=["election_dt", "contest_name", "name_on_ballot", "party_candidate"])
    frame = frame[pd.to_datetime(frame.election_dt).eq(pd.Timestamp("2026-11-03"))]
    rows = []
    for row in frame.drop_duplicates().to_dict(orient="records"):
        name = str(row["contest_name"])
        district = re.fullmatch(r"US HOUSE OF REPRESENTATIVES DISTRICT (\d+)", name)
        if name != "US SENATE" and not district:
            continue
        rows.append(
            {
                "state_po": "NC",
                "office": "us_house" if district else "us_senate",
                "district_num": int(district[1]) if district else 0,
                "candidate_name": row["name_on_ballot"],
                "party": PARTIES.get(row["party_candidate"], "OTHER"),
            }
        )
    return validate(pd.DataFrame(rows), state="NC", expected_house=14, expected_senate=1)


def florida(path: Path) -> pd.DataFrame:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(path.read_bytes(), "html.parser")
    rows = []
    for table in soup.select("table.results"):
        heading = table.find_previous(["h2", "h3", "b", "strong", "p"])
        title = heading.get_text(" ", strip=True) if heading else ""
        if title not in {"United States Senator", "United States Representative"}:
            continue
        house = title == "United States Representative"
        district = 0
        for tr in table.find_all("tr"):
            if not tr.find("a", href=re.compile("CanDetail", re.I)):
                continue
            cells = [td.get_text(" ", strip=True) for td in tr.find_all("td", recursive=False)]
            if not cells:
                continue
            if house and len(cells) == 5:
                value = cells.pop(0)
                if value:
                    district = int(value)
            if len(cells) != 4:
                raise ValueError("Florida ballot table layout changed")
            name, status, primary, _ = cells
            if status.strip() not in {"Qualified", "Unopposed", "Elected"} or primary == "Eliminated":
                continue
            match = re.match(r"(.+?)\s*\((DEM|REP|NPA|WRI|LPF|GRE|FFP|IND)\)", name)
            if not match:
                raise ValueError("Florida ballot candidate has no recognized party field")
            raw_name = re.sub(r"\s+", " ", match[1]).strip()
            if "," in raw_name:
                last, first = raw_name.split(",", 1)
                raw_name = f"{first.strip()} {last.strip()}"
            rows.append(
                {
                    "state_po": "FL",
                    "office": "us_house" if house else "us_senate",
                    "district_num": district,
                    "candidate_name": raw_name,
                    "party": PARTIES.get(match[2], "OTHER"),
                }
            )
    return validate(pd.DataFrame(rows), state="FL", expected_house=28, expected_senate=1)


def new_york(path: Path) -> pd.DataFrame:
    from pypdf import PdfReader

    rows = []
    active, district = False, None
    for page in PdfReader(path).pages:
        for line in (page.extract_text(extraction_mode="layout") or "").splitlines():
            text = line.strip()
            if text.startswith("Office:"):
                active = "Representative in Congress" in text
                district = None
            elif active and text.startswith("District:"):
                district = int(text.split(":", 1)[1].strip())
            elif active and district is not None:
                fields = re.split(r"\s{2,}", text, maxsplit=1)
                if len(fields) != 2 or fields[0].startswith(
                    ("Counties:", "Vote For:", "Party", "Certification")
                ):
                    continue
                party, name = fields
                if not re.fullmatch(r"[A-Za-z &'-]+", party) or len(name.split()) < 2:
                    continue
                rows.append(
                    {
                        "state_po": "NY",
                        "office": "us_house",
                        "district_num": district,
                        "candidate_name": re.sub(r"\s+", " ", name),
                        "party": {"Democratic": "DEMOCRAT", "Republican": "REPUBLICAN"}.get(party, "OTHER"),
                    }
                )
    frame = pd.DataFrame(rows)
    # A fusion line is another line for the same candidate, not another candidate.
    grouped = []
    for _, group in frame.groupby(["state_po", "office", "district_num", "candidate_name"], sort=False):
        major = set(group.party) & {"DEMOCRAT", "REPUBLICAN"}
        if len(major) > 1:
            raise ValueError("cross-endorsed candidate needs explicit party review")
        row = group.iloc[0].to_dict()
        row["party"] = next(iter(major)) if major else "OTHER"
        grouped.append(row)
    return validate(pd.DataFrame(grouped), state="NY", expected_house=26, expected_senate=0)


def maryland(path: Path) -> pd.DataFrame:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(path.read_bytes(), "html.parser")
    summary = soup.find("summary", id="representativeincongressbydistrict")
    if summary is None or summary.parent is None:
        raise ValueError("Maryland general ballot table missing")
    rows = []
    for heading in summary.parent.find_all("h3"):
        # Status terms are explicit in the official list, regardless of CSS classes.
        status = next(
            (tag for tag in heading.find_all_next("dt") if tag.get_text(strip=True) == "Status"), None
        )
        value = status.find_next_sibling("dd") if status is not None else None
        if value is None or value.get_text(" ", strip=True) != "Active":
            continue
        district_heading = heading.find_previous("h2")
        if district_heading is None:
            raise ValueError("Maryland candidate has no district heading")
        district = district_heading.get_text(" ", strip=True).split()[-1]
        party = str(heading.next_sibling).strip()
        rows.append(
            {
                "state_po": "MD",
                "office": "us_house",
                "district_num": int(district),
                "candidate_name": heading.get_text(" ", strip=True),
                "party": {"Democratic": "DEMOCRAT", "Republican": "REPUBLICAN"}.get(party, "OTHER"),
            }
        )
    return validate(pd.DataFrame(rows), state="MD", expected_house=8, expected_senate=0)


def michigan(path: Path) -> pd.DataFrame:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(path.read_bytes(), "html.parser")
    table = soup.find("table", id="JR_PAGE_ANCHOR_0_1")
    if table is None:
        raise ValueError("Michigan official candidate table missing")
    contest: tuple[str, int] | None = None
    rows = []
    for tr in table.find_all("tr", recursive=False):
        cells = [td.get_text(" ", strip=True) for td in tr.find_all("td", recursive=False)]
        if len(cells) == 3 and cells[1]:
            title = cells[1]
            district = re.match(r"(\d+)(?:st|nd|rd|th) District Representative in Congress", title)
            contest = (
                ("us_senate", 0)
                if title.startswith("U.S. Senate ")
                else ("us_house", int(district[1]))
                if district
                else None
            )
        elif contest and len(cells) >= 5 and cells[4] and cells[3].endswith("Party"):
            if any(token in " ".join(cells[:3]).upper() for token in ("DISQ", "WITHD")):
                continue
            name = cells[4]
            if "," in name:
                last, first = name.split(",", 1)
                name = f"{first.strip()} {last.strip()}"
            rows.append(
                {
                    "state_po": "MI",
                    "office": contest[0],
                    "district_num": contest[1],
                    "candidate_name": name,
                    "party": {"Democratic Party": "DEMOCRAT", "Republican Party": "REPUBLICAN"}.get(
                        cells[3], "OTHER"
                    ),
                }
            )
    return validate(pd.DataFrame(rows), state="MI", expected_house=13, expected_senate=1)


def validate(frame: pd.DataFrame, *, state: str, expected_house: int, expected_senate: int) -> pd.DataFrame:
    if frame.empty or not set(BALLOT_COLUMNS).issubset(frame):
        raise ValueError("ballot parser returned no canonical candidate rows")
    if set(frame.state_po) != {state} or frame[BALLOT_COLUMNS].isna().any().any():
        raise ValueError("ballot facts have missing values or wrong state")
    races = frame[["office", "district_num"]].drop_duplicates()
    house = set(races.loc[races.office.eq("us_house"), "district_num"].astype(int))
    expected = {0} if expected_house == 1 else set(range(1, expected_house + 1))
    if house != expected or races.office.eq("us_senate").sum() != expected_senate:
        raise ValueError(f"incomplete official ballot coverage for {state}: {sorted(house)}")
    if frame.duplicated(["office", "district_num", "candidate_name", "party"]).any():
        raise ValueError("duplicate ballot candidate")
    return frame.reset_index(drop=True)


def delaware(path: Path) -> pd.DataFrame:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(path.read_bytes(), "html.parser")
    text = soup.get_text(" ", strip=True)
    if "November 3, 2026 General Election" not in text:
        raise ValueError("Delaware source is not the November general sample ballot")
    rows = []
    for tr in soup.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all("td", recursive=False)]
        if not cells or cells[0] not in {"U.S. Senator", "Representative In Congress"}:
            continue
        if len(cells) != 5 or cells[1] != "Vote for 1":
            raise ValueError("Delaware federal sample ballot layout changed")
        for name, party in zip(cells[2:4], ("DEMOCRAT", "REPUBLICAN"), strict=True):
            rows.append(
                {
                    "state_po": "DE",
                    "office": "us_senate" if cells[0] == "U.S. Senator" else "us_house",
                    "district_num": 0,
                    "candidate_name": name,
                    "party": party,
                }
            )
    return validate(pd.DataFrame(rows), state="DE", expected_house=1, expected_senate=1)


def new_jersey(path: Path) -> pd.DataFrame:
    from pypdf import PdfReader

    rows = []
    reader = PdfReader(path)
    house = "Candidates for House of Representatives" in (reader.pages[0].extract_text() or "")
    ordinals = [
        "First",
        "Second",
        "Third",
        "Fourth",
        "Fifth",
        "Sixth",
        "Seventh",
        "Eighth",
        "Ninth",
        "Tenth",
        "Eleventh",
        "Twelfth",
    ]
    for page in reader.pages:
        text = page.extract_text(extraction_mode="layout") or ""
        if "ForGENERALELECTION11/03/2026" not in re.sub(r"\s+", "", text) or "Official List" not in text:
            raise ValueError("New Jersey source is not the official November general list")
        district = 0
        if house:
            heading = re.search(r"(\w+) Congressional District:", text)
            if heading is None:
                if "Candidate Totals for Party" in text:
                    continue
                raise ValueError("New Jersey House district heading missing")
            district = ordinals.index(heading[1]) + 1
        lines = text.splitlines()
        header = next((line for line in lines if re.match(r"Name\s+Address\s+Party\s+County", line)), None)
        if header is None:
            continue
        address_col, party_col, county_col = [header.index(label) for label in ("Address", "Party", "County")]
        for line in lines:
            name = line[:address_col].strip().removesuffix("*").strip()
            party = line[party_col:county_col].strip()
            if party not in {"Democratic", "Republican"} or not name or name == "Name":
                continue
            if len(name.split()) < 2 or not re.fullmatch(r"[A-Z .'\-]+", name):
                raise ValueError("New Jersey candidate column unexpectedly truncated")
            rows.append(
                {
                    "state_po": "NJ",
                    "office": "us_house" if house else "us_senate",
                    "district_num": district,
                    "candidate_name": name,
                    "party": "DEMOCRAT" if party == "Democratic" else "REPUBLICAN",
                }
            )
    # Minor-party candidates are not inferred from the variable-width slogan column.
    # This parser establishes positive incumbent presence only; absence cannot establish retirement.
    frame = pd.DataFrame(rows)
    frame["positive_evidence_only"] = True
    return validate(frame, state="NJ", expected_house=12 if house else 0, expected_senate=0 if house else 1)


def identity(name: str) -> tuple[str, str]:
    # Match only a unique surname/first initial within a state/office roster. No fuzzy score.
    last, first = split_name(name)
    return last, first[:1]

"""Source-specific presidential precinct repair parsers, with no heuristic de-duplication."""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

import pandas as pd


def florida_federal_specials(path: Path) -> dict[int, dict[str, int]]:
    """Read the official April 1 federal table, not its frameset or legislative primary."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(path.read_bytes(), "html.parser")
    text = soup.get_text(" ", strip=True)
    if "April 1, 2025" not in text or "Official Results" not in text:
        raise ValueError("Florida source is not the official April 1 special results table")
    found = {}
    for table in soup.find_all("table"):
        rows = [
            [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"], recursive=False)]
            for tr in table.find_all("tr", recursive=False)
        ]
        if not rows or not rows[0] or not re.fullmatch(r"District: (1|6)", rows[0][0]):
            continue
        district = int(rows[0][0].split()[-1])
        if district in found or len(rows) < 3 or rows[2][0] != "Total" or len(rows[1]) != len(rows[2]):
            raise ValueError("Florida special results layout changed")
        totals = {"dem_votes": 0, "rep_votes": 0, "other_votes": 0}
        for name, count in zip(rows[1][1:], rows[2][1:], strict=True):
            match = re.fullmatch(r".+\((DEM|REP|NPA|WRI|LPF)\)", name)
            if match is None or not re.fullmatch(r"[\d,]+", count):
                raise ValueError("Florida candidate party/count requires review")
            key = {"DEM": "dem_votes", "REP": "rep_votes"}.get(match[1], "other_votes")
            totals[key] += int(count.replace(",", ""))
        found[district] = totals
    if set(found) != {1, 6}:
        raise ValueError("Florida official page needs both congressional specials")
    return found


def north_carolina_president(path: Path, counties: pd.DataFrame, *, cycle: int) -> pd.DataFrame:
    """Original public administrative-precinct results, never noise-reversed precinct sorts."""
    with zipfile.ZipFile(path) as archive:
        names = [n for n in archive.namelist() if n.endswith(".txt")]
        if len(names) != 1:
            raise ValueError("NC results ZIP must contain exactly one results TXT")
        with archive.open(names[0]) as handle:
            frame = pd.read_csv(handle, sep="\t", dtype=str)
    required = {
        "County",
        "Election Date",
        "Precinct",
        "Contest Name",
        "Choice",
        "Choice Party",
        "Total Votes",
    }
    if not required.issubset(frame):
        raise ValueError("NC official results schema changed")
    frame = frame[
        frame["Contest Name"].eq("US PRESIDENT") & frame["Choice Party"].isin(["DEM", "REP"])
    ].copy()
    if frame.empty or not pd.to_datetime(frame["Election Date"]).dt.year.eq(cycle).all():
        raise ValueError("NC presidential contest missing or wrong election year")
    if frame.duplicated(["County", "Precinct", "Choice Party"]).any():
        raise ValueError("NC duplicate party/precinct rows require review")
    frame["votes"] = pd.to_numeric(frame["Total Votes"], errors="raise")
    if not frame.votes.ge(0).all() or not frame.votes.mod(1).eq(0).all():
        raise ValueError("NC published votes must be nonnegative integers")
    lookup = counties[counties.STATEFP.eq("37")].assign(county_name=lambda d: d.NAME.str.upper())
    mapping = lookup.set_index("county_name").GEOID.to_dict()
    if set(frame.County) != set(mapping):
        raise ValueError("NC official results must cover all 100 counties")
    return pd.DataFrame(
        {
            "county_name": frame.County,
            "county_fips": frame.County.map(mapping),
            "precinct": frame.Precinct,
            "party": frame["Choice Party"].map({"DEM": "DEMOCRAT", "REP": "REPUBLICAN"}),
            "votes": frame.votes,
        }
    )


def georgia_special(path: Path, *, district: int) -> dict[str, int]:
    """One congressional contest only; exclude adjacent legislative contests and totals."""
    frame = pd.read_excel(path, sheet_name="Total Votes")
    if not {"Contest ID", "Ballot Name", "Party", "Total"}.issubset(frame):
        raise ValueError("Georgia total-votes workbook schema changed")
    contest = frame[frame["Contest ID"].eq(f"USH{district}")]
    totals = contest[contest["Ballot Name"].str.strip().eq("Total Votes")]
    candidates = contest[~contest.index.isin(totals.index)]
    if len(totals) != 1 or candidates.empty:
        raise ValueError("Georgia contest needs candidates and exactly one published total")
    counts = {"dem_votes": 0, "rep_votes": 0, "other_votes": 0}
    for row in candidates.to_dict(orient="records"):
        party = str(row["Party"]).strip().lower()
        if party == "nan":
            match = re.search(r"(?:\(|-\s*)(Dem|Rep|Ind|Lib)\)?\s*$", str(row["Ballot Name"]))
            if match is None:
                raise ValueError("Georgia candidate has no explicit party")
            party = match[1].lower()
        value = float(row["Total"])
        if not pd.notna(value) or value < 0 or not value.is_integer():
            raise ValueError("Georgia count must be a nonnegative integer")
        key = {"dem": "dem_votes", "rep": "rep_votes"}.get(party, "other_votes")
        counts[key] += int(value)
    if sum(counts.values()) != float(totals.Total.iloc[0]):
        raise ValueError("Georgia candidate counts do not reconcile to published contest total")
    return counts


def kansas_2024(path: Path, counties: pd.DataFrame) -> pd.DataFrame:
    county_ids = counties[counties.STATEFP.eq("20")].set_index("NAME").GEOID.to_dict()
    rows = []
    suppressed = []
    tidy = pd.read_excel(path, sheet_name="OfficialPrecinctLevelResults")
    required = {"County", "Precinct", "Candidate", "Party", "Votes", "VTD"}
    if not required.issubset(tidy):
        raise ValueError("Kansas official precinct workbook schema changed")
    for row in tidy.to_dict(orient="records"):
        county, precinct = str(row["County"]).strip(), str(row["Precinct"]).strip()
        if county not in county_ids:
            raise ValueError(f"unrecognized Kansas county {county}")
        party = str(row["Party"]).strip().lower()
        if pd.isna(row["Votes"]):
            suppressed.append({"county": county, "precinct": precinct, "reason": "blank published count"})
            continue
        rows.append(
            {
                "county_name": county,
                "county_fips": county_ids[county],
                "precinct": precinct,
                "vtd_key": str(row["VTD"]),
                "party": {"democratic": "DEMOCRAT", "republican": "REPUBLICAN"}.get(party, "OTHER"),
                "votes": row["Votes"],
            }
        )
    # These are distinct published layouts, explicitly mapped to their named candidates.
    layouts = {
        "JOHNSON": (0, 1, 3, 6, [4, 5]),
        "SEDGWICK": (0, None, 1, 4, [2, 3]),
        "SHAWNEE": (0, None, 2, 3, [4, 5]),
        "WYANDOTTE": (0, None, 1, 4, [2, 3]),
    }
    for sheet, (precinct_col, vtd_col, dem_col, rep_col, other_cols) in layouts.items():
        table = pd.read_excel(path, sheet_name=sheet, header=None)
        county = sheet.title()
        for values in table.iloc[2:].itertuples(index=False, name=None):
            precinct = str(values[precinct_col]).strip()
            if (
                precinct.upper() == "COUNTY TOTALS"
                or precinct.lower().startswith(("total", "nan"))
                or not precinct
            ):
                continue
            if str(values[dem_col]).strip() == "KSA 25-2701(a)(2)":
                suppressed.append({"county": county, "precinct": precinct})
                continue
            votes = pd.to_numeric(
                pd.Series([values[dem_col], values[rep_col], *[values[i] for i in other_cols]]),
                errors="coerce",
            )
            if votes.isna().any():
                raise ValueError(f"non-numeric Kansas precinct row in {sheet}: {precinct}")
            for party, value in [
                ("DEMOCRAT", votes.iloc[0]),
                ("REPUBLICAN", votes.iloc[1]),
                ("OTHER", votes.iloc[2:].sum()),
            ]:
                rows.append(
                    {
                        "county_name": county,
                        "county_fips": county_ids[county],
                        "precinct": precinct,
                        "vtd_key": str(values[vtd_col]) if vtd_col is not None else None,
                        "party": party,
                        "votes": value,
                    }
                )
    frame = pd.DataFrame(rows)
    frame["votes"] = pd.to_numeric(frame.votes, errors="raise")
    if not frame.votes.ge(0).all() or not frame.votes.mod(1).eq(0).all():
        raise ValueError("Kansas votes must be nonnegative integers")
    if set(frame.county_name) != set(county_ids):
        raise ValueError("Kansas presidential repair must cover all 105 counties")
    # Multiple write-ins can legitimately share OTHER; collapse only at the declared party grain.
    out = frame.groupby(
        ["county_fips", "county_name", "precinct", "vtd_key", "party"], dropna=False, as_index=False
    ).votes.sum()
    out.attrs["suppressed_rows"] = suppressed
    return out


def reconciliation(frame: pd.DataFrame, races: pd.DataFrame, *, state: str, cycle: int) -> dict:
    certified = races[races.cycle.eq(cycle) & races.office.eq("president") & races.state_po.eq(state)]
    if len(certified) != 1:
        raise ValueError("repair requires one certified statewide presidential target")
    totals = frame.groupby("party").votes.sum()
    expected = certified.iloc[0]
    comparisons = {
        "dem_votes": {"parsed": float(totals.get("DEMOCRAT", 0)), "certified": float(expected.dem_votes)},
        "rep_votes": {"parsed": float(totals.get("REPUBLICAN", 0)), "certified": float(expected.rep_votes)},
    }
    return {
        "state_po": state,
        "cycle": cycle,
        "counties": int(frame.county_fips.nunique()),
        "comparisons": comparisons,
        "reconciles": all(v["parsed"] == v["certified"] for v in comparisons.values()),
        "suppressed_rows": frame.attrs.get("suppressed_rows", []),
        "district_assignment": "Not inferred; published VTD retained; split-county geography gated",
    }

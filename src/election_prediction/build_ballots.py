"""Acquire official general-election lists and explicitly reconcile current incumbents."""

from __future__ import annotations

import argparse
import json
import re
import shutil
from datetime import date
from pathlib import Path

import pandas as pd

from .data import acquire, ballots
from .data.manifest import sha256_file
from .data.privacy import PrivacyTier
from .data.public_sources import snapshot
from .features import senate_roster
from .features.candidate_crosswalk import split_name

SOURCES = {
    "CA": ("https://media.sos.ca.gov/media/C26GG.txt", "California Secretary of State", "C26GG.txt", "text"),
    "TX": (
        "https://www.sos.texas.gov/elections/forms/2026-ballot-cert.pdf",
        "Texas Secretary of State",
        "2026-ballot-cert.pdf",
        "pdf",
    ),
    "NC": (
        "https://s3.amazonaws.com/dl.ncsbe.gov/Elections/2026/Candidate%20Filing/Candidate_Listing_2026.csv",
        "North Carolina State Board of Elections",
        "Candidate_Listing_2026.csv",
        "csv",
    ),
    "FL": (
        "https://dos.elections.myflorida.com/candidates/canlist.asp?elecid=20261103-GEN",
        "Florida Division of Elections",
        "candidates.html",
        "html",
    ),
    "NY": (
        "https://elections.ny.gov/certification-november-3-2026-general-election",
        "New York State Board of Elections",
        "ballot.pdf",
        "pdf",
    ),
    "MD": (
        "https://elections.maryland.gov/elections/2026/general_candidates/2026_GG_statewide_candidatelist.html",
        "Maryland State Board of Elections",
        "candidates.html",
        "html",
    ),
    "MI": (
        "https://mi-boe.entellitrak.com/etk-mi-boe-prod/page.request.do?electionType=GEN&electionYear=2026&page=page.miboePublicReport",
        "Michigan Department of State",
        "candidates.html",
        "html",
    ),
    "DE": (
        "https://elections.delaware.gov/elections/general/sampleballots/GE2026/01-01.html",
        "Delaware Department of Elections",
        "sample.html",
        "html",
    ),
    "NJ": (
        "https://www.nj.gov/state/elections/assets/pdf/election-results/2026/"
        "2026-official-general-candidates-us-house-0904.pdf",
        "New Jersey Division of Elections",
        "house.pdf",
        "pdf",
    ),
}
EXTRA_SOURCES = {
    "NJ": (
        "https://www.nj.gov/state/elections/assets/pdf/election-results/2026/"
        "2026-official-general-candidates-us-senate.pdf",
        "New Jersey Division of Elections",
        "senate.pdf",
        "pdf",
    )
}
PARSERS = {
    "CA": ballots.california,
    "TX": ballots.texas,
    "NC": ballots.north_carolina,
    "FL": ballots.florida,
    "NY": ballots.new_york,
    "MD": ballots.maryland,
    "MI": ballots.michigan,
    "DE": ballots.delaware,
    "NJ": ballots.new_jersey,
}


def compile_evidence(
    candidates: pd.DataFrame,
    roster: pd.DataFrame,
    *,
    as_of: str,
    identity_reviews: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, list]:
    rows, ambiguous = [], []
    reviews = identity_reviews if identity_reviews is not None else pd.DataFrame()
    if not reviews.empty:
        reviews = reviews[pd.to_datetime(reviews.retrieved_on).le(pd.Timestamp(as_of))]
        if reviews.duplicated(["state_po", "office", "ballot_name", "incumbent_name"]).any():
            raise ValueError("duplicate candidate identity review")
    for (state, office, district), group in candidates.groupby(["state_po", "office", "district_num"]):
        holders = roster[roster.state_po.eq(state) & roster.office.eq(office)]
        current = holders[holders.district_num.fillna(0).eq(district)]
        if len(current) != 1:
            raise ValueError(f"ballot has no unique current seat identity: {state} {office} {district}")
        incumbent = current.iloc[0]
        pool: dict[tuple[str, str], list[dict]] = {}
        for holder in holders.to_dict(orient="records"):
            pool.setdefault(ballots.identity(holder["incumbent_name"]), []).append(holder)
        on_ballot = []
        unresolved_identity = False
        reviewed_candidates = set()
        for candidate in group.to_dict(orient="records"):
            possible = pool.get(ballots.identity(candidate["candidate_name"]), [])
            candidate_first = split_name(candidate["candidate_name"])[1]
            decisions = (
                reviews[
                    reviews.state_po.eq(state)
                    & reviews.office.eq(office)
                    & reviews.ballot_name.eq(candidate["candidate_name"])
                ]
                if not reviews.empty
                else pd.DataFrame()
            )
            if not decisions.empty:
                if not decisions.same_person.astype(str).isin(["True", "False"]).all():
                    raise ValueError("identity same_person must be explicit True or False")
                reviewed_candidates.add(candidate["candidate_name"])
                rejected = set(decisions.loc[decisions.same_person.astype(str).eq("False"), "incumbent_name"])
                possible = [h for h in possible if h["incumbent_name"] not in rejected]
            matches = [
                holder for holder in possible if split_name(holder["incumbent_name"])[1] == candidate_first
            ]
            if not decisions.empty:
                accepted = set(decisions.loc[decisions.same_person.astype(str).eq("True"), "incumbent_name"])
                reviewed_holders = [
                    h for h in holders.to_dict(orient="records") if h["incumbent_name"] in accepted
                ]
                if accepted and len(reviewed_holders) != len(accepted):
                    raise ValueError("identity review does not match the current roster")
                matches = reviewed_holders or matches
            if possible and not matches:
                unresolved_identity = True
                ambiguous.append(
                    {
                        "state_po": state,
                        "office": office,
                        "candidate": candidate["candidate_name"],
                        "reason": "surname/initial hit but given names differ; alias review required",
                    }
                )
            if len(matches) > 1:
                unresolved_identity = True
                ambiguous.append(
                    {"state_po": state, "office": office, "candidate": candidate["candidate_name"]}
                )
                continue
            if matches:
                on_ballot.append(matches[0])
        if unresolved_identity:
            continue
        key = f"2026_{office}_{state.lower()}" + (f"_{int(district):02d}" if office == "us_house" else "")
        running = any(h["incumbent_name"] == incumbent.incumbent_name for h in on_ballot)
        positive_only = "positive_evidence_only" in group and group.positive_evidence_only.fillna(False).any()
        if positive_only and not running:
            ambiguous.append({"race_key": key, "reason": "partial candidate extraction cannot prove absence"})
            continue
        row = {
            "race_key": key,
            "incumbent_name": incumbent.incumbent_name or "VACANT",
            "incumbent_running": running,
            "dem_nominee": " | ".join(group.loc[group.party.eq("DEMOCRAT"), "candidate_name"]),
            "rep_nominee": " | ".join(group.loc[group.party.eq("REPUBLICAN"), "candidate_name"]),
            "source_url": group.source_url.iloc[0],
            "retrieved_on": as_of,
            "identity_method": "unique full given name or sourced exact-pair review; "
            + ("positive ballot presence only" if positive_only else "complete district ballot"),
            "ballot_incumbent_dem": int(any(h["incumbent_party"] == "DEMOCRAT" for h in on_ballot)),
            "ballot_incumbent_rep": int(any(h["incumbent_party"] == "REPUBLICAN" for h in on_ballot)),
        }
        # A surname shared with an unmatched first name may be a nickname, not a retirement.
        holder_last, _ = ballots.identity(incumbent.incumbent_name)
        unresolved = not running and any(
            ballots.identity(n)[0] == holder_last and n not in reviewed_candidates
            for n in group.candidate_name
        )
        if unresolved:
            ambiguous.append({"race_key": key, "reason": "same surname but unresolved given-name identity"})
            continue
        rows.append(row)
    return pd.DataFrame(rows), ambiguous


def load_identity_reviews(*, as_of: str) -> pd.DataFrame:
    from bs4 import BeautifulSoup

    path = Path("data/reference/candidate_identity_2026.csv")
    if not path.exists():
        return pd.DataFrame()
    reviews = pd.read_csv(path, dtype=str)
    reviews = reviews[pd.to_datetime(reviews.retrieved_on).le(pd.Timestamp(as_of))].copy()
    accepted, status = [], []
    for row in reviews.to_dict(orient="records"):
        key = f"{row['state_po']}_{ballots.identity(row['incumbent_name'])[0]}"
        try:
            source = snapshot(
                row["source_url"],
                Path(f"data/raw/source=candidate_identity_2026/snapshot={row['retrieved_on']}/{key}.html"),
                source_id="candidate_identity_2026",
                owner="Official congressional member site",
                expect="html",
                tier=PrivacyTier.PUBLIC_PERSONAL,
            )
        except acquire.AcquisitionError as exc:
            status.append(
                {
                    "state_po": row["state_po"],
                    "ballot_name": row["ballot_name"],
                    "source_url": row["source_url"],
                    "verified": False,
                    "error": str(exc),
                }
            )
            continue
        text = BeautifulSoup(source.read_bytes(), "html.parser").get_text(" ", strip=True)
        if row["evidence_name"].casefold() not in text.casefold():
            raise ValueError(f"identity evidence name not found in official source: {key}")
        accepted.append(row)
        status.append(
            {
                "state_po": row["state_po"],
                "ballot_name": row["ballot_name"],
                "source_url": row["source_url"],
                "raw_sha256": sha256_file(source),
                "verified": True,
            }
        )
    report = Path(f"reports/refresh_{as_of}/identity_review_status.json")
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(status, indent=2))
    return pd.DataFrame(accepted)


def load_presence_reviews(roster: pd.DataFrame, *, as_of: str) -> pd.DataFrame:
    """Explicit positive ballot observations; no retirement inferred from partial documents."""
    from pypdf import PdfReader

    path = Path("data/reference/ballot_presence_reviews_2026.csv")
    if not path.exists():
        return pd.DataFrame()
    reviews = pd.read_csv(path, dtype=str)
    reviews = reviews[pd.to_datetime(reviews.retrieved_on).le(pd.Timestamp(as_of))]
    rows = []
    for row in reviews.to_dict(orient="records"):
        _, _, _, state = row["race_key"].split("_")
        state = state.upper()
        current = roster[roster.state_po.eq(state) & roster.office.eq("us_senate")]
        if len(current) != 1 or current.iloc[0].incumbent_name != row["incumbent_name"]:
            raise ValueError("positive ballot review does not match current Senate seat")
        raw = snapshot(
            row["source_url"],
            Path(
                f"data/raw/source=official_ballots/state={state}/snapshot={row['retrieved_on']}/presence.pdf"
            ),
            source_id="official_ballots_2026",
            owner=f"{state} official election authority",
            expect="pdf",
            tier=PrivacyTier.PUBLIC_PERSONAL,
        )
        text = " ".join(p.extract_text() or "" for p in PdfReader(raw).pages)

        def normalize(t: str) -> str:
            return re.sub(r"[^A-Z0-9]", "", t.upper())

        if not all(
            normalize(row[k]) in normalize(text) for k in ("election_marker", "office_marker", "ballot_name")
        ):
            raise ValueError(f"positive ballot review source markers missing: {state}")
        rows.append(
            {
                "race_key": row["race_key"],
                "incumbent_name": row["incumbent_name"],
                "incumbent_running": True,
                "source_url": row["source_url"],
                "retrieved_on": row["retrieved_on"],
                "identity_method": "reviewed positive official ballot presence",
                "ballot_incumbent_dem": int(current.iloc[0].incumbent_party == "DEMOCRAT"),
                "ballot_incumbent_rep": int(current.iloc[0].incumbent_party == "REPUBLICAN"),
            }
        )
    return pd.DataFrame(rows)


def build(*, as_of: str, states: list[str] | None = None) -> dict:
    output = Path("reports") / f"refresh_{as_of}"
    output.mkdir(parents=True, exist_ok=True)
    url = "https://clerk.house.gov/xml/lists/MemberData.xml"
    path = snapshot(
        url,
        Path(f"data/raw/source=house_current_roster/snapshot={as_of}/MemberData.xml"),
        source_id="house_current_roster",
        owner="Clerk of the U.S. House",
        expect="xml",
        tier=PrivacyTier.PUBLIC_PERSONAL,
    )
    house = ballots.house_roster(path)
    house["source_url"], house["retrieved_on"] = url, as_of
    house.to_csv(f"data/reference/house_roster_{as_of}.csv", index=False)
    house["office"] = "us_house"
    sen_paths = sorted(
        p
        for p in Path("data/reference").glob("senate_roster_*.csv")
        if p.stem.removeprefix("senate_roster_") <= as_of
    )
    sen = senate_roster.scheduled_seats(
        senate_roster.load_roster(sen_paths[-1]),
        pd.read_csv("data/reference/senate_specials_2026.csv", comment="#"),
        cycle=2026,
    ).rename(columns={"ballot_party": "incumbent_party"})
    sen["office"], sen["district_num"] = "us_senate", 0
    roster = pd.concat([house, sen], ignore_index=True)
    frames, provenance = [], []
    requested_states = states or list(SOURCES)
    documents = [(state, *SOURCES[state]) for state in requested_states]
    documents.extend((state, *EXTRA_SOURCES[state]) for state in requested_states if state in EXTRA_SOURCES)
    for state, url, owner, filename, kind in documents:
        path = snapshot(
            url,
            Path(f"data/raw/source=official_ballots/state={state}/snapshot={as_of}/{filename}"),
            source_id="official_ballots_2026",
            owner=owner,
            expect=kind,
            tier=PrivacyTier.PUBLIC_PERSONAL if state != "CA" else PrivacyTier.PUBLIC_AGGREGATE,
        )
        suffix = f"_{Path(filename).stem}" if state in EXTRA_SOURCES else ""
        cache = Path(f"data/silver/ballots_{state}_{as_of}{suffix}.parquet")
        key_path = cache.with_suffix(".lineage.json")
        key = {"raw_sha256": sha256_file(path), "parser_sha256": sha256_file(ballots.__file__)}
        if cache.is_file() and key_path.is_file() and json.loads(key_path.read_text()) == key:
            frame = pd.read_parquet(cache)
        else:
            frame = PARSERS[state](path)
            frame["source_url"], frame["retrieved_on"] = url, as_of
            cache.parent.mkdir(parents=True, exist_ok=True)
            frame.to_parquet(cache, index=False)
            key_path.write_text(json.dumps(key))
        frames.append(frame)
        provenance.append(
            {
                "state_po": state,
                **key,
                "candidates": len(frame),
                "races": len(frame[["office", "district_num"]].drop_duplicates()),
            }
        )
        print(f"ballots {state}: {len(frame)} candidate facts", flush=True)
    candidates = pd.concat(frames, ignore_index=True)
    reviews = load_identity_reviews(as_of=as_of)
    evidence, ambiguous = compile_evidence(candidates, roster, as_of=as_of, identity_reviews=reviews)
    presence = load_presence_reviews(roster, as_of=as_of)
    if not presence.empty:
        evidence = pd.concat(
            [evidence[~evidence.race_key.isin(presence.race_key)], presence], ignore_index=True
        )
    reference = Path("data/reference/candidacy_2026.csv")
    if reference.is_file():
        digest = sha256_file(reference)
        original = Path(
            f"data/raw/source=candidate_candidacy_announcements_2026/snapshot={as_of}/sha256={digest}/candidacy.csv"
        )
        original.parent.mkdir(parents=True, exist_ok=True)
        if not original.exists():
            shutil.copyfile(reference, original)
        old = pd.read_csv(reference)
        observed_keys = {
            f"2026_{office}_{state.lower()}" + (f"_{int(district):02d}" if office == "us_house" else "")
            for state, office, district in candidates[["state_po", "office", "district_num"]]
            .drop_duplicates()
            .itertuples(index=False, name=None)
        }
        stale_automatic = (
            old.race_key.isin(observed_keys)
            & old.get("identity_method", pd.Series(pd.NA, index=old.index)).notna()
        )
        retained = old[~old.race_key.isin(evidence.race_key) & ~stale_automatic]
        evidence = pd.concat([retained, evidence], ignore_index=True)
    evidence.sort_values("race_key").to_csv(reference, index=False)
    candidates.to_csv(output / "official_ballot_candidates.csv", index=False)
    report = {
        "as_of": as_of,
        "source_coverage": provenance,
        "verified_races": len(evidence),
        "ambiguous_matches": ambiguous,
        "roster_rows": len(house),
        "remaining_unknown": 470 - len(evidence),
        "not_a_filing_based_nomination": True,
    }
    (output / "ballot_coverage.json").write_text(json.dumps(report, indent=2))
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", default=date.today().isoformat())
    parser.add_argument("--states", nargs="+", choices=list(SOURCES))
    args = parser.parse_args(argv)
    build(as_of=args.as_of, states=args.states)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

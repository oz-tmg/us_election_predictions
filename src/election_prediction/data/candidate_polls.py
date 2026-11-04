"""Manual archived candidate toplines for research, not live forecast promotion."""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from ..geography.reference import STATES
from . import polling_archive
from .manifest import SourceManifest, sha256_file

REQUIRED = {
    "question_id",
    "poll_id",
    "cycle",
    "state",
    "office_type",
    "seat_number",
    "election_date",
    "stage",
    "start_date",
    "end_date",
    "created_at",
    "pollster",
    "methodology",
    "partisan",
    "sample_size",
    "ranked_choice_reallocated",
    "candidate_id",
    "candidate_name",
    "pct",
}
OFFICES = {"U.S. House": "us_house", "U.S. Senate": "us_senate"}


def read_candidate_file(path: Path) -> pd.DataFrame:
    data = pd.read_csv(path, dtype=str)
    if not REQUIRED.issubset(data) or not ({"party", "candidate_party"} & set(data)):
        raise ValueError(f"unexpected candidate-poll schema: {path.name}")
    expected = "U.S. House" if path.name.startswith("house_") else "U.S. Senate"
    if path.name not in polling_archive.POLL_URLS or not data.office_type.eq(expected).all():
        raise ValueError("filename/office mismatch or unregistered filename")
    if "party" in data and "candidate_party" in data:
        both = data.party.notna() & data.candidate_party.notna()
        if data.loc[both, "party"].ne(data.loc[both, "candidate_party"]).any():
            raise ValueError("conflicting party columns")
        data["party"] = data.party.fillna(data.candidate_party)
    elif "party" not in data:
        data["party"] = data.candidate_party
    data["source_file"] = path.name
    return data


def preserve_manual_file(
    path: Path,
    *,
    archive_url: str,
    provenance_basis: str = "user_supplied_archive_url",
    raw_root: Path = Path("data/raw/source=538_race_poll_history/manual"),
) -> dict:
    """Preserve bytes and distinguish archive capture, ingestion and unknown retrieval."""
    match = re.fullmatch(r"https://web\.archive\.org/web/(\d{14})(?:[a-z]+_)?/(https://[^\s]+)", archive_url)
    if not match or match[2] != polling_archive.POLL_URLS.get(path.name):
        raise ValueError("exact registered publisher URL and Wayback capture URL required")
    capture = datetime.strptime(match[1], "%Y%m%d%H%M%S").replace(tzinfo=UTC)
    now = datetime.now(UTC)
    if capture > now:
        raise ValueError("archive capture cannot be in the future")
    frame = read_candidate_file(path)
    digest = sha256_file(path)
    destination = raw_root / f"sha256={digest}" / path.name
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if sha256_file(destination) != digest:
            raise ValueError("immutable raw snapshot conflict")
    else:
        with destination.open("xb") as handle:
            handle.write(path.read_bytes())
    if sha256_file(destination) != digest or sha256_file(path) != digest:
        raise ValueError("file changed during intake")
    metadata = destination.with_suffix(".provenance.json")
    if metadata.exists():
        existing = json.loads(metadata.read_text())
        if existing["archive_url"] != archive_url or existing["sha256"] != digest:
            raise ValueError("immutable provenance conflict")
        polling_archive.verify_registered_archive(destination)
        return existing
    manifest_path = polling_archive.preserve_archive(
        destination, url=archive_url, retrieved_at=now.isoformat()
    )
    manifest = SourceManifest.load(manifest_path)
    manifest.acquisition_method = "manual_import; acquired_at is project ingestion, not browser retrieval"
    manifest.office_coverage = sorted(frame.office_type.map(OFFICES).unique())
    manifest.election_cycle = ",".join(sorted(frame.cycle.dropna().unique()))
    manifest.row_count = len(frame)
    manifest.validation_status = "pending"
    manifest.known_caveats = (
        "Raw CSV schema checked; research eligibility requires separate question/round/target review. "
        "Original browser retrieval time unknown. Archive capture is not poll publication. "
        "Browser provenance does not independently authenticate archive-server bytes."
    )
    manifest.write()
    result = {
        "filename": path.name,
        "raw_path": str(destination),
        "sha256": digest,
        "publisher_url": match[2],
        "archive_url": archive_url,
        "archive_capture_at": capture.isoformat(),
        "project_ingested_at": now.isoformat(),
        "browser_retrieved_at": None,
        "provenance_basis": provenance_basis,
        "independently_refetched": False,
        "manifest": str(manifest_path),
        "candidate_answer_rows": len(frame),
        "questions": int(frame.question_id.nunique()),
        "cycle_rows": frame.cycle.value_counts().to_dict(),
        "field_end_min": str(pd.to_datetime(frame.end_date, format="mixed").min().date()),
        "field_end_max": str(pd.to_datetime(frame.end_date, format="mixed").max().date()),
    }
    with metadata.open("x") as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
    return result


def prepare_candidates(
    frames: list[pd.DataFrame],
    *,
    races: pd.DataFrame,
    presidential: pd.DataFrame,
    fundamentals: pd.DataFrame,
    house_panel: pd.DataFrame,
) -> tuple[pd.DataFrame, dict]:
    """Collapse answer rows without selecting candidates using eventual vote outcomes."""
    raw = pd.concat(frames, ignore_index=True)
    raw["cycle"] = pd.to_numeric(raw.cycle, errors="coerce")
    raw["pct"] = pd.to_numeric(raw.pct, errors="coerce")
    for column in ("question_id", "poll_id", "candidate_id"):
        raw[column] = raw[column].fillna("").astype(str).str.strip()
    raw["party"] = raw.party.fillna("").str.upper()
    coverage = raw.assign(office=raw.office_type.map(OFFICES))[["office", "cycle"]].drop_duplicates()
    names = {s.name: key for key, s in STATES.items()}
    counts = races[races.office.eq("us_house")].groupby(["cycle", "state_po"]).district_num.nunique()
    rejected: list[dict] = []
    rows = []
    duplicate_answers = 0
    metadata = [
        "poll_id",
        "cycle",
        "state",
        "office_type",
        "seat_number",
        "election_date",
        "stage",
        "start_date",
        "end_date",
        "created_at",
        "pollster",
        "methodology",
        "partisan",
        "sample_size",
        "ranked_choice_reallocated",
    ]

    def reject(question: str, reason: str) -> None:
        rejected.append({"question_id": question, "reason": reason})

    for question, group in raw.groupby("question_id", sort=True, dropna=False):
        key = str(question)
        first = group.iloc[0]
        if not key or not first.poll_id or group.candidate_id.eq("").any():
            reject(key, "missing_identifiers")
            continue
        if group[metadata].nunique(dropna=False).gt(1).any():
            reject(key, "conflicting_question_metadata")
            continue
        if pd.isna(first.pollster) or not str(first.pollster).strip():
            reject(key, "missing_pollster")
            continue
        cycle = first.cycle
        if pd.isna(cycle) or cycle not in range(1998, 2025, 2):
            reject(key, "outside_even_1998_2024")
            continue
        office = OFFICES.get(first.office_type)
        state = names.get(first.state, first.state if first.state in STATES else None)
        if office is None or state in (None, "DC", "PR"):
            reject(key, "invalid_geography_or_office")
            continue
        election = pd.to_datetime(first.election_date, format="mixed", errors="coerce")
        if first.stage != "general" or election != polling_archive._november_general(int(cycle)):
            reject(key, "not_november_general")
            continue
        if state == "LA" or (state == "AK" and cycle >= 2022) or (state == "ME" and cycle >= 2018):
            reject(key, "round_not_verified")
            continue
        if str(first.ranked_choice_reallocated).lower() != "false" or (
            "ranked_choice_round" in group and group.ranked_choice_round.notna().any()
        ):
            reject(key, "ranked_choice_round_not_verified")
            continue
        if "hypothetical" in group:
            flags = group.hypothetical.dropna().astype(str).str.lower()
            if (~flags.isin(["true", "false"])).any() or flags.eq("true").any():
                reject(key, "hypothetical_or_unknown_matchup")
                continue
        pairs = group[["candidate_id", "candidate_name", "party", "pct"]].drop_duplicates()
        duplicate_answers += len(group) - len(pairs)
        if (
            pairs.candidate_id.duplicated().any()
            or pairs.groupby("party").size().reindex(["DEM", "REP"], fill_value=0).ne(1).any()
        ):
            reject(key, "not_unique_dem_rep_pair")
            continue
        if (
            not np.isfinite(pairs.pct).all()
            or not pairs.pct.between(0, 100).all()
            or pairs.pct.sum() > 100.01
        ):
            reject(key, "invalid_topline")
            continue
        dr = pairs.set_index("party").pct
        total = dr["DEM"] + dr["REP"]
        sample = pd.to_numeric(first.sample_size, errors="coerce")
        if total <= 0 or not np.isfinite(sample) or sample <= 0:
            reject(key, "invalid_sample_or_zero_major_party_total")
            continue
        start = pd.to_datetime(first.start_date, format="mixed", errors="coerce")
        end = pd.to_datetime(first.end_date, format="mixed", errors="coerce")
        created = pd.to_datetime(first.created_at, format="mixed", errors="coerce")
        if pd.isna(start) or pd.isna(end) or start > end or end > election or pd.isna(created):
            reject(key, "invalid_field_or_entry_date")
            continue
        district = pd.to_numeric(first.seat_number, errors="coerce") if office == "us_house" else -1
        if office == "us_house" and counts.get((cycle, state), 0) == 1:
            if district not in (0, 1):
                reject(key, "invalid_at_large_district")
                continue
            district = 0
        if pd.isna(district) or district != int(district):
            reject(key, "invalid_district")
            continue
        rows.append(
            {
                "question_id": key,
                "poll_id": str(first.poll_id),
                "cycle": int(cycle),
                "office": office,
                "state_po": state,
                "district_num": int(district),
                "election_date": election,
                "poll_date": start + (end - start) / 2,
                "field_start": start,
                "field_end": end,
                "database_created_at": created.normalize(),
                "poll_dem_share": float(dr["DEM"] / total),
                "sample_size": float(sample),
                "pollster": first.pollster,
                "sponsor_partisan": first.partisan if pd.notna(first.partisan) else "UNKNOWN",
                "mode": first.methodology if pd.notna(first.methodology) else "UNKNOWN",
                "source_files": ";".join(sorted(group.source_file.unique())),
                "source_kind": "candidate_archive",
                "exclusion": "",
            }
        )
    data = pd.DataFrame(rows)
    if data.empty:
        raise ValueError("no candidate questions survived schema/round review")
    out, ambiguous = polling_archive.attach_research_features(
        data, races=races, presidential=presidential, fundamentals=fundamentals, house_panel=house_panel
    )
    rejected.extend(
        out.loc[out.exclusion.ne(""), ["question_id", "exclusion"]]
        .rename(columns={"exclusion": "reason"})
        .to_dict("records")
    )
    accepted = out[out.exclusion.eq("")].copy()
    accepted["actual_dem_win"] = accepted.winner_party.eq("DEMOCRAT").astype(int)
    accepted["publication_verified"] = False
    accepted["field_end_verified"] = True
    accepted["geography_verified"] = False
    accepted["fundamentals_vintage_verified"] = False
    accepted["publication_basis"] = "Unverified; database created_at is not publication"
    report = {
        "candidate_answer_rows": len(raw),
        "input_questions": int(raw.question_id.nunique()),
        "duplicate_answer_rows_collapsed": duplicate_answers,
        "accepted_poll_rows_before_horizon": len(accepted),
        "exclusions": dict(Counter(r["reason"] for r in rejected)),
        "rejected_questions": rejected,
        "replacement_office_cycles": coverage.to_dict("records"),
        "ambiguous_canonical_keys": ambiguous,
        "cycle_office_coverage": accepted.groupby(["office", "cycle"])
        .size()
        .reset_index(name="poll_rows")
        .to_dict("records"),
        "real_time_vintage_verified": False,
        "promotion_eligible": False,
        "date_basis": "Field midpoint proxy; field end and database-entry date must precede fixed cutoff",
        "limitations": [
            "Archive/database timestamps do not prove original publication availability",
            "Candidate names are archived matchups, not independently verified historical ballots",
            "House uses lagged House proxy, not election-vintage presidential district lean",
            "Historical fundamentals and maps are not proven real-time vintages",
        ],
    }
    return accepted.reset_index(drop=True), report


def replace_overlapping_cycles(
    ratings: pd.DataFrame,
    candidates: pd.DataFrame,
    coverage: list[dict],
) -> tuple[pd.DataFrame, int]:
    """Never let ratings backfill a candidate question excluded on richer metadata."""
    keys = {(r["office"], r["cycle"]) for r in coverage}
    replace = pd.Series(
        [(o, c) in keys for o, c in zip(ratings.office, ratings.cycle, strict=True)], index=ratings.index
    )
    older = ratings.loc[~replace].copy()
    older["source_kind"] = "ratings_archive"
    combined = pd.concat([older, candidates], ignore_index=True)
    combined["question_id"] = combined.question_id.astype(str)
    combined["poll_id"] = combined.poll_id.astype(str)
    if combined.question_id.duplicated().any():
        raise ValueError("overlapping question IDs after office-cycle replacement")
    return combined, int(replace.sum())

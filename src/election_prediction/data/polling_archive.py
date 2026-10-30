"""Governed historical polling intake for the unpromoted lean experiment."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from ..geography.reference import STATES
from . import acquire
from .manifest import SourceManifest, sha256_file
from .privacy import PrivacyTier

RATINGS_URL = "https://raw.githubusercontent.com/fivethirtyeight/data/master/pollster-ratings/raw_polls.csv"
POLL_URLS = {
    name: f"https://projects.fivethirtyeight.com/polls-page/data/{name}"
    for name in (
        "senate_polls_historical.csv",
        "senate_polls.csv",
        "house_polls_historical.csv",
        "house_polls.csv",
    )
}
RATINGS_COLUMNS = {
    "poll_id",
    "question_id",
    "cycle",
    "location",
    "type_simple",
    "pollster",
    "methodology",
    "partisan",
    "polldate",
    "electiondate",
    "samplesize",
    "cand1_party",
    "cand2_party",
    "cand1_pct",
    "cand2_pct",
    "cand1_actual",
    "cand2_actual",
}


def preserve_archive(path: Path, *, url: str, retrieved_at: str) -> Path:
    """Register an already acquired aggregate file; never invent its retrieval date."""
    timestamp = datetime.fromisoformat(retrieved_at.replace("Z", "+00:00"))
    if timestamp.tzinfo is None or timestamp > datetime.now(UTC):
        raise ValueError("retrieved_at must have a timezone and cannot be in the future")
    if not path.is_file():
        raise ValueError("archive does not exist")
    with path.open("rb") as handle:
        acquire._validate_body(handle.read(4096), expect="csv", url=url)
    digest = sha256_file(path)
    manifest = SourceManifest.for_snapshot(
        raw_path=path,
        source_id=f"538_race_poll_history_{digest[:12]}",
        dataset_name=path.name,
        source_owner="FiveThirtyEight",
        source_url=url,
        privacy_tier=PrivacyTier.PUBLIC_AGGREGATE,
        license_or_terms="CC BY 4.0; FiveThirtyEight repository LICENSE; compilation rights only",
        permitted_use="Nonpartisan aggregate research; attribution and transformations disclosed",
        prohibited_use="No respondent records, targeting or retrospective ratings as predictors",
        office_coverage=["us_house", "us_senate"],
        geography_coverage=["state", "district"],
        election_cycle="historical",
        owner="Alex Oswald",
        required_attribution="FiveThirtyEight",
        known_caveats="Retrospective compilation; source availability and selection require separate review",
    )
    manifest.acquired_at = timestamp.isoformat()
    manifest.snapshot_date = timestamp.astimezone(UTC).date().isoformat()
    dest = Path("data/manifests") / f"{manifest.snapshot_id}.json"
    if dest.exists():
        old = SourceManifest.load(dest)
        if old.raw_path != str(path) or old.source_url != url or old.checksum_sha256 != digest:
            raise ValueError("archive manifest conflict; preserve existing evidence")
        return dest
    return manifest.write()


def download_archives(directory: Path, *, include_candidate_files: bool = False) -> list[dict]:
    """Acquire registered publisher files, explicitly retaining endpoint failures."""
    urls = {"raw_polls.csv": RATINGS_URL, **(POLL_URLS if include_candidate_files else {})}
    attempts = []
    for filename, url in urls.items():
        path = directory / filename
        try:
            if not path.exists():
                acquire.fetch(url, path, expect="csv", timeout=30)
            stamp = datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat()
            manifest = preserve_archive(path, url=url, retrieved_at=stamp)
            frame = pd.read_csv(path)
            if filename == "raw_polls.csv" and not RATINGS_COLUMNS.issubset(frame):
                raise ValueError("ratings archive has unexpected columns")
            if filename != "raw_polls.csv" and not {"question_id", "candidate_id", "pct"}.issubset(frame):
                raise ValueError("candidate-poll endpoint did not return candidate-level toplines")
            attempts.append(
                {
                    "file": str(path),
                    "url": url,
                    "status": "acquired_unreviewed",
                    "sha256": sha256_file(path),
                    "manifest": str(manifest),
                    "rows": len(frame),
                }
            )
        except (acquire.AcquisitionError, ValueError, pd.errors.ParserError) as exc:
            attempts.append(
                {"file": str(path), "url": url, "status": "unavailable_or_invalid", "error": str(exc)}
            )
    return attempts


def _november_general(cycle: int) -> pd.Timestamp:
    first = pd.Timestamp(year=cycle, month=11, day=1)
    return first + pd.Timedelta(days=(7 - first.weekday()) % 7 + 1)


def prepare_ratings(
    raw: pd.DataFrame,
    *,
    races: pd.DataFrame,
    presidential: pd.DataFrame,
    fundamentals: pd.DataFrame,
    house_panel: pd.DataFrame,
) -> tuple[pd.DataFrame, dict]:
    """Reconcile by structural race keys; never choose a race using its vote outcome.

    Senate lean is lagged presidential lean. House uses a separately labeled lagged
    House proxy until election-vintage presidential district baselines are available.
    Publication, geography and historical roster vintages are NOT asserted verified.
    """
    if not RATINGS_COLUMNS.issubset(raw):
        raise ValueError(f"ratings archive missing columns: {sorted(RATINGS_COLUMNS - set(raw))}")
    data = raw.rename(columns={"race_id": "publisher_race_id"}).copy().reset_index(drop=True)
    data["exclusion"] = ""

    def reject(mask: pd.Series, reason: str) -> None:
        data.loc[data.exclusion.eq("") & mask.fillna(True), "exclusion"] = reason

    reject(~data.type_simple.isin(["House-G", "Sen-G"]), "other_office_or_primary")
    data["cycle"] = pd.to_numeric(data.cycle, errors="coerce")
    reject(~data.cycle.between(1998, 2024) | data.cycle.mod(2).ne(0), "outside_even_1998_2024")
    data["poll_date"] = pd.to_datetime(data.polldate, errors="coerce")
    data["election_date"] = pd.to_datetime(data.electiondate, errors="coerce")
    expected = data.cycle.map(lambda c: _november_general(int(c)) if pd.notna(c) else pd.NaT)
    reject(data.election_date.ne(expected), "not_november_general")
    reject(~(data.cand1_party.eq("DEM") & data.cand2_party.eq("REP")), "not_dem_rep_top_two")
    location = data.location.astype(str).str.extract(r"^([A-Z]{2})(?:-(\d+))?$")
    data["state_po"] = location[0]
    data["district_num"] = pd.to_numeric(location[1], errors="coerce")
    data["office"] = data.type_simple.map({"House-G": "us_house", "Sen-G": "us_senate"})
    reject(~data.state_po.isin(set(STATES) - {"DC", "PR"}), "invalid_geography")
    # Publisher uses district 1 for historical at-large seats; MEDSL uses zero.
    counts = races[races.office.eq("us_house")].groupby(["cycle", "state_po"]).district_num.nunique()
    one_seat = pd.Series(
        [counts.get((c, s), 0) == 1 for c, s in zip(data.cycle, data.state_po, strict=True)],
        index=data.index,
    )
    data.loc[data.office.eq("us_house") & one_seat, "district_num"] = 0
    data.loc[data.office.eq("us_senate"), "district_num"] = -1
    reject(data.district_num.isna(), "missing_district")
    reject(data.state_po.eq("LA"), "louisiana_round_not_verified")
    reject(
        (data.state_po.eq("AK") & data.cycle.ge(2022)) | (data.state_po.eq("ME") & data.cycle.ge(2018)),
        "ranked_choice_round_not_verified",
    )
    numeric = ["cand1_pct", "cand2_pct", "cand1_actual", "cand2_actual", "samplesize"]
    data[numeric] = data[numeric].apply(pd.to_numeric, errors="coerce")
    reject(
        ~np.isfinite(data[numeric]).all(axis=1)
        | data.samplesize.le(0)
        | ~data[numeric[:4]].ge(0).all(axis=1)
        | ~data[numeric[:4]].le(100).all(axis=1)
        | (data.cand1_pct + data.cand2_pct).le(0)
        | (data.cand1_actual + data.cand2_actual).le(0)
        | (data.cand1_pct + data.cand2_pct).gt(100.01),
        "invalid_topline_or_sample",
    )
    reject(
        data.poll_date.isna() | data.poll_date.gt(data.election_date) | data.pollster.isna(),
        "invalid_poll_date_or_pollster",
    )
    if data.loc[data.exclusion.eq(""), "question_id"].duplicated().any():
        raise ValueError("duplicate survey question; explicitly review rather than double count")
    data["archive_actual"] = data.cand1_actual / (data.cand1_actual + data.cand2_actual)
    out, ambiguous = attach_research_features(
        data[data.exclusion.eq("")],
        races=races,
        presidential=presidential,
        fundamentals=fundamentals,
        house_panel=house_panel,
    )
    exclusions = pd.concat([data[["exclusion"]], out[["exclusion"]]])
    accepted = out[out.exclusion.eq("")].copy()
    accepted["poll_dem_share"] = accepted.cand1_pct / (accepted.cand1_pct + accepted.cand2_pct)
    accepted["sample_size"] = accepted.samplesize
    accepted["sponsor_partisan"] = accepted.partisan.fillna("NONE")
    accepted["mode"] = accepted.methodology.fillna("UNKNOWN")
    accepted["actual_dem_win"] = accepted.winner_party.eq("DEMOCRAT").astype(int)
    for gate in (
        "publication_verified",
        "field_end_verified",
        "geography_verified",
        "fundamentals_vintage_verified",
    ):
        accepted[gate] = False
    accepted["publication_basis"] = "unavailable; median field date is not publication"
    report = {
        "input_rows": len(raw),
        "accepted_poll_rows_before_horizon": len(accepted),
        "exclusions": exclusions.loc[exclusions.exclusion.ne(""), "exclusion"].value_counts().to_dict(),
        "ambiguous_canonical_keys": ambiguous,
        "cycle_office_coverage": accepted.groupby(["office", "cycle"])
        .size()
        .reset_index(name="poll_rows")
        .to_dict("records"),
        "real_time_vintage_verified": False,
        "promotion_eligible": False,
        "limitations": [
            "Retrospective selection of surveys and eventual top-two candidates",
            "Median dates, some imputed sample sizes; missing publication and field-end dates",
            "House lean is a lagged House proxy, not prior presidential district lean",
            "Historical maps/rosters are reconstructed, not archived forecast-date vintages",
            "No 2024 congressional polls in the acquired ratings file",
        ],
    }
    return accepted.reset_index(drop=True), report


def attach_research_features(
    data: pd.DataFrame,
    *,
    races: pd.DataFrame,
    presidential: pd.DataFrame,
    fundamentals: pd.DataFrame,
    house_panel: pd.DataFrame,
) -> tuple[pd.DataFrame, list[dict]]:
    """Join targets structurally and strictly lagged features, never by observed outcome.

    Ratings supply an independent archived outcome for reconciliation; candidate
    toplines do not, and must not be given fabricated archive outcomes.
    """
    keys = ["cycle", "office", "state_po", "district_num"]
    canonical = races[races.office.isin(["us_house", "us_senate"])].copy()
    canonical.loc[canonical.office.eq("us_senate"), "district_num"] = -1
    ambiguous = canonical.duplicated(keys, keep=False)
    excluded = canonical.loc[ambiguous, keys].drop_duplicates()
    canonical = canonical[~ambiguous]
    out = data[data.exclusion.eq("")].merge(
        canonical[
            keys + ["race_id", "two_party_dem_share", "certified_flag", "uncontested_flag", "winner_party"]
        ],
        on=keys,
        how="left",
        validate="many_to_one",
    )
    mismatch = (
        (out.archive_actual - out.two_party_dem_share).abs().gt(0.0005)
        if "archive_actual" in out
        else pd.Series(False, index=out.index)
    )
    out["exclusion"] = np.select(
        [
            out.race_id.isna(),
            out.certified_flag.ne(True),
            out.uncontested_flag.ne(False),
            out.winner_party.eq("OTHER"),
            mismatch,
        ],
        [
            "missing_or_ambiguous_canonical_race",
            "not_certified",
            "uncontested_or_unknown",
            "other_party_winner",
            "certified_share_mismatch",
        ],
        default="",
    )
    out = out.rename(columns={"two_party_dem_share": "actual_dem_share"})
    prior = fundamentals[["race_id", "pred_dem_share", "resid_sigma", "train_through"]].copy()
    prior = prior[prior.race_id.isin(out.race_id)]
    if prior.race_id.duplicated().any():
        raise ValueError("fundamentals must be unique per race")
    out = out.merge(prior, on="race_id", how="left", validate="many_to_one")
    out.loc[
        out.exclusion.eq("") & (out.train_through.isna() | out.train_through.ge(out.cycle)), "exclusion"
    ] = "missing_or_nonchronological_fundamentals"
    pres = presidential.rename(columns={"cycle": "lean_reference_cycle"}).copy()
    pres["lean"] = pres.two_party_dem_share - pres.national_dem_share
    senate = out[out.office.eq("us_senate")].copy()
    senate = pd.merge_asof(
        senate.sort_values("cycle"),
        pres[["state_po", "lean_reference_cycle", "lean"]].sort_values("lean_reference_cycle"),
        left_on="cycle",
        right_on="lean_reference_cycle",
        by="state_po",
        direction="backward",
        allow_exact_matches=False,
    )
    senate["lean_basis"] = "lagged_presidential_state"
    house = out[out.office.eq("us_house")].copy()
    house = house.merge(
        house_panel.loc[
            house_panel.race_id.isin(house.race_id), ["race_id", "district_lean", "lag_dem_share"]
        ],
        on="race_id",
        how="left",
        validate="many_to_one",
    )
    house["lean"] = house.district_lean.where(house.lag_dem_share.between(0, 1, inclusive="neither"))
    house["lean_reference_cycle"] = house.cycle - 2
    house["lean_basis"] = "lagged_house_proxy_unverified_historical_map"
    out = pd.concat([senate, house], ignore_index=True)
    out.loc[out.exclusion.eq("") & out.lean.isna(), "exclusion"] = "missing_lagged_lean"
    return out, excluded.to_dict("records")


def verify_registered_archive(path: Path) -> None:
    matching = []
    for manifest_path in Path("data/manifests").glob("538_race_poll_history*__*.json"):
        record = SourceManifest.load(manifest_path)
        if Path(record.raw_path).resolve() == path.resolve():
            matching.append(record)
    if not matching or any(m.checksum_sha256 != sha256_file(path) for m in matching):
        raise ValueError("poll archive is unregistered or its registered checksum changed")


def inspect_local_archives(directory: Path, *, supplied: list[Path] | None = None) -> list[dict]:
    result = []
    for name, url in POLL_URLS.items():
        paths = [p for p in supplied or [] if p.name == name and p.is_file()]
        if not paths and (directory / name).is_file():
            paths = [directory / name]
        result.append(
            {
                "filename": name,
                "publisher_url": url,
                "status": "present_needs_review" if paths else "missing",
                "sha256": sha256_file(paths[0]) if len(paths) == 1 else None,
                "paths": [{"raw_path": str(p), "sha256": sha256_file(p)} for p in paths],
            }
        )
    return result

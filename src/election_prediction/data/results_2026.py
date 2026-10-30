"""Capture 2026 results as they certify, because the record cannot be rebuilt afterwards.

``evaluation/score_preregistration`` grades the sealed forecast against a frame of
``geography_id, office, actual_dem_share, certified_on``. Nothing in this project could
produce that frame: MEDSL will not publish 2026 district returns for a year or more, and the
registration pre-committed to a rule that needs more than the final numbers —

    "The caller must pass ``as_of``. A seat with no certified result by that date is
    excluded and counted in ``unscored``, never silently dropped."

That rule needs to know **which seats were certified on a given date**, and that is
information which exists only while it is happening. A state's canvass page shows today's
status, not last week's. If nobody writes down that Pennsylvania had certified and Georgia
had not on 12 November, no later download recovers it, and the scoring date silently becomes
a free parameter — the exact failure the registration was sealed to prevent.

So this module is a **ledger, not a download**. Each observation is appended as a dated
snapshot that is never rewritten, and ``certified_on`` is *derived* as the earliest snapshot
in which a seat was first seen certified. That makes the certification timeline an
accumulated observation rather than a reconstruction, and it makes the ledger auditable: the
evidence for "this seat certified on the 18th" is a file written on the 18th.

**Compiled by hand, with provenance per row**, for the same reason
``docs/special-elections-sourcing.md`` compiles specials by hand: there are fifty-one
publishing authorities, no common API, and no upstream checksum. Every row needs its
``source_url`` and ``retrieved_on`` or validation rejects it. Slow and auditable beats fast
and unattributable when the output is the only out-of-sample evidence the project has.

Scraping state canvass pages is deliberately **not** done here. Live result pages change
format mid-count, and a scraper that silently returns yesterday's HTML would corrupt the one
artefact that cannot be rebuilt.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import pandas as pd

from ..geography import reference
from .manifest import sha256_file

#: A compiled snapshot. ``certified`` is the officially-certified flag as the *source*
#: reported it on ``retrieved_on`` -- not an inference from how complete the count looks.
SNAPSHOT_COLUMNS = [
    "state_po",
    "district_num",
    "office",
    "dem_votes",
    "rep_votes",
    "other_votes",
    "certified",
    "source_url",
    "retrieved_on",
]

#: What the scorer consumes. Deliberately the names in
#: ``score_preregistration.ACTUAL_COLUMNS`` rather than a parallel vocabulary.
ACTUAL_COLUMNS = ["geography_id", "office", "actual_dem_share", "certified_on"]

SNAPSHOT_DIR = Path("data/raw/source=state_canvass/dataset=us_house_2026")


class SnapshotRejected(ValueError):
    """A compiled snapshot is missing provenance or is internally inconsistent."""


#: Offices keyed at state level rather than by district. The sealed forecast keys a Senate
#: seat on ``state:02``, not ``state:02|district:cong_00``, and building the district form
#: for it would join to nothing — 33 of the registration's 468 seats, silently unscored.
STATEWIDE_OFFICES = frozenset({"us_senate", "governor", "president"})


def _boolean(values: pd.Series, column: str) -> pd.Series:
    text = values.astype(str).str.strip().str.upper()
    if not text.isin({"TRUE", "T", "Y", "YES", "1", "FALSE", "F", "N", "NO", "0"}).all():
        raise SnapshotRejected(f"{column} must be an explicit boolean")
    return text.isin({"TRUE", "T", "Y", "YES", "1"})


def geography_id(state_fips: str, district_num: Any, office: str = "us_house") -> str:
    """The id the sealed forecast keys on, built the same way the projection builds it."""
    state = f"state:{str(state_fips).zfill(2)}"
    if str(office).strip().lower() in STATEWIDE_OFFICES or district_num is None or pd.isna(district_num):
        return state
    return f"{state}|district:cong_{int(district_num):02d}"


def validate_snapshot(df: pd.DataFrame) -> pd.DataFrame:
    """Refuse a snapshot that cannot be audited, rather than storing it and hoping.

    There is no upstream checksum for a hand-compiled table, so provenance *is* the
    validation. A row without a source URL and a retrieval date is an assertion, and an
    assertion has no place in the only out-of-sample evidence this project will get.
    """
    missing = [c for c in SNAPSHOT_COLUMNS if c not in df.columns]
    if missing:
        raise SnapshotRejected(f"snapshot is missing column(s) {missing}")
    if not len(df):
        raise SnapshotRejected("snapshot is empty")

    out = df.copy()
    out["state_po"] = out["state_po"].astype(str).str.strip().str.upper()
    out["office"] = out["office"].astype(str).str.strip().str.lower()
    states = set(reference.STATES) - {"DC", "PR"}
    if not out.state_po.isin(states).all():
        raise SnapshotRejected("only the 50 states are in the congressional capture universe")
    if not out.office.isin({"us_house", "us_senate"}).all():
        raise SnapshotRejected("office must be us_house or us_senate")
    if "winner_party" in out:
        out["winner_party"] = out["winner_party"].fillna("").astype(str).str.strip().str.upper()
        if not out["winner_party"].isin(["", "DEMOCRAT", "REPUBLICAN", "OTHER"]).all():
            raise SnapshotRejected("winner_party must be DEMOCRAT, REPUBLICAN or OTHER")
    for col in ("dem_votes", "rep_votes", "other_votes"):
        out[col] = pd.to_numeric(out[col], errors="coerce")
    votes = out[["dem_votes", "rep_votes", "other_votes"]]
    if votes.isna().any().any():
        raise SnapshotRejected("all vote counts must be numeric on every row")
    if (votes < 0).any().any() or (votes % 1 != 0).any().any():
        raise SnapshotRejected("vote counts must be nonnegative integers")

    for col in ("source_url", "retrieved_on"):
        blank = out[col].isna() | out[col].astype(str).str.strip().eq("")
        if blank.any():
            raise SnapshotRejected(
                f"{int(blank.sum())} row(s) have no {col}; every row needs its own provenance"
            )
    if not out.source_url.map(
        lambda url: urlsplit(str(url)).scheme in {"http", "https"} and bool(urlsplit(str(url)).hostname)
    ).all():
        raise SnapshotRejected("source_url must be an absolute HTTP(S) URL")
    if not out.retrieved_on.astype(str).str.fullmatch(r"\d{4}-\d{2}-\d{2}").all():
        raise SnapshotRejected("retrieved_on must be an ISO date, not an ambiguous timestamp")
    out["retrieved_on"] = pd.to_datetime(out["retrieved_on"], errors="coerce")
    if out["retrieved_on"].isna().any():
        raise SnapshotRejected("retrieved_on must be a date on every row")

    out["certified"] = _boolean(out["certified"], "certified")
    louisiana_house = out.state_po.eq("LA") & out.office.eq("us_house")
    if louisiana_house.any() and not {"election_round", "outcome_resolved"}.issubset(out):
        raise SnapshotRejected("Louisiana House needs election_round and explicit outcome_resolved")
    out["election_round"] = out.get("election_round", pd.Series("general", index=out.index)).fillna("general")
    if not out.election_round.isin({"general", "first_round", "runoff", "rcv_final"}).all():
        raise SnapshotRejected("unsupported election_round; do not ingest nomination-primary counts")
    if (louisiana_house & ~out.election_round.isin({"first_round", "runoff"})).any():
        raise SnapshotRejected("Louisiana House uses first_round or runoff, not ordinary general")
    resolved = out.get("outcome_resolved", pd.Series(True, index=out.index))
    if resolved[louisiana_house].isna().any():
        raise SnapshotRejected("Louisiana House needs explicit outcome_resolved")
    out["outcome_resolved"] = _boolean(resolved.fillna(True), "outcome_resolved")
    statewide = out["office"].isin(STATEWIDE_OFFICES)
    district = pd.to_numeric(out["district_num"], errors="coerce")
    if ((~statewide) & (district.isna() | (district < 0) | (district % 1 != 0))).any():
        raise SnapshotRejected("district races require a nonnegative integer district_num")
    out["district_num"] = district.where(~statewide).astype("Int64")
    dupes = out.duplicated(["state_po", "district_num", "office"], keep=False)
    if dupes.any():
        raise SnapshotRejected(
            f"{int(dupes.sum())} duplicated seat row(s); a snapshot holds one row per seat"
        )
    return out


def write_snapshot(
    df: pd.DataFrame, *, observed_on: str | None = None, directory: Path | None = None
) -> Path:
    """Append a dated snapshot. **Never overwrites.**

    An existing snapshot for a date is a record of what was true then; replacing it would
    rewrite the evidence. A correction is a new snapshot on a new date, which is the same
    rule ``reporting.preregistration`` applies to the seal itself.
    """
    validated = validate_snapshot(df)
    observed_on = observed_on or datetime.now(UTC).date().isoformat()
    try:
        observed_on = date.fromisoformat(observed_on).isoformat()
    except ValueError as exc:
        raise SnapshotRejected("observed_on must be an ISO date") from exc
    if (validated["retrieved_on"] > pd.Timestamp(observed_on)).any():
        raise SnapshotRejected("retrieved_on cannot be after observed_on")
    directory = directory or SNAPSHOT_DIR
    directory.mkdir(parents=True, exist_ok=True)
    out = directory / f"snapshot={observed_on}.csv"
    if out.exists():
        raise SnapshotRejected(
            f"{out} already exists. A snapshot is a record of what was true on its date; "
            "write a new date rather than rewriting the evidence."
        )
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=directory, prefix=".capture-", delete=False) as handle:
            temporary = Path(handle.name)
            validated.assign(observed_on=observed_on).to_csv(handle, index=False)
            handle.flush()
            os.fsync(handle.fileno())
        # Same-filesystem hard link atomically publishes a complete file without replacement.
        os.link(temporary, out)
    except FileExistsError as exc:
        raise SnapshotRejected(f"{out} already exists; never overwrite a captured observation") from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return out


def read_snapshots(directory: Path | None = None) -> pd.DataFrame:
    """Every snapshot, oldest first, with the date each was observed."""
    directory = directory or SNAPSHOT_DIR
    if not directory.is_dir():
        return pd.DataFrame(columns=[*SNAPSHOT_COLUMNS, "observed_on"])
    frames = []
    for path in sorted(directory.glob("snapshot=*.csv")):
        manifest = path.with_suffix(".manifest.json")
        if manifest.exists() and json.loads(manifest.read_text())["compiled_sha256"] != sha256_file(path):
            raise SnapshotRejected(f"captured snapshot checksum mismatch: {path}")
        frame = pd.read_csv(path, dtype=str)
        observed = path.stem.split("=", 1)[1]
        if "observed_on" in frame and not frame.observed_on.eq(observed).all():
            raise SnapshotRejected(f"observation date conflicts with filename: {path}")
        frame = validate_snapshot(frame)
        if (frame.retrieved_on > pd.Timestamp(observed)).any():
            raise SnapshotRejected(f"future retrieval date in {path}")
        frame["observed_on"] = observed
        frames.append(frame)
    if not frames:
        return pd.DataFrame(columns=[*SNAPSHOT_COLUMNS, "observed_on"])
    return pd.concat(frames, ignore_index=True).sort_values("observed_on")


def certification_ledger(snapshots: pd.DataFrame, *, as_of: str | None = None) -> pd.DataFrame:
    """Collapse to the first eligible observation in the current certification episode.

    The latest snapshot supplies the votes; the **earliest** snapshot in which the seat was
    certified supplies ``certified_on``. Taking the latest for both would date every
    certification to whenever the ledger was last touched, which would make ``as_of`` a free
    parameter again by the back door. Revocation/unresolved status clears eligibility;
    a later recertification starts a new episode without changing earlier as-of replays.
    """
    if not len(snapshots):
        return pd.DataFrame(columns=[*SNAPSHOT_COLUMNS, "certified_on"])

    s = snapshots.copy()
    if as_of is not None:
        cutoff = pd.Timestamp(as_of)
        s = s[pd.to_datetime(s["observed_on"], errors="raise") <= cutoff].copy()
        if s.empty:
            return pd.DataFrame(columns=[*SNAPSHOT_COLUMNS, "certified_on"])
    s["certified"] = _boolean(s["certified"], "certified")
    resolved = s.get("outcome_resolved", pd.Series(True, index=s.index)).fillna(True)
    s["outcome_resolved"] = _boolean(resolved, "outcome_resolved")
    s["district_num"] = pd.to_numeric(s["district_num"], errors="coerce").astype("Int64")
    s.loc[s["office"].isin(STATEWIDE_OFFICES), "district_num"] = pd.NA
    key = ["state_po", "district_num", "office"]

    if s.duplicated([*key, "observed_on"]).any():
        raise SnapshotRejected("duplicate seat observations on the same date")
    s = s.sort_values("observed_on")
    eligible = s.certified & s.outcome_resolved
    # A revocation breaks the certification episode; a later recertification starts anew.
    s["_episode"] = (~eligible).groupby([s[k] for k in key], dropna=False).cumsum()
    latest = s.drop_duplicates(key, keep="last")
    first_cert = s[eligible].groupby([*key, "_episode"], as_index=False, dropna=False)["observed_on"].first()
    ledger = latest.merge(
        first_cert.rename(columns={"observed_on": "certified_on"}), on=[*key, "_episode"], how="left"
    )
    ledger.loc[~(ledger.certified & ledger.outcome_resolved), "certified_on"] = pd.NA
    return ledger.drop(columns="_episode")


def to_actual(ledger: pd.DataFrame, *, state_fips: dict[str, str]) -> pd.DataFrame:
    """The frame ``score_preregistration`` consumes.

    ``actual_dem_share`` is a **two-party** share, matching the basis the forecast predicted
    on (CLAUDE.md §6). A seat never seen certified carries a null ``certified_on``, which the
    scorer treats as unscored at any ``as_of`` — the registered behaviour, not a convenience.
    """
    if not len(ledger):
        return pd.DataFrame(columns=ACTUAL_COLUMNS)
    out = ledger.copy()
    unknown_states = sorted(set(out["state_po"]) - set(state_fips))
    if unknown_states:
        raise SnapshotRejected(f"unknown state(s): {unknown_states}")
    for col in ("dem_votes", "rep_votes", "other_votes"):
        if col not in out:
            out[col] = 0
        out[col] = pd.to_numeric(out[col], errors="coerce")
    two_party = out["dem_votes"] + out["rep_votes"]
    out["actual_dem_share"] = out["dem_votes"] / two_party.where(two_party > 0)
    winner = out.get("winner_party", pd.Series("", index=out.index)).fillna("").str.upper()
    ambiguous = (out["other_votes"] > 0) & (out["other_votes"] >= out[["dem_votes", "rep_votes"]].max(axis=1))
    if (ambiguous & winner.eq("") & out["certified_on"].notna()).any():
        raise SnapshotRejected("a possible third-party winner needs explicit winner_party")
    out["actual_dem_win"] = (out["dem_votes"] > out["rep_votes"]).where(winner.eq(""), winner.eq("DEMOCRAT"))
    out["geography_id"] = [
        geography_id(state_fips.get(str(s), "00"), d, o)
        for s, d, o in zip(out["state_po"], out["district_num"], out["office"], strict=True)
    ]
    return out.reindex(columns=[*ACTUAL_COLUMNS, "actual_dem_win", "state_po", "district_num"])

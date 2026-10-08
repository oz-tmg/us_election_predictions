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

from datetime import date
from pathlib import Path

import pandas as pd

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


def geography_id(state_fips: str, district_num: object, office: str = "us_house") -> str:
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
    for col in ("dem_votes", "rep_votes", "other_votes"):
        out[col] = pd.to_numeric(out[col], errors="coerce")
    if out[["dem_votes", "rep_votes"]].isna().any().any():
        raise SnapshotRejected("dem_votes and rep_votes must both be numeric on every row")
    if (out[["dem_votes", "rep_votes"]] < 0).any().any():
        raise SnapshotRejected("negative votes")

    for col in ("source_url", "retrieved_on"):
        blank = out[col].isna() | out[col].astype(str).str.strip().eq("")
        if blank.any():
            raise SnapshotRejected(
                f"{int(blank.sum())} row(s) have no {col}; every row needs its own provenance"
            )
    out["retrieved_on"] = pd.to_datetime(out["retrieved_on"], errors="coerce")
    if out["retrieved_on"].isna().any():
        raise SnapshotRejected("retrieved_on must be a date on every row")

    out["certified"] = (
        out["certified"].astype(str).str.strip().str.upper().isin({"TRUE", "T", "Y", "YES", "1"})
    )
    out["district_num"] = out["district_num"].fillna("")
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
    observed_on = observed_on or date.today().isoformat()
    directory = directory or SNAPSHOT_DIR
    directory.mkdir(parents=True, exist_ok=True)
    out = directory / f"snapshot={observed_on}.csv"
    if out.exists():
        raise SnapshotRejected(
            f"{out} already exists. A snapshot is a record of what was true on its date; "
            "write a new date rather than rewriting the evidence."
        )
    validated.assign(observed_on=observed_on).to_csv(out, index=False)
    return out


def read_snapshots(directory: Path | None = None) -> pd.DataFrame:
    """Every snapshot, oldest first, with the date each was observed."""
    directory = directory or SNAPSHOT_DIR
    if not directory.is_dir():
        return pd.DataFrame(columns=[*SNAPSHOT_COLUMNS, "observed_on"])
    frames = []
    for path in sorted(directory.glob("snapshot=*.csv")):
        frame = pd.read_csv(path, dtype=str)
        frame["observed_on"] = path.stem.split("=", 1)[1]
        frames.append(frame)
    if not frames:
        return pd.DataFrame(columns=[*SNAPSHOT_COLUMNS, "observed_on"])
    return pd.concat(frames, ignore_index=True).sort_values("observed_on")


def certification_ledger(snapshots: pd.DataFrame) -> pd.DataFrame:
    """Collapse the snapshots into one row per seat, with the date it was *first* certified.

    The latest snapshot supplies the votes; the **earliest** snapshot in which the seat was
    certified supplies ``certified_on``. Taking the latest for both would date every
    certification to whenever the ledger was last touched, which would make ``as_of`` a free
    parameter again by the back door.
    """
    if not len(snapshots):
        return pd.DataFrame(columns=[*SNAPSHOT_COLUMNS, "certified_on"])

    s = snapshots.copy()
    s["certified"] = s["certified"].astype(str).str.strip().str.upper().isin({"TRUE", "T", "Y", "YES", "1"})
    s["district_num"] = pd.to_numeric(s["district_num"], errors="coerce").astype("Int64")
    key = ["state_po", "district_num", "office"]

    latest = s.sort_values("observed_on").groupby(key, as_index=False).last()
    first_cert = (
        s[s["certified"]].sort_values("observed_on").groupby(key, as_index=False)["observed_on"].first()
    )
    ledger = latest.merge(first_cert.rename(columns={"observed_on": "certified_on"}), on=key, how="left")
    return ledger


def to_actual(ledger: pd.DataFrame, *, state_fips: dict[str, str]) -> pd.DataFrame:
    """The frame ``score_preregistration`` consumes.

    ``actual_dem_share`` is a **two-party** share, matching the basis the forecast predicted
    on (CLAUDE.md §6). A seat never seen certified carries a null ``certified_on``, which the
    scorer treats as unscored at any ``as_of`` — the registered behaviour, not a convenience.
    """
    if not len(ledger):
        return pd.DataFrame(columns=ACTUAL_COLUMNS)
    out = ledger.copy()
    for col in ("dem_votes", "rep_votes"):
        out[col] = pd.to_numeric(out[col], errors="coerce")
    two_party = out["dem_votes"] + out["rep_votes"]
    out["actual_dem_share"] = out["dem_votes"] / two_party.where(two_party > 0)
    out["geography_id"] = [
        geography_id(state_fips.get(str(s), "00"), d, o)
        for s, d, o in zip(out["state_po"], out["district_num"], out["office"], strict=True)
    ]
    return out.reindex(columns=[*ACTUAL_COLUMNS, "state_po", "district_num"])

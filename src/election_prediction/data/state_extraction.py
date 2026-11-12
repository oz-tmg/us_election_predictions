"""Per-state extraction of official aggregate releases, tested against certified history.

Election night needs, for every state, a parser that turns that state's own official
release into the capture schema (``results_2026.SNAPSHOT_COLUMNS``). A parser is only
trusted after it has reproduced a past certified result: ``reconcile`` compares what a
parser extracts from the state's **2024** official release with the certified 2024
returns already in ``race_results`` (MEDSL), race by race and party by party.

A parser never decides certification: ``to_snapshot`` takes the ``certified`` flag from
the operator, who reads it off the source (results_2026: "the officially-certified flag
as the source reported it"). Aggregate files only; nothing here may read a voter file.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

import pandas as pd

from .results_2026 import SNAPSHOT_COLUMNS

EXTRACTED_COLUMNS = [
    "state_po",
    "district_num",
    "office",
    "dem_votes",
    "rep_votes",
    "other_votes",
    "winner_party",
]
OFFICES = {"us_house", "us_senate"}
#: Optional round fields, required by the ledger for Louisiana House
#: (``results_2026.validate_snapshot``); carried through when a parser sets them.
ROUND_COLUMNS = ["election_round", "outcome_resolved"]

Parser = Callable[[Sequence[Path]], pd.DataFrame]
PARSERS: dict[str, Parser] = {}


def register(state: str) -> Callable[[Parser], Parser]:
    def wrap(fn: Parser) -> Parser:
        if state in PARSERS:
            raise ValueError(f"parser for {state} already registered")
        PARSERS[state] = fn
        return fn

    return wrap


def party_bucket(label: object) -> str:
    """Map a party label as states print it to DEMOCRAT / REPUBLICAN / OTHER."""
    text = str(label or "").strip().upper().replace(".", "")
    if text in {"D", "DEM", "DEMOCRAT", "DEMOCRATIC", "DEMOCRATIC PARTY", "DEMOCRATIC-FARMER-LABOR", "DFL"}:
        return "DEMOCRAT"
    if text in {"R", "REP", "REPUBLICAN", "REPUBLICAN PARTY", "GOP"}:
        return "REPUBLICAN"
    return "OTHER"


def from_candidates(
    rows: pd.DataFrame, *, state_po: str, office: str, district_num: int | None
) -> dict[str, object]:
    """Collapse one contest's candidate rows (``party``, ``votes``) into one race row.

    Parties are bucketed after summing, so a candidate listed on two lines is summed, and
    ``winner_party`` comes from the top single candidate, not a party total.
    """
    if office not in OFFICES:
        raise ValueError(f"office must be one of {sorted(OFFICES)}")
    r = rows.assign(bucket=rows["party"].map(party_bucket), votes=pd.to_numeric(rows["votes"]))
    by_bucket = r.groupby("bucket")["votes"].sum()
    top = r.loc[r["votes"].idxmax(), "bucket"] if len(r) else None
    return {
        "state_po": state_po,
        "district_num": district_num,
        "office": office,
        "dem_votes": int(by_bucket.get("DEMOCRAT", 0)),
        "rep_votes": int(by_bucket.get("REPUBLICAN", 0)),
        "other_votes": int(by_bucket.get("OTHER", 0)),
        "winner_party": top,
    }


def validate_extracted(frame: pd.DataFrame) -> pd.DataFrame:
    missing = set(EXTRACTED_COLUMNS) - set(frame.columns)
    if missing:
        raise ValueError(f"extracted frame missing {sorted(missing)}")
    out = frame[EXTRACTED_COLUMNS + [c for c in ROUND_COLUMNS if c in frame]].copy()
    if not out["office"].isin(OFFICES).all():
        raise ValueError("unknown office in extraction")
    for c in ("dem_votes", "rep_votes", "other_votes"):
        out[c] = pd.to_numeric(out[c]).astype(int)
        if (out[c] < 0).any():
            raise ValueError(f"negative {c}")
    out["district_num"] = out["district_num"].astype("Int64").where(out["office"] == "us_house")
    keys = ["office", "district_num"]
    if out.duplicated(keys).any():
        raise ValueError(f"duplicate races: {out[out.duplicated(keys, keep=False)][keys].to_dict('records')}")
    return out.sort_values(keys).reset_index(drop=True)


def extract(state: str, paths: Sequence[Path]) -> pd.DataFrame:
    if state not in PARSERS:
        raise KeyError(f"no parser registered for {state}")
    frame = PARSERS[state](paths)
    frame["state_po"] = state
    return validate_extracted(frame)


def to_snapshot(
    extracted: pd.DataFrame, *, source_url: str, retrieved_on: str, certified: bool
) -> pd.DataFrame:
    """The capture-schema rows ``build_results_2026 capture`` accepts."""
    out = extracted.assign(certified=bool(certified), source_url=source_url, retrieved_on=retrieved_on)
    return out[[*SNAPSHOT_COLUMNS, "winner_party", *(c for c in ROUND_COLUMNS if c in out)]]


def _tolerance(certified_votes: float) -> float:
    """The quarantine's reconciliation rule: within max(10 votes, 0.1%)."""
    return max(10.0, abs(certified_votes) * 0.001)


def reconcile(extracted: pd.DataFrame, race_results: pd.DataFrame, *, state: str, cycle: int) -> pd.DataFrame:
    """Race-by-race comparison with certified returns for one state and cycle (general only)."""
    cert = race_results[
        (race_results["state_po"] == state)
        & (race_results["cycle"] == cycle)
        & race_results["office"].isin(OFFICES)
        & race_results["race_id"].str.endswith("_gen")
    ].copy()
    cert["district_num"] = cert["district_num"].astype("Int64").where(cert["office"] == "us_house")
    cert = cert[["office", "district_num", "dem_votes", "rep_votes", "uncontested_flag"]].fillna(
        {"dem_votes": 0, "rep_votes": 0}
    )
    ext = extracted[["office", "district_num", "dem_votes", "rep_votes", "other_votes"]].copy()
    ext["district_num"] = ext["district_num"].astype("Int64")
    m = ext.merge(
        cert, on=["office", "district_num"], how="outer", suffixes=("_ext", "_cert"), indicator=True
    )
    out = []
    for r in m.to_dict(orient="records"):
        row = {
            "state_po": state,
            "office": r["office"],
            "district_num": r["district_num"],
            "dem_ext": r["dem_votes_ext"],
            "dem_cert": r["dem_votes_cert"],
            "rep_ext": r["rep_votes_ext"],
            "rep_cert": r["rep_votes_cert"],
            "share_diff": None,
        }
        if r["_merge"] == "left_only":
            row["status"] = "extra_in_extract"
        elif r["_merge"] == "right_only":
            row["status"] = "missing_in_extract"
        else:
            d_ext, d_cert, r_ext, r_cert = (
                float(r[k]) for k in ("dem_votes_ext", "dem_votes_cert", "rep_votes_ext", "rep_votes_cert")
            )
            exact = d_ext == d_cert and r_ext == r_cert
            close = abs(d_ext - d_cert) <= _tolerance(d_cert) and abs(r_ext - r_cert) <= _tolerance(r_cert)
            row["status"] = "exact" if exact else ("within_tolerance" if close else "mismatch")
            if d_ext + r_ext and d_cert + r_cert:
                row["share_diff"] = d_ext / (d_ext + r_ext) - d_cert / (d_cert + r_cert)
        out.append(row)
    return pd.DataFrame(out).sort_values(["office", "district_num"]).reset_index(drop=True)


def summarize(reconciliation: pd.DataFrame) -> dict[str, object]:
    counts = reconciliation["status"].value_counts().to_dict()
    passed = set(counts) <= {"exact", "within_tolerance"} and len(reconciliation) > 0
    diffs = reconciliation.get("share_diff", pd.Series(dtype=float)).dropna().abs()
    return {
        "passed": bool(passed),
        "races": int(len(reconciliation)),
        "status_counts": {k: int(v) for k, v in counts.items()},
        "max_abs_share_diff": float(diffs.max()) if len(diffs) else None,
    }

"""Validation checks that gate ingested data before it lands in silver/gold.

Lightweight, dependency-free reconciliation and schema checks (a Pandera-equivalent
that runs anywhere). Mirrors the quality gates in docs/ingestion-playbook.md steps
4-6: schema, unique keys, vote-total reconciliation, geography validity, freshness.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from ..geography import reference as ref


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class ValidationReport:
    dataset: str
    results: list[CheckResult] = field(default_factory=list)

    def add(self, name: str, passed: bool, detail: str = "") -> None:
        self.results.append(CheckResult(name, passed, detail))

    @property
    def ok(self) -> bool:
        return all(r.passed for r in self.results)

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"check": r.name, "status": "PASS" if r.passed else "FAIL", "detail": r.detail}
                for r in self.results
            ]
        )

    def summary(self) -> str:
        n_pass = sum(r.passed for r in self.results)
        head = f"[{self.dataset}] {n_pass}/{len(self.results)} checks passed"
        lines = [head] + [
            f"  {'PASS' if r.passed else 'FAIL'}  {r.name}" + (f" — {r.detail}" if r.detail else "")
            for r in self.results
        ]
        return "\n".join(lines)


def validate_silver_returns(df: pd.DataFrame, *, required_columns: list[str]) -> ValidationReport:
    """Run silver-layer quality gates on conformed election returns."""
    rep = ValidationReport(dataset="silver.election_returns")

    # 1. schema
    missing = [c for c in required_columns if c not in df.columns]
    rep.add("schema.required_columns", not missing, "" if not missing else f"missing: {missing}")

    # 2. non-empty
    rep.add("rows.non_empty", len(df) > 0, f"{len(df)} rows")

    # 3. unique natural key (race_id + candidate + party line)
    #
    # The party line is part of the key because MEDSL records aggregate minor-party
    # and scattering votes with no candidate name — several such rows per race, each
    # on a different party line. They are real counted votes that reconcile to the
    # race total, so they are kept; keying on candidate alone would flag them as
    # duplicates. A genuine double-count of one candidate on one party line is still
    # caught, and fusion lines are already merged upstream (``medsl._collapse_fusion``).
    if {"race_id", "candidate", "party"}.issubset(df.columns):
        dupes = df.duplicated(["race_id", "candidate", "party"]).sum()
        rep.add(
            "keys.unique_race_candidate_party",
            dupes == 0,
            "" if dupes == 0 else f"{dupes} duplicate race_id+candidate+party rows",
        )

    # 4. nonnegative votes
    if "candidatevotes" in df.columns:
        neg = int((df["candidatevotes"] < 0).sum())
        rep.add("votes.nonnegative", neg == 0, "" if neg == 0 else f"{neg} negative vote rows")

    # 5. vote-total reconciliation: sum(candidatevotes) == totalvotes per race.
    #
    # Delegated to `quarantine.unreconciled_races` so this gate and the quarantine cannot
    # disagree about what reconciles -- they are the same question asked twice, and when
    # they were implemented separately they drifted: exact equality here excluded 32 races
    # the quarantine had already been corrected to accept. The rule allows either of the two
    # conventions MEDSL uses for blank and void ballots; see that module.
    if {"race_id", "candidatevotes", "totalvotes"}.issubset(df.columns):
        from . import quarantine as _q

        unreconciled, n_checked = _q.unreconciled_races(df)
        mism = len(unreconciled)
        rep.add(
            "votes.reconcile_to_total",
            mism == 0,
            ""
            if mism == 0
            else f"{mism}/{n_checked} races where candidate sum != totalvotes under either convention",
        )

    # 6. vote share in [0, 1]
    if "vote_share" in df.columns:
        bad = int(((df["vote_share"] < -1e-9) | (df["vote_share"] > 1 + 1e-9)).sum())
        rep.add("share.in_unit_interval", bad == 0, "" if bad == 0 else f"{bad} out-of-range shares")

    # 7. geography validity (state FIPS resolvable)
    if "state_fips" in df.columns:
        bad_states = []
        for fips in df["state_fips"].dropna().unique():
            try:
                ref.by_fips(fips)
            except KeyError:
                bad_states.append(fips)
        rep.add(
            "geography.state_fips_valid",
            not bad_states,
            "" if not bad_states else f"unknown FIPS: {bad_states}",
        )

    return rep


def validate_geography_table(df: pd.DataFrame) -> ValidationReport:
    rep = ValidationReport(dataset="silver.geography")
    rep.add(
        "keys.unique_geography_id",
        df["geography_id"].is_unique,
        "" if df["geography_id"].is_unique else "duplicate geography_id",
    )
    valid_levels = {"nation", "state", "county", "cong_district"}
    bad = set(df["geog_level"].unique()) - valid_levels
    rep.add("levels.known", not bad, "" if not bad else f"unknown levels: {bad}")
    return rep

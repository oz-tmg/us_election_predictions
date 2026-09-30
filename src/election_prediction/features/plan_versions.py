"""Plan-version register: which congressional map a state actually used (RD-001).

``incumbency.plan_era`` derives a district's map from the cycle year alone — one map per
decade, 1972, 1982, ... 2022. That is true most of the time and false exactly now: nine
states vote under a different congressional map in November 2026 than they used in 2024,
and three of them (AL, LA, NC) also changed between 2022 and 2024. A district number is a
label a legislature attaches to territory, and the label survives changes the territory
does not.

This module replaces the year function with a sourced, per-state lookup backed by
``data/reference/house_plan_versions.csv``. States with no row fall back to the decennial
default, so the register only carries rows where something changed.

Two vocabulary decisions are encoded here, both signed off 2026-09-30 and both recorded in
``PROJECT_CONTEXT.md`` §13:

* **``boundary_confidence`` is about territory, nothing else** — ``unchanged``,
  ``redrawn`` or ``unverified``. The older ``pending`` value conflated "the territory
  moved" with "a court might move it", which got Missouri exactly backwards: Missouri
  enacted a 2025 map, is enjoined from using it, and votes its 2022 map in the general, so
  its territory is *unchanged* and its 2024 priors are valid. Routing on litigation would
  have discarded eight good priors.
* **``litigation_risk`` is a separate flag the report prints and the routing ignores.**
  Whether a map might move before election day is real and worth stating; it is not a
  statement about whether this cycle's district is last cycle's district.

The register applies to historical cycles as well as forward ones (decision 2026-09-30).
``apply_to_history=False`` pins historical ``plan_id`` to the decennial default and exists
so the change could be landed in two attributable steps — the plumbing first with the
backtest provably unmoved, then the flip. It is not a supported production mode.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .incumbency import plan_era

REGISTER_COLUMNS = [
    "state_po",
    "plan_id",
    "first_cycle",
    "last_cycle",
    "authority",
    "enacted_on",
    "status",
    "litigation_risk",
    "source_url",
    "baf_url",
    "retrieved_on",
    "verified_by",
    "notes",
]

# A row must say where the claim came from and who checked it. `baf_url` is allowed to be
# empty — block-assignment files are RD-003's collection task and none is located yet.
REQUIRED_NON_EMPTY = [
    "state_po",
    "plan_id",
    "authority",
    "status",
    "source_url",
    "retrieved_on",
    "verified_by",
]

STATUS_IN_EFFECT = "in_effect"
STATUS_SUPERSEDED = "superseded"
STATUS_ENJOINED = "enjoined"
STATUS_VALUES = {STATUS_IN_EFFECT, STATUS_SUPERSEDED, STATUS_ENJOINED}

# `boundary_confidence` describes territory only. `pending` is deliberately absent.
BOUNDARY_UNCHANGED = "unchanged"
BOUNDARY_REDRAWN = "redrawn"
BOUNDARY_UNVERIFIED = "unverified"

LITIGATION_NONE = "none"
LITIGATION_ACTIVE = "active"
LITIGATION_VALUES = {LITIGATION_NONE, LITIGATION_ACTIVE}

DEFAULT_REGISTER = Path(__file__).resolve().parents[3] / "data" / "reference" / "house_plan_versions.csv"


class PlanRegisterError(ValueError):
    """The register is malformed, unsourced, or self-contradictory."""


def decennial_plan_id(state_po: str, cycle: int) -> str:
    """The plan a state is assumed to use when the register carries no row for it."""
    return f"{state_po.upper()}_DEC{plan_era(int(cycle))}"


def load_register(path: str | Path | None = None) -> pd.DataFrame:
    """Read the register, normalising blanks to NA and cycles to nullable ints."""
    src = Path(path) if path is not None else DEFAULT_REGISTER
    df = pd.read_csv(src, dtype=str).fillna("")
    for col in REGISTER_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    for col in df.columns:
        df[col] = df[col].astype(str).str.strip()
    df["state_po"] = df["state_po"].str.upper()
    for col in ("first_cycle", "last_cycle"):
        df[col] = pd.to_numeric(df[col].replace("", pd.NA), errors="coerce").astype("Int64")
    df["litigation_risk"] = df["litigation_risk"].replace("", LITIGATION_NONE)
    return df[REGISTER_COLUMNS]


def validate_plan_versions(register: pd.DataFrame, *, cycles: list[int] | None = None) -> dict:
    """Raise on a register that cannot be trusted; return a summary if it can.

    The checks, in the order they earn their keep:

    1. **Every state in the register governs each requested cycle with exactly one plan.**
       Membership is by cycle range, not by ``status``: a plan superseded today still
       governed its own elections, while an ``enjoined`` plan governed nothing. This is
       the check that catches the Missouri error — closing ``MO_2022`` at 2024 while the
       only 2026 row is ``enjoined`` leaves the state with no map and hands the cycle to a
       plan a court has blocked. Write its test first.
    2. Unknown ``status`` or ``litigation_risk`` values.
    3. A missing source, retrieval date or verifier — an unverified row is a lead, not a
       fact, and must not reach the modelling layer.
    4. Overlapping cycle ranges within a state: two maps cannot both govern one election.
    5. A row with a cycle range but status ``enjoined`` — an enjoined plan was not used.
    """
    problems: list[str] = []

    missing = [c for c in REGISTER_COLUMNS if c not in register.columns]
    if missing:
        raise PlanRegisterError(f"register is missing column(s) {missing}")

    for col in REQUIRED_NON_EMPTY:
        blank = register[register[col].astype(str).str.strip() == ""]
        for _, row in blank.iterrows():
            problems.append(f"{row['plan_id'] or '<no plan_id>'}: empty {col}")

    bad_status = register.loc[~register["status"].isin(STATUS_VALUES), "plan_id"].tolist()
    if bad_status:
        problems.append(f"unknown status on {bad_status}; expected {sorted(STATUS_VALUES)}")

    bad_lit = register.loc[~register["litigation_risk"].isin(LITIGATION_VALUES), "plan_id"].tolist()
    if bad_lit:
        problems.append(f"unknown litigation_risk on {bad_lit}; expected {sorted(LITIGATION_VALUES)}")

    bad_url = register.loc[~register["source_url"].str.startswith("http"), "plan_id"].tolist()
    if bad_url:
        problems.append(f"source_url is not a URL on {bad_url}")

    enjoined_with_cycles = register[
        (register["status"] == STATUS_ENJOINED) & register["first_cycle"].notna()
    ]["plan_id"].tolist()
    if enjoined_with_cycles:
        problems.append(
            f"enjoined plan(s) {enjoined_with_cycles} carry a cycle range; "
            "an enjoined map was not used"
        )

    for state, rows in register.groupby("state_po"):
        spans = [
            (int(r["first_cycle"]), int(r["last_cycle"]) if pd.notna(r["last_cycle"]) else 9999, r["plan_id"])
            for _, r in rows.iterrows()
            if pd.notna(r["first_cycle"])
        ]
        for i, (a0, a1, aid) in enumerate(spans):
            for b0, b1, bid in spans[i + 1 :]:
                if a0 <= b1 and b0 <= a1:
                    problems.append(f"{state}: cycle ranges of {aid} and {bid} overlap")

    # `status` describes a plan's standing *today*; the cycle range says which elections it
    # actually governed. A plan superseded in 2026 still governed 2022, so the coverage
    # check is on the range, excluding only plans that were enjoined and never used.
    for cycle in cycles or []:
        for state, rows in register.groupby("state_po"):
            live = [
                r["plan_id"]
                for _, r in rows.iterrows()
                if r["status"] != STATUS_ENJOINED
                and pd.notna(r["first_cycle"])
                and int(r["first_cycle"]) <= cycle
                and (pd.isna(r["last_cycle"]) or int(r["last_cycle"]) >= cycle)
            ]
            if len(live) != 1:
                problems.append(
                    f"{state} has {len(live)} governing plan(s) for cycle {cycle} "
                    f"({live or 'none'}); expected exactly 1"
                )

    if problems:
        raise PlanRegisterError("plan-version register failed validation:\n  - " + "\n  - ".join(problems))

    return {
        "rows": int(len(register)),
        "states": int(register["state_po"].nunique()),
        "cycles_checked": sorted(cycles or []),
        "oldest_retrieved_on": min(register.loc[register["status"] != STATUS_SUPERSEDED, "retrieved_on"]),
        "litigation_active": sorted(
            register.loc[register["litigation_risk"] == LITIGATION_ACTIVE, "state_po"].unique().tolist()
        ),
    }


@dataclass(frozen=True)
class PlanVersions:
    """Per-state plan identity, with the decennial default as the fallback.

    ``apply_to_history`` exists only so the register could be landed in two attributable
    commits; production reads the register for every cycle.
    """

    register: pd.DataFrame
    apply_to_history: bool = True
    history_before: int = 2026

    @classmethod
    def load(cls, path: str | Path | None = None, **kwargs) -> PlanVersions:
        return cls(register=load_register(path), **kwargs)

    def _consults_register(self, cycle: int) -> bool:
        return self.apply_to_history or int(cycle) >= self.history_before

    def plan_id(self, state_po: str, cycle: int) -> str:
        """The plan in effect for ``state_po`` in ``cycle``; decennial default if unknown."""
        state, cycle = state_po.upper(), int(cycle)
        if not self._consults_register(cycle):
            return decennial_plan_id(state, cycle)
        rows = self.register[
            (self.register["state_po"] == state) & (self.register["status"] != STATUS_ENJOINED)
        ]
        for _, r in rows.iterrows():
            if pd.isna(r["first_cycle"]):
                continue
            if int(r["first_cycle"]) <= cycle and (pd.isna(r["last_cycle"]) or int(r["last_cycle"]) >= cycle):
                return str(r["plan_id"])
        return decennial_plan_id(state, cycle)

    def boundary_confidence(self, state_po: str, cycle: int, *, term: int = 2) -> str:
        """Territory only: is ``cycle``'s district the same territory as ``cycle - term``'s?

        Never returns ``unverified`` — that value means "the register has not been consulted
        for this seat", which is the caller's state, not the register's.
        """
        this = self.plan_id(state_po, cycle)
        prior = self.plan_id(state_po, int(cycle) - term)
        return BOUNDARY_UNCHANGED if this == prior else BOUNDARY_REDRAWN

    def litigation_risk(self, state_po: str, cycle: int) -> str:
        """Whether the map in effect could still move. Printed in reports; never routed on."""
        state, cycle = state_po.upper(), int(cycle)
        pid = self.plan_id(state, cycle)
        hit = self.register[(self.register["state_po"] == state) & (self.register["plan_id"] == pid)]
        if len(hit):
            return str(hit.iloc[0]["litigation_risk"])
        return LITIGATION_NONE

    def annotate(self, seats: pd.DataFrame, *, cycle: int, term: int = 2) -> pd.DataFrame:
        """Attach ``plan_id``, ``boundary_confidence`` and ``litigation_risk`` to a seat frame."""
        out = seats.copy()
        if not len(out):
            for col in ("plan_id", "boundary_confidence", "litigation_risk"):
                out[col] = pd.Series(dtype=str)
            return out
        states = out["state_po"].astype(str)
        out["plan_id"] = [self.plan_id(s, cycle) for s in states]
        out["boundary_confidence"] = [self.boundary_confidence(s, cycle, term=term) for s in states]
        out["litigation_risk"] = [self.litigation_risk(s, cycle) for s in states]
        return out

    def redrawn_states(self, cycle: int, *, term: int = 2) -> list[str]:
        """States whose territory changed between ``cycle - term`` and ``cycle``."""
        states = sorted(self.register["state_po"].unique())
        return [s for s in states if self.boundary_confidence(s, cycle, term=term) == BOUNDARY_REDRAWN]

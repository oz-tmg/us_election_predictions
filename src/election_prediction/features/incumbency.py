"""Incumbency and open-seat features (F-001).

MEDSL returns carry no incumbency flag, so incumbency is *derived*: the winner of the
prior election for the same seat is looked up, and the current race is checked for a
candidate with the same name. That yields the three states that matter for a baseline
model — an incumbent is running, the seat is open, or the prior result is unusable.

Two office-specific rules make the derivation valid:

* **House — redistricting breaks the lookup.** District boundaries are redrawn for the
  election two years after each decennial census (1972, 1982, ... 2022), so a district
  number does not refer to the same territory across that boundary. Matching across one
  would silently mislabel open seats in exactly the cycles that matter, so races in the
  first cycle of a plan era are marked ``redistricting_break`` and get no incumbency
  claim (CLAUDE.md §6, PROJECT_CONTEXT §16).
* **Senate — terms are six years, not two.** The prior election for the same seat is six
  cycles' worth of years earlier, which also keeps the two classes within a state
  distinct. Special elections are off-schedule and are excluded from the lookup rather
  than being treated as the regular seat.

Name matching is deliberately shallow. Measured on the real 1976-2024 House file,
normalizing punctuation and spacing recovers only ~1.2 percentage points over exact
string matching, so a heavier alias crosswalk (P0-003) is not on the critical path here.
"""

from __future__ import annotations

import re

import pandas as pd

INCUMBENCY_COLUMNS = [
    "race_id",
    "cycle",
    "office",
    "state_po",
    "district_num",
    "geography_id",
    "prior_race_id",
    "incumbent_name",
    "incumbent_party",
    "incumbent_running",
    "open_seat",
    "incumbent_won",
    "redistricting_break",
    "prior_available",
]

# Term length in years, i.e. how far back the same seat was last contested.
TERM_YEARS = {"us_house": 2, "us_senate": 6, "president": 4}

# House maps are redrawn for the election two years after each decennial census.
FIRST_PLAN_CYCLE_OFFSET = 2


def plan_era(cycle: int) -> int:
    """First cycle of the redistricting plan era ``cycle`` belongs to (1972, 1982, ...)."""
    return ((cycle - FIRST_PLAN_CYCLE_OFFSET) // 10) * 10 + FIRST_PLAN_CYCLE_OFFSET


def normalize_name(name: object) -> str:
    """Collapse a candidate name to a comparable key.

    Uppercase, strip everything that is not a letter. MEDSL is internally consistent
    about name order within an office (``FORD, GERALD`` for president, ``JACK EDWARDS``
    for House), so cross-cycle matching within one office does not need to reorder parts.
    """
    return re.sub(r"[^A-Z]", "", str(name).upper())


def _seat_key(row: pd.Series) -> str:
    """Identity of the seat being contested, independent of cycle."""
    if row["office"] == "us_house":
        district = row["district_num"]
        d = f"{int(district):02d}" if pd.notna(district) else "na"
        return f"us_house:{row['state_po']}:{d}"
    return f"{row['office']}:{row['state_po']}"


def build_incumbency(returns: pd.DataFrame, office: str) -> pd.DataFrame:
    """Derive incumbency flags for every race of ``office`` in the silver returns.

    ``returns`` must carry the silver schema — the full candidate list is required,
    since "is the incumbent running" cannot be answered from winners alone.
    """
    if office not in TERM_YEARS:
        raise ValueError(f"Unsupported office for incumbency: {office!r}")
    term = TERM_YEARS[office]

    df = returns[returns["office"] == office].copy()
    # Special elections are off-schedule; they neither establish nor inherit a regular term.
    regular = df[~df["special"].fillna(False)] if "special" in df.columns else df

    # Winner and full candidate roster per race.
    winners = (
        regular.sort_values("candidatevotes", ascending=False, na_position="last")
        .groupby("race_id", as_index=False)
        .first()[
            [
                "race_id",
                "cycle",
                "office",
                "state_po",
                "district_num",
                "geography_id",
                "candidate",
                "party_simplified",
            ]
        ]
        .rename(columns={"candidate": "winner", "party_simplified": "winner_party"})
    )
    winners["seat"] = winners.apply(_seat_key, axis=1)
    roster = (
        regular.assign(name_key=regular["candidate"].map(normalize_name))
        .groupby("race_id")["name_key"]
        .apply(set)
    )

    # Prior contest for the same seat, one full term earlier.
    prior = winners.assign(cycle=winners["cycle"] + term)[
        ["seat", "cycle", "race_id", "winner", "winner_party"]
    ].rename(
        columns={"race_id": "prior_race_id", "winner": "incumbent_name", "winner_party": "incumbent_party"}
    )
    merged = winners.merge(prior, on=["seat", "cycle"], how="left")

    merged["prior_available"] = merged["incumbent_name"].notna()
    if office == "us_house":
        merged["redistricting_break"] = merged["cycle"].map(plan_era) != merged["cycle"].sub(term).map(
            plan_era
        )
    else:
        merged["redistricting_break"] = False

    # A district number does not survive a redraw, so no incumbency is claimed across one.
    usable = merged["prior_available"] & ~merged["redistricting_break"]
    incumbent_key = merged["incumbent_name"].map(normalize_name).where(usable)
    running = [
        bool(key) and key in roster.get(rid, set())
        for key, rid in zip(incumbent_key.fillna(""), merged["race_id"], strict=True)
    ]
    merged["incumbent_running"] = pd.Series(running, index=merged.index) & usable
    merged["open_seat"] = usable & ~merged["incumbent_running"]
    merged["incumbent_won"] = merged["incumbent_running"] & (
        merged["winner"].map(normalize_name) == incumbent_key.fillna("")
    )
    merged.loc[~usable, ["incumbent_name", "incumbent_party", "prior_race_id"]] = pd.NA

    return merged[INCUMBENCY_COLUMNS].sort_values(["cycle", "state_po", "race_id"]).reset_index(drop=True)


def incumbency_summary(inc: pd.DataFrame) -> dict:
    """Headline rates, for the data-quality report and for sanity-checking the join."""
    usable = inc[inc["prior_available"] & ~inc["redistricting_break"]]
    return {
        "races": int(len(inc)),
        "races_with_prior": int(len(usable)),
        "redistricting_breaks": int(inc["redistricting_break"].sum()),
        "incumbent_running_rate": (
            float(usable["incumbent_running"].mean()) if len(usable) else float("nan")
        ),
        "open_seat_rate": float(usable["open_seat"].mean()) if len(usable) else float("nan"),
        "incumbent_win_rate": (
            float(inc.loc[inc["incumbent_running"], "incumbent_won"].mean())
            if inc["incumbent_running"].any()
            else float("nan")
        ),
    }

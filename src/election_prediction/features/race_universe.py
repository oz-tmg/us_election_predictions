"""Canonical election cycle and prospective race universe (P0-001).

Everything else in this project backtests history. This module answers the forward
question a forecast actually needs: *which seats are on the ballot, and who holds them
now?* It is the join between the historical stack and a live cycle.

What is derivable from the validated returns, with no new data source:

* **House** — all 435 voting seats are contested every even year. Fixed by statute.
* **Senate** — terms are six years, so the seats up in year Y are exactly the seats last
  contested in a *regular* election in Y-6. Deriving the class from our own returns
  rather than hardcoding a state list means it stays correct for any cycle and is
  checkable: 2020's 33 regular races reproduce Class II exactly.
* **Incumbent** — the winner of that seat's last regular contest.

What is **not** derivable and is therefore left explicitly unknown rather than guessed:

* **Who is actually running.** Filings, retirements, primary defeats, and party switches
  are candidate-level facts no returns file contains. Every row carries
  ``incumbent_status = "unknown"`` until a filings source is joined; the registry entry
  for ``fec_api`` is the documented next step, and it needs an API key plus a registry
  review before use (CLAUDE.md §7 — a source is registered before it is used).
* **Governor.** 2026 has gubernatorial races, but this project has not ingested
  gubernatorial returns: MEDSL splits them across a 2016 state-level file and
  precinct-level per-state files for 2018-2024 rather than publishing one series
  (`docs/dataset-registry.md`). The office is reported as out-of-coverage rather than
  silently omitted.
* **Vacancies and appointments.** A seat whose holder resigned or died carries the last
  *elected* winner; returns cannot show a subsequent appointment.

**Mid-decade redistricting is a live caveat for the House.** ``plan_era`` treats
2022-2030 as one map, but several states have redrawn congressional maps since 2022. A
2026 district keyed to its 2022-era number may not be the same territory. F-008
(redistricting change / crosswalk confidence) is still open, and until it lands the
House rows carry ``boundary_confidence = "unverified"``.
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from ..models.baseline.house import NON_VOTING_JURISDICTIONS, VOTING_SEATS
from .incumbency import TERM_YEARS, plan_era

CYCLE_TABLE_COLUMNS = [
    "cycle",
    "election_date",
    "office",
    "jurisdiction",
    "election_type",
    "seats",
    "coverage",
    "notes",
]

UNIVERSE_COLUMNS = [
    "race_key",
    "cycle",
    "election_date",
    "office",
    "election_type",
    "state_po",
    "district_num",
    "geography_id",
    "last_contested_cycle",
    "incumbent_name",
    "incumbent_party",
    "incumbent_status",
    "prior_dem_share",
    "prior_source",
    "incumbent_source",
    "boundary_confidence",
]


def election_day(year: int) -> date:
    """U.S. federal general election day: the first Tuesday after the first Monday in November."""
    d = date(year, 11, 1)
    # Advance to the first Monday, then take the next day.
    d += timedelta(days=(0 - d.weekday()) % 7)
    return d + timedelta(days=1)


def senate_states_up(returns: pd.DataFrame, cycle: int) -> list[str]:
    """States whose regular Senate seat is contested in ``cycle``.

    Derived from the six-year term: the class up now is the class last elected in
    ``cycle - 6``. Special elections are excluded — they are off-schedule and fill the
    remainder of another class's term, so counting them would double-count a state.
    """
    term = TERM_YEARS["us_senate"]
    sen = returns[(returns["office"] == "us_senate") & (returns["cycle"] == cycle - term)]
    if "special" in sen.columns:
        sen = sen[~sen["special"].fillna(False)]
    return sorted(sen["state_po"].dropna().unique().tolist())


# A runoff supersedes the general election it follows, so it outranks it when deciding
# who actually won the seat.
_DECISIVE_RANK = {"gen": 0, "general": 0, "runoff": 1, "gen runoff": 1}


def _regular_winners(returns: pd.DataFrame, office: str) -> pd.DataFrame:
    """Winner of every regular contest for ``office``, keyed by seat and election cycle.

    Runoff states make "who won" more than a max-votes lookup. Georgia's 2020 Senate
    race went to a January 2021 runoff, which MEDSL files as a separate contest in cycle
    **2021** — so reading the November general alone names Perdue, who led that round but
    lost the seat to Ossoff. Georgia's 2022 runoff instead sits in the same cycle as its
    general. Both are handled by folding a runoff back onto the even-numbered election
    year it decides and letting it outrank the general.
    """
    df = returns[returns["office"] == office].copy()
    if "special" in df.columns:
        df = df[~df["special"].fillna(False)]

    stage = df["stage"].astype(str).str.strip().str.lower()
    df["decisive_rank"] = stage.map(_DECISIVE_RANK).fillna(0).astype(int)
    # An odd-year contest is a runoff deciding the previous even-year election.
    df["election_cycle"] = df["cycle"].where(df["cycle"] % 2 == 0, df["cycle"] - 1)

    return (
        df.sort_values(["decisive_rank", "candidatevotes"], ascending=[False, False], na_position="last")
        .groupby(["geography_id", "election_cycle"], as_index=False)
        .first()[
            ["geography_id", "election_cycle", "candidate", "party_simplified", "state_po", "district_num"]
        ]
        .rename(columns={"election_cycle": "cycle"})
    )


def _seat_holder(returns: pd.DataFrame, office: str, cycle: int) -> pd.DataFrame:
    """Who currently holds each seat that is up in ``cycle``.

    The holder is the winner **exactly one term ago**, not the most recent winner in the
    same geography. For the Senate those differ and the distinction is the whole point:
    a state's two seats share one ``geography_id``, so "most recent" returns the *other*
    class — it would name Alaska's 2026 incumbent as Murkowski (Class III, elected 2022)
    rather than the Class II holder elected in 2020. This is the same six-year rule
    :mod:`.incumbency` uses.

    A seat whose defining contest is missing (a quarantined district, say) falls back to
    the most recent earlier regular winner, flagged in ``incumbent_source`` so a
    stale-but-plausible name is never mistaken for a confirmed one.
    """
    term = TERM_YEARS[office]
    winners = _regular_winners(returns, office)

    exact = winners[winners["cycle"] == cycle - term].copy()
    exact["incumbent_source"] = f"regular_winner_{cycle - term}"

    earlier = winners[winners["cycle"] < cycle - term].sort_values("cycle")
    fallback = earlier.groupby("geography_id", as_index=False).last()
    fallback = fallback[~fallback["geography_id"].isin(set(exact["geography_id"]))].copy()
    fallback["incumbent_source"] = "earlier_regular_winner_fallback"

    out = pd.concat([exact, fallback], ignore_index=True)
    return out.rename(
        columns={
            "cycle": "last_contested_cycle",
            "candidate": "incumbent_name",
            "party_simplified": "incumbent_party",
        }
    )


def build_cycle_table(cycles: list[int], returns: pd.DataFrame) -> pd.DataFrame:
    """Canonical cycle x office table: dates, jurisdictions, and coverage (P0-001)."""
    rows = []
    for cycle in cycles:
        day = election_day(cycle)
        presidential = cycle % 4 == 0
        rows.append(
            {
                "cycle": cycle,
                "election_date": day,
                "office": "us_house",
                "jurisdiction": "nation",
                "election_type": "regular",
                "seats": VOTING_SEATS,
                "coverage": "covered",
                "notes": "All voting seats contested every even year; non-voting delegates excluded.",
            }
        )
        states = senate_states_up(returns, cycle)
        rows.append(
            {
                "cycle": cycle,
                "election_date": day,
                "office": "us_senate",
                "jurisdiction": "nation",
                "election_type": "regular",
                "seats": len(states),
                "coverage": "covered" if states else "no_prior_class_data",
                "notes": f"Class derived from regular races in {cycle - TERM_YEARS['us_senate']}. "
                "Specials are not predictable from returns and are excluded.",
            }
        )
        rows.append(
            {
                "cycle": cycle,
                "election_date": day,
                "office": "president",
                "jurisdiction": "nation",
                "election_type": "regular" if presidential else "not_held",
                "seats": 1 if presidential else 0,
                "coverage": "covered" if presidential else "not_held",
                "notes": "Presidential elections occur in years divisible by four.",
            }
        )
        rows.append(
            {
                "cycle": cycle,
                "election_date": day,
                "office": "governor",
                "jurisdiction": "states",
                "election_type": "regular",
                "seats": pd.NA,
                "coverage": "out_of_coverage",
                "notes": "Gubernatorial returns are not ingested: MEDSL splits them across "
                "a 2016 state-level file and 2018-2024 precinct-level per-state files rather "
                "than one series, so the seat count cannot be derived (backlog P1-003).",
            }
        )
    return pd.DataFrame(rows, columns=CYCLE_TABLE_COLUMNS)


def build_race_universe(
    returns: pd.DataFrame,
    race_table: pd.DataFrame,
    *,
    cycle: int,
    seat_universe: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, dict]:
    """One row per federal seat on the ballot in ``cycle``, with its current holder.

    ``seat_universe`` is the House chamber built by ``models.baseline.house`` — passing
    it keeps the forecast and the race universe on the same 435 seats rather than two
    independently derived lists that can silently disagree.
    """
    day = election_day(cycle)
    rows = []

    # ---- House: the full current-era chamber -----------------------------
    seat_cols = ["geography_id", "state_po", "district_num"]
    if seat_universe is not None and len(seat_universe):
        seats = seat_universe[seat_cols].copy()
    elif {"office", "cycle", "state_po"}.issubset(race_table.columns) and len(race_table):
        era = plan_era(cycle)
        era_rows = race_table[
            (race_table["office"] == "us_house")
            & (race_table["cycle"].map(plan_era) == era)
            & (~race_table["state_po"].isin(NON_VOTING_JURISDICTIONS))
        ]
        seats = era_rows[seat_cols].drop_duplicates("geography_id")
    else:
        # No chamber roster available (no race table, no prebuilt universe). Report a
        # Senate-only universe rather than raising: the caller can still see coverage.
        seats = pd.DataFrame(columns=seat_cols)

    if len(seats):
        house_winners = _seat_holder(returns, "us_house", cycle)
        house = seats.merge(
            house_winners.drop(columns=["state_po", "district_num"]), on="geography_id", how="left"
        )
        house["office"] = "us_house"
        house["boundary_confidence"] = "unverified"  # mid-decade redraws; F-008 open
        rows.append(house)

    # ---- Senate: the class whose term expires ----------------------------
    states = senate_states_up(returns, cycle)
    senate_winners = _seat_holder(returns, "us_senate", cycle)
    senate = senate_winners[senate_winners["state_po"].isin(states)].copy()
    senate["office"] = "us_senate"
    senate["boundary_confidence"] = "n/a"  # statewide; no boundary risk
    rows.append(senate)

    universe = pd.concat(rows, ignore_index=True)
    universe["cycle"] = cycle
    universe["election_date"] = day
    universe["election_type"] = "regular"
    # Whether the holder actually runs is a candidate-level fact no returns file has.
    universe["incumbent_status"] = "unknown"

    # Attach the seat's most recent two-party share as a starting prior. A seat with no
    # usable prior keeps its row — the seat exists either way — and is counted in
    # ``prior_known`` so the gap is visible.
    if {"cycle", "geography_id", "two_party_dem_share"}.issubset(race_table.columns):
        prior = (
            race_table[race_table["cycle"] < cycle]
            .dropna(subset=["two_party_dem_share"])
            .sort_values("cycle")
            .groupby("geography_id")
            .last()[["two_party_dem_share", "cycle"]]
            .rename(columns={"two_party_dem_share": "prior_dem_share", "cycle": "prior_cycle"})
        )
        universe = universe.merge(prior, on="geography_id", how="left")
    else:
        universe["prior_dem_share"] = pd.NA
        universe["prior_cycle"] = pd.NA
    universe["prior_source"] = universe["prior_cycle"].map(
        lambda c: f"last_result_{int(c)}" if pd.notna(c) else "none"
    )
    universe["race_key"] = [
        f"{cycle}_{o}_{s}".lower() + (f"_{int(d):02d}" if pd.notna(d) and o == "us_house" else "")
        for o, s, d in zip(universe["office"], universe["state_po"], universe["district_num"], strict=True)
    ]

    universe = universe.reindex(columns=UNIVERSE_COLUMNS).sort_values(
        ["office", "state_po", "district_num"], na_position="first"
    )

    counts = universe["office"].value_counts().to_dict()
    coverage = {
        "cycle": cycle,
        "election_date": day.isoformat(),
        "seats_total": int(len(universe)),
        "by_office": counts,
        "house_complete": bool(counts.get("us_house", 0) == VOTING_SEATS),
        "senate_states": len(states),
        "incumbent_known": int(universe["incumbent_name"].notna().sum()),
        "incumbent_by_source": universe["incumbent_source"].value_counts(dropna=False).to_dict(),
        "prior_known": int(universe["prior_dem_share"].notna().sum()),
        # Seats whose holder could not be assigned a major party. MEDSL leaves the party
        # field null for some contests entirely (Wyoming's 2020 Senate race, for one), so
        # this is a source gap that P0-003's candidate/party crosswalk would close. It is
        # counted rather than hidden, because an unresolved party silently becomes a
        # third-party seat in any downstream count.
        "party_unresolved": int((universe["incumbent_party"] == "OTHER").sum()),
        # Stated so a consumer cannot mistake this for a candidate list.
        "not_derivable": [
            "candidate filings / who is actually running (needs fec_api — registered, key required)",
            "retirements, primary outcomes, party switches",
            "appointed incumbents filling a vacancy",
            "governor (returns not ingested; MEDSL splits them by year and geography level)",
            "special elections (off-schedule by definition)",
            "post-2022 mid-decade redistricting (F-008 open)",
        ],
    }
    return universe.reset_index(drop=True), coverage

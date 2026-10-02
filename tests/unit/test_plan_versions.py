"""Plan-version register (RD-001): what the register must refuse, and what it must not confuse.

The first test is the Missouri coverage check, because Missouri is the error this register
exists to prevent: a state that enacted a map, is enjoined from using it, and votes its old
map anyway. Both the naive "it redrew, discard the prior" reading and the naive "close the
old plan's range" edit get it wrong, in opposite directions.
"""

from __future__ import annotations

import pandas as pd
import pytest

from election_prediction.features import plan_versions as pv

BASE = {
    "state_po": "MO",
    "plan_id": "MO_2022",
    "first_cycle": "2022",
    "last_cycle": "",
    "authority": "legislature",
    "enacted_on": "2022-05-18",
    "status": "in_effect",
    "litigation_risk": "active",
    "litigation_risk_status": "researched_secondary",
    "litigation_source_url": "https://redistricting.lls.edu/state/missouri/",
    "litigation_retrieved_on": "2026-10-01",
    "source_url": "https://www.sos.mo.gov/example",
    "baf_url": "",
    "retrieved_on": "2026-09-30",
    "verified_by": "AO",
    "notes": "8 districts.",
}


def _register(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame([{**BASE, **r} for r in rows])[pv.REGISTER_COLUMNS]
    for col in ("first_cycle", "last_cycle"):
        df[col] = pd.to_numeric(df[col].replace("", pd.NA), errors="coerce").astype("Int64")
    return df


# --------------------------------------------------------------------------------------
# 1. The Missouri check
# --------------------------------------------------------------------------------------
def test_state_with_no_governing_plan_for_a_cycle_is_rejected():
    """Closing MO_2022 at 2024 leaves 2026 to an enjoined map. That must not validate."""
    reg = _register(
        [
            {"plan_id": "MO_2022", "first_cycle": "2022", "last_cycle": "2024"},
            {"plan_id": "MO_2025", "first_cycle": "", "last_cycle": "", "status": "enjoined"},
        ]
    )
    with pytest.raises(pv.PlanRegisterError, match=r"MO has 0 .*plan\(s\) for cycle 2026"):
        pv.validate_plan_versions(reg, cycles=[2026])


def test_missouri_territory_is_unchanged_even_though_litigation_is_active():
    """The split's whole purpose: an enjoined new map does not move the old map's territory."""
    reg = _register(
        [
            {"plan_id": "MO_2022", "first_cycle": "2022", "last_cycle": ""},
            {"plan_id": "MO_2025", "first_cycle": "", "last_cycle": "", "status": "enjoined"},
        ]
    )
    plans = pv.PlanVersions(reg)
    assert plans.plan_id("MO", 2026) == "MO_2022"
    assert plans.boundary_confidence("MO", 2026) == pv.BOUNDARY_UNCHANGED
    assert plans.litigation_risk("MO", 2026) == pv.LITIGATION_ACTIVE


def test_litigation_risk_never_changes_boundary_confidence():
    """Flip only the litigation flag; territory must not move."""
    quiet = _register([{"plan_id": "MO_2022", "litigation_risk": "none"}])
    loud = _register([{"plan_id": "MO_2022", "litigation_risk": "active"}])
    assert pv.PlanVersions(quiet).boundary_confidence("MO", 2026) == pv.PlanVersions(
        loud
    ).boundary_confidence("MO", 2026)


# --------------------------------------------------------------------------------------
# 2. Lookup and fallback
# --------------------------------------------------------------------------------------
def test_state_absent_from_register_falls_back_to_the_decennial_default():
    plans = pv.PlanVersions(_register([{}]))
    assert plans.plan_id("GA", 2026) == pv.decennial_plan_id("GA", 2026)
    assert plans.boundary_confidence("GA", 2026) == pv.BOUNDARY_UNCHANGED


def test_decennial_default_changes_only_across_a_decennial_boundary():
    assert pv.decennial_plan_id("GA", 2024) == pv.decennial_plan_id("GA", 2022)
    assert pv.decennial_plan_id("GA", 2022) != pv.decennial_plan_id("GA", 2020)


def test_a_new_plan_marks_the_seat_redrawn():
    reg = _register(
        [
            {"state_po": "TX", "plan_id": "TX_2021", "first_cycle": "2022", "last_cycle": "2024",
             "status": "superseded", "litigation_risk": "none"},
            {"state_po": "TX", "plan_id": "TX_2025", "first_cycle": "2026", "last_cycle": "",
             "litigation_risk": "none"},
        ]
    )
    plans = pv.PlanVersions(reg)
    assert plans.boundary_confidence("TX", 2026) == pv.BOUNDARY_REDRAWN
    assert plans.boundary_confidence("TX", 2024) == pv.BOUNDARY_UNCHANGED


def test_superseded_plans_still_govern_their_own_cycles():
    """`status` is standing today; the cycle range is which elections a plan actually ran."""
    reg = _register(
        [
            {"state_po": "TX", "plan_id": "TX_2021", "first_cycle": "2022", "last_cycle": "2024",
             "status": "superseded", "litigation_risk": "none"},
            {"state_po": "TX", "plan_id": "TX_2025", "first_cycle": "2026", "last_cycle": "",
             "litigation_risk": "none"},
        ]
    )
    assert pv.PlanVersions(reg).plan_id("TX", 2024) == "TX_2021"
    pv.validate_plan_versions(reg, cycles=[2022, 2024, 2026])


def test_history_can_be_pinned_to_the_decennial_default():
    """The escape hatch that let the register land in two attributable commits."""
    reg = _register(
        [
            {"state_po": "AL", "plan_id": "AL_2021", "first_cycle": "2022", "last_cycle": "2022",
             "status": "superseded", "litigation_risk": "none"},
            {"state_po": "AL", "plan_id": "AL_2023", "first_cycle": "2024", "last_cycle": "",
             "status": "superseded", "litigation_risk": "none"},
        ]
    )
    assert pv.PlanVersions(reg, apply_to_history=True).plan_id("AL", 2024) == "AL_2023"
    pinned = pv.PlanVersions(reg, apply_to_history=False)
    assert pinned.plan_id("AL", 2024) == pv.decennial_plan_id("AL", 2024)
    assert pinned.boundary_confidence("AL", 2024) == pv.BOUNDARY_UNCHANGED


# --------------------------------------------------------------------------------------
# 3. What the validator must refuse
# --------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("verified_by", "", "empty verified_by"),
        ("source_url", "", "empty source_url"),
        ("retrieved_on", "", "empty retrieved_on"),
        ("status", "probably", "unknown status"),
        ("litigation_risk", "maybe", "unknown litigation_risk"),
        ("source_url", "sos.mo.gov/x", "not a URL"),
    ],
)
def test_validator_refuses_unusable_rows(field, value, match):
    with pytest.raises(pv.PlanRegisterError, match=match):
        pv.validate_plan_versions(_register([{field: value}]))


def test_validator_refuses_overlapping_cycle_ranges():
    reg = _register(
        [
            {"plan_id": "MO_A", "first_cycle": "2022", "last_cycle": "2026"},
            {"plan_id": "MO_B", "first_cycle": "2024", "last_cycle": ""},
        ]
    )
    with pytest.raises(pv.PlanRegisterError, match="overlap"):
        pv.validate_plan_versions(reg)


def test_validator_refuses_an_enjoined_plan_that_claims_cycles():
    reg = _register([{"plan_id": "MO_2025", "status": "enjoined", "first_cycle": "2026"}])
    with pytest.raises(pv.PlanRegisterError, match="enjoined"):
        pv.validate_plan_versions(reg)


def test_validator_refuses_two_plans_governing_one_cycle():
    reg = _register(
        [
            {"plan_id": "MO_A", "first_cycle": "2022", "last_cycle": "2026"},
            {"plan_id": "MO_B", "first_cycle": "2026", "last_cycle": ""},
        ]
    )
    with pytest.raises(pv.PlanRegisterError):
        pv.validate_plan_versions(reg, cycles=[2026])


# --------------------------------------------------------------------------------------
# 4. Annotation
# --------------------------------------------------------------------------------------
def test_annotate_attaches_all_three_fields_and_leaves_the_frame_otherwise_intact():
    reg = _register(
        [
            {"plan_id": "MO_2022", "first_cycle": "2022", "last_cycle": ""},
            {"state_po": "TX", "plan_id": "TX_2021", "first_cycle": "2022", "last_cycle": "2024",
             "status": "superseded", "litigation_risk": "none"},
            {"state_po": "TX", "plan_id": "TX_2025", "first_cycle": "2026", "last_cycle": "",
             "litigation_risk": "none"},
        ]
    )
    seats = pd.DataFrame({"geography_id": ["a", "b", "c"], "state_po": ["MO", "TX", "GA"]})
    out = pv.PlanVersions(reg).annotate(seats, cycle=2026)
    assert list(out["boundary_confidence"]) == ["unchanged", "redrawn", "unchanged"]
    assert list(out["litigation_risk"]) == ["active", "none", "none"]
    assert list(out["geography_id"]) == ["a", "b", "c"]


def test_annotate_on_an_empty_frame_still_returns_the_columns():
    out = pv.PlanVersions(_register([{}])).annotate(
        pd.DataFrame(columns=["geography_id", "state_po"]), cycle=2026
    )
    assert {"plan_id", "boundary_confidence", "litigation_risk"} <= set(out.columns)


# --------------------------------------------------------------------------------------
# 5. The committed register itself
# --------------------------------------------------------------------------------------
def test_the_real_register_validates_for_every_cycle_it_covers():
    report = pv.validate_plan_versions(pv.load_register(), cycles=[2022, 2024, 2026])
    assert report["rows"] == 23
    assert report["states"] == 10


def test_the_real_register_reports_the_published_redrawn_count():
    """Nine states, 173 of 435 seats -- the number that appears in the public writing."""
    plans = pv.PlanVersions.load()
    assert plans.redrawn_states(2026) == ["AL", "CA", "FL", "LA", "NC", "OH", "TN", "TX", "UT"]
    assert plans.redrawn_states(2024) == ["AL", "LA", "NC"]


def test_missouri_keeps_its_prior_in_the_real_register():
    plans = pv.PlanVersions.load()
    assert plans.plan_id("MO", 2026) == "MO_2022"
    assert plans.boundary_confidence("MO", 2026) == pv.BOUNDARY_UNCHANGED
    assert plans.litigation_risk("MO", 2026) == pv.LITIGATION_ACTIVE


def test_alabama_2026_is_the_legislative_plan_not_the_remedial_one():
    """AL_2023_LEG is not AL_2023; recording the wrong one would break RD-003's transfer."""
    plans = pv.PlanVersions.load()
    assert plans.plan_id("AL", 2026) == "AL_2023_LEG"
    assert plans.plan_id("AL", 2024) == "AL_2023"
    assert plans.boundary_confidence("AL", 2026) == pv.BOUNDARY_REDRAWN


# --------------------------------------------------------------------------------------
# 6. litigation_risk provenance (open question 9)
# --------------------------------------------------------------------------------------
def test_litigation_values_carry_how_well_they_are_known():
    """Researched against a tracker on 2026-10-01 -- better than our own notes, short of a docket."""
    report = pv.validate_plan_versions(pv.load_register(), cycles=[2026])
    assert report["litigation_risk_by_status"]["researched_secondary"] == 11
    # Every live row is sourced to a tracker and still awaits a docket-level sign-off.
    assert report["litigation_sourced_to_a_tracker_not_a_docket"] == [
        "AL", "CA", "FL", "LA", "MO", "NC", "OH", "TN", "TX", "UT"
    ]


def test_research_corrected_five_states_our_own_notes_had_called_quiet():
    """CA, FL, NC, TX and UT all had pending cases while the register said `none`.

    Each note recorded a *denied injunction* -- which settles which map is in effect, not
    whether the case is over. Reading one as the other understated litigation in five of
    nine states, always in the same direction.
    """
    report = pv.validate_plan_versions(pv.load_register(), cycles=[2026])
    assert set(report["litigation_active"]) >= {"CA", "FL", "NC", "TX", "UT"}
    assert "OH" not in report["litigation_active"]


def test_every_live_litigation_row_cites_where_the_claim_came_from():
    reg = pv.load_register()
    live = reg[reg["litigation_risk_status"] == pv.LITIGATION_RESEARCHED]
    assert live["litigation_source_url"].str.startswith("https://").all()
    assert (live["litigation_retrieved_on"] == "2026-10-01").all()


def test_an_unknown_litigation_status_is_refused():
    reg = _register([{"litigation_risk_status": "probably fine"}])
    with pytest.raises(pv.PlanRegisterError, match="unknown litigation_risk_status"):
        pv.validate_plan_versions(reg)


def test_a_blank_litigation_status_reads_unverified_rather_than_verified(tmp_path):
    """Silence must never be read as a clean bill of health."""
    src = tmp_path / "reg.csv"
    header = ",".join(pv.REGISTER_COLUMNS)
    row = {c: "" for c in pv.REGISTER_COLUMNS}
    row.update(
        state_po="MO", plan_id="MO_2022", first_cycle="2022", authority="legislature",
        enacted_on="2022-05-18", status="in_effect", source_url="https://example.gov",
        retrieved_on="2026-09-30", verified_by="AO",
    )
    src.write_text(header + "\n" + ",".join(row[c] for c in pv.REGISTER_COLUMNS) + "\n")
    loaded = pv.load_register(src)
    assert loaded["litigation_risk_status"].iloc[0] == pv.LITIGATION_UNVERIFIED


def test_litigation_status_never_affects_the_boundary_judgement():
    verified = _register([{"litigation_risk": "active", "litigation_risk_status": "verified"}])
    derived = _register([{"litigation_risk": "active", "litigation_risk_status": "researched_secondary"}])
    assert pv.PlanVersions(verified).boundary_confidence("MO", 2026) == pv.PlanVersions(
        derived
    ).boundary_confidence("MO", 2026)

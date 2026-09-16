"""National-environment estimator contract (NE-001)."""

from __future__ import annotations

import json

import pandas as pd
import pytest

from election_prediction.data import special_elections as se
from election_prediction.models.baseline import national_environment as ne

_EST = {
    "status": "ok",
    "n": 8,
    "mean_overperformance": 0.1877,
    "std_error": 0.022,
    "date_range": ["2025-03-01", "2026-06-30"],
    "caveats": ["Specials are a non-random sample of seats; they occur where a vacancy happened."],
}


def test_specials_produce_a_band_not_a_point():
    out = ne.from_specials(_EST, baseline_national_dem_share=0.4922)
    assert out.status == "band"
    assert out.national_dem_share is None
    assert out.identified is False
    assert len(out.band) == len(se.SHRINKAGE_SENSITIVITY)
    assert out.band["national_dem_share"].is_monotonic_increasing


def test_every_band_row_carries_the_assumption_that_generated_it():
    out = ne.from_specials(_EST, baseline_national_dem_share=0.4922)
    assert out.band["assumption"].tolist() == [f"shrinkage={f:g}" for f in se.SHRINKAGE_SENSITIVITY]
    ne.validate(out)  # and the validator agrees


def test_a_specials_estimate_can_never_claim_to_be_identified():
    """The field that does the work: a validator fails the build, not a flag a caller can skip."""
    out = ne.from_specials(_EST, baseline_national_dem_share=0.4922)
    out.identified = True
    with pytest.raises(ne.ContractError, match="unidentified by construction"):
        ne.validate(out)


def test_a_band_row_without_an_assumption_is_rejected():
    out = ne.from_specials(_EST, baseline_national_dem_share=0.4922)
    out.band.loc[0, "assumption"] = ""
    with pytest.raises(ne.ContractError, match="assumption"):
        ne.validate(out)


def test_a_projection_cannot_start_from_an_unidentified_point():
    """The plan's acceptance criterion, stated as a test."""
    bare = ne.NationalEnvironment(
        estimator="generic_ballot",
        status="point",
        national_dem_share=0.52,
        band=None,
        identified=False,
        assumptions=["house effects not estimated"],
    )
    with pytest.raises(ne.ContractError, match="unidentified point"):
        ne.projectable(bare)


def test_a_projection_may_start_from_a_band_an_identified_point_or_a_scenario():
    band = ne.from_specials(_EST, baseline_national_dem_share=0.4922)
    assert len(ne.projectable(band)) == len(se.SHRINKAGE_SENSITIVITY)

    point = ne.NationalEnvironment(
        estimator="generic_ballot", status="point", national_dem_share=0.52, band=None, identified=True
    )
    rows = ne.projectable(point)
    assert rows["national_dem_share"].tolist() == [0.52]

    what_if = ne.scenario(0.50, label="tied national environment")
    rows = ne.projectable(what_if)
    assert rows["assumption"].tolist() == ["scenario: tied national environment"]
    assert what_if.identified is False


def test_a_scenario_cannot_claim_to_be_identified_either():
    what_if = ne.scenario(0.50, label="tied")
    what_if.identified = True
    with pytest.raises(ne.ContractError):
        ne.validate(what_if)


def test_an_insufficient_specials_estimate_is_unavailable_and_not_projectable():
    out = ne.from_specials(
        {"status": "insufficient_data", "n": 3, "reason": "too few"}, baseline_national_dem_share=0.49
    )
    assert out.status == "unavailable"
    with pytest.raises(ne.ContractError, match="unavailable"):
        ne.projectable(out)


def test_the_contract_is_json_serialisable():
    out = ne.from_specials(_EST, baseline_national_dem_share=0.4922, snapshot_date="2026-09-15")
    payload = json.loads(json.dumps(out.to_dict()))
    assert payload["estimator"] == "specials_band"
    assert payload["provenance"]["snapshot_date"] == "2026-09-15"
    assert payload["band"][0]["assumption"] == "shrinkage=0.25"


def test_malformed_estimates_are_refused():
    with pytest.raises(ne.ContractError, match="unknown estimator"):
        ne.validate(ne.NationalEnvironment("vibes", "point", 0.5, None, True))
    with pytest.raises(ne.ContractError, match="no single national_dem_share"):
        ne.validate(ne.NationalEnvironment("specials_band", "band", 0.5, pd.DataFrame(), False))
    with pytest.raises(ne.ContractError, match="requires national_dem_share"):
        ne.validate(ne.NationalEnvironment("generic_ballot", "point", None, None, True))


# ---- band-level conclusions -----------------------------------------------------------


def _band(ps: list[float]) -> pd.DataFrame:
    return pd.DataFrame({"assumption": [f"shrinkage={i}" for i in range(len(ps))], "p": ps})


def test_a_conclusion_that_holds_across_the_band_is_stated_as_such():
    text = ne.control_conclusion(_band([0.52, 0.62, 0.79]), chamber="House", p_column="p")
    assert text.startswith("House: Democrats favored at every assumption")
    text = ne.control_conclusion(_band([0.27, 0.36, 0.45]), chamber="Senate", p_column="p")
    assert text.startswith("Senate: Republicans favored at every assumption")


def test_a_flip_inside_the_band_is_named_as_the_falsifier():
    text = ne.control_conclusion(_band([0.27, 0.45, 0.55]), chamber="Senate", p_column="p")
    assert "depends on the assumption" in text
    assert "shrinkage=2" in text
    assert "cannot resolve this chamber" in text

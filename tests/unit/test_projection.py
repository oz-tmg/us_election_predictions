"""Forward projection of a live cycle (2026) from fitted baselines."""

from __future__ import annotations

import pandas as pd
import pytest

from election_prediction.features import filings
from election_prediction.models.baseline import projection
from election_prediction.models.baseline.presidential import OLSModel


def _fitted_house_model() -> OLSModel:
    train = pd.DataFrame(
        {
            "district_lean": [-0.2, -0.1, 0.0, 0.1, 0.2, 0.05],
            "national_dem_share": [0.49, 0.50, 0.51, 0.52, 0.53, 0.50],
            "incumbent_dem": [0.0, 1.0, 0.0, 1.0, 0.0, 1.0],
            "incumbent_rep": [1.0, 0.0, 1.0, 0.0, 1.0, 0.0],
            "two_party_dem_share": [0.30, 0.42, 0.50, 0.62, 0.70, 0.55],
        }
    )
    return OLSModel(
        features=list(
            projection.__dict__.get("_", [])
            or ["district_lean", "national_dem_share", "incumbent_dem", "incumbent_rep"]
        )
    ).fit(train)


def _roster(boundary: str = "unchanged") -> pd.DataFrame:
    return pd.DataFrame(
        {
            "office": ["us_house", "us_house", "us_house", "us_senate"],
            "state_po": ["GA", "GA", "DC", "WY"],
            "district_num": [1.0, 2.0, 0.0, None],
            "geography_id": ["g1", "g2", "gdc", "swy"],
            "incumbent_party": ["DEMOCRAT", "REPUBLICAN", "DEMOCRAT", "OTHER"],
            "incumbent_name": ["A", "B", "C", "CYNTHIA M. LUMMIS"],
            "prior_dem_share": [0.55, 0.45, 0.90, 0.24],
            "boundary_confidence": [boundary, boundary, boundary, "n/a"],
        }
    )


_PRES_REF = pd.DataFrame({"state_po": ["GA"], "state_pres_lean": [-0.02]})


def test_non_voting_delegates_are_excluded_from_the_projected_chamber():
    """DC elects a Delegate; counting it would put 436 seats in a 435-seat House."""
    out, cov = projection.project_house(
        _roster(), _fitted_house_model(), national_dem_share=0.52, lagged_national_dem_share=0.49
    )
    assert set(out["state_po"]) == {"GA"}
    assert cov["seats_in_roster"] == 2


def test_a_stronger_national_environment_moves_every_district_up():
    model = _fitted_house_model()
    low, _ = projection.project_house(
        _roster(), model, national_dem_share=0.49, lagged_national_dem_share=0.49
    )
    high, _ = projection.project_house(
        _roster(), model, national_dem_share=0.55, lagged_national_dem_share=0.49
    )
    assert (high["mean_dem_share"].to_numpy() > low["mean_dem_share"].to_numpy()).all()


def test_an_unlabelled_incumbent_is_an_open_seat_without_a_resolved_party():
    """Wyoming's 2020 returns carry a null party, so Lummis reads OTHER.

    With nothing to resolve her against, both indicators go to zero and the seat trains as
    open -- which is wrong, and is exactly the defect P0-003 exists to fix. The test pins
    the un-fixed behaviour so the fix below is demonstrably doing the work.
    """
    terms = projection._incumbency_terms(_roster())
    lummis = terms[terms["state_po"] == "WY"].iloc[0]
    assert lummis["incumbent_rep"] == 0.0
    assert lummis["incumbent_dem"] == 0.0


def _resolved_roster(fec_parties: list[str]) -> pd.DataFrame:
    """A roster carrying the resolved column, built the way the pipeline builds it.

    Deliberately routed through ``filings.resolve_incumbent_status`` rather than assigning
    ``RESOLVED_PARTY_COLUMN`` by hand. Hand-assignment is what let the producer and the
    consumer disagree on the column name while every test still passed -- the projection
    silently fell back to the raw ``incumbent_party`` and the Lummis fix never ran.
    """
    roster = _roster()
    roster["incumbent_fec_party"] = fec_parties
    roster["incumbent_party_resolved"] = filings.resolved_incumbent_party(roster)
    return roster


def test_the_filings_producer_and_the_projection_consumer_agree_on_the_column():
    """The seam itself: whatever filings emits must be what the projection reads."""
    out = filings.resolve_incumbent_status(
        pd.DataFrame(
            [
                {
                    "geography_id": "swy",
                    "office": "us_senate",
                    "state_po": "WY",
                    "district_num": None,
                    "election_cycle": 2026,
                    "incumbent_name": "CYNTHIA M. LUMMIS",
                    "incumbent_party": "OTHER",
                }
            ]
        ),
        None,
        cycle=2026,
    )
    assert projection.RESOLVED_PARTY_COLUMN in out.columns
    assert projection.RESOLVED_PARTY_COLUMN in filings.FILING_COLUMNS


def test_a_resolved_party_column_fills_an_unlabelled_incumbent():
    """P0-003: FEC records Lummis as REP, which recovers the incumbency the returns lost."""
    roster = _resolved_roster(["DEM", "REP", "DEM", "REP"])
    terms = projection._incumbency_terms(roster)
    lummis = terms[terms["state_po"] == "WY"].iloc[0]
    assert lummis["incumbent_rep"] == 1.0
    assert lummis["incumbent_dem"] == 0.0


def test_a_resolved_party_never_overwrites_a_party_the_returns_state():
    """The resolved column only fills gaps; a disagreement must not reclassify a seat."""
    # Contradict every stated party. The two seats the returns label must not move.
    roster = _resolved_roster(["REP", "DEM", "REP", "REP"])
    terms = projection._incumbency_terms(roster)
    ga = terms[terms["state_po"] == "GA"].sort_values("district_num")
    assert ga["incumbent_dem"].tolist() == [1.0, 0.0]
    assert ga["incumbent_rep"].tolist() == [0.0, 1.0]


def test_projections_never_claim_verified_incumbency():
    """Every 2026 seat has incumbent_status 'unknown'; primaries are not compiled."""
    out, cov = projection.project_house(
        _roster(), _fitted_house_model(), national_dem_share=0.52, lagged_national_dem_share=0.49
    )
    assert cov["incumbency_verified"] is False
    assert out["incumbency_assumed"].all()


# ---- RD-002: boundary routing -----------------------------------------------------------


def test_unverified_boundaries_are_refused_by_default():
    """The register (RD-001) is not compiled; a caller must opt in and the report must say so."""
    with pytest.raises(projection.UnverifiedBoundaryError):
        projection.project_house(
            _roster("unverified"),
            _fitted_house_model(),
            national_dem_share=0.52,
            lagged_national_dem_share=0.49,
        )


def test_a_roster_without_the_column_is_treated_as_unverified():
    """An old roster cannot slip past the gate by omitting the column."""
    roster = _roster().drop(columns=["boundary_confidence"])
    with pytest.raises(projection.UnverifiedBoundaryError):
        projection.project_house(
            roster, _fitted_house_model(), national_dem_share=0.52, lagged_national_dem_share=0.49
        )


def test_opting_in_projects_unverified_seats_as_unchanged_and_counts_the_assumption():
    model = _fitted_house_model()
    verified, _ = projection.project_house(
        _roster(), model, national_dem_share=0.52, lagged_national_dem_share=0.49
    )
    assumed, cov = projection.project_house(
        _roster("unverified"),
        model,
        national_dem_share=0.52,
        lagged_national_dem_share=0.49,
        allow_unverified=True,
    )
    assert assumed["mean_dem_share"].tolist() == verified["mean_dem_share"].tolist()
    assert set(assumed["source"]) == {"model_unverified"}
    assert cov["boundaries_assumed_unchanged"] == 2


def test_a_redrawn_seat_is_never_projected_from_its_old_number_prior():
    """The plan's acceptance test: whatever a redrawn seat gets, it is not the model on the old prior."""
    model = _fitted_house_model()
    old, _ = projection.project_house(
        _roster(), model, national_dem_share=0.52, lagged_national_dem_share=0.49
    )
    new, cov = projection.project_house(
        _roster("redrawn"),
        model,
        national_dem_share=0.52,
        lagged_national_dem_share=0.49,
        resid_sigma=0.05,
        pres_reference=_PRES_REF,
        fallback_lean_sd=0.15,
    )
    assert set(new["source"]) == {"fallback_state_lean"}
    # The old priors (0.55 / 0.45) describe different territory and must not survive; the
    # only thing still separating the two Georgia seats is their incumbent's party.
    assert not (new["mean_dem_share"].to_numpy() == old["mean_dem_share"].to_numpy()).any()
    # Old-prior spread was 0.10 of lean; after routing, the spread is just the incumbency gap.
    assert abs(new["mean_dem_share"].diff().iloc[-1]) < abs(old["mean_dem_share"].diff().iloc[-1])
    assert cov["redrawn_states"] == ["GA"]
    assert cov["seats_by_source"] == {"fallback_state_lean": 2}


def test_the_fallback_sigma_is_wider_than_the_residual_and_measured_not_invented():
    """sigma = hypot(resid, beta_lean * within-state sd) -- both inputs come from data."""
    model = _fitted_house_model()
    out, cov = projection.project_house(
        _roster("redrawn"),
        model,
        national_dem_share=0.52,
        lagged_national_dem_share=0.49,
        resid_sigma=0.05,
        pres_reference=_PRES_REF,
        fallback_lean_sd=0.15,
    )
    beta = projection._lean_coefficient(model)
    expected = (0.05**2 + (beta * 0.15) ** 2) ** 0.5
    assert out["sigma"].unique().tolist() == pytest.approx([expected])
    assert expected > 0.05
    assert cov["fallback_sigma"] == pytest.approx(expected)


def test_a_redrawn_seat_without_stated_uncertainty_is_an_error_not_a_default():
    with pytest.raises(ValueError, match="fallback_lean_sd"):
        projection.project_house(
            _roster("redrawn"),
            _fitted_house_model(),
            national_dem_share=0.52,
            lagged_national_dem_share=0.49,
            pres_reference=_PRES_REF,
        )


def test_pending_is_no_longer_a_boundary_confidence_value():
    """`pending` conflated moved territory with live litigation; it was split 2026-09-30.

    Missouri is why: it enacted a 2025 map, is enjoined from using it, and votes its 2022
    map in the general. Routing `pending` like `redrawn` discarded eight valid priors.
    """
    assert "pending" not in projection.BOUNDARY_CONFIDENCE_VALUES
    with pytest.raises(ValueError, match="unknown boundary_confidence"):
        projection.project_house(
            _roster("pending"),
            _fitted_house_model(),
            national_dem_share=0.52,
            lagged_national_dem_share=0.49,
            pres_reference=_PRES_REF,
            fallback_lean_sd=0.15,
        )


def test_litigation_risk_is_reported_but_never_changes_routing():
    """Same territory, opposite litigation flags -> identical priors, differing report."""
    quiet, loud = _roster("unchanged"), _roster("unchanged")
    quiet[projection.LITIGATION_RISK_COLUMN] = "none"
    loud[projection.LITIGATION_RISK_COLUMN] = "active"

    kwargs = dict(
        national_dem_share=0.52,
        lagged_national_dem_share=0.49,
        pres_reference=_PRES_REF,
        fallback_lean_sd=0.15,
    )
    out_q, cov_q = projection.project_house(quiet, _fitted_house_model(), **kwargs)
    out_l, cov_l = projection.project_house(loud, _fitted_house_model(), **kwargs)

    pd.testing.assert_frame_equal(
        out_q.drop(columns=[projection.LITIGATION_RISK_COLUMN]),
        out_l.drop(columns=[projection.LITIGATION_RISK_COLUMN]),
    )
    assert cov_q["litigation_active_states"] == []
    # Only the projected voting seats: DC is a delegate and WY is a Senate row.
    assert cov_l["litigation_active_states"] == ["GA"]


def test_a_transferred_prior_is_preferred_over_the_fallback_and_needs_its_own_sigma():
    """The Track C seam: a prior on the new boundaries routes to model_transferred."""
    roster = _roster("redrawn")
    roster[projection.TRANSFERRED_PRIOR_COLUMN] = [0.60, None, None, None]
    with pytest.raises(ValueError, match="transfer_sigma"):
        projection.project_house(
            roster,
            _fitted_house_model(),
            national_dem_share=0.52,
            lagged_national_dem_share=0.49,
            pres_reference=_PRES_REF,
            fallback_lean_sd=0.15,
        )
    out, cov = projection.project_house(
        roster,
        _fitted_house_model(),
        national_dem_share=0.52,
        lagged_national_dem_share=0.49,
        pres_reference=_PRES_REF,
        fallback_lean_sd=0.15,
        transfer_sigma=0.03,
    )
    by_seat = out.set_index("geography_id")["source"]
    assert by_seat["g1"] == "model_transferred"
    assert by_seat["g2"] == "fallback_state_lean"
    assert out.set_index("geography_id").loc["g1", "sigma"] < out.set_index("geography_id").loc["g2", "sigma"]
    assert cov["seats_by_source"] == {"fallback_state_lean": 1, "model_transferred": 1}


def test_an_unknown_confidence_value_is_rejected():
    with pytest.raises(ValueError, match="unknown boundary_confidence"):
        projection.project_house(
            _roster("probably_fine"),
            _fitted_house_model(),
            national_dem_share=0.52,
            lagged_national_dem_share=0.49,
        )


def test_uniform_swing_is_additive_and_separate_from_the_senate_model():
    train = pd.DataFrame(
        {
            "state_pres_lean": [-0.2, -0.1, 0.0, 0.1, 0.2, 0.05],
            "incumbent_dem": [0.0, 1.0, 0.0, 1.0, 0.0, 1.0],
            "incumbent_rep": [1.0, 0.0, 1.0, 0.0, 1.0, 0.0],
            "midterm_penalty": [1.0, 1.0, 0.0, 0.0, -1.0, 1.0],
            "two_party_dem_share": [0.30, 0.42, 0.50, 0.62, 0.70, 0.55],
        }
    )
    model = OLSModel(features=["state_pres_lean", "incumbent_dem", "incumbent_rep", "midterm_penalty"]).fit(
        train
    )
    ref = pd.DataFrame({"state_po": ["WY"], "state_pres_lean": [-0.25]})
    flat, _ = projection.project_senate(_roster(), model, ref, midterm_penalty=1.0)
    swung, cov = projection.project_senate(_roster(), model, ref, midterm_penalty=1.0, uniform_swing=0.03)
    assert swung.iloc[0]["mean_dem_share"] == pytest.approx(flat.iloc[0]["mean_dem_share"] + 0.03)
    assert cov["uniform_swing"] == 0.03

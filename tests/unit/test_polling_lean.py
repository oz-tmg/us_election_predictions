"""Synthetic-only tests for lean bias, chronological leakage and shared uncertainty."""

from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from election_prediction.data import polling_archive
from election_prediction.polling import lean


@pytest.fixture
def design():
    return lean.Design(bootstrap_draws=20, n_sims=300)


def _polls(cycles=range(2000, 2016, 2)):
    rows = []
    for cycle in cycles:
        election = polling_archive._november_general(cycle)
        for i, value in enumerate(np.linspace(-0.2, 0.2, 16)):
            actual = 0.5 + value * 0.5
            for j in range(2):
                rows.append(
                    {
                        "question_id": f"q-{cycle}-{i}-{j}",
                        "poll_id": f"p-{cycle}-{i}-{j}",
                        "race_id": f"r-{cycle}-{i}",
                        "cycle": cycle,
                        "office": "us_senate",
                        "state_po": ["OH", "VA", "TX", "MA"][i % 4],
                        "poll_date": election - pd.Timedelta(days=10 + j),
                        "election_date": election,
                        "pollster": f"Pollster {i % 2}",
                        "sponsor_partisan": "NONE",
                        "mode": "phone",
                        "sample_size": 900,
                        "poll_dem_share": actual - 0.16 * value + 0.002 * j,
                        "actual_dem_share": actual,
                        "actual_dem_win": int(actual > 0.5),
                        "lean": value,
                        "lean_reference_cycle": cycle - 4,
                        "pred_dem_share": actual,
                        "resid_sigma": 0.06,
                        "train_through": cycle - 2,
                        "lean_basis": "lagged_presidential_state",
                        **dict.fromkeys(lean.GATES, False),
                    }
                )
    return pd.DataFrame(rows)


def test_slope_units_direction_and_cycle_intercepts(design):
    races, _ = lean.aggregate_races(_polls(), design)
    fit = lean.fit_slope(races, prediction_column="poll_mean", design=design)
    assert fit["status"] == "estimated_research_only"
    assert fit["slope"] == pytest.approx(0.16, abs=0.001)
    shifted = races.copy()
    shifted["actual_dem_share"] += (shifted.cycle - shifted.cycle.min()) * 0.002
    shifted_fit = lean.fit_slope(shifted, prediction_column="poll_mean", design=design)
    assert shifted_fit["slope"] == pytest.approx(fit["slope"])
    assert len(fit["slope_draws"]) == design.bootstrap_draws


def test_residual_correction_is_fitted_after_blending(design):
    races, _ = lean.aggregate_races(_polls(), design)
    raw = lean.fit_slope(races, prediction_column="poll_mean", design=design)
    blended = lean.fit_slope(races, prediction_column="blend_mean", design=design)
    assert 0 < blended["slope"] < raw["slope"]
    assert blended["slope"] == pytest.approx(raw["slope"] * races.poll_weight.mean(), abs=0.001)


def test_pollster_composition_is_not_mislabeled_as_lean_bias(design):
    races, _ = lean.aggregate_races(_polls(), design)
    biased_firm = races.lean.gt(-0.05).astype(float)
    races["control:pollster_left"] = 1 - biased_firm
    races["control:pollster_right"] = biased_firm
    races["poll_mean"] = races.actual_dem_share + 0.08 * (biased_firm - 0.5)
    result = lean.fit_slope(races, prediction_column="poll_mean", design=design)
    assert result["slope"] == pytest.approx(0, abs=0.001)
    with pytest.raises(ValueError, match="one aggregated row"):
        lean.fit_slope(pd.concat([races, races.iloc[[0]]]), prediction_column="poll_mean", design=design)


@pytest.mark.parametrize(
    "column,value",
    [
        ("lean_reference_cycle", 2000),
        ("train_through", 2000),
        ("poll_dem_share", 51),
        ("lean", float("inf")),
        ("sample_size", 0),
        ("publication_verified", "False"),
        ("office", "governor"),
        ("actual_dem_win", 2),
        ("poll_date", None),
    ],
)
def test_invalid_or_leaking_inputs_fail_closed(column, value):
    polls = _polls([2000])
    polls[column] = value
    with pytest.raises(ValueError):
        lean.validate_panel(polls)


def test_duplicate_question_and_conflicting_race_refused():
    polls = _polls([2000])
    with pytest.raises(ValueError, match="duplicate"):
        lean.validate_panel(pd.concat([polls, polls.iloc[[0]]]))
    polls.loc[0, "actual_dem_share"] += 0.01
    with pytest.raises(ValueError, match="conflicting"):
        lean.validate_panel(polls)


def test_repeated_questions_do_not_gain_poll_weight_or_precision(design):
    polls = _polls([2000])
    baseline, _ = lean.aggregate_races(polls, design)
    duplicate = polls.iloc[[0]].copy()
    duplicate["question_id"] = "alternate-question-same-survey"
    changed, _ = lean.aggregate_races(pd.concat([polls, duplicate], ignore_index=True), design)
    for column in ("poll_mean", "poll_sigma", "poll_weight"):
        np.testing.assert_allclose(changed[column], baseline[column])
    assert changed.n_polls.tolist() == baseline.n_polls.tolist()


def test_horizon_and_known_publication_field_end_are_enforced(design):
    polls = _polls([2000])
    polls["published_on"] = polls.poll_date
    polls["field_end"] = polls.poll_date
    polls.loc[0, "published_on"] = polls.loc[0, "election_date"]
    polls.loc[1, "field_end"] = polls.loc[1, "election_date"]
    polls.loc[2, "poll_date"] = polls.loc[2, "election_date"] - pd.Timedelta(days=3)
    _, report = lean.aggregate_races(polls, design)
    assert report["eligible_poll_rows"] == len(polls) - 3
    assert report["known_publication_or_field_end_after_cutoff"] == 2
    polls["publication_verified"] = True
    with pytest.raises(ValueError, match="actual published_on"):
        lean.validate_panel(polls.drop(columns="published_on"))


def test_one_slope_is_shared_between_simulated_states(design):
    races = pd.DataFrame({"state_po": ["TX", "OH", "MA"], "lean": [-0.1, -0.1, 0.1]})
    draws = lean.simulate_with_lean(
        races, mean=np.full(3, 0.5), sigma=np.zeros(3), design=design, slope_draws=np.linspace(-0.3, 0.3, 100)
    )
    np.testing.assert_allclose(draws[:, 0], draws[:, 1])
    np.testing.assert_allclose(draws[:, 0] + draws[:, 2], 1)
    assert np.std(draws[:, 0]) > 0.01


def test_common_random_numbers_match_zero_correction(design):
    races, _ = lean.aggregate_races(_polls([2000]), design)
    kwargs = {"mean": races.blend_mean.to_numpy(), "sigma": races.blend_sigma.to_numpy(), "design": design}
    baseline = lean.simulate_with_lean(races, **kwargs)
    zero = lean.simulate_with_lean(races, slope_draws=np.zeros(20), **kwargs)
    np.testing.assert_array_equal(baseline, zero)


def test_chronological_holdout_ignores_future_outcomes(design):
    races, _ = lean.aggregate_races(_polls(), design)
    original, report = lean.evaluate(races, design)
    changed = races.copy()
    changed.loc[changed.cycle.eq(changed.cycle.max()), "actual_dem_share"] += 0.05
    rerun, _ = lean.evaluate(changed, design)
    earlier = original.cycle.lt(original.cycle.max())
    pd.testing.assert_frame_equal(
        original[earlier].reset_index(drop=True), rerun[earlier].reset_index(drop=True)
    )
    assert original.train_through.lt(original.cycle).all()
    assert set(original.pipeline) == set(lean.PIPELINES)
    assert not report["promoted"]
    assert report["2026_polling_correction"] is None
    assert report["chamber_control_probability"] is None
    assert not report["gates"]["us_senate"]["vintage_gate_passed"]


def test_offices_are_not_pooled_and_insufficient_history_is_explicit(design):
    races, _ = lean.aggregate_races(_polls([2000, 2002, 2004]), design)
    assert (
        lean.fit_slope(races, prediction_column="poll_mean", design=design)["status"]
        == "insufficient_history"
    )
    races.loc[0, "office"] = "us_house"
    with pytest.raises(ValueError, match="office separately"):
        lean.fit_slope(races, prediction_column="poll_mean", design=design)
    with pytest.raises(ValueError):
        replace(design, min_training_cycles=1)


def _archive_inputs():
    raw = pd.DataFrame(
        [
            {
                "poll_id": 1,
                "question_id": 1,
                "race_id": 999,
                "cycle": 2022,
                "location": "OH",
                "type_simple": "Sen-G",
                "pollster": "Synthetic",
                "methodology": "phone",
                "partisan": None,
                "polldate": "2022-10-20",
                "electiondate": "2022-11-08",
                "samplesize": 900,
                "cand1_party": "DEM",
                "cand2_party": "REP",
                "cand1_pct": 48,
                "cand2_pct": 52,
                "cand1_actual": 45,
                "cand2_actual": 55,
            }
        ]
    )
    races = pd.DataFrame(
        [
            {
                "race_id": "canonical",
                "cycle": 2022,
                "office": "us_senate",
                "state_po": "OH",
                "district_num": np.nan,
                "two_party_dem_share": 0.45,
                "certified_flag": True,
                "uncontested_flag": False,
                "winner_party": "REPUBLICAN",
            }
        ]
    )
    pres = pd.DataFrame(
        [
            {"cycle": c, "state_po": "OH", "two_party_dem_share": 0.45, "national_dem_share": 0.5}
            for c in (2020, 2024)
        ]
    )
    prior = pd.DataFrame(
        [{"race_id": "canonical", "pred_dem_share": 0.46, "resid_sigma": 0.06, "train_through": 2020}]
    )
    house = pd.DataFrame(columns=["race_id", "district_lean", "lag_dem_share"])
    return raw, {"races": races, "presidential": pres, "fundamentals": prior, "house_panel": house}


def test_archive_uses_structural_join_and_lagged_presidential_lean():
    raw, inputs = _archive_inputs()
    accepted, report = polling_archive.prepare_ratings(raw, **inputs)
    assert accepted.race_id.tolist() == ["canonical"]
    assert accepted.lean_reference_cycle.tolist() == [2020]
    assert accepted.lean.iloc[0] == pytest.approx(-0.05)
    assert not report["promotion_eligible"]
    assert accepted[lean.GATES].eq(False).all().all()


@pytest.mark.parametrize(
    "fault,reason",
    [
        ("actual", "certified_share_mismatch"),
        ("ambiguous", "missing_or_ambiguous_canonical_race"),
        ("future_prior", "missing_or_nonchronological_fundamentals"),
        ("independent", "not_dem_rep_top_two"),
        ("runoff", "not_november_general"),
    ],
)
def test_archive_exclusions_are_explicit_not_guessed(fault, reason):
    raw, inputs = _archive_inputs()
    if fault == "actual":
        raw["cand1_actual"] = 40
    elif fault == "ambiguous":
        duplicate = inputs["races"].copy().assign(race_id="special")
        inputs["races"] = pd.concat([inputs["races"], duplicate])
    elif fault == "future_prior":
        inputs["fundamentals"]["train_through"] = 2022
    elif fault == "independent":
        raw["cand1_party"] = "IND"
    else:
        raw["electiondate"] = "2022-12-06"
    accepted, report = polling_archive.prepare_ratings(raw, **inputs)
    assert accepted.empty
    assert report["exclusions"][reason] == 1


def test_registered_source_tampering_is_rejected(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "polls.csv"
    path.write_text("question_id,pct\n1,50\n")
    polling_archive.preserve_archive(
        path, url=polling_archive.RATINGS_URL, retrieved_at="2025-01-01T12:00:00Z"
    )
    polling_archive.verify_registered_archive(path)
    path.write_text("question_id,pct\n1,60\n")
    with pytest.raises(ValueError, match="checksum"):
        polling_archive.verify_registered_archive(path)


def test_missing_files_are_named_without_claiming_a_valid_feed(tmp_path):
    inventory = polling_archive.inspect_local_archives(tmp_path)
    assert {r["filename"] for r in inventory} == set(polling_archive.POLL_URLS)
    assert all(r["status"] == "missing" for r in inventory)


def test_archive_inventory_checks_supplied_paths_outside_ratings_folder(tmp_path):
    path = tmp_path / "manual" / "senate_polls.csv"
    path.parent.mkdir()
    path.write_text("question_id,pct\n1,50\n")
    inventory = polling_archive.inspect_local_archives(tmp_path / "ratings", supplied=[path])
    record = next(r for r in inventory if r["filename"] == path.name)
    assert record["status"] == "present_needs_review"
    assert record["paths"][0]["raw_path"] == str(path)
    assert record["sha256"] is not None


@pytest.mark.parametrize("senate_present", [False, True])
def test_research_report_uses_observed_2024_coverage(senate_present):
    from election_prediction.build_polling_lean import _markdown

    coverage = [{"office": "us_house", "cycle": 2024, "races": 30}]
    if senate_present:
        coverage.append({"office": "us_senate", "cycle": 2024, "races": 18})
    report = {
        "review_date": "2026-10-25",
        "intake": {"input_rows": 1},
        "window": {"eligible_poll_rows": 1, "eligible_races": 1},
        "evaluation": {"summary": {}, "gates": {}},
        "input_cycle_coverage": coverage,
    }
    text = _markdown(report)
    assert "House included" in text
    assert f"Senate {'included' if senate_present else 'absent'}" in text
    assert "Senate polling remains missing" not in text


@pytest.mark.parametrize("retrieved_at", ["2026-01-01T12:00:00", "2099-01-01T12:00:00Z"])
def test_archive_retrieval_requires_real_timezone_and_date(tmp_path, retrieved_at):
    path = tmp_path / "archive.csv"
    path.write_text("question_id,pct\n1,50\n")
    with pytest.raises(ValueError, match="timezone"):
        polling_archive.preserve_archive(path, url=polling_archive.RATINGS_URL, retrieved_at=retrieved_at)


def test_acquisition_does_not_call_html_a_csv(tmp_path, monkeypatch):
    from election_prediction.data import acquire

    def unavailable(*args, **kwargs):
        raise acquire.InvalidResponse("HTML, not candidate-poll data")

    monkeypatch.setattr(acquire, "fetch", unavailable)
    result = polling_archive.download_archives(tmp_path, include_candidate_files=True)
    assert len(result) == 5
    assert all(r["status"] == "unavailable_or_invalid" for r in result)
    assert not list(tmp_path.glob("*.csv"))

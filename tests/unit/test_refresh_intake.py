"""Synthetic intake tests: availability, identity, immutability and vintage leakage."""

import json
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from election_prediction.build_ballots import compile_evidence
from election_prediction.data import acquire, ballots, fec, fred, official_repairs, public_sources
from election_prediction.evaluation import chamber
from election_prediction.features import block_crosswalk
from election_prediction.features import national_fundamentals as nf
from election_prediction.models.baseline import economic_fundamentals as econ
from election_prediction.models.baseline.national_environment import ContractError, projectable
from election_prediction.polling import generic, schema
from election_prediction.polling.average import average_polls


def test_fec_snapshot_exclusive_and_no_address(tmp_path):
    path = tmp_path / "snapshot.json"
    fec._snapshot(
        [{"candidate_id": "TEST", "address_city": "PRIVATE"}],
        path,
        endpoint="/candidates/",
        params={"api_key": "SECRET"},
    )
    assert "PRIVATE" not in path.read_text() and "SECRET" not in path.read_text()
    with pytest.raises(FileExistsError):
        fec._snapshot([], path, endpoint="/candidates/", params={})


def test_fec_refresh_preserves_old_and_reuses_same_day(tmp_path, monkeypatch):
    old = tmp_path / "source=fec_api/dataset=candidates/cycle=2026/fec_candidates__us_house__2026.json"
    old.parent.mkdir(parents=True)
    old.write_text("original")
    calls = []
    monkeypatch.setattr(fec, "fetch_all_pages", lambda *a, **kw: calls.append(kw) or [])
    new = fec.download_candidates(2026, "us_house", tmp_path, refresh=True)
    assert new != old and old.read_text() == "original"
    assert fec.download_candidates(2026, "us_house", tmp_path, refresh=True) == new
    assert len(calls) == 1


def _fred_document():
    return {
        "query": {"series_id": "UNRATE", "realtime_start": "2020-10-20", "realtime_end": "2020-10-20"},
        "retrieved_on": "2026-10-21",
        "response": {
            "realtime_start": "2020-10-20",
            "realtime_end": "2020-10-20",
            "observations": [{"date": "2020-09-01", "value": "7.8"}],
        },
    }


def test_fred_keeps_vintage_distinct_from_retrieval(tmp_path):
    path = tmp_path / "fred.json"
    path.write_text(json.dumps(_fred_document()))
    row = fred.parse(path, series_id="UNRATE", vintage="2020-10-20").iloc[0]
    assert row.data_vintage == "2020-10-20" and row.retrieved_on == "2026-10-21"
    assert row.release_date is None


@pytest.mark.parametrize("fault", ["query", "response", "future", "duplicate"])
def test_fred_refuses_leakage(tmp_path, fault):
    document = _fred_document()
    if fault in {"query", "response"}:
        document[fault]["realtime_start"] = "2024-10-20"
    if fault == "future":
        document["response"]["observations"][0]["date"] = "2020-11-01"
    if fault == "duplicate":
        document["response"]["observations"] *= 2
    path = tmp_path / "fred.json"
    path.write_text(json.dumps(document))
    with pytest.raises(ValueError):
        fred.parse(path, series_id="UNRATE", vintage="2020-10-20")


def _observations():
    return pd.DataFrame(
        [
            {"series_id": series, "observation_date": date, "data_vintage": "2020-10-20", "value": value}
            for series in ["A229RX0", "UNRATE", "CPIAUCSL"]
            for date, value in [("2019-09-01", 100.0), ("2020-09-01", 102.0)]
        ]
    )


def test_economic_growth_exact_year_and_missing_not_backfilled():
    rows = nf.economic_features(_observations(), cycle=2020, vintage="2020-10-20")
    assert rows["income_growth"] == pytest.approx(np.log(1.02))
    assert rows["unemployment_change"] == 2
    empty = _observations().query("series_id != 'A229RX0'")
    assert np.isnan(nf.economic_features(empty, cycle=2020, vintage="2020-10-20")["income_growth"])


@pytest.mark.parametrize("fault", ["mixed", "future", "duplicate"])
def test_economic_features_refuse_bad_vintages(fault):
    rows = _observations()
    if fault == "mixed":
        rows.loc[0, "data_vintage"] = "2024-10-20"
    elif fault == "future":
        rows.loc[0, "observation_date"] = "2021-01-01"
    else:
        rows = pd.concat([rows, rows.iloc[[0]]])
    with pytest.raises(ValueError):
        nf.economic_features(rows, cycle=2020, vintage="2020-10-20")


def test_economics_small_history_cannot_promote():
    frame = pd.DataFrame(
        [
            {
                "cycle": year,
                "income_growth": year % 7 / 100,
                "unemployment_change": year % 3,
                "inflation": year % 9 / 100,
                "president_on_ballot": year % 4 == 0,
                "consecutive_terms": 1 + year % 3,
                "midterm": year % 4 == 2,
                "incumbent_share": 0.45 + year % 7 / 100,
                "white_house_party": "DEMOCRAT",
                "data_vintage": f"{year}-10-20",
            }
            for year in range(2008, 2026, 2)
        ]
    )
    result = econ.evaluate(frame)
    assert all(not r["promotion_eligible"] for r in result.values())
    for r in result.values():
        assert all(p["train_through"] < p["cycle"] for p in r["predictions"])
    estimate = econ.estimate(frame, frame.iloc[[-1]], result)
    with pytest.raises(ContractError):
        projectable(estimate)
    assert econ.estimate(frame, frame.iloc[:0], result).status == "unavailable"


def _polls():
    return schema.standardize_polls(
        pd.DataFrame(
            [
                {
                    "poll_id": "synthetic",
                    "pollster": "Example",
                    "office": "us_house_generic",
                    "cycle": 2026,
                    "geography_id": "nation:us",
                    "state_po": "US",
                    "field_start": "2026-10-01",
                    "field_end": "2026-10-02",
                    "published_on": "2026-10-10",
                    "sample_size": 1000,
                    "population": "RV",
                    "mode": "online",
                    "dem_pct": 53,
                    "rep_pct": 47,
                    "source_url": "https://example.org/poll",
                }
            ]
        ),
        source_id="synthetic",
        snapshot_date="2026-10-21",
    )


def test_generic_national_geography_does_not_allow_state_poll_escape():
    polls = _polls()
    assert schema.validate_polls(polls)["ok"]
    polls["office"] = "us_senate"
    assert not schema.validate_polls(polls)["ok"]


def test_poll_publication_cutoff_not_just_field_end():
    polls = _polls()
    with pytest.raises(ValueError, match="No polls"):
        average_polls(polls, reference_date="2026-10-05")
    assert average_polls(polls, reference_date="2026-10-11").iloc[0].n_polls == 1
    assert generic.estimate(polls, as_of="2026-10-05", historical={}).status == "unavailable"


def test_generic_cross_check_unpromotable_and_house_effects_use_no_current_truth():
    polls = _polls()
    estimate = generic.estimate(polls, as_of="2026-10-21", historical={"rmse": 0.04})
    with pytest.raises(ContractError):
        projectable(estimate)
    targets = pd.DataFrame([{"cycle": 2026, "actual_dem_share": 0.9}])
    assert generic.house_effects(polls, targets, cycle=2026).empty


def test_ballot_moves_incumbency_with_candidate_not_district_number():
    roster = pd.DataFrame(
        [
            {
                "state_po": "AA",
                "office": "us_house",
                "district_num": d,
                "incumbent_name": name,
                "incumbent_party": party,
            }
            for d, name, party in [(1, "Jane Alpha", "DEMOCRAT"), (2, "John Beta", "REPUBLICAN")]
        ]
    )
    candidates = pd.DataFrame(
        [
            {
                "state_po": "AA",
                "office": "us_house",
                "district_num": 1,
                "candidate_name": "John Beta",
                "party": "REPUBLICAN",
                "source_url": "https://example.org/ballot",
            }
        ]
    )
    rows, ambiguous = compile_evidence(candidates, roster, as_of="2026-10-21")
    assert not ambiguous and not rows.iloc[0].incumbent_running
    assert rows.iloc[0].ballot_incumbent_rep == 1 and rows.iloc[0].ballot_incumbent_dem == 0
    candidates["candidate_name"] = "James Alpha"
    rows, ambiguous = compile_evidence(candidates, roster, as_of="2026-10-21")
    # Same initial is not sufficient identity evidence for distinct given names.
    assert rows.empty and ambiguous


def test_ballot_validation_refuses_missing_districts_and_duplicates():
    row = {
        "state_po": "AA",
        "office": "us_house",
        "district_num": 1,
        "candidate_name": "Example Person",
        "party": "DEMOCRAT",
    }
    with pytest.raises(ValueError):
        ballots.validate(pd.DataFrame([row]), state="AA", expected_house=2, expected_senate=0)
    with pytest.raises(ValueError):
        ballots.validate(pd.DataFrame([row, row]), state="AA", expected_house=1, expected_senate=0)


@pytest.mark.parametrize("fault", ["duplicate", "wrong_state", "missing_member"])
def test_bef_refuses_bad_block_keys(tmp_path, fault):
    path = tmp_path / "cd120.zip"
    body = "GEOID,STATEFP,CDFP\n010010001001000,01,01\n"
    if fault == "duplicate":
        body += "010010001001000,01,01\n"
    elif fault == "wrong_state":
        body = body.replace("010010001001000", "020010001001000")
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("CD120_02.txt" if fault == "missing_member" else "CD120_01.txt", body)
    with pytest.raises(ValueError):
        block_crosswalk.block_to_equivalency(Path("not_used"), path, state_fips="01")


def test_repairs_cannot_accept_partial_certified_totals():
    frame = pd.DataFrame(
        [
            {"party": "DEMOCRAT", "votes": 99, "county_fips": "20001"},
            {"party": "REPUBLICAN", "votes": 100, "county_fips": "20001"},
        ]
    )
    races = pd.DataFrame(
        [{"cycle": 2024, "office": "president", "state_po": "KS", "dem_votes": 100, "rep_votes": 100}]
    )
    assert not official_repairs.reconciliation(frame, races, state="KS", cycle=2024)["reconciles"]


def test_georgia_parser_excludes_adjacent_contests(tmp_path):
    path = tmp_path / "synthetic.xlsx"
    frame = pd.DataFrame(
        [
            {"Contest ID": "USH14", "Ballot Name": "Example Candidate (Dem)", "Party": None, "Total": 40},
            {"Contest ID": "USH14", "Ballot Name": "Other Candidate - Rep", "Party": None, "Total": 60},
            {"Contest ID": "USH14", "Ballot Name": "Total Votes", "Party": None, "Total": 100},
            {"Contest ID": "SSD53", "Ballot Name": "Legislative Candidate (Dem)", "Party": None, "Total": 30},
        ]
    )
    frame.to_excel(path, sheet_name="Total Votes", index=False)
    assert official_repairs.georgia_special(path, district=14) == {
        "dem_votes": 40,
        "rep_votes": 60,
        "other_votes": 0,
    }
    frame.loc[2, "Total"] = 101
    frame.to_excel(path, sheet_name="Total Votes", index=False)
    with pytest.raises(ValueError, match="reconcile"):
        official_repairs.georgia_special(path, district=14)


def test_full_chamber_refuses_partial_house():
    with pytest.raises(ValueError, match="partial"):
        chamber.evaluate(pd.DataFrame([{"cycle": 2024, "geography_id": "one"}]), [])


def test_full_house_retains_missing_share_seat_and_excludes_delegate():
    rows = []
    for cycle in (1980, 1982, 1984, 1986):
        for i in range(4):
            rows.append(
                {
                    "race_id": f"{cycle}-{i}",
                    "cycle": cycle,
                    "state_po": "TX",
                    "geography_id": str(i),
                    "district_lean": i / 100,
                    "national_dem_share": 0.5,
                    "lag_dem_share": 0.5,
                    "incumbent_dem": i % 2,
                    "incumbent_rep": (i + 1) % 2,
                    "two_party_dem_share": 0.48 + i / 100 + cycle % 3 / 100,
                    "uncontested_flag": False,
                    "midterm_penalty": 0.0,
                }
            )
    actual = []
    for i in range(435):
        row = {
            "race_id": f"1990-{i}",
            "cycle": 1990,
            "state_po": "TX",
            "geography_id": str(i),
            "office": "us_house",
            "winner_party": "DEMOCRAT",
            "two_party_dem_share": 0.51 if i < 434 else np.nan,
        }
        actual.append(row)
        if i < 434:
            rows.append({**rows[0], **row, "national_dem_share": 0.51})
    actual.append({**actual[0], "race_id": "delegate", "state_po": "DC", "geography_id": "dc"})
    pres = pd.DataFrame(
        [{"cycle": 1988, "state_po": "TX", "two_party_dem_share": 0.4, "national_dem_share": 0.5}]
    )
    predictions, omitted = chamber.house_predictions(pd.DataFrame(rows), pres, pd.DataFrame(actual))
    assert not omitted and len(predictions) == 435
    missing_share = predictions[predictions.race_id.eq("1990-434")].iloc[0]
    assert missing_share.prediction_source == "lagged_state_presidential_fallback"
    assert pd.notna(missing_share.pred_dem_share) and missing_share.actual_dem_win


def test_public_pdf_snapshot_rejects_html(tmp_path):
    path = tmp_path / "not_pdf.pdf"
    path.write_text("<html>temporary error</html>")
    with pytest.raises(acquire.InvalidResponse):
        public_sources.snapshot(
            "https://example.org/file", path, source_id="synthetic", owner="Example", expect="pdf"
        )


def test_sourced_identity_pairs_do_not_turn_distinct_people_into_incumbents():
    roster = pd.DataFrame(
        [
            {
                "state_po": "AA",
                "office": "us_house",
                "district_num": 1,
                "incumbent_name": "John Alpha",
                "incumbent_party": "REPUBLICAN",
            }
        ]
    )
    candidates = pd.DataFrame(
        [
            {
                "state_po": "AA",
                "office": "us_house",
                "district_num": 1,
                "candidate_name": "James Alpha",
                "party": "REPUBLICAN",
                "source_url": "https://example.gov/ballot",
            }
        ]
    )
    review = pd.DataFrame(
        [
            {
                "state_po": "AA",
                "office": "us_house",
                "ballot_name": "James Alpha",
                "incumbent_name": "John Alpha",
                "same_person": "False",
                "retrieved_on": "2026-10-22",
            }
        ]
    )
    rows, ambiguous = compile_evidence(candidates, roster, as_of="2026-10-22", identity_reviews=review)
    assert not ambiguous and not rows.iloc[0].incumbent_running
    assert rows.iloc[0].ballot_incumbent_rep == 0
    rows, ambiguous = compile_evidence(candidates, roster, as_of="2026-10-21", identity_reviews=review)
    assert rows.empty and ambiguous
    candidates["candidate_name"] = "Johnny Alpha"
    review["ballot_name"], review["same_person"] = "Johnny Alpha", "True"
    rows, ambiguous = compile_evidence(candidates, roster, as_of="2026-10-22", identity_reviews=review)
    assert not ambiguous and rows.iloc[0].incumbent_running


def test_partial_ballot_parser_cannot_prove_incumbent_absence():
    roster = pd.DataFrame(
        [
            {
                "state_po": "AA",
                "office": "us_senate",
                "district_num": 0,
                "incumbent_name": "John Alpha",
                "incumbent_party": "REPUBLICAN",
            }
        ]
    )
    candidates = pd.DataFrame(
        [
            {
                "state_po": "AA",
                "office": "us_senate",
                "district_num": 0,
                "candidate_name": "Jane Beta",
                "party": "DEMOCRAT",
                "source_url": "https://example.gov/ballot",
                "positive_evidence_only": True,
            }
        ]
    )
    rows, ambiguous = compile_evidence(candidates, roster, as_of="2026-10-22")
    assert rows.empty and ambiguous


@pytest.mark.parametrize("fault", [None, "duplicate", "wrong_cycle", "missing_county", "fractional"])
def test_nc_official_original_results_preserve_counts_and_fail_closed(tmp_path, fault):
    counties = pd.DataFrame(
        [
            {"STATEFP": "37", "NAME": "Alpha", "GEOID": "37001"},
            {"STATEFP": "37", "NAME": "Beta", "GEOID": "37003"},
        ]
    )
    rows = pd.DataFrame(
        [
            {
                "County": county,
                "Election Date": "11/05/2024",
                "Precinct": "0001",
                "Contest Name": "US PRESIDENT",
                "Choice": party,
                "Choice Party": party,
                "Total Votes": 100,
            }
            for county in ("ALPHA", "BETA")
            for party in ("DEM", "REP")
        ]
    )
    if fault == "duplicate":
        rows = pd.concat([rows, rows.iloc[[0]]])
    elif fault == "wrong_cycle":
        rows["Election Date"] = "11/03/2020"
    elif fault == "missing_county":
        rows = rows[rows.County.eq("ALPHA")]
    elif fault == "fractional":
        rows["Total Votes"] = 1.5
    path = tmp_path / "synthetic.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("results.txt", rows.to_csv(sep="\t", index=False))
    if fault:
        with pytest.raises(ValueError):
            official_repairs.north_carolina_president(path, counties, cycle=2024)
    else:
        parsed = official_repairs.north_carolina_president(path, counties, cycle=2024)
        assert parsed.votes.sum() == 400 and parsed.county_fips.nunique() == 2


def test_cached_public_snapshot_preserves_retrieval_manifest_and_detects_tampering(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = Path("data/raw/example.html")
    path.parent.mkdir(parents=True)
    path.write_text("<html>synthetic original</html>")
    kwargs = {"source_id": "synthetic", "owner": "Example", "expect": "html"}
    public_sources.snapshot("https://example.gov/results", path, **kwargs)
    manifest = next(Path("data/manifests").glob("*.json"))
    before = manifest.read_bytes()
    public_sources.snapshot("https://example.gov/results", path, **kwargs)
    assert manifest.read_bytes() == before
    path.write_text("<html>changed</html>")
    with pytest.raises(acquire.InvalidResponse, match="changed"):
        public_sources.snapshot("https://example.gov/results", path, **kwargs)


def test_florida_special_table_sums_explicit_parties_and_refuses_frameset(tmp_path):
    path = tmp_path / "synthetic.html"
    header = "<h1>April 1, 2025 Official Results</h1>"
    tables = "".join(
        f"<table><tr><td>District: {district}</td></tr>"
        "<tr><td></td><td>Alpha (REP)</td><td>Beta (DEM)</td><td>Gamma (WRI)</td></tr>"
        "<tr><td>Total</td><td>100</td><td>90</td><td>2</td></tr></table>"
        for district in (1, 6)
    )
    path.write_text(header + tables)
    assert official_repairs.florida_federal_specials(path)[1] == {
        "dem_votes": 90,
        "rep_votes": 100,
        "other_votes": 2,
    }
    path.write_text("<frameset></frameset>")
    with pytest.raises(ValueError):
        official_repairs.florida_federal_specials(path)

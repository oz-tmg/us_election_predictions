"""Unit tests for the P0 data-and-entity foundation."""
from __future__ import annotations

import pandas as pd
import pytest

from election_prediction.data import medsl, synthetic
from election_prediction.data.manifest import SourceManifest, json_schema, sha256_file
from election_prediction.data.privacy import GovernanceError, PrivacyTier, assert_public_safe
from election_prediction.data.validation import validate_silver_returns
from election_prediction.features.race_table import build_race_table
from election_prediction.geography import canonical, reference


# --------------------------------------------------------------- privacy/governance
def test_public_tier_boundary_allows_0_to_2():
    for t in (PrivacyTier.PUBLIC_AGGREGATE, PrivacyTier.PUBLIC_PERSONAL):
        assert_public_safe(t)  # no raise


def test_restricted_tier_refused():
    for t in (PrivacyTier.LICENSED_PERSONAL, PrivacyTier.CAMPAIGN_OPERATIONAL,
              PrivacyTier.DERIVED_SENSITIVE):
        with pytest.raises(GovernanceError):
            assert_public_safe(t, context="test")


def test_manifest_refuses_restricted_tier(tmp_path):
    f = tmp_path / "x.csv"
    f.write_text("a,b\n1,2\n")
    with pytest.raises(GovernanceError):
        SourceManifest.for_snapshot(
            raw_path=f, source_id="s", dataset_name="d", source_owner="o",
            source_url="u", privacy_tier=PrivacyTier.LICENSED_PERSONAL,
            license_or_terms="l", permitted_use="p", prohibited_use="x",
            office_coverage=["president"], geography_coverage=["state"],
            election_cycle="2024", owner="me",
        )


# ---------------------------------------------------------------------- manifest
def test_manifest_checksum_and_roundtrip(tmp_path):
    f = tmp_path / "data.csv"
    f.write_text("year,candidatevotes\n2020,100\n")
    m = SourceManifest.for_snapshot(
        raw_path=f, source_id="medsl_president_1976_2020", dataset_name="d",
        source_owner="MEDSL", source_url="u", privacy_tier=PrivacyTier.PUBLIC_AGGREGATE,
        license_or_terms="l", permitted_use="p", prohibited_use="x",
        office_coverage=["president"], geography_coverage=["state"],
        election_cycle="1976-2020", owner="me",
    )
    assert m.checksum_sha256 == sha256_file(f)
    assert len(m.checksum_sha256) == 64
    out = m.write(tmp_path / "manifests")
    reloaded = SourceManifest.load(out)
    assert reloaded.snapshot_id == m.snapshot_id
    assert reloaded.privacy_tier == 0


def test_json_schema_caps_tier_at_2():
    schema = json_schema()
    assert schema["properties"]["privacy_tier"]["maximum"] == 2


# --------------------------------------------------------------------- geography
def test_state_reference_complete():
    assert len(reference.STATES) >= 51  # 50 + DC
    assert reference.by_postal("VA").fips == "51"
    assert reference.normalize_state("51").postal == "VA"
    assert reference.normalize_state("California").postal == "CA"


def test_geography_ids():
    assert canonical.geography_id("state", state_fips="51") == "state:51"
    assert canonical.geography_id("county", state_fips="51", county_fips="59") == "state:51|county:059"
    cd = canonical.geography_id("cong_district", state_fips="51", district_num=7)
    assert cd == "state:51|district:cong_07"


def test_geography_table_unique_and_has_nation():
    g = canonical.build_geography_table()
    assert g["geography_id"].is_unique
    assert (g["geog_level"] == "nation").sum() == 1
    assert (g["geog_level"] == "state").sum() >= 51


# ------------------------------------------------------------------------- medsl
@pytest.fixture
def silver_returns():
    parts = []
    for office in ("president", "us_senate", "us_house"):
        raw = synthetic.build_fixture(office)
        raw.columns = [c.lower() for c in raw.columns]
        raw["source_id"] = "test"
        raw["snapshot_date"] = "2026-07-08"
        parts.append(medsl.standardize_silver(raw, office))
    return pd.concat(parts, ignore_index=True)


def test_silver_schema_and_shares(silver_returns):
    assert list(silver_returns.columns) == medsl.SILVER_COLUMNS
    # vote shares within a race sum to ~1 for contested races
    contested = silver_returns[~silver_returns["uncontested_flag"]]
    sums = contested.groupby("race_id")["vote_share"].sum()
    assert ((sums - 1.0).abs() < 1e-6).all()


def test_house_geography_ids(silver_returns):
    house = silver_returns[silver_returns["office"] == "us_house"]
    assert house["geog_level"].eq("cong_district").all()
    assert house["geography_id"].str.contains(r"\|district:cong_\d{2}").all()


def test_uncontested_flagged(silver_returns):
    # synthetic fixture makes district 1 in each state uncontested
    assert silver_returns["uncontested_flag"].any()


# -------------------------------------------------------------------- race table
def test_race_table_winner_and_two_party(silver_returns):
    rt = build_race_table(silver_returns)
    assert rt["race_id"].is_unique
    # two-party dem share in [0,1] where defined
    tp = rt["two_party_dem_share"].dropna()
    assert ((tp >= 0) & (tp <= 1)).all()
    # winner_votes >= runner_up_votes
    assert (rt["winner_votes"] >= rt["runner_up_votes"]).all()


# -------------------------------------------------------------------- validation
def test_validation_passes_on_clean_data(silver_returns):
    rep = validate_silver_returns(silver_returns, required_columns=medsl.SILVER_COLUMNS)
    assert rep.ok, rep.summary()


def test_validation_catches_negative_votes(silver_returns):
    bad = silver_returns.copy()
    bad.loc[bad.index[0], "candidatevotes"] = -5
    rep = validate_silver_returns(bad, required_columns=medsl.SILVER_COLUMNS)
    assert not rep.ok
    assert any("nonnegative" in r.name and not r.passed for r in rep.results)

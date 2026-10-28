"""Dashboard: bundle contract, store isolation, Access verification and app wiring.

All fixtures are synthetic (CLAUDE.md §4); no build artefact is read.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import jwt
import pandas as pd
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from election_prediction.dashboard import figures
from election_prediction.dashboard.access import AccessDenied, AccessVerifier, insecure_local_allowed
from election_prediction.dashboard.app import create_app, races_table
from election_prediction.dashboard.bundle import BundleError, RunKind, RunManifest, Tier
from election_prediction.dashboard.export import (
    export_backtest,
    export_history,
    export_preregistration,
    export_refresh,
    write_bundle,
)
from election_prediction.dashboard.store import BundleStore

BAND = [
    {
        "assumption": f"shrinkage={s}",
        "shrinkage": s,
        "nat_share": 0.5 + s / 10,
        "house_mean_seats": 200 + 40 * s,
        "house_5th": 150 + 40 * s,
        "house_95th": 260 + 40 * s,
        "house_p_dem": 0.4 + 0.3 * s,
        "sen_dem_seats_up": 15,
        "sen_mean_total": 48 + 4 * s,
        "sen_p_dem": 0.3 + 0.4 * s,
    }
    for s in (0.25, 0.5, 1.0)
]
NE = {
    "estimator": "specials_band",
    "status": "band",
    "identified": False,
    "band": [
        {"assumption": b["assumption"], "national_dem_share": b["nat_share"], "share_std_error": 0.003}
        for b in BAND
    ],
    "assumptions": ["shrinkage swept"],
    "caveats": ["specials are non-random"],
    "provenance": {"n": 8},
}


def _seats() -> pd.DataFrame:
    rows = []
    for b in BAND:
        for i, (office, geo, st, dn, src) in enumerate(
            [
                ("us_house", "state:51|district:cong_01", "VA", 1.0, "model"),
                ("us_house", "state:48|district:cong_02", "TX", 2.0, "model_transferred"),
                ("us_house", "state:01|district:cong_01", "AL", 1.0, "fallback_state_lean"),
                ("us_senate", "state:20", "KS", None, "model"),
                ("us_senate", "state:12", "FL", None, "model"),
            ]
        ):
            rows.append(
                {
                    "geography_id": geo,
                    "state_po": st,
                    "district_num": dn,
                    "office": office,
                    "mean_dem_share": 0.45 + 0.03 * i,
                    "sigma": 0.1,
                    "source": src,
                    "boundary_confidence": "unchanged" if office == "us_house" else None,
                    "litigation_risk": "none",
                    "incumbent_party": "REPUBLICAN",
                    "incumbency_assumed": True,
                    "dem_win_prob": 0.3 + 0.1 * i,
                    "assumption": b["assumption"],
                    "candidate_name": "SHOULD NOT SURVIVE EXPORT",
                }
            )
    return pd.DataFrame(rows)


@pytest.fixture
def refresh_dir(tmp_path: Path) -> Path:
    d = tmp_path / "refresh_2026-10-22"
    d.mkdir()
    _seats().to_csv(d / "projection_seats.csv", index=False)
    (d / "national_environment_2026-10-22.json").write_text(
        json.dumps(
            {
                "generated_on": "2026-10-22",
                "national_environment": NE,
                "band_results": BAND,
                "conclusions": ["House: favoured across the band.", "Senate: unresolved."],
                "correlation_parameters": {"house": {"national": 0.45, "regional": 0.25, "state": 0.3}},
                "house_coverage": {
                    "seats_by_source": {"model": 1, "model_transferred": 1, "fallback_state_lean": 1}
                },
            }
        )
    )
    (d / "refresh_summary.json").write_text(json.dumps({"as_of": "2026-10-22", "git_commit": "abc123"}))
    return d


@pytest.fixture
def race_results(tmp_path: Path) -> Path:
    df = pd.DataFrame(
        {
            "race_id": ["2024_president_ks_gen", "2024_president_va_gen", "2024_us_senate_ks_gen"],
            "cycle": [2024, 2024, 2024],
            "office": ["president", "president", "us_senate"],
            "state_po": ["KS", "VA", "KS"],
            "district_num": [None, None, None],
            "geography_id": ["state:20", "state:51", "state:20"],
            "two_party_dem_share": [0.42, 0.53, None],
            "winner_party": ["REPUBLICAN", "DEMOCRAT", "REPUBLICAN"],
            "winner": ["A", "B", "C"],
            "uncontested_flag": [False, False, True],
            "certified_flag": [True, True, True],
            "source_id": ["medsl"] * 3,
            "snapshot_date": ["2026-10-07"] * 3,
        }
    )
    p = tmp_path / "race_results.parquet"
    df.to_parquet(p)
    return p


@pytest.fixture
def bundles(tmp_path: Path, refresh_dir: Path, race_results: Path) -> Path:
    out = tmp_path / "bundles"
    export_refresh(refresh_dir, out)
    export_history(race_results, out)
    p1 = {
        k: {
            e: {
                "n": 10,
                "mae_vote_share": 0.04,
                "rmse_vote_share": 0.05,
                "brier": 0.1,
                "log_score": 0.3,
                "ece": 0.05,
                "coverage_90": 0.9,
                "coverage_95": 0.95,
                "calibration_curve": [
                    {"bin_low": 0, "bin_high": 0.5, "n": 5, "mean_pred": 0.2, "observed_freq": 0.25}
                ],
            },
            b: {"naive_persistence_mae": 0.05, "winner_accuracy": 0.9},
        }
        for k, e, b in (
            ("presidential", "demographics_eval", "demographics_backtest"),
            ("house", "evaluation", "backtest"),
            ("senate", "evaluation", "backtest"),
        )
    }
    (tmp_path / "p1_results.json").write_text(json.dumps(p1))
    export_backtest(tmp_path / "p1_results.json", out, as_of="2026-09-01")
    return out


# --- bundle contract --------------------------------------------------------------------


@pytest.mark.parametrize("kind", [k for k in RunKind if k is not RunKind.HISTORICAL])
def test_only_historical_runs_can_be_public(kind: RunKind) -> None:
    with pytest.raises(BundleError, match="cannot be public"):
        RunManifest(run_id="r", kind=kind, tier=Tier.PUBLIC, title="t", as_of="2026-10-22", summary="s")


def test_manifest_requires_summary_and_safe_run_id() -> None:
    with pytest.raises(BundleError, match="summary"):
        RunManifest(run_id="r", kind=RunKind.REFRESH, tier=Tier.VAULT, title="t", as_of="x", summary=" ")
    with pytest.raises(BundleError, match="run_id"):
        RunManifest(run_id="../r", kind=RunKind.REFRESH, tier=Tier.VAULT, title="t", as_of="x", summary="s")


def test_manifest_round_trips() -> None:
    m = RunManifest(
        run_id="r",
        kind=RunKind.REFRESH,
        tier=Tier.VAULT,
        title="t",
        as_of="2026-10-22",
        summary="s",
        tables=("seats",),
        caveats=("c",),
        sources={"a": "b"},
    )
    assert RunManifest.from_json(m.to_json()) == m


def test_export_keeps_only_declared_columns(bundles: Path) -> None:
    seats = pd.read_parquet(bundles / "vault" / "refresh_2026-10-22" / "seats.parquet")
    assert "candidate_name" not in seats.columns
    assert "incumbency_assumed" not in seats.columns
    results = pd.read_parquet(bundles / "public" / "certified_results_2026-10-07" / "results.parquet")
    assert "winner" not in results.columns
    assert set(results["race_type"]) == {"gen"}


def test_refresh_manifest_carries_provenance(bundles: Path) -> None:
    m = RunManifest.read(bundles / "vault" / "refresh_2026-10-22")
    assert m.tier is Tier.VAULT and m.kind is RunKind.REFRESH
    assert m.source_git_commit == "abc123"
    assert set(m.sources) == {
        "projection_seats.csv",
        "national_environment_2026-10-22.json",
        "refresh_summary.json",
    }
    assert "state-lean fallback" in m.summary
    assert any("asserted, not estimated" in c for c in m.caveats)


def test_bundles_are_immutable(bundles: Path, refresh_dir: Path) -> None:
    with pytest.raises(BundleError, match="immutable"):
        export_refresh(refresh_dir, bundles)
    export_refresh(refresh_dir, bundles, replace=True)


def test_write_bundle_rejects_missing_required_columns(tmp_path: Path) -> None:
    m = RunManifest(
        run_id="r",
        kind=RunKind.REFRESH,
        tier=Tier.VAULT,
        title="t",
        as_of="x",
        summary="s",
        tables=("seats",),
    )
    with pytest.raises(BundleError, match="missing required columns"):
        write_bundle(tmp_path, m, {"seats": pd.DataFrame({"office": ["us_house"]})})
    assert not (tmp_path / "vault" / "r").exists()


def test_preregistration_export(tmp_path: Path) -> None:
    reg = {
        "registered_on": "2026-09-30",
        "status": "PRE-REGISTERED",
        "national_environment": NE,
        "predictions": {"band": BAND},
        "conclusions": ["c"],
        "declared_defects": ["d"],
        "git_commit_at_registration": "9e4e",
        "predictions_sha256": "ff",
    }
    p = tmp_path / "preregistration_2026-11-03.json"
    p.write_text(json.dumps(reg))
    _seats().drop(columns=["incumbent_party"]).to_csv(
        tmp_path / "preregistration_2026-11-03_seats.csv", index=False
    )
    out = export_preregistration(p, tmp_path / "b")
    m = RunManifest.read(out)
    assert m.kind is RunKind.PREREGISTRATION and m.as_of == "2026-09-30" and "d" in m.caveats
    band = json.loads((out / "band.json").read_text())
    assert band["seal"]["predictions_sha256"] == "ff"


# --- store ------------------------------------------------------------------------------


def test_store_is_bound_to_one_tier(bundles: Path) -> None:
    public = BundleStore(bundles, Tier.PUBLIC)
    assert [m.kind for m in public.runs()] == [RunKind.HISTORICAL]
    vault = BundleStore(bundles, Tier.VAULT)
    assert {m.run_id for m in vault.runs()} == {"refresh_2026-10-22", "backtest_2026-09-01"}
    with pytest.raises(BundleError):
        public.manifest("refresh_2026-10-22")


def test_store_refuses_a_misfiled_vault_bundle(bundles: Path) -> None:
    (bundles / "vault" / "refresh_2026-10-22").rename(bundles / "public" / "refresh_2026-10-22")
    with pytest.raises(BundleError, match="vault bundle found in the public store"):
        BundleStore(bundles, Tier.PUBLIC)


# --- access -----------------------------------------------------------------------------

TEAM = "savepoint.cloudflareaccess.com"
AUD = "aud-tag-123"


class _StaticKeys:
    def __init__(self, public_key) -> None:
        self.public_key = public_key

    def get_signing_key_from_jwt(self, token: str):
        return type("K", (), {"key": self.public_key})()


@pytest.fixture(scope="module")
def rsa_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _token(key, **overrides) -> str:
    now = dt.datetime.now(dt.UTC)
    claims = {
        "aud": [AUD],
        "iss": f"https://{TEAM}",
        "email": "reviewer@example.com",
        "iat": now,
        "exp": now + dt.timedelta(minutes=5),
    }
    claims.update(overrides)
    return jwt.encode(claims, key, algorithm="RS256")


def test_verifier_accepts_a_valid_token(rsa_key) -> None:
    v = AccessVerifier(TEAM, AUD, keys=_StaticKeys(rsa_key.public_key()))
    assert v.verify(_token(rsa_key))["email"] == "reviewer@example.com"


@pytest.mark.parametrize(
    "overrides",
    [
        {"aud": ["other-app"]},
        {"iss": "https://evil.cloudflareaccess.com"},
        {"exp": dt.datetime(2020, 1, 1, tzinfo=dt.UTC), "iat": dt.datetime(2019, 12, 31, tzinfo=dt.UTC)},
    ],
)
def test_verifier_rejects_bad_claims(rsa_key, overrides) -> None:
    v = AccessVerifier(TEAM, AUD, keys=_StaticKeys(rsa_key.public_key()))
    with pytest.raises(AccessDenied):
        v.verify(_token(rsa_key, **overrides))


def test_verifier_rejects_a_token_signed_by_another_key(rsa_key) -> None:
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    v = AccessVerifier(TEAM, AUD, keys=_StaticKeys(rsa_key.public_key()))
    with pytest.raises(AccessDenied):
        v.verify(_token(other))
    with pytest.raises(AccessDenied):
        v.verify(None)


def test_insecure_local_is_refused_on_cloud_run() -> None:
    assert insecure_local_allowed({"EP_DASH_INSECURE_LOCAL": "1"}) is True
    assert insecure_local_allowed({}) is False
    with pytest.raises(RuntimeError, match="Cloud Run"):
        insecure_local_allowed({"EP_DASH_INSECURE_LOCAL": "1", "K_SERVICE": "dash-vault"})


# --- app --------------------------------------------------------------------------------


def test_public_app_is_never_given_vault_data(bundles: Path) -> None:
    public, vault = BundleStore(bundles, Tier.PUBLIC), BundleStore(bundles, Tier.VAULT)
    with pytest.raises(ValueError, match="never given a vault store"):
        create_app(Tier.PUBLIC, public, vault)


def test_vault_app_requires_a_verifier(bundles: Path) -> None:
    public, vault = BundleStore(bundles, Tier.PUBLIC), BundleStore(bundles, Tier.VAULT)
    with pytest.raises(ValueError, match="Access verifier"):
        create_app(Tier.VAULT, public, vault)


def test_vault_app_rejects_requests_without_access(bundles: Path, rsa_key) -> None:
    public, vault = BundleStore(bundles, Tier.PUBLIC), BundleStore(bundles, Tier.VAULT)
    verifier = AccessVerifier(TEAM, AUD, keys=_StaticKeys(rsa_key.public_key()))
    client = create_app(Tier.VAULT, public, vault, verifier=verifier).server.test_client()
    assert client.get("/").status_code == 403
    assert client.get("/_dash-layout").status_code == 403
    assert client.get("/healthz").status_code == 200
    ok = client.get("/", headers={"Cf-Access-Jwt-Assertion": _token(rsa_key)})
    assert ok.status_code == 200
    assert ok.headers["Cache-Control"] == "private, no-store"
    assert "frame-ancestors 'none'" in ok.headers["Content-Security-Policy"]


def test_public_app_serves_without_access(bundles: Path) -> None:
    client = create_app(Tier.PUBLIC, BundleStore(bundles, Tier.PUBLIC)).server.test_client()
    resp = client.get("/_dash-layout")
    assert resp.status_code == 200
    assert b"run-select" not in resp.data


def test_pages_render_from_bundles(bundles: Path) -> None:
    from election_prediction.dashboard import app as app_mod

    public, vault = BundleStore(bundles, Tier.PUBLIC), BundleStore(bundles, Tier.VAULT)
    for page in (app_mod.page_overview, app_mod.page_map, app_mod.page_races):
        assert page(vault, "refresh_2026-10-22", "shrinkage=0.5")
    assert app_mod.page_diagnostics(vault)
    assert app_mod.page_history(public, "president", 2024)
    assert app_mod.page_runs([public, vault])


# --- figures ----------------------------------------------------------------------------


def test_house_strip_marks_fallback_seats_hollow() -> None:
    seats = _seats().query("assumption == 'shrinkage=0.5'")
    fig = figures.house_strip(seats)
    solid, hollow = fig.data
    assert solid.marker.symbol == "circle" and len(solid.x) == 2
    assert hollow.marker.symbol == "circle-open" and len(hollow.x) == 1


def test_history_map_never_colours_uncontested_races(race_results: Path) -> None:
    df = pd.read_parquet(race_results)
    df["race_type"] = "gen"
    fig = figures.history_map(df, "us_senate", 2024)
    assert len(fig.data) == 2
    assert len(fig.data[0].locations) == 0
    assert list(fig.data[1].locations) == ["KS"]


def test_interval_is_clipped() -> None:
    lo, hi = figures.interval_90(pd.Series([0.02, 0.98]), pd.Series([0.1, 0.1]))
    assert lo.min() == 0 and hi.max() == 1


def test_races_table_labels_districts() -> None:
    t = races_table(_seats().query("assumption == 'shrinkage=0.5'"))
    assert {"VA-01", "TX-02", "AL-01", "KS", "FL"} == set(t["Race"])

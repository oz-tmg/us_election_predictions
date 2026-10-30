#!/usr/bin/env python
"""2026 House and Senate projection from fitted baselines + the specials environment.

Run from the repo root. Reads only gold tables and the compiled specials table, so it is
reproducible from a clean checkout once ``ep-build-p1`` has run.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, "src")

from election_prediction.data import special_elections as se  # noqa: E402
from election_prediction.features import (
    candidacy,
    plan_versions,
    race_universe,
    senate_roster,
    transferred_priors,
)  # noqa: E402
from election_prediction.features.incumbency import normalize_name  # noqa: E402
from election_prediction.geography import reference as ref  # noqa: E402
from election_prediction.models import simulation  # noqa: E402
from election_prediction.models.baseline import house, projection, senate  # noqa: E402
from election_prediction.models.baseline import national_environment as ne  # noqa: E402

GOLD = "data/gold"
REPORTS = "reports"
N_SIMS = 20_000


def main(
    *,
    preregister: bool = False,
    as_of: str | None = None,
    reports_dir: Path = Path(REPORTS),
    correlation_params: simulation.CorrelationParams | None = None,
    senate_correlation_params: simulation.CorrelationParams | None = None,
    senate_features: list[str] | None = None,
) -> dict:
    """Project the 2026 band.

    ``senate_features`` selects the Senate specification (default: ``senate.DEFAULT_FEATURES``;
    a refresh passes the one its promotion gate selected).
    """
    stamp = as_of or date.today().isoformat()
    reports_dir.mkdir(parents=True, exist_ok=True)
    # ---- national environment: the estimator contract (NE-001) --------------
    # The specials mean enters through ``national_environment.from_specials`` as a *band*
    # over the shrinkage factor, never as a point: ``projectable`` refuses an unidentified
    # point, so the loop below iterates a contract rather than a specials-specific frame.
    specials = se.compute_overperformance(se.read_compiled("data/reference/special_elections_2025_2026.csv"))
    est = se.national_environment_estimate(specials)

    house_panel = pd.read_parquet(f"{GOLD}/house_panel.parquet")
    nat = house_panel.groupby("cycle")["national_dem_share"].first()
    base_2024 = float(nat.loc[2024])

    env = ne.from_specials(
        est,
        baseline_national_dem_share=base_2024,
        snapshot_date=str(specials["retrieved_on"].max()) if "retrieved_on" in specials else None,
    )
    sweep = ne.projectable(env)
    prov = env.provenance
    print(
        f"national environment: {env.estimator} (status={env.status}, identified={env.identified})\n"
        f"specials: n={prov['n']}  mean overperformance {prov['mean_overperformance']:+.4f} "
        f"(se {prov['std_error']:.4f})"
    )
    print(f"2024 House national model input (contested races, total-vote weighted): {base_2024:.4f}\n")
    print("implied national environment by shrinkage factor")
    print(sweep.drop(columns=["assumption"]).round(4).to_string(index=False))

    # ---- fit the models on all history -----------------------------------
    hmodel = house.fit_full(house_panel)
    hsigma = hmodel.resid_sigma_
    spanel = pd.read_parquet(f"{GOLD}/senate_panel.parquet")
    smodel = senate.fit_full(spanel, senate_features)
    ssigma = smodel.resid_sigma_
    print(f"\nfitted resid sigma: house {hsigma:.4f}  senate {ssigma:.4f}")

    universe = pd.read_parquet(f"{GOLD}/race_universe_2026.parquet")
    roster_paths = sorted(
        p
        for p in Path("data/reference").glob("senate_roster_*.csv")
        if p.stem.removeprefix("senate_roster_") <= stamp
    )
    if not roster_paths:
        raise ValueError("a dated official Senate roster is required for a current projection")
    roster = senate_roster.load_roster(roster_paths[-1])
    specials_schedule = pd.read_csv("data/reference/senate_specials_2026.csv")
    universe, _ = race_universe.build_race_universe(
        pd.read_parquet("data/silver/election_returns.parquet"),
        pd.read_parquet(f"{GOLD}/race_results.parquet"),
        cycle=2026,
        seat_universe=universe[universe.office.eq("us_house")],
        plans=plan_versions.PlanVersions.load(),
        senate_roster=roster,
        senate_specials=specials_schedule,
    )
    lagged_nat = base_2024  # the universe's prior is the 2024 result; match its national basis
    prior_cycles = pd.to_numeric(
        universe["prior_source"].str.extract(r"last_result_(\d{4})", expand=False), errors="coerce"
    )
    universe[projection.PRIOR_NATIONAL_COLUMN] = prior_cycles.map(nat)

    current_house_paths = sorted(
        p
        for p in Path("data/reference").glob("house_roster_*.csv")
        if p.stem.removeprefix("house_roster_") <= stamp
    )
    if current_house_paths:
        current_house = pd.read_csv(current_house_paths[-1]).fillna("")
        current_house["geography_id"] = [
            f"state:{ref.by_postal(s).fips}|district:cong_{int(d):02d}"
            for s, d in zip(current_house.state_po, current_house.district_num, strict=True)
        ]
        if len(current_house) != 435 or current_house.geography_id.duplicated().any():
            raise ValueError("current House roster must cover exactly 435 unique voting districts")
        for column in ("incumbent_name", "incumbent_party"):
            mapping = current_house.set_index("geography_id")[column]
            changed = universe.office.eq("us_house") & universe.geography_id.isin(mapping.index)
            universe.loc[changed, column] = universe.loc[changed, "geography_id"].map(mapping)
        universe.loc[universe.incumbent_name.eq(""), "incumbent_name"] = "VACANT"

    # ---- FEC filings layer (P0-003), when ep-build-fec has run -------------------
    # ``projection`` reads ``RESOLVED_PARTY_COLUMN`` to fill a seat whose party the returns
    # leave null (Lummis, WY). The FEC build writes that column to its own gold table, not
    # back into the universe, so it has to be joined here or the fallback runs forever.
    filings_path = Path(f"{GOLD}/incumbent_filings_2026.parquet")
    if filings_path.is_file():
        fil = pd.read_parquet(filings_path)[
            ["geography_id", "office", "incumbent_name", "incumbent_status", projection.RESOLVED_PARTY_COLUMN]
        ].rename(columns={"incumbent_name": "filing_incumbent_name"})
        universe = universe.drop(columns=["incumbent_status"]).merge(
            fil, on=["geography_id", "office"], how="left", validate="one_to_one"
        )
        same_holder = universe.incumbent_name.map(normalize_name).eq(
            universe.filing_incumbent_name.map(normalize_name)
        )
        universe.loc[~same_holder, "incumbent_status"] = "unknown"
        universe.loc[~same_holder, projection.RESOLVED_PARTY_COLUMN] = pd.NA
        print(f"\nfilings joined: incumbent_status {universe['incumbent_status'].value_counts().to_dict()}")
    else:
        print("\nfilings NOT joined (run ep-build-fec): unlabelled incumbents project as open seats.")

    universe, candidacy_coverage = candidacy.attach(
        universe, Path("data/reference/candidacy_2026.csv"), as_of=stamp
    )
    universe, transfer_provenance = transferred_priors.attach(
        universe,
        Path("data/reference/transferred_priors_2026.csv"),
        cycle=2026,
        plans=plan_versions.PlanVersions.load(),
    )
    print(f"candidacy evidence: {candidacy_coverage}")

    # Class II and the sourced special-election seats are removed from the holdover roster.
    composition = senate_roster.reconcile(roster, universe[universe.office.eq("us_senate")])
    dem_holdovers = composition["democratic_holdovers"]
    print(
        f"\nsenate holdover seats not up in 2026: {composition['holdovers']}  "
        f"Democratic-held: {dem_holdovers}"
    )

    # Composition comes from the dated official roster, including independents' caucuses.
    print(
        f"  official roster caucuses: Democratic {composition['current_democratic_caucus']}, "
        f"Republican {composition['current_republican_caucus']}; 100 seats reconciled"
    )

    # State presidential lean must cover all 50 states, so it comes from the presidential
    # panel. senate_panel only holds states that had a Senate race in a given cycle, which
    # silently dropped 17 of the 33 seats up in 2026.
    pres = pd.read_parquet(f"{GOLD}/presidential_panel.parquet")
    p24 = pres[pres["cycle"] == 2024].copy()
    p24["state_pres_lean"] = p24["two_party_dem_share"] - p24["national_dem_share"]
    pres_ref = p24[["state_po", "state_pres_lean"]].drop_duplicates("state_po")

    # ---- district boundaries (RD-002) ----------------------------------------
    # A redrawn seat that has no prior on its new boundaries is projected from its state's
    # lean with a sigma widened by how much district leans vary *within* a state -- measured
    # from the latest cycle's panel, not assumed. The plan-version register (RD-001) now
    # supplies every House row's boundary_confidence, so `allow_unverified` is gone: a seat
    # in a redrawn state loses its old-number prior instead of being silently projected as
    # unchanged. If the register were ever missing, project_house would refuse outright,
    # which is the behaviour we want.
    latest = house_panel[house_panel["cycle"] == house_panel["cycle"].max()].dropna(subset=["district_lean"])
    within = latest["district_lean"] - latest.groupby("state_po")["district_lean"].transform("mean")
    fallback_lean_sd = float((within**2).mean() ** 0.5)

    # ---- project + simulate across the shrinkage band ----------------------
    rows = []
    seat_frames = []  # per-seat predictions, kept for the pre-registration
    for _, s in sweep.iterrows():
        hproj, hcov = projection.project_house(
            universe,
            hmodel,
            national_dem_share=float(s["national_dem_share"]),
            lagged_national_dem_share=lagged_nat,
            resid_sigma=hsigma,
            pres_reference=pres_ref,
            fallback_lean_sd=fallback_lean_sd,
        )
        hsim = _simulate(
            hproj, total_seats=house.VOTING_SEATS, with_win_probs=True, params=correlation_params
        )
        hproj = hproj.assign(dem_win_prob=hsim.pop("dem_win_prob"))

        # The Senate model carries no national term, so the environment enters only as an
        # explicit uniform-swing scenario -- half the applied margin swing, in share points.
        swing = float(s["applied_margin_swing"]) / 2.0
        sproj, scov = projection.project_senate(
            universe,
            smodel,
            pres_ref,
            midterm_penalty=1.0,  # Republican president in 2026
            resid_sigma=ssigma,
            uniform_swing=swing,
        )
        ssim = _simulate(
            sproj,
            total_seats=100,
            holdover_dem=dem_holdovers,
            with_win_probs=True,
            params=senate_correlation_params,
        )
        sproj = sproj.assign(dem_win_prob=ssim.pop("dem_win_prob"))

        for frame, off in ((hproj, "us_house"), (sproj, "us_senate")):
            keep = frame.copy()
            keep["assumption"] = s["assumption"]
            keep["office"] = off
            seat_frames.append(keep)
        rows.append(
            {
                "assumption": s["assumption"],
                "shrinkage": s["shrinkage"],
                "nat_share": round(float(s["national_dem_share"]), 4),
                "house_mean_seats": round(hsim["mean_dem_seats"], 1),
                "house_5th": hsim["seats_5th"],
                "house_95th": hsim["seats_95th"],
                "house_p_dem": round(hsim["p_dem_control"], 3),
                "sen_dem_seats_up": round(ssim["mean_dem_seats"] - dem_holdovers, 1),
                "sen_mean_total": round(ssim["mean_dem_seats"], 1),
                "sen_p_dem": round(ssim["p_dem_control"], 3),
            }
        )
    results = pd.DataFrame(rows)
    print(
        f"\nhouse seats projected: {hcov['seats_projected']}/{hcov['seats_in_roster']}"
        f"   senate seats up: {scov['seats_projected']}\n"
    )
    print(results.drop(columns=["assumption"]).to_string(index=False))

    # ---- band-level conclusions, as text (NE-001 acceptance criterion) -------
    # The band is the output. What it says about control is stated, not left for the
    # reader to infer from the table -- and a flip inside the band is named as such.
    conclusions = [
        ne.control_conclusion(results, chamber="House", p_column="house_p_dem"),
        ne.control_conclusion(results, chamber="Senate", p_column="sen_p_dem"),
    ]
    print()
    for line in conclusions:
        print(line)

    # Machine-readable sibling so the band can be diffed across runs rather than re-read
    # from formatted text.
    payload = {
        "generated_on": stamp,
        "national_environment": env.to_dict(),
        "band_results": results.to_dict(orient="records"),
        "conclusions": conclusions,
        "house_coverage": hcov,
        "senate_coverage": scov,
        "senate_composition": composition,
        "correlation_parameters": {
            "house": vars(correlation_params or simulation.CorrelationParams()),
            "senate": vars(senate_correlation_params or simulation.CorrelationParams()),
        },
        "candidacy_coverage": candidacy_coverage,
        "transfer_provenance": transfer_provenance,
        "senate_specification": {
            "features": list(smodel.features),
            "coefficients": dict(
                zip(["intercept", *smodel.features], [float(c) for c in smodel.coef_], strict=True)
            ),
            "resid_sigma": float(ssigma),
        },
        "seats": pd.concat(seat_frames, ignore_index=True).to_dict(orient="records"),
    }
    out_path = reports_dir / f"national_environment_{stamp}.json"
    out_path.write_text(json.dumps(payload, indent=2, default=str))
    print(f"\nband written to {out_path}")
    status = universe["incumbent_status"].value_counts().to_dict()
    filed, not_found = status.get("filed", 0), status.get("not_found", 0)
    if filed:
        print(
            f"\nincumbency: {filed} sitting members have an FEC filing for 2026; {not_found} were not "
            "found in the roster (not spelled 'retired': absence misses most departures). "
            f"Candidacy verified for {candidacy_coverage['verified']}; "
            f"assumed for {candidacy_coverage['unknown']} remaining seats."
        )
    else:
        print("\nincumbency assumed (not verified): every sitting member runs and is renominated.")

    # ---- boundary treatment, stated as text (RD-002 acceptance criterion) -----
    by_conf = hcov["seats_by_boundary_confidence"]
    by_src = hcov["seats_by_source"]
    print(f"district boundaries: {by_conf}   projected by source: {by_src}")
    if hcov["boundaries_assumed_unchanged"]:
        print(
            f"boundaries assumed unchanged (NOT verified): {hcov['boundaries_assumed_unchanged']} House "
            "seats are projected from their 2024 result on the assumption that the district is the same "
            "territory. The plan-version register (RD-001) should have supplied this; seeing it here "
            "means the register was not loaded. See docs/redistricting-change-plan.md."
        )
    if hcov["redrawn_states"]:
        n_redrawn = hcov["seats_by_boundary_confidence"].get("redrawn", 0)
        n_fallback = hcov["seats_by_source"].get("fallback_state_lean", 0)
        print(
            f"redrawn states (sourced, RD-001): {', '.join(hcov['redrawn_states'])} -- {n_redrawn} seats. "
            "These use a different congressional map in 2026 than in 2024, so their 2024 result describes "
            "different territory and is discarded rather than reused. "
            f"{n_fallback} seats still lack a transferred prior and fall back to state lean "
            f"with sigma {hcov['fallback_sigma']:.4f} "
            f"(residual {hcov['resid_sigma']:.4f} widened by within-state lean sd "
            f"{hcov['fallback_lean_sd']:.4f})."
        )
    if preregister:
        _write_preregistration(
            results=results,
            seat_frames=seat_frames,
            env=env,
            hcov=hcov,
            scov=scov,
            conclusions=conclusions,
            universe=universe,
            specials=specials,
        )

    if hcov.get("litigation_active_states"):
        print(
            f"litigation active: {', '.join(hcov['litigation_active_states'])} -- a court could still move "
            "these maps before election day. This is reported, not routed on: it says nothing about whether "
            "this cycle's territory matches last cycle's. Missouri is the case in point -- it is enjoined "
            "from using its 2025 map and votes its 2022 map, so its territory is unchanged and its prior "
            "is valid."
        )
    return payload


def _declared_defects(hcov: dict, universe: pd.DataFrame) -> list[str]:
    """What I expect to be wrong, written down before the event (see reporting.preregistration)."""
    n_fallback = hcov["seats_by_source"].get("fallback_state_lean", 0)
    status = universe["incumbent_status"].value_counts().to_dict()
    unknown = int(universe["incumbent_running"].isna().sum())
    return [
        f"{n_fallback} House seats have no prior on their 2026 boundaries. They use their state's "
        f"presidential lean with sigma {hcov['fallback_sigma']:.4f} against a modelled "
        f"{hcov['resid_sigma']:.4f}. Live vote transfer remains incomplete, so these seats are the "
        "least informed part of the chamber and should show visibly worse per-seat scores.",
        f"Renomination remains assumed for {unknown} seats without dated candidacy evidence. "
        f"{status.get('filed', 0)} holders have a 2026 FEC filing and "
        f"{status.get('not_found', 0)} were not found. A filing is not nomination evidence.",
        "The national environment is unidentified. The shrinkage factor is an assumption swept "
        "over, not an estimate, and no historical calibration for it exists yet (NE-002 open).",
        f"Maps in {', '.join(hcov.get('litigation_active_states', [])) or 'no states'} are under live "
        "litigation and could move before election day. The register records the plan in effect at "
        "the snapshot date; a late court order would invalidate those seats' boundaries.",
        "The simulation's correlated-error split (45/25/30 national/regional/state) is asserted, "
        "not promoted from residual estimates: full-universe validation is incomplete. "
        "Chamber-level interval width is sensitive to it.",
    ]


def _write_preregistration(*, results, seat_frames, env, hcov, scov, conclusions, universe, specials) -> None:
    from election_prediction.reporting import preregistration as prereg

    seats = pd.concat(seat_frames, ignore_index=True)
    for col in ("litigation_risk", "boundary_confidence"):
        if col not in seats.columns:
            seats[col] = pd.NA
    payload = prereg.build(
        election_date=str(universe["election_date"].iloc[0]),
        band=results,
        seats=seats,
        environment=env.to_dict(),
        house_coverage=hcov,
        senate_coverage=scov,
        conclusions=conclusions,
        declared_defects=_declared_defects(hcov, universe),
        data_snapshots={
            "MEDSL certified returns": "2026-09-30 (cycles 1976-2024)",
            "Census ACS 5-year": "vintage 2023",
            "FEC filings": "2026-09-15",
            "plan-version register (RD-001)": "verified 2026-09-30",
            "compiled special elections": (
                f"{len(specials)} rows compiled through {specials['election_date'].max()}; "
                f"{env.provenance['n']} used after same-party and seat double-count gating"
            ),
        },
    )
    json_path, md_path = prereg.write(payload, REPORTS)
    csv_path = Path(REPORTS) / f"preregistration_{payload['election_date']}_seats.csv"
    seats[prereg.SEAT_COLUMNS].to_csv(csv_path, index=False)
    print(f"\nPRE-REGISTERED -> {json_path}\n               -> {md_path}\n               -> {csv_path}")
    print(f"predictions SHA-256: {payload['predictions_sha256']}")
    print("This artefact is sealed. Scoring rules are fixed; see its evaluation_plan block.")


def _simulate(
    proj: pd.DataFrame,
    *,
    total_seats: int,
    holdover_dem: int = 0,
    with_win_probs: bool = False,
    params: simulation.CorrelationParams | None = None,
) -> dict:
    """Seat distribution from correlated draws. ``with_win_probs`` adds the per-seat column,
    which the pre-registration needs: a chamber total cannot be scored for calibration."""
    from election_prediction.geography import reference as ref

    regions = [ref.by_postal(s).census_region for s in proj["state_po"]]
    sim = simulation.simulate_shares(
        proj["mean_dem_share"].to_numpy(), proj["sigma"].to_numpy(), regions, n_sims=N_SIMS, params=params
    )
    dist = simulation.seat_distribution(sim, proj["state_po"].tolist(), total_seats=total_seats)
    if with_win_probs:
        dist = {**dist, "dem_win_prob": (sim > 0.5).mean(axis=0)}
    if holdover_dem:
        # Shift the whole distribution by seats not on the ballot, then re-derive control.
        dem = (sim > 0.5).sum(axis=1) + holdover_dem
        dist = {
            **dist,
            "mean_dem_seats": float(dem.mean()),
            "p_dem_control": float((dem > total_seats / 2).mean()),
            "seats_5th": float(pd.Series(dem).quantile(0.05)),
            "seats_95th": float(pd.Series(dem).quantile(0.95)),
        }
    return dist


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preregister", action="store_true")
    parser.add_argument("--as-of", default=None)
    parser.add_argument("--reports-dir", type=Path, default=Path(REPORTS))
    args = parser.parse_args()
    main(preregister=args.preregister, as_of=args.as_of, reports_dir=args.reports_dir)

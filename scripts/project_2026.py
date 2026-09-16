#!/usr/bin/env python
"""2026 House and Senate projection from fitted baselines + the specials environment.

Run from the repo root. Reads only gold tables and the compiled specials table, so it is
reproducible from a clean checkout once ``ep-build-p1`` has run.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, "src")

from election_prediction.data import special_elections as se  # noqa: E402
from election_prediction.models import simulation  # noqa: E402
from election_prediction.models.baseline import house, projection, senate  # noqa: E402

GOLD = "data/gold"
N_SIMS = 20_000


def main() -> None:
    # ---- national environment from specials -------------------------------
    specials = se.compute_overperformance(se.read_compiled("data/reference/special_elections_2025_2026.csv"))
    est = se.national_environment_estimate(specials)

    house_panel = pd.read_parquet(f"{GOLD}/house_panel.parquet")
    nat = house_panel.groupby("cycle")["national_dem_share"].first()
    base_2024 = float(nat.loc[2024])

    sweep = se.shrinkage_sensitivity(est, baseline_national_dem_share=base_2024)
    print(
        f"specials: n={est['n']}  mean overperformance {est['mean_overperformance']:+.4f} "
        f"(se {est['std_error']:.4f})"
    )
    print(f"2024 House national two-party Dem share: {base_2024:.4f}\n")
    print("implied national environment by shrinkage factor")
    print(sweep.round(4).to_string(index=False))

    # ---- fit the models on all history -----------------------------------
    hmodel = house.fit_full(house_panel)
    hsigma = hmodel.resid_sigma_
    spanel = pd.read_parquet(f"{GOLD}/senate_panel.parquet")
    smodel = senate.fit_full(spanel)
    ssigma = smodel.resid_sigma_
    print(f"\nfitted resid sigma: house {hsigma:.4f}  senate {ssigma:.4f}")

    universe = pd.read_parquet(f"{GOLD}/race_universe_2026.parquet")
    lagged_nat = float(nat.loc[2022])  # basis for 2024 district leans

    # ---- FEC filings layer (P0-003), when ep-build-fec has run -------------------
    # ``projection`` reads ``RESOLVED_PARTY_COLUMN`` to fill a seat whose party the returns
    # leave null (Lummis, WY). The FEC build writes that column to its own gold table, not
    # back into the universe, so it has to be joined here or the fallback runs forever.
    filings_path = Path(f"{GOLD}/incumbent_filings_2026.parquet")
    if filings_path.is_file():
        fil = pd.read_parquet(filings_path)[
            ["geography_id", "office", "incumbent_status", projection.RESOLVED_PARTY_COLUMN]
        ]
        universe = universe.drop(columns=["incumbent_status"]).merge(
            fil, on=["geography_id", "office"], how="left"
        )
        print(f"\nfilings joined: incumbent_status {universe['incumbent_status'].value_counts().to_dict()}")
    else:
        print("\nfilings NOT joined (run ep-build-fec): unlabelled incumbents project as open seats.")

    # ---- Senate holdovers, derived rather than asserted --------------------
    # 2026 is Class II. Classes III (elected 2022) and I (elected 2024) hold over, and
    # every one of those seats is a regular election in our returns -- so the non-2026
    # composition comes from our own data rather than an external tally. Counting is by
    # *seat*, not by state: a state holds two seats in different classes.
    race_table = pd.read_parquet(f"{GOLD}/race_results.parquet")
    sen = race_table[(race_table["office"] == "us_senate") & (race_table["cycle"].isin([2022, 2024]))]
    holdovers = sen[~sen["race_id"].str.contains("special")].copy()
    caucus_dem = [
        (r["state_po"], int(r["cycle"])) in projection.INDEPENDENT_DEM_CAUCUS for _, r in holdovers.iterrows()
    ]
    dem_holdovers = int(
        ((holdovers["two_party_dem_share"] > 0.5) | pd.Series(caucus_dem, index=holdovers.index)).sum()
    )
    print(f"\nsenate holdover seats not up in 2026: {len(holdovers)}  Democratic-held: {dem_holdovers}")
    print(f"  (includes {len(projection.INDEPENDENT_DEM_CAUCUS)} independents who caucus with Democrats)")

    # Reconciliation, printed whether or not it closes. Derived composition = Democratic
    # holdovers + Democratic-held seats on the 2026 ballot. It currently lands 2 short of
    # the chamber's actual Democratic caucus, which is the unresolved candidate/party
    # crosswalk (P0-003) showing up again: two-party share cannot identify every member's
    # affiliation. The projection therefore likely understates Democratic Senate seats by
    # about two, and that is reported rather than absorbed into the numbers.
    sen_up = universe[universe["office"] == "us_senate"]
    dem_up_now = int((sen_up["incumbent_party"] == "DEMOCRAT").sum())
    print(
        f"  derived current Democratic caucus: {dem_holdovers} holdover + {dem_up_now} up "
        f"= {dem_holdovers + dem_up_now} of {len(holdovers) + len(sen_up)} seats"
    )
    print("  NOTE: 2 seats short of the actual Democratic caucus -- unresolved party crosswalk (P0-003).")

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
    # from the latest cycle's panel, not assumed. Until the plan-version register (RD-001)
    # is compiled every House row is ``unverified``; opting in projects them as unchanged,
    # and that assumption is printed with the incumbency one below.
    latest = house_panel[house_panel["cycle"] == house_panel["cycle"].max()].dropna(subset=["district_lean"])
    within = latest["district_lean"] - latest.groupby("state_po")["district_lean"].transform("mean")
    fallback_lean_sd = float((within**2).mean() ** 0.5)

    # ---- project + simulate across the shrinkage band ----------------------
    rows = []
    for _, s in sweep.iterrows():
        hproj, hcov = projection.project_house(
            universe,
            hmodel,
            national_dem_share=float(s["national_dem_share"]),
            lagged_national_dem_share=lagged_nat,
            resid_sigma=hsigma,
            pres_reference=pres_ref,
            fallback_lean_sd=fallback_lean_sd,
            allow_unverified=True,
        )
        hsim = _simulate(hproj, total_seats=house.VOTING_SEATS)

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
        ssim = _simulate(sproj, total_seats=100, holdover_dem=dem_holdovers)
        rows.append(
            {
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
    print(
        f"\nhouse seats projected: {hcov['seats_projected']}/{hcov['seats_in_roster']}"
        f"   senate seats up: {scov['seats_projected']}\n"
    )
    print(pd.DataFrame(rows).to_string(index=False))
    status = universe["incumbent_status"].value_counts().to_dict()
    filed, not_found = status.get("filed", 0), status.get("not_found", 0)
    if filed:
        print(
            f"\nincumbency: {filed} sitting members have an FEC filing for 2026; {not_found} were not "
            "found in the roster (not spelled 'retired': absence misses most departures). "
            "Renomination is assumed for all -- primaries are not compiled."
        )
    else:
        print("\nincumbency assumed (not verified): every sitting member runs and is renominated.")

    # ---- boundary treatment, stated as text (RD-002 acceptance criterion) -----
    by_conf = hcov["seats_by_boundary_confidence"]
    by_src = hcov["seats_by_source"]
    print(f"district boundaries: {by_conf}   projected by source: {by_src}")
    if hcov["boundaries_assumed_unchanged"]:
        print(
            f"boundaries assumed unchanged (not verified): {hcov['boundaries_assumed_unchanged']} House "
            "seats are projected from their 2024 result on the assumption that the district is the same "
            "territory. Several states use a different congressional map in 2026 than in 2024; until the "
            "plan-version register (RD-001) is compiled this projection cannot tell which. "
            "See docs/redistricting-change-plan.md."
        )
    if hcov["redrawn_states"]:
        print(
            f"redrawn/pending states: {', '.join(hcov['redrawn_states'])} -- seats without a transferred "
            f"prior use the state presidential lean with sigma {hcov['fallback_sigma']:.4f} "
            f"(residual {hcov['resid_sigma']:.4f} widened by within-state lean sd "
            f"{hcov['fallback_lean_sd']:.4f})."
        )


def _simulate(proj: pd.DataFrame, *, total_seats: int, holdover_dem: int = 0) -> dict:
    from election_prediction.geography import reference as ref

    regions = [ref.by_postal(s).census_region for s in proj["state_po"]]
    sim = simulation.simulate_shares(
        proj["mean_dem_share"].to_numpy(), proj["sigma"].to_numpy(), regions, n_sims=N_SIMS
    )
    dist = simulation.seat_distribution(sim, proj["state_po"].tolist(), total_seats=total_seats)
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
    main()

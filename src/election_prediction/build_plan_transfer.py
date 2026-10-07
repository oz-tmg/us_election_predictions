"""Build a transferred prior: old precinct results on new district lines (RD-003).

173 of 435 House seats vote in November 2026 on territory different from their 2024
result, so their priors are discarded and they fall back to a state presidential lean with
an inflated sigma. This build is what replaces that fallback — but only once the error it
introduces has been *measured*, which is what the ``--backtest`` path does.

The pilot is Virginia 2020 → 2022, chosen because both maps and both generals are observed,
so the answer is known and the method can be scored rather than asserted.

What happens, in order:

1. **Precinct results to blocks.** A precinct's votes are apportioned across its blocks in
   proportion to block population (``POP20``). This is the only modelled step in the chain:
   block-to-precinct and block-to-district are both authoritative assignments.
2. **County-aggregate ballots to blocks.** Virginia reported 63.5% of its 2020 presidential
   vote in two pseudo-precincts per locality (``# AB - CENTRAL ABSENTEE PRECINCT`` and
   ``## PROVISIONAL``), which belong to no precinct at all. They are spread across their
   county's blocks in proportion to the *precinct-level vote already placed there* —
   turnout, not population, for the same reason ``features/cd_baseline`` weights on
   turnout: it does not assume absentee voters are distributed like residents.
3. **Blocks to new districts**, and the three confidence components, via
   ``features/plan_transfer.transfer``.
4. **Score it** against the two comparators the plan names — no prior at all, and the
   state-lean fallback in use today — via ``features/plan_transfer.backtest_transfer``.

Run:  ep-build-plan-transfer --state VA --from-cycle 2020 --to-plan cd118 --backtest 2022
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

import pandas as pd

from .data import governor, medsl
from .features import block_crosswalk, cd_baseline, plan_transfer
from .models.baseline import basis_mapping, projection

#: Registry ids, asserted by ``plan_transfer.assert_sources_registered`` before any run.
#: ``rdh_precinct_boundaries`` is registered but **not used**: Census's own Block Assignment
#: Files supply the precinct-to-block link, so no commercial or account-gated boundary file
#: is needed for the pilot. It stays in the required set because the gate is about having
#: reviewed a licence, and dropping a source from the gate to make a run succeed is exactly
#: the move the gate exists to prevent.
SOURCES = {
    "census_pl94171_2020": "registered 2026-09-30; POP20 used in place of VAP, see --weight",
    "census_baf_2020": "acquired 2026-10-02, data/raw/source=census_baf/",
    "rdh_precinct_boundaries": "registered 2026-09-30; not required by this path",
}

#: Virginia's county-level pseudo-precincts. They are identified by the leading marker
#: Virginia uses, not by name matching, so a renamed absentee precinct still lands here.
PSEUDO_PRECINCT_PREFIXES = ("#",)


def precinct_votes(path: Path) -> tuple[pd.DataFrame, dict]:
    """Two-party presidential votes per precinct for one state's precinct file.

    Reuses ``cd_baseline``'s reader and mode collapse, so a transfer and a CD baseline built
    from the same file cannot disagree about how many votes were cast.
    """
    raw = cd_baseline.read_president_and_house(path)
    if raw.empty:
        raise ValueError(f"{path.name}: no presidential rows")
    collapsed, _ = governor.collapse_precinct_modes(raw)
    pres = collapsed[collapsed["office"] == "president"].copy()
    parties = pres.apply(medsl._canon_party, axis=1, result_type="expand")
    pres["party_simplified"] = parties[1]
    pres["_major"] = cd_baseline._major_party(pres)
    pres["county_fips"] = pres["county_fips"].astype(str).str.strip()
    pres["precinct"] = pres["precinct"].astype(str).str.strip()

    out = (
        pres.assign(
            dem_votes=pres["candidatevotes"].where(pres["_major"] == "DEMOCRAT", 0.0),
            rep_votes=pres["candidatevotes"].where(pres["_major"] == "REPUBLICAN", 0.0),
        )
        .groupby(["county_fips", "precinct"], as_index=False)[["dem_votes", "rep_votes"]]
        .sum()
    )
    out["is_pseudo"] = out["precinct"].str.startswith(PSEUDO_PRECINCT_PREFIXES)
    # Normalised identically to the crosswalk side; a numeric parse destroyed North
    # Carolina's alphanumeric codes and left 55% of its votes unplaced.
    out["vtd_key"] = out["precinct"].map(block_crosswalk.normalise_precinct_code)
    out.loc[out["is_pseudo"], "vtd_key"] = None
    out["precinct_id"] = out["county_fips"] + "|" + out["precinct"]
    two_party = out["dem_votes"] + out["rep_votes"]
    return out, {
        "precincts": int(len(out)),
        "two_party_votes": float(two_party.sum()),
        "pseudo_precincts": int(out["is_pseudo"].sum()),
        "share_in_pseudo_precincts": round(float(two_party[out["is_pseudo"]].sum() / two_party.sum()), 4),
    }


def apportion_to_blocks(
    votes: pd.DataFrame, block_vtd: pd.DataFrame, block_pop: pd.DataFrame
) -> tuple[pd.DataFrame, dict]:
    """Spread each precinct's votes over its blocks, then county blocks for the rest.

    Returns block-level ``precinct_id, block_id, dem_votes, rep_votes``. Votes are conserved
    exactly in both passes; what cannot be placed at all is reported, never redistributed
    across the state.
    """
    blocks = block_vtd.merge(block_pop[["block_id", "pop"]], on="block_id", how="left")
    blocks["pop"] = blocks["pop"].fillna(0.0)

    real = votes[~votes["is_pseudo"] & votes["vtd_key"].notna()]
    keyed = blocks.dropna(subset=["vtd_key"])
    merged = real.merge(
        keyed[["block_id", "county_fips", "vtd_key", "pop"]],
        on=["county_fips", "vtd_key"],
        how="inner",
    )

    # Pass 1: population weight inside the precinct. A precinct whose blocks are all
    # unpopulated is split evenly rather than dropped -- it still cast votes.
    totals = merged.groupby("precinct_id")["pop"].transform("sum")
    counts = merged.groupby("precinct_id")["block_id"].transform("size")
    merged["weight"] = (merged["pop"] / totals).where(totals > 0, 1.0 / counts)
    placed = pd.DataFrame(
        {
            "precinct_id": merged["precinct_id"],
            "county_fips": merged["county_fips"],
            "block_id": merged["block_id"],
            "dem_votes": merged["dem_votes"] * merged["weight"],
            "rep_votes": merged["rep_votes"] * merged["weight"],
        }
    )

    matched_ids = set(merged["precinct_id"])
    # Reported for visibility, then allocated by county in pass 2 rather than discarded.
    unmatched = real[~real["precinct_id"].isin(matched_ids)]

    # Pass 2: everything pass 1 could not place, weighted by the turnout it did place.
    #
    # This is *anything* unplaced, not only the precincts marked pseudo. A precinct whose
    # code does not resolve to a VTD is in exactly the same epistemic position as a
    # county-level absentee block: its county is known and its blocks are not. Dropping it
    # instead cost North Carolina 47% of its vote, because its one-stop and absentee batches
    # ("ABSEN 1-40", "OSAP 1-40", "ABSENTEE BY MAIL") are real vote carrying no VTD code and
    # do not begin with the "#" marker Virginia uses.
    pseudo = votes[~votes["precinct_id"].isin(matched_ids)]
    county_blocks = (
        placed.assign(two_party=placed["dem_votes"] + placed["rep_votes"])
        .groupby(["county_fips", "block_id"], as_index=False)["two_party"]
        .sum()
    )
    county_totals = county_blocks.groupby("county_fips", as_index=False)["two_party"].sum()
    county_blocks = county_blocks.merge(
        county_totals.rename(columns={"two_party": "_county_total"}), on="county_fips"
    )
    county_blocks = county_blocks[county_blocks["_county_total"] > 0].copy()
    county_blocks["weight"] = county_blocks["two_party"] / county_blocks["_county_total"]

    spread = pseudo.merge(county_blocks[["county_fips", "block_id", "weight"]], on="county_fips", how="inner")
    allocated = pd.DataFrame(
        {
            "precinct_id": spread["precinct_id"],
            "county_fips": spread["county_fips"],
            "block_id": spread["block_id"],
            "dem_votes": spread["dem_votes"] * spread["weight"],
            "rep_votes": spread["rep_votes"] * spread["weight"],
        }
    )

    unplaceable = pseudo[~pseudo["county_fips"].isin(set(county_blocks["county_fips"]))]
    out = pd.concat([placed, allocated], ignore_index=True)
    offered = float((votes["dem_votes"] + votes["rep_votes"]).sum())
    return out, {
        "precincts_matched_to_vtd": int(len(matched_ids)),
        "precincts_unmatched": int(len(unmatched)),
        # Did not resolve to a VTD. Not a loss: these go through county allocation below,
        # and what truly could not be placed is `votes_unplaceable`.
        "votes_unmatched_to_a_vtd": float((unmatched["dem_votes"] + unmatched["rep_votes"]).sum()),
        "unmatched_precincts": sorted(unmatched["precinct_id"].tolist())[:25],
        "votes_from_county_aggregates": float((allocated["dem_votes"] + allocated["rep_votes"]).sum()),
        "votes_unplaceable": float((unplaceable["dem_votes"] + unplaceable["rep_votes"]).sum()),
        "votes_offered": offered,
        "votes_placed": float((out["dem_votes"] + out["rep_votes"]).sum()),
    }


def _actual_from_house_returns(returns_path: Path, state: str, cycle: int) -> pd.DataFrame:
    """The new districts' observed two-party Democratic share, from certified returns."""
    df = pd.read_parquet(returns_path)
    rows = df[(df["office"] == "us_house") & (df["cycle"] == cycle) & (df["state_po"] == state)]
    rows = rows[rows["party_simplified"].isin(["DEMOCRAT", "REPUBLICAN"])]
    wide = (
        rows.assign(district_num=pd.to_numeric(rows["district_num"], errors="coerce"))
        .dropna(subset=["district_num"])
        .pivot_table(index="district_num", columns="party_simplified", values="candidatevotes", aggfunc="sum")
        .fillna(0.0)
    )
    for party in ("DEMOCRAT", "REPUBLICAN"):
        if party not in wide.columns:
            wide[party] = 0.0
    two = wide["DEMOCRAT"] + wide["REPUBLICAN"]
    return pd.DataFrame(
        {
            "state_po": state,
            "new_district": wide.index.astype(int),
            "actual_dem_share": (wide["DEMOCRAT"] / two.where(two > 0)).to_numpy(),
            "actual_two_party_votes": two.to_numpy(),
        }
    ).dropna(subset=["actual_dem_share"])


def same_office_control(baseline_path: Path, transferred: pd.DataFrame, state: str) -> dict:
    """Score the transfer against the *same office* measured directly on the new lines.

    The ``--backtest`` comparison is the operationally useful one — can a transferred prior
    beat the fallback at predicting the next House result — but it conflates two errors: the
    geography, and everything that separates a presidential share from a House share four
    years later. This control removes the second. ``cd_presidential_baseline_<cycle>`` is the
    presidential vote by district computed *directly* from precinct returns on the new
    lines, so comparing a transferred presidential prior against it leaves only the
    geography and the intervening national swing.

    The swing shows up as the **mean** error and the geography as the **standard
    deviation**, which is the distinction that matters: a projection models a national swing
    separately, so the quantity it needs from a transfer is the spread, not the bias. For
    Virginia 2020→2022 the mean is +0.019 (the Democratic decline from 2020 to 2024) and the
    spread is 0.016.
    """
    baseline = pd.read_parquet(baseline_path)
    rows = baseline[baseline["state_po"] == state.upper()]
    if rows.empty:
        return {"skipped": f"no {state} rows in {baseline_path.name}"}
    merged = transferred.merge(
        rows[["district_num", "baseline_dem_share", "baseline_quality"]].rename(
            columns={"district_num": "new_district"}
        ),
        on="new_district",
        how="inner",
    )
    if not len(merged):
        return {"skipped": "no district overlap with the directly measured baseline"}
    err = merged["transferred_dem_share"] - merged["baseline_dem_share"]
    return {
        "compared_against": baseline_path.name,
        "n_districts": int(len(merged)),
        "mae": round(float(err.abs().mean()), 5),
        # The national swing between the two cycles, not a transfer defect.
        "mean_error": round(float(err.mean()), 5),
        # The geography error, which is the number a projection needs.
        "sd_error": round(float(err.std(ddof=1)), 5) if len(merged) > 1 else None,
        "max_abs_error": round(float(err.abs().max()), 5),
        "worst": [
            {
                "new_district": int(r.new_district),
                "transferred": round(float(r.transferred_dem_share), 4),
                "measured": round(float(r.baseline_dem_share), 4),
                "error": round(float(r.transferred_dem_share - r.baseline_dem_share), 4),
                "unsplit_share": round(float(r.unsplit_share), 4),
                "old_district_majority_share": round(float(r.old_district_majority_share), 4),
            }
            for r in merged.reindex(err.abs().sort_values(ascending=False).index).head(5).itertuples()
        ],
    }


def _mapped_backtest(
    transferred: pd.DataFrame,
    actual: pd.DataFrame,
    state_lean: pd.DataFrame,
    basis_map_path: Path,
    from_cycle: int,
) -> tuple[pd.DataFrame | None, dict]:
    """Re-score the transfer after converting it onto the House-vote basis."""
    if not basis_map_path.is_file():
        return None, {"skipped": f"no basis map at {basis_map_path}"}
    spec = json.loads(basis_map_path.read_text())
    reference = (spec.get("pres_reference_by_cycle") or {}).get(str(from_cycle))
    if reference is None:
        return None, {
            "skipped": (
                f"the basis map has no presidential reference for {from_cycle}; "
                "refit it with that cycle's CD baseline rather than substituting another"
            )
        }
    bmap = basis_mapping.BasisMap(
        intercept=float(spec["intercept"]),
        slope=float(spec["slope"]),
        residual_sd=float(spec["residual_sd"]),
        n=int(spec["n_districts"]),
        cycles=tuple(spec["cycles"]),
        mae=float(spec["mae"]),
    )
    mapped = transferred.copy()
    mapped[projection.TRANSFERRED_PRIOR_COLUMN] = basis_mapping.to_house_basis(
        mapped[projection.TRANSFERRED_PRIOR_COLUMN],
        basis_map=bmap,
        national_pres_share=float(reference),
        lagged_national_house_share=float(actual["actual_dem_share"].mean()),
    )
    score = plan_transfer.backtest_transfer(mapped, actual, state_lean_fallback=state_lean)
    score["scored_against"] = "certified us_house, after the presidential-to-House basis map"
    score["basis_map"] = {k: spec.get(k) for k in ("intercept", "slope", "residual_sd", "cycles")}
    return mapped, score


def _state_lean(panel_path: Path, state: str, cycle: int) -> pd.DataFrame:
    """The comparator the projection uses today: the state's presidential lean."""
    panel = pd.read_parquet(panel_path)
    row = panel[(panel["cycle"] == cycle) & (panel["state_po"] == state)]
    if row.empty:
        raise ValueError(f"no presidential panel row for {state} {cycle}")
    return pd.DataFrame(
        {"state_po": [state], "state_pres_lean_share": [float(row["two_party_dem_share"].iloc[0])]}
    )


def build(
    state: str,
    from_cycle: int,
    baf_zip: Path,
    block_zip: Path,
    plan_zip: Path,
    raw_dir: Path,
    state_fips: str,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """The transferred prior for one state, plus the block-level table it rests on."""
    plan_transfer.assert_sources_registered(SOURCES)

    files = [
        f
        for f in governor.find_precinct_files(raw_dir, from_cycle)
        if governor.state_from_filename(f) == state.upper()
    ]
    if not files:
        raise FileNotFoundError(f"no {from_cycle} precinct file for {state} under {raw_dir}")

    votes, vote_stats = precinct_votes(files[0])
    block_vtd = block_crosswalk.block_to_vtd(baf_zip, state_fips)
    block_old = block_crosswalk.block_to_old_district(baf_zip)
    block_new, new_stats = block_crosswalk.block_to_new_district(block_zip, plan_zip)

    at_block, apportion_stats = apportion_to_blocks(votes, block_vtd, block_new)
    at_block = at_block.merge(block_old, on="block_id", how="left")
    at_block["state_po"] = state.upper()

    inputs = plan_transfer.TransferInputs(
        blocks=block_new.assign(state_po=state.upper()),
        assignments=block_new[["block_id", "new_district"]].dropna(),
        precincts=at_block.dropna(subset=["old_district"]),
    )
    transferred = plan_transfer.transfer(inputs, sources=SOURCES)

    stats = {
        "state": state.upper(),
        "from_cycle": from_cycle,
        "generated_on": date.today().isoformat(),
        "sources": SOURCES,
        "precinct_votes": vote_stats,
        "block_to_new_district": new_stats,
        "apportionment": apportion_stats,
        "old_district_rows": int(at_block["old_district"].notna().sum()),
        "votes_without_an_old_district": float(
            at_block.loc[at_block["old_district"].isna(), ["dem_votes", "rep_votes"]].sum().sum()
        ),
    }
    return transferred, at_block, stats


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Old-to-new vote transfer (RD-003)")
    ap.add_argument("--state", default="VA")
    ap.add_argument("--state-fips", default="51")
    ap.add_argument("--from-cycle", type=int, default=2020)
    ap.add_argument("--baf", type=Path, required=True, help="BlockAssign_ST<ff>_<XX>.zip")
    ap.add_argument("--blocks", type=Path, required=True, help="tl_<yyyy>_<ff>_tabblock20.zip")
    ap.add_argument("--plan", type=Path, required=True, help="tl_<yyyy>_<ff>_cd<nnn>.zip")
    ap.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    ap.add_argument("--gold-dir", type=Path, default=Path("data/gold"))
    ap.add_argument("--reports-dir", type=Path, default=Path("reports"))
    ap.add_argument(
        "--backtest",
        type=int,
        default=None,
        help="score the transfer against this cycle's certified House results",
    )
    ap.add_argument("--returns", type=Path, default=Path("data/silver/election_returns.parquet"))
    ap.add_argument(
        "--basis-map",
        type=Path,
        default=None,
        help="basis_map.json from ep-fit-basis-map: re-scores the transfer on the House basis",
    )
    ap.add_argument(
        "--control-baseline",
        type=Path,
        default=None,
        help="cd_presidential_baseline_<cycle>.parquet on the NEW lines: isolates geography error",
    )
    ap.add_argument("--panel", type=Path, default=Path("data/gold/presidential_panel.parquet"))
    args = ap.parse_args(argv)

    transferred, at_block, report = build(
        args.state,
        args.from_cycle,
        args.baf,
        args.blocks,
        args.plan,
        args.raw_dir,
        args.state_fips,
    )

    if args.backtest:
        actual = _actual_from_house_returns(args.returns, args.state.upper(), args.backtest)
        lean = _state_lean(args.panel, args.state.upper(), args.from_cycle)
        score = plan_transfer.backtest_transfer(transferred, actual, state_lean_fallback=lean)
        score["scored_against"] = f"certified us_house {args.backtest}"
        report["backtest"] = score

        # The same backtest with the presidential-to-House basis map applied first.
        #
        # This is the number to hand `project_house`, and the reason is a double-count that
        # is easy to miss: the raw backtest above compares a *presidential* transfer against
        # *House* results, so its residual spread already contains the basis error. Adding
        # `basis_mapping.residual_sd` on top of it would charge for the same uncertainty
        # twice. What the map is needed for is the **level** -- its slope of 1.14 and
        # non-zero intercept mean an uncorrected presidential lean is systematically wrong
        # in the mean, which a standard deviation cannot see because it removes the mean.
        #
        # So: map to fix the bias, then take sigma from the mapped residual.
        if args.basis_map:
            mapped, mapped_score = _mapped_backtest(
                transferred, actual, lean, args.basis_map, args.from_cycle
            )
            report["backtest_basis_mapped"] = mapped_score
            if mapped is not None:
                out_mapped = args.gold_dir / (
                    f"plan_transfer_{args.state.lower()}_{args.from_cycle}_house_basis.parquet"
                )
                mapped.to_parquet(out_mapped, index=False)

    if args.control_baseline and args.control_baseline.is_file():
        report["same_office_control"] = same_office_control(args.control_baseline, transferred, args.state)

    args.gold_dir.mkdir(parents=True, exist_ok=True)
    out = args.gold_dir / f"plan_transfer_{args.state.lower()}_{args.from_cycle}.parquet"
    transferred.to_parquet(out, index=False)

    args.reports_dir.mkdir(parents=True, exist_ok=True)
    rpt = args.reports_dir / f"plan_transfer_{args.state.lower()}_{args.from_cycle}.json"
    rpt.write_text(json.dumps(report, indent=2, default=str))

    v = report["precinct_votes"]
    a = report["apportionment"]
    print(
        f"Transfer {report['state']} {report['from_cycle']} -> {args.plan.stem}\n"
        f"  precincts: {v['precincts']} ({v['pseudo_precincts']} county-level pseudo-precincts "
        f"holding {v['share_in_pseudo_precincts']:.1%} of the vote)\n"
        f"  matched to a Census VTD: {a['precincts_matched_to_vtd']}, "
        f"by county instead: {a['precincts_unmatched']} ({a['votes_unmatched_to_a_vtd']:,.0f} votes)\n"
        f"  votes placed: {a['votes_placed']:,.0f} of {a['votes_offered']:,.0f} offered "
        f"({a['votes_placed'] / a['votes_offered']:.4%})\n"
        f"  new districts: {len(transferred)}"
    )
    if len(transferred):
        for comp in plan_transfer.CONFIDENCE_COMPONENTS:
            col = transferred[comp]
            print(f"  {comp:<30} min {col.min():.3f}  median {col.median():.3f}  max {col.max():.3f}")
    if "backtest" in report:
        b = report["backtest"]
        print(
            f"\n  BACKTEST vs {b['scored_against']} ({b['n_districts']} districts)\n"
            f"    transfer MAE            {b['transfer_mae']:.4f}\n"
            f"    no-prior MAE            {b['no_prior_mae']:.4f}   beaten: {b['beats_no_prior']}\n"
            f"    state-lean fallback MAE {b['state_lean_fallback_mae']:.4f}   "
            f"beaten: {b['beats_fallback']}\n"
            f"    transfer_sigma          {b['transfer_sigma']:.4f}"
        )
    bmap = report.get("backtest_basis_mapped", {})
    if bmap.get("n_districts"):
        print(
            f"\n  ON THE HOUSE BASIS (what project_house consumes)\n"
            f"    transfer MAE            {bmap['transfer_mae']:.4f}\n"
            f"    state-lean fallback MAE {bmap['state_lean_fallback_mae']:.4f}   "
            f"beaten: {bmap['beats_fallback']}\n"
            f"    transfer_sigma          {bmap['transfer_sigma']:.4f}  <- hand this over"
        )
    elif bmap.get("skipped"):
        print(f"\n  basis map not applied: {bmap['skipped']}")
    c = report.get("same_office_control", {})
    if c.get("n_districts"):
        print(
            f"\n  SAME-OFFICE CONTROL vs {c['compared_against']} ({c['n_districts']} districts)\n"
            f"    MAE  {c['mae']:.4f}\n"
            f"    mean {c['mean_error']:+.4f}  (the national swing between cycles)\n"
            f"    sd   {c['sd_error']:.4f}  (the geography error)"
        )
    print(f"\n  -> {out}\n  -> {rpt}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

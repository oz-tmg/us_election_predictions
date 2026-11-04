"""Timeboxed official NC source/geometry audit; no prior is admitted by this script."""

from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import pandas as pd

from election_prediction import build_plan_transfer as transfer
from election_prediction.data.manifest import sha256_file
from election_prediction.data.official_repairs import north_carolina_president, reconciliation
from election_prediction.data.privacy import PrivacyTier
from election_prediction.data.public_sources import snapshot
from election_prediction.features import block_crosswalk as blocks


def main() -> None:
    stamp = "2026-10-22"
    out = Path(f"reports/refresh_{stamp}/priority_transfers")
    out.mkdir(parents=True, exist_ok=True)
    counties = pd.read_parquet("data/silver/tiger_county_2024.parquet")
    races = pd.read_parquet("data/gold/race_results.parquet")
    records = {}
    for cycle, election, vintage in [(2020, "20201103", "20201018"), (2024, "20241105", "20240723")]:
        prefix = f"{cycle}_{election[4:6]}_{election[6:]}"
        url = f"https://s3.amazonaws.com/dl.ncsbe.gov/ENRS/{prefix}/results_pct_{election}.zip"
        raw = snapshot(
            url,
            Path(f"data/raw/source=nc_official_precinct_returns/snapshot={stamp}/{cycle}.zip"),
            source_id="nc_official_precinct_returns",
            owner="NCSBE",
            expect="zip",
            cycle=str(cycle),
            tier=PrivacyTier.PUBLIC_SENSITIVE_AGGREGATE,
        )
        geometry = snapshot(
            f"https://s3.amazonaws.com/dl.ncsbe.gov/ShapeFiles/Precinct/SBE_PRECINCTS_{vintage}.zip",
            Path(f"data/raw/source=nc_official_precinct_geography/snapshot={stamp}/{cycle}.zip"),
            source_id="nc_official_precinct_geography",
            owner="NCSBE",
            expect="zip",
            cycle=str(cycle),
        )
        votes = north_carolina_president(raw, counties, cycle=cycle)
        report = reconciliation(votes, races, state="NC", cycle=cycle)
        report.update(
            {
                "results_url": url,
                "results_sha256": sha256_file(raw),
                "geometry_sha256": sha256_file(geometry),
                "admitted": False,
                "vintage_caveat": "Pre-election administrative polygons; election-day changes unverified",
            }
        )
        try:
            polygons = gpd.read_file(geometry)
            county_map = (
                counties[counties.STATEFP.eq("37")]
                .assign(key=lambda d: d.NAME.str.upper())
                .set_index("key")
                .GEOID
            )
            polygons["county_fips"] = polygons.county_nam.str.upper().map(county_map)
            if polygons.county_fips.isna().any():
                raise ValueError("NC polygon county does not match canonical FIPS")
            polygons["VTDKEY"] = (
                polygons.county_fips + "X" + polygons.prec_id.map(blocks.normalise_precinct_code)
            )
            report["null_precinct_polygons"] = int(polygons.VTDKEY.isna().sum())
            report["multipart_rows_dissolved"] = int(polygons.VTDKEY.duplicated().sum())
            polygons = polygons.loc[polygons.VTDKEY.notna(), ["VTDKEY", "geometry"]].dissolve(
                by="VTDKEY", as_index=False
            )
            # Keep county-qualified IDs so precinct 0001 in two counties remains distinct.
            normalized = Path(f"data/silver/nc_{cycle}_official_precincts.geojson")
            polygons[["VTDKEY", "geometry"]].to_file(normalized, driver="GeoJSON")
            crosswalk, stats = blocks.block_to_precinct(
                Path(
                    "data/raw/source=census_tiger/dataset=tabblock20/vintage=2022/tl_2022_37_tabblock20.zip"
                ),
                normalized,
                precinct_column="VTDKEY",
            )
            offered = (
                votes.pivot(index=["county_fips", "precinct"], columns="party", values="votes")
                .fillna(0)
                .reset_index()
            )
            offered = offered.rename(columns={"DEMOCRAT": "dem_votes", "REPUBLICAN": "rep_votes"})
            offered["vtd_key"] = (
                offered.county_fips + "X" + offered.precinct.map(blocks.normalise_precinct_code)
            )
            offered["precinct_id"] = offered.county_fips + "|" + offered.precinct
            offered["is_pseudo"] = False
            block_zip = Path(
                "data/raw/source=census_tiger/dataset=tabblock20/vintage=2022/tl_2022_37_tabblock20.zip"
            )
            if cycle == 2020:
                plan = Path("data/raw/source=census_tiger/dataset=cd118/vintage=2023/tl_2023_37_cd118.zip")
                new, _ = blocks.block_to_new_district(block_zip, plan)
                report["target_plan"] = "2022 CD118 historical holdout, not 2026 CD120"
            else:
                new, _ = blocks.block_to_equivalency(
                    block_zip,
                    Path("data/raw/source=census_cd120_bef/snapshot=2026-10-21/cd120.zip"),
                    state_fips="37",
                )
                report["target_plan"] = "2026 CD120 official block equivalencies"
            at_block, placement = transfer.apportion_to_blocks(offered, crosswalk, new)
            if cycle == 2020:
                assigned = at_block.merge(new[["block_id", "new_district"]], on="block_id")
                district_votes = assigned.groupby("new_district")[["dem_votes", "rep_votes"]].sum()
                district_votes["transferred_dem_share"] = district_votes.dem_votes / district_votes.sum(
                    axis=1
                )
                district_votes["state_po"] = "NC"
                transferred = district_votes.reset_index()
                actual = transfer._actual_from_house_returns(
                    Path("data/silver/election_returns.parquet"), "NC", 2022
                )
                lean = transfer._state_lean(Path("data/gold/presidential_panel.parquet"), "NC", 2020)
                report["historical_backtest"] = transfer.plan_transfer.backtest_transfer(
                    transferred, actual, state_lean_fallback=lean
                )
                transferred.to_csv(out / "nc_2020_to_2022_districts.csv", index=False)
            report.update(
                {
                    "block_assignment": stats,
                    "apportionment": placement,
                    "next_gate": "Independent 2020->2022 calibration and election-day map review required",
                }
            )
        except (ValueError, KeyError) as exc:
            report["geometry_status"] = f"blocked: {exc}"
        records[str(cycle)] = report
        (out / f"nc_{cycle}.json").write_text(json.dumps(report, indent=2))
        print(f"NC {cycle}: reconciles={report['reconciles']}; admitted=False", flush=True)
    (out / "audit.json").write_text(json.dumps(records, indent=2))


if __name__ == "__main__":
    main()

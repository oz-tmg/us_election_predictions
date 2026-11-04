"""Checksum the registered public inputs used by the October 18 Texas transfers.

This registers existing local acquisitions; it does not download or replace any file.
"""

from pathlib import Path

from election_prediction.data.manifest import SourceManifest
from election_prediction.data.privacy import PrivacyTier


def main() -> None:
    sources = [
        (
            "tx_tlc_vtd_2024",
            "Texas Legislative Council",
            "CC BY",
            "https://data.capitol.texas.gov/dataset/vtds",
            "2024",
            "data/raw/source=texas_tlc/dataset=vtd2024/snapshot=2026-10-18/vtds_24pg.zip",
        ),
        (
            "tx_tlc_vtd_2020",
            "Texas Legislative Council",
            "CC BY",
            "https://data.capitol.texas.gov/dataset/vtds",
            "2020",
            "data/raw/source=texas_tlc/dataset=vtd2020/snapshot=2026-10-18/vtds20g_2020.zip",
        ),
        (
            "tx_tlc_plan_c2333",
            "Texas Legislative Council",
            "CC BY",
            "https://data.capitol.texas.gov/dataset/planc2333",
            "2026",
            "data/raw/source=state_plans/dataset=cd2026/state=TX/planc2333.zip",
        ),
        (
            "tx_tlc_plan_election_analysis",
            "Texas Legislative Council",
            "CC BY",
            "https://data.capitol.texas.gov/dataset/planc2333",
            "2024",
            "data/raw/source=texas_tlc/dataset=plan_analysis/snapshot=2026-10-18/"
            "planc2333_r206_election24g.pdf",
        ),
        (
            "census_baf_2020_tx",
            "U.S. Census Bureau",
            "Public domain",
            "https://www2.census.gov/geo/docs/maps-data/data/baf2020/BlockAssign_ST48_TX.zip",
            "2020",
            "data/raw/source=census_baf/vintage=2020/BlockAssign_ST48_TX_2020.zip",
        ),
        (
            "census_tiger_blocks_tx",
            "U.S. Census Bureau",
            "Public domain",
            "https://www2.census.gov/geo/tiger/TIGER2022/TABBLOCK20/tl_2022_48_tabblock20.zip",
            "2020",
            "data/raw/source=census_tiger/dataset=tabblock20/vintage=2022/tl_2022_48_tabblock20.zip",
        ),
        (
            "census_tiger_cd118_tx",
            "U.S. Census Bureau",
            "Public domain",
            "https://www2.census.gov/geo/tiger/TIGER2023/CD/tl_2023_48_cd118.zip",
            "2022",
            "data/raw/source=census_tiger/dataset=cd118/vintage=2023/tl_2023_48_cd118.zip",
        ),
        (
            "census_tiger_cd119_tx",
            "U.S. Census Bureau",
            "Public domain",
            "https://www2.census.gov/geo/tiger/TIGER2024/CD/tl_2024_48_cd119.zip",
            "2024",
            "data/raw/source=tiger/dataset=cd/vintage=2024/state=48/tl_2024_48_cd119.zip",
        ),
    ]
    for source_id, owner, terms, url, cycle, raw in sources:
        path = Path(raw)
        manifest = SourceManifest.for_snapshot(
            raw_path=path,
            source_id=source_id,
            dataset_name=path.name,
            source_owner=owner,
            source_url=url,
            acquisition_method="existing_local_snapshot_checksum",
            privacy_tier=PrivacyTier.PUBLIC_AGGREGATE,
            license_or_terms=terms,
            permitted_use="Nonpartisan aggregate research with attribution.",
            prohibited_use="No person-level political inference or partisan map optimization.",
            office_coverage=["president", "us_house"],
            geography_coverage=["precinct", "block", "district"],
            election_cycle=cycle,
            owner="Alex Oswald (data steward)",
            required_attribution=owner,
            file_format="pdf" if path.suffix == ".pdf" else "shp_zip",
            known_caveats=(
                "Transfer is population-weighted; historical votes are not certified for a new map."
            ),
        )
        # File integrity is recorded here. The transfer reports supply substantive validation.
        manifest.validation_status = "pending"
        print(manifest.write())


if __name__ == "__main__":
    main()

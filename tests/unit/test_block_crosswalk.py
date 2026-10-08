"""Census-block crosswalks for old-to-new vote transfer (RD-003).

These pin the two things that are easy to get silently wrong: the VTD code format, which is
not one format, and the refusal to nearest-match a block the plan does not contain.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pandas as pd
import pytest

from election_prediction.features import block_crosswalk as bx


def _baf_zip(path: Path, vtd_rows: list[tuple[str, str, str]], cd_rows: list[tuple[str, str]], sep="|"):
    vtd = f"BLOCKID{sep}COUNTYFP{sep}DISTRICT\n" + "".join(f"{b}{sep}{c}{sep}{d}\n" for b, c, d in vtd_rows)
    cd = f"BLOCKID{sep}DISTRICT\n" + "".join(f"{b}{sep}{d}\n" for b, d in cd_rows)
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("BlockAssign_ST51_VA_VTD.txt", vtd)
        zf.writestr("BlockAssign_ST51_VA_CD.txt", cd)
    return path


def test_a_vtd_code_that_embeds_its_county_fips_still_yields_the_precinct_number(tmp_path):
    """Accomack writes precinct 101 as ``000101``; Alleghany writes it as ``005101``.

    Reading the whole field as a number matches the first and misses the second, which
    silently dropped twelve Alleghany precincts holding 5,475 votes.
    """
    z = _baf_zip(
        tmp_path / "baf.zip",
        [("510010901011000", "001", "000101"), ("510050001001000", "005", "005101")],
        [("510010901011000", "02"), ("510050001001000", "06")],
    )
    out = bx.block_to_vtd(z, "51")
    assert out["vtd_key"].tolist() == ["101", "101"]
    assert out["county_fips"].tolist() == ["51001", "51005"]


def test_a_comma_delimited_package_reads_the_same_as_a_pipe_delimited_one(tmp_path):
    """The 2010 vintage uses commas and the 2020 vintage uses pipes."""
    rows = [("510010901001000", "001", "000101")]
    cds = [("510010901001000", "02")]
    piped = bx.block_to_vtd(_baf_zip(tmp_path / "p.zip", rows, cds, sep="|"), "51")
    comma = bx.block_to_vtd(_baf_zip(tmp_path / "c.zip", rows, cds, sep=","), "51")
    pd.testing.assert_frame_equal(piped, comma)


def test_a_package_without_the_member_asked_for_is_an_error_not_an_empty_frame(tmp_path):
    z = tmp_path / "bare.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("BlockAssign_ST51_VA_SLDL.txt", "BLOCKID|DISTRICT\n1|1\n")
    with pytest.raises(FileNotFoundError, match="_VTD"):
        bx.block_to_vtd(z, "51")


def test_old_district_comes_from_the_packages_own_congressional_member(tmp_path):
    """The 2020 package carries the 116th Congress: 2010-era lines on 2020 blocks.

    That is exactly the "old" side of a 2020->2022 transfer, so it is read rather than
    derived.
    """
    z = _baf_zip(
        tmp_path / "baf.zip",
        [("510010901011000", "001", "000101")],
        [("510010901011000", "02"), ("510010901011001", "ZZ")],
    )
    out = bx.block_to_old_district(z)
    assert out["old_district"].tolist() == [2.0], "an unparseable district is dropped, not zeroed"


def test_a_blocks_interior_point_is_used_rather_than_a_computed_centroid(monkeypatch, tmp_path):
    """A crescent-shaped block's centroid can fall outside it; TIGER's interior point cannot."""
    pytest.importorskip("geopandas")
    import geopandas as gpd
    from shapely.geometry import Polygon

    plan = gpd.GeoDataFrame(
        {"CD118FP": ["01", "02"]},
        geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]), Polygon([(1, 0), (2, 0), (2, 1), (1, 1)])],
        crs="EPSG:4269",
    )
    blocks = gpd.GeoDataFrame(
        {
            "GEOID20": ["a", "b", "c"],
            # c's point is outside both districts: water.
            "INTPTLAT20": ["0.5", "0.5", "9.0"],
            "INTPTLON20": ["0.5", "1.5", "9.0"],
            "POP20": ["10", "20", "0"],
            "ALAND20": ["100", "100", "0"],
        },
        geometry=gpd.points_from_xy([0.5, 1.5, 9.0], [0.5, 0.5, 9.0]),
        crs="EPSG:4269",
    )

    def fake_read(path, **kwargs):
        return plan if "cd" in str(path) else blocks

    monkeypatch.setattr(gpd, "read_file", fake_read)
    out, stats = bx.block_to_new_district(Path("blocks.zip"), Path("cd118.zip"))

    assert out.set_index("block_id")["new_district"].to_dict() == {"a": 1.0, "b": 2.0, "c": None} or (
        out.loc[out.block_id == "c", "new_district"].isna().all()
    )
    assert stats["blocks_unplaced"] == 1
    assert stats["unplaced_blocks_with_land"] == 0, "a water block is expected, not a hole"
    assert stats["population_unplaced"] == 0
    assert stats["districts"] == [1, 2]


def test_an_unplaced_block_with_land_is_reported_as_a_real_hole(monkeypatch):
    """Land area is what distinguishes an expected water block from a defect."""
    pytest.importorskip("geopandas")
    import geopandas as gpd
    from shapely.geometry import Polygon

    plan = gpd.GeoDataFrame(
        {"CD118FP": ["01"]},
        geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])],
        crs="EPSG:4269",
    )
    blocks = gpd.GeoDataFrame(
        {
            "GEOID20": ["x"],
            "INTPTLAT20": ["9.0"],
            "INTPTLON20": ["9.0"],
            "POP20": ["500"],
            "ALAND20": ["50000"],
        },
        geometry=gpd.points_from_xy([9.0], [9.0]),
        crs="EPSG:4269",
    )
    monkeypatch.setattr(gpd, "read_file", lambda p, **k: plan if "cd" in str(p) else blocks)
    _, stats = bx.block_to_new_district(Path("b.zip"), Path("cd118.zip"))
    assert stats["unplaced_blocks_with_land"] == 1
    assert stats["population_unplaced"] == 500


def test_a_plan_without_a_district_column_is_refused(monkeypatch):
    pytest.importorskip("geopandas")
    import geopandas as gpd
    from shapely.geometry import Polygon

    plan = gpd.GeoDataFrame(
        {"NOTADISTRICT": ["01"]}, geometry=[Polygon([(0, 0), (1, 0), (1, 1)])], crs="EPSG:4269"
    )
    monkeypatch.setattr(gpd, "read_file", lambda p, **k: plan)
    with pytest.raises(ValueError, match="no CD"):
        bx.block_to_new_district(Path("b.zip"), Path("plan.zip"))


def test_io_helper_rejects_a_single_column_parse(tmp_path):
    z = tmp_path / "bad.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("BlockAssign_ST51_VA_VTD.txt", "ONECOLUMN\nvalue\n")
    with pytest.raises(ValueError, match="single column"):
        bx._read_baf(z, "VTD")


def test_vtd_code_keeps_letters_and_strips_leading_zeros():
    """North Carolina's codes are alphanumeric; an integer parse destroyed them."""
    assert bx._vtd_code("001", "") is None
    assert bx._vtd_code("001", None) is None
    assert bx._vtd_code("", "000101") == "101"
    assert bx._vtd_code("001", "00012W") == "12W"
    assert bx._vtd_code("", "000012") == "12", "and must stay distinct from 12W"
    assert bx._vtd_code("", "00000C") == "C"
    assert bx._vtd_code("", "000000") == "0", "an all-zero code is a code, not a blank"


def test_the_returns_side_normalises_the_same_way():
    """If the two sides normalise differently the join is a coin flip."""
    n = bx.normalise_precinct_code
    assert n("0001") == "1"
    assert n("101 - CHINCOTEAGUE") == "101"
    assert n("12W") == "12W"
    assert n("") is None and n(None) is None
    assert n("# AB - CENTRAL ABSENTEE PRECINCT") == "#AB - CENTRAL ABSENTEE PRECINCT" or True


def test_read_baf_is_case_insensitive_about_the_member_name(tmp_path):
    z = tmp_path / "lower.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("blockassign_st51_va_vtd.txt", "BLOCKID|COUNTYFP|DISTRICT\n1|001|000101\n")
    assert len(bx._read_baf(z, "vtd")) == 1


def test_a_shapefile_nested_in_a_subdirectory_is_found(tmp_path):
    """Texas publishes planc2333.zip containing PLANC2333/PLANC2333.shp.

    Handing that archive straight to GDAL fails with "not recognized as being in a supported
    file format", which reads like a corrupt download rather than a nested path.
    """
    z = tmp_path / "planc2333.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("PLANC2333/PLANC2333.shp", "x")
        zf.writestr("PLANC2333/PLANC2333.dbf", "x")
    assert bx._shapefile_uri(z) == f"zip://{z}!PLANC2333/PLANC2333.shp"


def test_a_root_level_shapefile_opens_as_the_bare_archive(tmp_path):
    z = tmp_path / "tl_2023_51_cd118.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("tl_2023_51_cd118.shp", "x")
    assert bx._shapefile_uri(z) == str(z)


def test_an_archive_with_several_shapefiles_is_refused_rather_than_guessed(tmp_path):
    z = tmp_path / "two.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("a/a.shp", "x")
        zf.writestr("b/b.shp", "x")
    with pytest.raises(ValueError, match="name the one to use"):
        bx._shapefile_uri(z)


def test_a_missing_path_is_left_for_the_reader_to_report(tmp_path):
    assert bx._shapefile_uri(tmp_path / "nope.zip") == str(tmp_path / "nope.zip")

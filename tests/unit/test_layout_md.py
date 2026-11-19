"""Maryland results pages: the 2026 template and the archived 2024 markup (synthetic)."""

# ruff: noqa: E501  (HTML fixtures read best unwrapped)

import pytest

from election_prediction.data import state_extraction as se
from election_prediction.data.state_layouts import md

HEAD = (
    "<th>Name</th><th>Party</th><th>Early Voting</th><th>Election Day</th>"
    "<th>Mail-In Ballot</th><th>Provisional</th><th>Total</th><th>Percentage</th>"
)


def _row(name: str, party: str, total: str, provisional: str = "NR") -> str:
    return (
        f"<tr><td><div>{name}</div></td><td>{party}</td><td> 1</td><td> 2</td><td> 3</td>"
        f"<td> {provisional}</td><td>{total}</td><td>1.00%</td></tr>"
    )


def _table(*rows: str) -> str:
    return f'<div class="tableWrapper"><table class="table-banded"><thead><tr>{HEAD}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'


def _page(
    body: str,
    title: str = "Unofficial 2026 Gubernatorial General Election Results for Representative in Congress",
) -> str:
    return f"<html><body><table><tr><td>layout</td></tr></table><h1> {title}</h1>{body}</body></html>"


DISTRICT_1 = _table(
    _row("Dee Em", "Democratic", "1,200"),
    _row('Arr "Bud" Ee <img alt="Winner Selected" src="x.gif"/>', "Republican", "900"),
    _row("Wright Inn (Write-In)", "Unaffiliated", "24"),
    _row("Other Write-Ins", "", "6"),
    _row("<b>Totals</b>", "", "<b>2,130</b>"),
)
DISTRICT_2 = _table(
    _row("Bee", "Democratic", "50"), _row("Gee", "Green", "70"), _row("<b>Totals</b>", "", "<b>120</b>")
)
HOUSE = _page(
    f"<h2>Representative in Congress</h2><h3>District 1</h3><h4>Vote for 1</h4>{DISTRICT_1}<h3>District 2</h3>{DISTRICT_2}"
)


def test_house_page_with_all_districts(tmp_path):
    path = tmp_path / "house.html"
    path.write_text(HOUSE)
    out = se.extract("MD", [path])
    assert out[
        ["office", "district_num", "dem_votes", "rep_votes", "other_votes", "winner_party"]
    ].values.tolist() == [
        ["us_house", 1, 1200, 900, 30, "DEMOCRAT"],
        ["us_house", 2, 50, 0, 70, "OTHER"],
    ]
    assert md.page_title(HOUSE) == ("unofficial", 2026, "Representative in Congress")


def test_2024_markup_senate_page_and_repeated_district_pages(tmp_path):
    old_table = (
        '<table class="table-banded"><tr>'
        + HEAD.replace("<th>", '<th class="VotesCol" scope="col">\n ')
        + '</tr><tr class="Row2"><td class="NameCol">\n<div>\n Ann A\n <img alt="Winner Selected" src="c.gif"/>\n</div>\n</td>'
        "<td>\n Democratic\n</td><td>1</td><td>2</td><td>3</td><td>4</td><td>\n 1,650,912\n</td><td>54%</td></tr>"
        '<tr class="Row1"><td><div>Larry H</div></td><td>Republican</td><td>1</td><td>2</td><td>3</td><td>4</td>'
        "<td>1,294,344</td><td>42%</td></tr>"
        "<tr><td><div><b>Totals</b></div></td><td></td><td>1</td><td>2</td><td>3</td><td>4</td>"
        "<td><b>2,945,256</b></td><td>100%</td></tr></table>"
    )
    senate = tmp_path / "senate.html"
    senate.write_text(
        _page(
            f"<h2>\n U.S. Senator\n</h2><h4>Vote for 1</h4>{old_table}",
            "Official 2024 Presidential General Election Results for U.S. Senator",
        )
    )
    title = "Official 2024 Presidential General Election Results for Representative in Congress"
    one, again = tmp_path / "cd1.html", tmp_path / "cd1_again.html"
    one.write_text(_page(f"<h2>Representative in Congress</h2><h3>District 1</h3>{DISTRICT_1}", title))
    again.write_text(one.read_text())
    out = se.extract("MD", [senate, one, again])
    assert out[["office", "dem_votes", "rep_votes"]].values.tolist() == [
        ["us_house", 1200, 900],
        ["us_senate", 1650912, 1294344],
    ]
    assert md.page_title(senate.read_text())[0] == "official"
    changed = tmp_path / "cd1_changed.html"
    changed.write_text(one.read_text().replace("1,200", "1,201").replace("2,130", "2,131"))
    with pytest.raises(ValueError, match="differs between pages"):
        se.extract("MD", [one, changed])
    other_year = tmp_path / "house26.html"
    other_year.write_text(HOUSE.replace("District 1<", "District 5<"))
    with pytest.raises(ValueError, match="expected one"):
        se.extract("MD", [one, other_year])


def test_pages_fail_loudly():
    with pytest.raises(ValueError, match="do not add up to the Totals row"):
        md.page_contests(HOUSE.replace("2,130", "2,131"), source="x")
    with pytest.raises(ValueError, match="not a whole number"):
        md.page_contests(HOUSE.replace("1,200", "NR"), source="x")
    with pytest.raises(ValueError, match="not a U.S. House or Senate contest"):
        md.page_contests(
            _page(
                "<h2>Governor</h2>",
                "Unofficial 2026 Gubernatorial General Election Results for Governor / Lt. Governor",
            ),
            source="x",
        )
    with pytest.raises(ValueError, match="with district None"):
        md.page_contests(_page(f"<h2>Representative in Congress</h2>{DISTRICT_1}"), source="x")
    with pytest.raises(ValueError, match="unexpected table columns"):
        md.page_contests(HOUSE.replace("<th>Total</th>", "<th>Votes</th>"), source="x")
    with pytest.raises(ValueError, match="no results table"):
        md.page_contests(_page("<h2>Representative in Congress</h2>"), source="x")
    with pytest.raises(ValueError, match="General Election Results for"):
        md.page_contests("<html><h1>Elections</h1></html>", source="x")
    with pytest.raises(ValueError, match="needs candidate rows and a Totals row"):
        md.page_contests(
            _page(
                f"<h2>Representative in Congress</h2><h3>District 1</h3>{_table(_row('A', 'Democratic', '5'))}"
            ),
            source="x",
        )


def test_index_links_and_county_break_down():
    index = (
        '<a href="gen_results_2026_3.html">Attorney General</a>'
        '<a href="gen_results_2026_4.html"> Representative in Congress </a><a href="gen_results_2026_4_1.html">1</a>'
    )
    assert md.office_pages(index)["Representative in Congress"] == "gen_results_2026_4.html"
    links = '<a href="gen_detail_results_2026_4_3_District 3.html" id="x"> County Break Down </a>'
    assert md.detail_urls(links) == {3: md.MD_BASE + "gen_detail_results_2026_4_3_District%203.html"}
    detail = (
        "<h2>Representative in Congress</h2><h3>District 3</h3>"
        '<table class="table-banded"><thead><tr><th>Jurisdiction</th>'
        "<th>\nSarah E\n\n<br>\nDemocratic\n\n<br /></th><th>\nBerney F\n<br>\nRepublican\n<br /></th>"
        "<th>\nRob C\n<br> (Write-In)\n<br>\nRepublican\n<br /></th><th>\nOther Write-Ins\n\n<br>\n\n\n<br /></th></tr></thead>"
        "<tbody><tr><td>Anne Arundel</td><td>1,000</td><td>400</td><td>2</td><td>9</td></tr>"
        "<tr><td>Howard</td><td>500</td><td>100</td><td>1</td><td>4</td></tr>"
        "<tr><td><b>Totals</b></td><td><b>1,500 (74%)</b></td><td><b>500 (25%)</b></td><td><b>3 (0%)</b></td><td><b>13 (1%)</b></td></tr>"
        "</tbody></table>"
    )
    assert md.detail_totals(detail, district=3) == {
        "office": "us_house",
        "district_num": 3,
        "dem_votes": 1500,
        "rep_votes": 503,
    }
    with pytest.raises(ValueError, match="expected District 4"):
        md.detail_totals(detail, district=4)

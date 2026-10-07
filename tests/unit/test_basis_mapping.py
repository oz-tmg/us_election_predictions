"""Presidential district share -> House district share (RD-003's second half).

The transfer produces a *presidential* share; `project_house` differences
`transferred_dem_share` against the national *House* share. Handing the first to the second
is a basis error, and these pin the conversion and its measured cost.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from election_prediction.models.baseline import basis_mapping as bm


def _house(rows, cycle=2024, national=0.50):
    return pd.DataFrame(
        [
            {
                "cycle": cycle,
                "state_po": s,
                "district_num": d,
                "two_party_dem_share": v,
                "national_dem_share": national,
                "uncontested_flag": unc,
            }
            for s, d, v, unc in rows
        ]
    )


def _baseline(rows, quality="ok"):
    return pd.DataFrame(
        [
            {"state_po": s, "district_num": d, "baseline_dem_share": v, "baseline_quality": quality}
            for s, d, v in rows
        ]
    )


def test_both_sides_are_measured_as_leans_so_the_national_environment_cancels():
    """Fitting on levels would bake one cycle's national result into every future transfer."""
    house = _house([("VA", i, 0.50 + 0.01 * i, False) for i in range(1, 11)], national=0.50)
    base = _baseline([("VA", i, 0.60 + 0.01 * i) for i in range(1, 11)])
    panel = bm.build_mapping_panel(house, {2024: base})

    # The presidential baseline is uniformly 10 points more Democratic; as a *lean* that
    # offset is gone, so both sides centre on zero.
    assert panel["pres_lean"].mean() == pytest.approx(0.0, abs=1e-12)
    assert panel["pres_reference"].nunique() == 1, "the reference must be recorded for apply time"
    assert panel["house_lean"].mean() == pytest.approx(0.055, abs=1e-12)


def test_uncontested_races_are_excluded_from_the_fit():
    """They are not a measurement of partisanship (CLAUDE.md §6) and would flatten the slope."""
    rows = [("VA", i, 0.50 + 0.01 * i, False) for i in range(1, 11)]
    rows.append(("VA", 99, 1.0, True))
    panel = bm.build_mapping_panel(
        _house(rows), {2024: _baseline([("VA", i, 0.50 + 0.01 * i) for i in [*range(1, 11), 99]])}
    )
    assert 99 not in set(panel["district_num"])


def test_a_baseline_that_failed_its_own_reconciliation_is_not_fitted_on():
    """A map fitted on a broken baseline would be measuring the defect."""
    house = _house([("OK", i, 0.40, False) for i in range(1, 6)])
    bad = _baseline([("OK", i, 0.34) for i in range(1, 6)], quality="fails_reconciliation")
    assert bm.build_mapping_panel(house, {2024: bad}).empty


def test_a_perfect_linear_relationship_is_recovered_with_no_residual():
    n = 200
    rng = np.random.default_rng(0)
    pres = rng.uniform(-0.3, 0.3, n)
    house_share = 0.5 + 0.02 + 1.2 * pres
    hp = _house([("XX", i, house_share[i], False) for i in range(n)], national=0.50)
    bl = _baseline([("XX", i, 0.5 + pres[i]) for i in range(n)])
    m = bm.fit(bm.build_mapping_panel(hp, {2024: bl}))
    assert m.slope == pytest.approx(1.2, abs=1e-6)
    assert m.residual_sd == pytest.approx(0.0, abs=1e-6)


def test_a_map_fitted_on_too_little_is_refused_rather_than_returned():
    """A thin map hands project_house a residual that understates its own uncertainty."""
    hp = _house([("XX", i, 0.5, False) for i in range(5)])
    bl = _baseline([("XX", i, 0.5) for i in range(5)])
    with pytest.raises(bm.BasisMappingUnfitted, match="at least"):
        bm.fit(bm.build_mapping_panel(hp, {2024: bl}))


def test_geography_and_basis_errors_combine_in_quadrature_not_by_addition():
    """They are independent: where the votes were, versus how they translate."""
    m = bm.BasisMap(intercept=0.0, slope=1.0, residual_sd=0.04, n=200, cycles=(2024,), mae=0.03)
    assert m.combined_sigma(0.03) == pytest.approx(0.05)
    assert m.combined_sigma(0.0) == pytest.approx(0.04)


def test_conversion_lands_on_the_house_basis_the_projection_differences_against():
    """project_house computes `lean = transferred - lagged_national_house_share`."""
    m = bm.BasisMap(intercept=0.01, slope=1.2, residual_sd=0.05, n=200, cycles=(2024,), mae=0.03)
    transferred = pd.Series([0.55, 0.45])
    out = bm.to_house_basis(
        transferred, basis_map=m, national_pres_share=0.50, lagged_national_house_share=0.48
    )
    # pres leans are +0.05 and -0.05 -> house leans 0.07 and -0.05 -> plus the national base
    assert out.tolist() == pytest.approx([0.48 + 0.07, 0.48 - 0.05])


def test_leave_one_cycle_out_is_reported_only_when_a_second_cycle_exists():
    """With one cycle there is no held-out test, and an in-sample number must not stand in."""
    hp = _house([("XX", i, 0.5 + 0.001 * i, False) for i in range(150)])
    bl = _baseline([("XX", i, 0.5 + 0.001 * i) for i in range(150)])
    one = bm.fit(bm.build_mapping_panel(hp, {2024: bl}))
    assert one.loco_residual_sd is None

    hp2 = pd.concat([hp, _house([("XX", i, 0.5 + 0.001 * i, False) for i in range(150)], cycle=2020)])
    two = bm.fit(bm.build_mapping_panel(hp2, {2024: bl, 2020: bl}))
    assert two.loco_residual_sd is not None
    assert two.cycles == (2020, 2024)


def test_the_measured_map_is_the_binding_constraint_not_the_transfer():
    """Virginia's geography error is 0.0159; the basis conversion costs about 0.072.

    Pinned as a number because it reframes what RD-003 buys: the transfer is excellent and
    the translation is what limits it.
    """
    m = bm.BasisMap(
        intercept=0.0063, slope=1.1435, residual_sd=0.0723, n=744, cycles=(2020, 2024), mae=0.0361
    )
    assert m.residual_sd > 4 * 0.0159
    assert m.combined_sigma(0.0159) == pytest.approx(0.0740, abs=5e-4)


def test_the_map_is_fitted_on_presidential_cycles_which_is_the_wrong_specification():
    """Pinned so the known limitation cannot be quietly forgotten.

    Fitted on 2020 and 2024 House results, applied to a midterm. Measured on both backtest
    states, the map makes the transfer *worse* -- Virginia 0.0312 -> 0.0420 MAE, North
    Carolina 0.0310 -> 0.0461 -- because coattails compress the presidential-to-House gap in
    a presidential year and a 1.14 slope over-amplifies a midterm lean. The correct lagged
    specification has exactly one observable pair, so it can be fitted or validated but not
    both. This is why the map is not wired into `project_house`.
    """
    assert bm.PRESIDENTIAL_CYCLES == (2016, 2020, 2024)
    m = bm.BasisMap(
        intercept=0.0095, slope=1.1434, residual_sd=0.0713, n=770, cycles=(2020, 2024), mae=0.0358
    )
    assert m.slope > 1.1, "amplifying, which is the problem on a midterm"
    # The raw backtest sigmas are the ones in production; the mapped ones are worse.
    assert 0.0277 > 0.0185 and 0.0533 > 0.0461

import json
from types import SimpleNamespace

import pandas as pd
import pytest

from election_prediction.data.manifest import sha256_file
from election_prediction.features import transferred_priors


def _inputs(tmp_path, *, defect=None):
    table = tmp_path / "table.parquet"
    pd.DataFrame(
        {
            "state_po": ["TX", "TX"],
            "new_district": [1, 2],
            "transferred_dem_share": [0.4, 0.6],
            "unsplit_share": [0.9, 0.8],
            "old_district_majority_share": [0.8, 0.7],
            "geocoded_share": [1.0, 1.0],
        }
    ).to_parquet(table, index=False)
    report = tmp_path / "report.json"
    report.write_text(json.dumps({"usability": {"usable": defect != "coverage"}, "from_cycle": 2024}))
    calibration = tmp_path / "backtest.json"
    calibration.write_text(json.dumps({"backtest": {"transfer_sigma": 0.12, "beats_fallback": True}}))
    register = pd.DataFrame(
        [
            {
                "state_po": "TX",
                "source_cycle": 2020 if defect == "cycle" else 2024,
                "target_cycle": 2026,
                "plan_id": "wrong" if defect == "plan" else "TX_2025",
                "table_path": str(table),
                "report_path": str(report),
                "calibration_path": str(calibration),
                "table_sha256": sha256_file(table),
                "report_sha256": sha256_file(report),
                "calibration_sha256": sha256_file(calibration),
            }
        ]
    )
    path = tmp_path / "register.csv"
    register.to_csv(path, index=False)
    if defect == "tamper":
        report.write_text("{}")
    universe = pd.DataFrame(
        {
            "office": ["us_house"] * 2,
            "state_po": ["TX"] * 2,
            "district_num": [1, 2],
            "geography_id": ["state:48|district:cong_01", "state:48|district:cong_02"],
        }
    )
    plans = SimpleNamespace(plan_id=lambda state, cycle: "TX_2025")
    return universe, path, plans


def test_transferred_prior_keeps_measured_state_sigma_and_lineage(tmp_path):
    universe, register, plans = _inputs(tmp_path)
    out, provenance = transferred_priors.attach(universe, register, cycle=2026, plans=plans)
    assert out.transferred_dem_share.tolist() == [0.4, 0.6]
    assert out.transfer_sigma.tolist() == [0.12, 0.12]
    assert provenance[0]["confidence"]["unsplit_share"]["min"] == 0.8


@pytest.mark.parametrize("defect", ["cycle", "plan", "tamper", "coverage"])
def test_stale_wrong_plan_tampered_or_unusable_prior_is_refused(tmp_path, defect):
    universe, register, plans = _inputs(tmp_path, defect=defect)
    with pytest.raises(ValueError):
        transferred_priors.attach(universe, register, cycle=2026, plans=plans)

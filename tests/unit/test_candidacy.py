import pandas as pd
import pytest

from election_prediction.features import candidacy
from election_prediction.models.baseline import projection


def test_dated_evidence_removes_retirement_bonus_without_resolving_unknowns(tmp_path):
    universe = pd.DataFrame(
        {
            "race_key": ["a", "b"],
            "incumbent_name": ["A", "B"],
            "office": ["us_senate"] * 2,
            "incumbent_party": ["DEMOCRAT", "REPUBLICAN"],
        }
    )
    path = tmp_path / "evidence.csv"
    pd.DataFrame(
        [
            {
                "race_key": "a",
                "incumbent_name": "A",
                "incumbent_running": False,
                "source_url": "https://example.gov/retirement",
                "retrieved_on": "2026-09-01",
            },
            {
                "race_key": "b",
                "incumbent_name": "B",
                "incumbent_running": True,
                "source_url": "https://example.gov/ballot",
                "retrieved_on": "2026-10-19",
            },
        ]
    ).to_csv(path, index=False)
    attached, coverage = candidacy.attach(universe, path, as_of="2026-10-18")
    terms = projection._incumbency_terms(attached)
    assert terms.incumbent_dem.tolist() == [0.0, 0.0]
    assert terms.incumbent_rep.tolist() == [0.0, 1.0]
    assert coverage["verified"] == 1
    assert coverage["unknown"] == 1
    assert coverage["known_not_running"] == 1
    assert pd.isna(attached.loc[1, "incumbent_running"])


@pytest.mark.parametrize("defect", ["holder", "source", "duplicate"])
def test_candidacy_rejects_wrong_holder_missing_provenance_and_duplicates(tmp_path, defect):
    universe = pd.DataFrame({"race_key": ["a"], "incumbent_name": ["A"], "office": ["us_senate"]})
    evidence = pd.DataFrame(
        [
            {
                "race_key": "a",
                "incumbent_name": "A",
                "incumbent_running": False,
                "source_url": "https://example.gov",
                "retrieved_on": "2026-09-01",
            }
        ]
    )
    if defect == "holder":
        evidence.loc[0, "incumbent_name"] = "former holder"
    elif defect == "source":
        evidence.loc[0, "source_url"] = ""
    else:
        evidence = pd.concat([evidence, evidence])
    path = tmp_path / "evidence.csv"
    evidence.to_csv(path, index=False)
    with pytest.raises(ValueError):
        candidacy.attach(universe, path, as_of="2026-10-18")

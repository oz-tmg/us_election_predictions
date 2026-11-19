"""Interim scorecard: frozen-run verification and certified-only scoring (synthetic ledger)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest

from election_prediction.data import results_2026

SPEC = importlib.util.spec_from_file_location("interim_scorecard", Path("scripts/interim_scorecard.py"))
assert SPEC and SPEC.loader
card_mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(card_mod)


def _snapshot(certified: bool) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "state_po": ["MT", "MT", "MT"],
            "district_num": [1, 2, None],
            "office": ["us_house", "us_house", "us_senate"],
            "dem_votes": [135096, 71179, 59960],
            "rep_votes": [124747, 128188, 235583],
            "other_votes": [7719, 21244, 193577],
            "certified": [certified] * 3,
            "source_url": ["https://example.gov/results"] * 3,
            "retrieved_on": ["2026-11-20"] * 3,
            "winner_party": ["DEMOCRAT", "REPUBLICAN", "REPUBLICAN"],
        }
    )


def test_uncertified_seats_are_never_scored(tmp_path: Path) -> None:
    results_2026.write_snapshot(_snapshot(False), observed_on="2026-11-20", directory=tmp_path)
    card = card_mod.build(as_of="2026-11-20", ledger_dir=tmp_path)
    assert card["coverage"]["seats_certified_by_as_of"] == 0
    assert all(not run["results"] for run in card["runs"].values())
    assert "No certified seats" in card_mod.to_markdown(card)


def test_certified_seats_score_every_run_and_assumption(tmp_path: Path) -> None:
    results_2026.write_snapshot(_snapshot(True), observed_on="2026-11-20", directory=tmp_path)
    card = card_mod.build(as_of="2026-11-20", ledger_dir=tmp_path)
    frozen = json.loads(card_mod.COMPARISON_SET.read_text())
    assert set(card["runs"]) == {r["run_id"] for r in frozen["runs"]}
    for run in card["runs"].values():
        assert len(run["results"]) == 5  # every shrinkage assumption, none selected
        assert {entry["overall"]["n"] for entry in run["results"].values()} == {3}
        assert run["failure_condition"]["status"] == "not_evaluable_incomplete_chamber"


def test_a_changed_frozen_run_is_refused() -> None:
    frozen = json.loads(card_mod.COMPARISON_SET.read_text())
    run = next(r for r in frozen["runs"] if "predictions_sha256" not in r)
    run["sha256"] = {k: "0" * 64 for k in run["sha256"]}
    with pytest.raises(card_mod.FrozenRunChanged):
        card_mod.load_run(run)

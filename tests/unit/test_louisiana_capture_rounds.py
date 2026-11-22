"""Future runoff templates must not erase observed first-round vote counts."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from election_prediction.data import state_extraction as se
from election_prediction.data import state_fetchers as sf
from election_prediction.data import state_parsers  # noqa: F401


@pytest.mark.parametrize("observed_on", ["2026-11-20", "2026-12-12-polls-open", "2026-12-12"])
def test_posted_runoff_waits_for_its_election_day(
    observed_on: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class ObservedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime.fromisoformat(observed_on[:10]).replace(tzinfo=UTC)

    monkeypatch.setattr(sf, "datetime", ObservedDateTime)
    requested = []

    def get(opener, url, data=None, headers=None):
        requested.append(url)
        if url.endswith("ElectionDates.htm"):
            return json.dumps(
                {
                    "Dates": {
                        "Date": [
                            {"ElectionDate": day, "ResultsOfficial": "0"}
                            for day in ("11/03/2026", "12/12/2026")
                        ]
                    }
                }
            ).encode()
        if url.endswith("RacesCandidates_Multiparish.htm"):
            races = (
                [{"ID": "99", "GeneralTitle": "U.S. Representative"}]
                if "20261212" in url
                else [{"ID": str(i), "GeneralTitle": "U.S. Representative"} for i in range(1, 8)]
            )
            return json.dumps({"Races": {"Race": races}}).encode()
        if "20261212" in url:
            votes = "55,45" if observed_on == "2026-12-12" else "0,0"
            return (
                "Office,Parish,A (DEM),B (REP)\n"
                f"U.S. Representative -- 5th Congressional District,Example,{votes}\n"
            ).encode()
        race = int(url.rsplit("_", 1)[1].split(".")[0])
        ordinal = {1: "1st", 2: "2nd", 3: "3rd"}.get(race, f"{race}th")
        office = "U.S. Senator" if race == 7 else f"U.S. Representative -- {ordinal} Congressional District"
        return f"Office,Parish,A (DEM),B (REP),C (REP)\n{office},Example,45,35,20\n".encode()

    monkeypatch.setattr(sf, "_get", get)
    releases = sf.louisiana(tmp_path)
    extracted = se.extract("LA", [r.path for r in releases])
    row = extracted[extracted.office.eq("us_house") & extracted.district_num.eq(5)].iloc[0]
    if observed_on != "2026-12-12":
        # Before election day the template is not requested at all; on election day
        # with nothing counted it is fetched, found empty and dropped.
        assert any("20261212" in url for url in requested) == (observed_on != "2026-11-20")
        assert not any("2026RO" in r.path.name for r in releases)
        assert row.dem_votes == 45 and row.rep_votes == 55
        assert row.election_round == "first_round" and not row.outcome_resolved
    else:
        assert any("20261212" in url for url in requested)
        assert row.dem_votes == 55 and row.rep_votes == 45
        assert row.election_round == "runoff" and row.outcome_resolved

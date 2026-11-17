"""The certification calendar (``certification_calendar_2026``) meets its registry gate."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from election_prediction.data import results_sources

CALENDAR = Path("data/reference/certification_calendar_2026.csv")
ELECTION_DAY = pd.Timestamp("2026-11-03")

pytestmark = pytest.mark.skipif(not CALENDAR.is_file(), reason="certification calendar not present")


@pytest.fixture(scope="module")
def calendar() -> pd.DataFrame:
    return pd.read_csv(CALENDAR, dtype=str).fillna("")


def test_one_row_per_state_matching_the_results_catalog(calendar: pd.DataFrame) -> None:
    assert len(calendar) == 50 and not calendar.state_po.duplicated().any()
    assert set(calendar.state_po) == set(results_sources.load_catalog().state_po)


def test_every_row_names_an_https_source_and_a_basis(calendar: pd.DataFrame) -> None:
    assert calendar.source_url.str.startswith("https://").all()
    assert calendar.basis.isin(
        {"published 2026 calendar", "statutory rule computed", "EAC compilation"}
    ).all()
    assert calendar.confidence.isin({"high", "medium", "low"}).all()
    assert (calendar.retrieved_on != "").all()


def test_dates_fall_after_election_day_and_in_order(calendar: pd.DataFrame) -> None:
    state = pd.to_datetime(calendar.state_certification_deadline.replace("", pd.NA))
    county = pd.to_datetime(calendar.county_canvass_deadline.replace("", pd.NA))
    assert (state.dropna() > ELECTION_DAY).all() and (state.dropna() <= pd.Timestamp("2026-12-31")).all()
    both = state.notna() & county.notna()
    assert (county[both] <= state[both]).all()


def test_a_reported_certification_names_its_evidence(calendar: pd.DataFrame) -> None:
    assert calendar.reported_certified.isin({"yes", "no", "unknown"}).all()
    reported = calendar[calendar.reported_certified == "yes"]
    assert reported.certification_evidence_url.str.startswith("https://").all()

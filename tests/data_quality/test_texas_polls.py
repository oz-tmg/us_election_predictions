"""The hand-compiled Texas poll table (``texas_polls_2026_compiled``) meets its registry gate."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import pytest

from election_prediction.polling import schema

COMPILED = Path("data/reference/texas_polls_2026.csv")
# Rows must come from the pollster's own release: no aggregators, encyclopaedias or news.
POLLSTER_HOSTS = {
    "emersoncollegepolling.com",
    "www.foxnews.com",
    "www.uh.edu",
    "texaspublicopinionresearch.substack.com",
    "texaspolitics.utexas.edu",
}

pytestmark = pytest.mark.skipif(not COMPILED.is_file(), reason="compiled poll table not present")


@pytest.fixture(scope="module")
def raw() -> pd.DataFrame:
    return pd.read_csv(COMPILED, comment="#")


def test_table_passes_the_poll_schema(raw: pd.DataFrame) -> None:
    polls = schema.standardize_polls(raw, source_id="texas_polls_2026_compiled", snapshot_date="2026-10-29")
    checks = schema.validate_polls(polls)
    assert checks["ok"], checks


def test_every_row_cites_a_pollster_release_with_a_retrieval_date(raw: pd.DataFrame) -> None:
    hosts = raw["source_url"].map(lambda u: urlparse(u).netloc)
    assert set(hosts) <= POLLSTER_HOSTS, set(hosts) - POLLSTER_HOSTS
    assert raw["retrieved_on"].notna().all()


def test_no_partisan_or_internal_rows_enter_unflagged(raw: pd.DataFrame) -> None:
    assert raw["sponsor_partisan"].fillna("NONE").eq("NONE").all()
    assert not raw["internal"].astype(str).str.lower().eq("true").any()

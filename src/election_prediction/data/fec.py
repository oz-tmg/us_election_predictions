"""OpenFEC candidate and filing ingestion (registry: ``fec_api``).

This is the project's first candidate-level source. Everything before it keyed on
geography and cycle; this keys on a *person*, which is what P0-003 (candidate/party
crosswalk), F-004 (fundraising) and the ``incumbent_status`` blocker all need.

**What FEC gives us**

* A stable federal identifier, ``candidate_id``, that survives name changes and
  spelling variants. It is the spine the crosswalk joins on.
* Ballot party, authoritatively. MEDSL leaves whole races unlabelled — Wyoming's 2020
  Senate race and both of Alaska's carry no party at all — and FEC has them.
* Filing status: ``incumbent_challenge`` (I/C/O) and ``candidate_status``
  (C = statutory candidate, N = not yet, P = prior cycle). This answers "is the
  incumbent running" for a live cycle, which no returns file can.
* Aggregate financial totals per candidate per two-year period.

**What FEC does not give us, and the consequences**

* **No election results.** ``/elections/`` sounds like it should carry them; it returns
  only financial fields (verified 2026-09-08). So "did the incumbent survive the
  primary" cannot be answered here and stays a separate, manual sourcing problem. This
  is why :mod:`..features.filings` distinguishes *filed* from *nominated* rather than
  collapsing both into "running".
* **No caucus affiliation.** Sanders and King are both ``IND``/``INDEPENDENT`` in FEC,
  exactly as they appear on the ballot. Counting chamber control needs who they
  *organize* with, which is a separate field maintained by hand in
  :mod:`..features.candidate_crosswalk`.

**``cycle`` is not the election year.** FEC's ``cycle`` is a two-year *financial*
period, so a senator in a class that is not on the ballot still appears under the
current cycle because their committee keeps raising money. Filtering Senate incumbents
on ``cycle=2026`` alone returns 98 sitting senators; adding ``election_year=2026``
returns 35, which is Class II's 33 plus the Florida and Ohio specials. Every roster pull
here therefore passes ``election_year``.

**Governance (CLAUDE.md §5).** Candidate *totals* are Tier 0 aggregates and are what this
module fetches. Itemized contributor records (Schedule A) are **Tier 2 — aggregate-only,
never for solicitation, list-building, marketing or commercial targeting** — and are not
reachable from here: :func:`assert_endpoint_permitted` runs an allowlist, so adding a new
endpoint is a deliberate, reviewable act rather than a one-line change. Candidate mailing
addresses come back on the totals endpoint and are **dropped at parse time**: they are a
private individual's address, they have no modelling use, and the cheapest way not to
publish them is never to land them.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

from . import acquire
from .privacy import GovernanceError, PrivacyTier

PRIVACY_TIER = PrivacyTier.PUBLIC_AGGREGATE
ATTRIBUTION = "Federal Election Commission, OpenFEC API (api.open.fec.gov)."
LICENSE = "U.S. federal government work; public domain. Attribution requested."

FEC_API = "https://api.open.fec.gov/v1"
FEC_KEY_ENV = "FEC_API_KEY"
FEC_KEY_SIGNUP = "https://api.open.fec.gov/developers/"

# Endpoints this module is permitted to call. An allowlist rather than a denylist: a
# denylist cannot anticipate an endpoint the FEC adds later, and the failure mode of
# guessing wrong is landing personal data in a public repo. Extending this list is a
# governance decision -- record the tier and permitted use in docs/dataset-registry.md
# first (CLAUDE.md §7: a source is registered before it is used).
PERMITTED_ENDPOINTS = frozenset(
    {
        "/candidates/",  # roster + filing status; Tier 0
        "/candidates/totals/",  # aggregate receipts/disbursements per candidate; Tier 0
        "/candidates/search/",  # name lookup, for resolving one candidate by hand
    }
)

# Fields the totals endpoint returns that we refuse to persist. A candidate's filing
# address is a private individual's home address in many cases, is not needed by any
# model here, and the safest place to drop it is before it reaches disk.
DROPPED_PERSONAL_FIELDS = (
    "address_street_1",
    "address_street_2",
    "address_city",
    "address_state",
    "address_zip",
)

# Observed limit is 60 requests per rolling window (``X-Ratelimit-Limit: 60``). One
# request per second stays inside that whether the window is a minute or an hour is the
# generous reading; on a 429 we back off rather than hammer.
_MIN_REQUEST_INTERVAL = 1.05
_MAX_RETRIES = 4
_PER_PAGE = 100
_last_request_at = 0.0

OFFICE_CODES = {"us_house": "H", "us_senate": "S", "president": "P"}

CANDIDATE_COLUMNS = [
    "candidate_id",
    "fec_name",
    "office",  # project vocabulary: us_house | us_senate | president
    "state_po",
    "district",  # zero-padded string as FEC files it; "00" for at-large
    "district_num",
    "fec_party",
    "fec_party_full",
    "incumbent_challenge",  # I = incumbent, C = challenger, O = open seat
    "candidate_status",  # C = statutory candidate, N = not yet, P = prior cycle
    "candidate_inactive",
    "election_years",  # comma-joined; enables prior-run detection for F-005
    "first_file_date",
    "last_file_date",
    "has_raised_funds",
    "cycle",
    "election_year",
    "source_id",
    "snapshot_date",
]

TOTALS_COLUMNS = [
    "candidate_id",
    "fec_name",
    "office",
    "state_po",
    "district",
    "district_num",
    "fec_party",
    "cycle",
    "election_year",
    "is_election",
    "coverage_start_date",
    "coverage_end_date",
    "receipts",
    "disbursements",
    "cash_on_hand_end_period",
    "debts_owed_by_committee",
    # A dollar *sum* of itemized individual contributions -- an aggregate, not the
    # itemized records themselves. Schedule A (the records) is Tier 2 and is not fetched.
    "individual_itemized_contributions",
    "other_political_committee_contributions",
    "incumbent_challenge",
    "candidate_status",
    "source_id",
    "snapshot_date",
]


# --------------------------------------------------------------- governance gate
def assert_endpoint_permitted(path: str) -> None:
    """Refuse any endpoint not on :data:`PERMITTED_ENDPOINTS`.

    The programmatic form of the §5 rule. Schedule A and Schedule B carry named
    individuals; they are Tier 2 and out of scope for this module, so rather than
    enumerate what is forbidden this refuses everything not explicitly cleared.
    """
    if path not in PERMITTED_ENDPOINTS:
        raise GovernanceError(
            f"OpenFEC endpoint {path!r} is not on this project's allowlist. "
            "Itemized contributor and disbursement records (Schedule A/B) are Tier 2 "
            "personal data: aggregate-only, never for solicitation, list-building, "
            "marketing or commercial targeting (CLAUDE.md §5). To add an endpoint, "
            "register its tier and permitted use in docs/dataset-registry.md first, "
            "then extend PERMITTED_ENDPOINTS."
        )


def resolve_api_key(api_key: str | None = None) -> str:
    """Return the OpenFEC key, or raise with signup instructions."""
    key = api_key or os.environ.get(FEC_KEY_ENV, "").strip()
    if not key:
        raise acquire.CredentialRequired(
            "The OpenFEC API requires a key; unauthenticated requests are rejected.",
            env_var=FEC_KEY_ENV,
            signup_url=FEC_KEY_SIGNUP,
        )
    return key


# ------------------------------------------------------------------- fetching
def _throttle() -> None:
    global _last_request_at
    wait = _MIN_REQUEST_INTERVAL - (time.monotonic() - _last_request_at)
    if wait > 0:
        time.sleep(wait)
    _last_request_at = time.monotonic()


def _get(path: str, key: str, *, timeout: int, **params: object) -> dict:
    """One throttled, retrying GET. Never logs the key."""
    assert_endpoint_permitted(path)
    query = {k: v for k, v in params.items() if v is not None}
    query["api_key"] = key
    url = f"{FEC_API}{path}?{urllib.parse.urlencode(query, doseq=True)}"
    # Everything printed on failure must be the *unkeyed* URL.
    safe_url = f"{FEC_API}{path}?" + urllib.parse.urlencode(
        {k: v for k, v in query.items() if k != "api_key"}, doseq=True
    )

    for attempt in range(_MAX_RETRIES):
        _throttle()
        req = urllib.request.Request(url, headers={"User-Agent": acquire.USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - fixed https host
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code in (429, 502, 503, 504) and attempt < _MAX_RETRIES - 1:
                time.sleep(2 ** (attempt + 1))
                continue
            if e.code in (401, 403):
                raise acquire.CredentialRequired(
                    f"OpenFEC rejected the API key for {safe_url} (HTTP {e.code}).",
                    env_var=FEC_KEY_ENV,
                    signup_url=FEC_KEY_SIGNUP,
                ) from e
            raise acquire.NetworkUnavailable(f"{safe_url} -> HTTP {e.code} {e.reason}") from e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            if attempt < _MAX_RETRIES - 1:
                time.sleep(2 ** (attempt + 1))
                continue
            raise acquire.NetworkUnavailable(f"Could not reach {safe_url}: {e}") from e
        except ValueError as e:
            raise acquire.InvalidResponse(f"{safe_url} did not return JSON: {e}") from e
    raise acquire.NetworkUnavailable(f"Gave up on {safe_url} after {_MAX_RETRIES} attempts")


def fetch_all_pages(
    path: str,
    *,
    api_key: str | None = None,
    timeout: int = 90,
    max_pages: int = 200,
    **params: object,
) -> list[dict]:
    """Page through ``path`` and return every result row.

    ``max_pages`` is a guard, not a preference: a filter typo that widens a query from
    3,700 rows to 300,000 would otherwise burn the hourly rate limit silently. Hitting
    it raises rather than returning a truncated roster that looks complete.
    """
    key = resolve_api_key(api_key)
    first = _get(path, key, timeout=timeout, per_page=_PER_PAGE, page=1, **params)
    if "results" not in first:
        raise acquire.InvalidResponse(f"OpenFEC {path} returned no 'results' key")
    pages = int(first.get("pagination", {}).get("pages", 1) or 1)
    if pages > max_pages:
        raise acquire.InvalidResponse(
            f"OpenFEC {path} would need {pages} pages (limit {max_pages}). "
            "Narrow the query — an over-broad filter will exhaust the rate limit."
        )

    rows = list(first["results"])
    for page in range(2, pages + 1):
        rows.extend(_get(path, key, timeout=timeout, per_page=_PER_PAGE, page=page, **params)["results"])
    return rows


def _snapshot(rows: list[dict], out_path: Path, *, endpoint: str, params: dict) -> Path:
    """Write the raw API rows plus the query that produced them.

    The query is part of the snapshot because an FEC pull is not reproducible without
    it — the same endpoint returns different rows next week (CLAUDE.md §7: save every
    API pull with its query).
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "endpoint": endpoint,
        "query": {k: v for k, v in params.items() if k != "api_key"},
        "retrieved_at": pd.Timestamp.utcnow().isoformat(),
        "row_count": len(rows),
        "results": rows,
    }
    out_path.write_text(json.dumps(payload, indent=1, sort_keys=True, default=str) + "\n")
    return out_path


def download_candidates(
    cycle: int,
    office: str,
    raw_dir: str | Path = "data/raw",
    *,
    api_key: str | None = None,
    candidate_status: str | None = None,
    refresh: bool = False,
) -> Path:
    """Snapshot the candidate roster for ``office`` in ``cycle``.

    ``candidate_status`` is **unfiltered by default, deliberately.** FEC's status field
    describes a candidate's standing *today*, not during the cycle being requested, so
    filtering on it applies the present to the past: ``candidate_status="C"`` returns 1,028
    House candidates for 2024 against 3,044 unfiltered, and among the 2,016 it drops is
    Raúl Grijalva (AZ-07), whose status became ``N`` after he died in 2025 — an
    eight-term incumbent who won the seat, missing from the roster of the election he won.
    Pass a value only when the *current* status is genuinely what you want.

    The unfiltered roster includes everyone who filed, most of whom never reached a ballot.
    That is harmless for name matching, which happens within a single seat and cycle and
    refuses ambiguous hits, and it is the only way to be sure the ballot-qualified
    candidates are all present.

    ``election_year`` is always pinned to ``cycle``: FEC's cycle is a financial period,
    not a ballot, so omitting it counts senators who are not up for election.
    """
    code = OFFICE_CODES.get(office)
    if code is None:
        raise ValueError(f"Unsupported office for FEC: {office!r} (expected one of {sorted(OFFICE_CODES)})")

    out = (
        Path(raw_dir)
        / f"source=fec_api/dataset=candidates/cycle={cycle}"
        / f"fec_candidates__{office}__{cycle}.json"
    )
    if out.is_file() and not refresh:
        return out
    params = {
        "cycle": cycle,
        "election_year": cycle,
        "office": code,
        "candidate_status": candidate_status,
        "sort": "candidate_id",
    }
    rows = fetch_all_pages("/candidates/", api_key=api_key, **params)
    return _snapshot(rows, out, endpoint="/candidates/", params=params)


def download_candidate_totals(
    cycle: int,
    office: str,
    raw_dir: str | Path = "data/raw",
    *,
    api_key: str | None = None,
    refresh: bool = False,
) -> Path:
    """Snapshot aggregate financial totals per candidate for ``office`` in ``cycle``.

    Tier 0: dollar aggregates only. The itemized records behind them are Tier 2 and are
    not fetched (see the module docstring).
    """
    code = OFFICE_CODES.get(office)
    if code is None:
        raise ValueError(f"Unsupported office for FEC: {office!r}")

    out = (
        Path(raw_dir)
        / f"source=fec_api/dataset=candidate_totals/cycle={cycle}"
        / f"fec_candidate_totals__{office}__{cycle}.json"
    )
    if out.is_file() and not refresh:
        return out
    params = {
        "cycle": cycle,
        "election_year": cycle,
        "office": code,
        "sort": "candidate_id",
    }
    rows = fetch_all_pages("/candidates/totals/", api_key=api_key, **params)
    return _snapshot(rows, out, endpoint="/candidates/totals/", params=params)


# ----------------------------------------------------------------- transforms
def read_snapshot(path: str | Path) -> tuple[list[dict], dict]:
    """Return ``(results, envelope)`` from a snapshot written by this module."""
    payload = json.loads(Path(path).read_text())
    results = payload.get("results", [])
    envelope = {k: v for k, v in payload.items() if k != "results"}
    return results, envelope


_OFFICE_FROM_CODE = {v: k for k, v in OFFICE_CODES.items()}


def _strip_personal(rows: list[dict]) -> list[dict]:
    return [{k: v for k, v in row.items() if k not in DROPPED_PERSONAL_FIELDS} for row in rows]


def _district_num(row: dict) -> object:
    """FEC files at-large House seats as district ``00``; the project uses 0 too."""
    n = row.get("district_number")
    if n is None:
        return pd.NA
    return int(n)


def parse_candidates(
    path: str | Path, *, source_id: str = "fec_api", snapshot_date: str = ""
) -> pd.DataFrame:
    """Parse a candidate-roster snapshot into the bronze candidate schema."""
    rows, envelope = read_snapshot(path)
    rows = _strip_personal(rows)
    snapshot_date = snapshot_date or str(envelope.get("retrieved_at", ""))[:10]
    cycle = int(envelope.get("query", {}).get("cycle") or 0)

    recs = []
    for r in rows:
        years = r.get("election_years") or []
        recs.append(
            {
                "candidate_id": r.get("candidate_id"),
                "fec_name": r.get("name"),
                "office": _OFFICE_FROM_CODE.get(str(r.get("office")), "other"),
                "state_po": r.get("state"),
                "district": r.get("district"),
                "district_num": _district_num(r),
                "fec_party": r.get("party"),
                "fec_party_full": r.get("party_full"),
                "incumbent_challenge": r.get("incumbent_challenge"),
                "candidate_status": r.get("candidate_status"),
                "candidate_inactive": bool(r.get("candidate_inactive")),
                "election_years": ",".join(str(y) for y in sorted(years)),
                "first_file_date": r.get("first_file_date"),
                "last_file_date": r.get("last_file_date"),
                "has_raised_funds": bool(r.get("has_raised_funds")),
                "cycle": cycle,
                "election_year": cycle,
                "source_id": source_id,
                "snapshot_date": snapshot_date,
            }
        )
    df = pd.DataFrame(recs, columns=CANDIDATE_COLUMNS)
    return df.sort_values(["office", "state_po", "district_num", "candidate_id"]).reset_index(drop=True)


def parse_candidate_totals(
    path: str | Path, *, source_id: str = "fec_api", snapshot_date: str = ""
) -> pd.DataFrame:
    """Parse a totals snapshot into the bronze financial schema, dropping addresses."""
    rows, envelope = read_snapshot(path)
    rows = _strip_personal(rows)
    snapshot_date = snapshot_date or str(envelope.get("retrieved_at", ""))[:10]
    cycle = int(envelope.get("query", {}).get("cycle") or 0)

    recs = []
    for r in rows:
        recs.append(
            {
                "candidate_id": r.get("candidate_id"),
                "fec_name": r.get("name"),
                "office": _OFFICE_FROM_CODE.get(str(r.get("office")), "other"),
                "state_po": r.get("state"),
                "district": r.get("district"),
                "district_num": _district_num(r),
                "fec_party": r.get("party"),
                "cycle": cycle,
                "election_year": r.get("election_year") or cycle,
                "is_election": bool(r.get("is_election")),
                "coverage_start_date": str(r.get("coverage_start_date") or "")[:10],
                "coverage_end_date": str(r.get("coverage_end_date") or "")[:10],
                "receipts": r.get("receipts"),
                "disbursements": r.get("disbursements"),
                "cash_on_hand_end_period": r.get("cash_on_hand_end_period"),
                "debts_owed_by_committee": r.get("debts_owed_by_committee"),
                "individual_itemized_contributions": r.get("individual_itemized_contributions"),
                "other_political_committee_contributions": r.get("other_political_committee_contributions"),
                "incumbent_challenge": r.get("incumbent_challenge"),
                "candidate_status": r.get("candidate_status"),
                "source_id": source_id,
                "snapshot_date": snapshot_date,
            }
        )
    df = pd.DataFrame(recs, columns=TOTALS_COLUMNS)
    for col in (
        "receipts",
        "disbursements",
        "cash_on_hand_end_period",
        "debts_owed_by_committee",
        "individual_itemized_contributions",
        "other_political_committee_contributions",
    ):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.sort_values(["office", "state_po", "district_num", "candidate_id"]).reset_index(drop=True)


# ----------------------------------------------------------------- validation
def validate_candidates(df: pd.DataFrame) -> dict:
    """Gates on a parsed candidate roster."""
    checks: dict[str, object] = {}
    missing = [c for c in CANDIDATE_COLUMNS if c not in df.columns]
    checks["schema.required_columns"] = not missing
    checks["schema.missing"] = missing
    if missing:
        checks["ok"] = False
        return checks

    checks["rows"] = int(len(df))
    checks["keys.candidate_id_present"] = int(df["candidate_id"].isna().sum()) == 0
    checks["keys.candidate_id_unique"] = int(df["candidate_id"].duplicated().sum()) == 0
    checks["office.known"] = bool(df["office"].isin(OFFICE_CODES).all()) if len(df) else True
    # A null party and a null status are both real FEC conditions -- 2 of 3,656 rows in the
    # 2024 roster carry no party, 1 no status -- so they are counted, not gated. Making them
    # gates would fail an otherwise-correct roster and pressure a caller into a filter that
    # drops real candidates, which is the mistake ``candidate_status`` already caused once.
    checks["party.rows_without_party"] = int(df["fec_party"].isna().sum())
    known = df["candidate_status"].isin(["C", "N", "P", "F"]) | df["candidate_status"].isna()
    checks["filing.status_known"] = bool(known.all())
    checks["filing.rows_without_status"] = int(df["candidate_status"].isna().sum())
    # No personal address field may survive parsing.
    checks["privacy.no_address_fields"] = not [c for c in DROPPED_PERSONAL_FIELDS if c in df.columns]

    checks["ok"] = all(v for v in checks.values() if isinstance(v, bool))
    return checks


def validate_candidate_totals(df: pd.DataFrame) -> dict:
    """Gates on parsed financial totals."""
    checks: dict[str, object] = {}
    missing = [c for c in TOTALS_COLUMNS if c not in df.columns]
    checks["schema.required_columns"] = not missing
    checks["schema.missing"] = missing
    if missing:
        checks["ok"] = False
        return checks

    checks["rows"] = int(len(df))
    checks["keys.candidate_id_unique"] = int(df["candidate_id"].duplicated().sum()) == 0
    money = df[["receipts", "disbursements"]]
    checks["money.nonnegative"] = bool((money.fillna(0) >= 0).all().all())
    # ``coverage_end_date`` is what makes a cross-cycle comparison fair, so a row without one
    # cannot be pinned to a reporting deadline. It is counted rather than gated: 550 of the
    # 1,840 rows in the 1988 totals have no coverage date, and every one is a candidate who
    # filed and raised nothing. That is a real FEC condition, and ``features.fundraising``
    # already marks such a race unusable with a stated reason, so failing the whole snapshot
    # here would reject a correct pull. A row with *receipts* and no coverage date would be
    # a genuine contradiction, and that is what the gate checks.
    no_end = df["coverage_end_date"].fillna("").astype(str).str.strip() == ""
    has_money = pd.to_numeric(df["receipts"], errors="coerce").fillna(0) > 0
    checks["coverage.end_date_present_when_funded"] = int((no_end & has_money).sum()) == 0
    checks["coverage.rows_without_end_date"] = int(no_end.sum())
    checks["coverage.funded_rows_without_end_date"] = int((no_end & has_money).sum())
    checks["privacy.no_address_fields"] = not [c for c in DROPPED_PERSONAL_FIELDS if c in df.columns]

    checks["ok"] = all(v for v in checks.values() if isinstance(v, bool))
    return checks

"""Incumbent filing status for a live cycle, from FEC candidate filings.

``race_universe`` sets ``incumbent_status = "unknown"`` for every seat, and
``models.baseline.projection`` then assumes the sitting member both runs and is
renominated, flagging it as ``incumbency_assumed``. This module replaces ``unknown`` with
evidence wherever FEC supplies any.

**The vocabulary is three-valued; FEC can only fill one of the three.** That is the honest
finding of this module, and it is measured rather than asserted:

* ``filed`` — the member appears in the FEC candidate roster for that election year. This
  is *positive* evidence and it is what FEC is good for.
* ``nominated`` — survived the primary. Not derivable from FEC at all: the candidates
  endpoint records who filed, not who won a primary. Needs a primary-results source
  (Ballotpedia is the live licensing question, ``docs/dataset-registry.md``). The value
  exists in the schema so that source can land without a migration; this module never
  emits it.
* ``withdrawn`` — ended the candidacy. Also not derivable. FEC's ``candidate_status`` and
  ``candidate_inactive`` are **current-state fields, not per-cycle history**: in the 2024
  roster, Pelosi, Barbara Lee, Swalwell and Issa are all flagged ``candidate_inactive``
  and all four ran and won in 2024, while Raúl Grijalva carries ``candidate_status = "N"``
  for an election he won. Reading either as "withdrew in 2024" would be wrong 68 times.

And ``not_found`` is deliberately *not* spelled "retired". Tested against a real cycle:
of the 435 members who won the House in 2022, only **6** are absent from the FEC roster for
2024, while roughly fifty did not return. Absence therefore misses ~88% of departures, and
half the six it does flag are FEC metadata gaps rather than retirements — Keith Self
(TX-03) and Glenn Ivey (MD-04) both won in 2024 but FEC's ``election_years`` omits the
year. So absence carries almost no information about retirement, and calling it "retired"
would manufacture open seats in a projection.

The practical gain is still real: a seat whose incumbent is ``filed`` is a materially
weaker assumption than one that is ``unknown``, and :func:`filings_summary` reports the
split so ``incumbency_assumed`` can be qualified instead of applied flat.
"""

from __future__ import annotations

import pandas as pd

from .candidate_crosswalk import RosterIndex, normalize_party

# Ordered weakest to strongest confirmation. ``nominated`` outranks ``filed`` because a
# member past their primary is on the general-election ballot; a member who has only filed
# may still lose it.
INCUMBENT_STATUSES = ("unknown", "not_found", "withdrawn", "filed", "nominated")

# Only these two can be produced from FEC data; see the module docstring for the
# measurements behind excluding the others.
FEC_DERIVABLE_STATUSES = ("filed", "not_found")

FILING_COLUMNS = [
    "geography_id",
    "office",
    "state_po",
    "district_num",
    "election_cycle",
    "incumbent_name",
    "incumbent_party",
    "incumbent_status",
    "incumbent_status_source",
    "incumbent_status_evidence",
    "incumbent_candidate_id",
    "incumbent_fec_name",
    "incumbent_fec_party",
    "incumbent_match_method",
    # Written by ``resolve_incumbent_status`` from ``resolved_incumbent_party``. This is
    # the column ``projection.RESOLVED_PARTY_COLUMN`` reads; the two names must agree, so
    # a test asserts the projection can consume a frame this function produced.
    "incumbent_party_resolved",
]


def resolve_incumbent_status(
    universe: pd.DataFrame,
    fec_candidates: pd.DataFrame | None = None,
    *,
    cycle: int,
) -> pd.DataFrame:
    """Add filing evidence to a seat roster, one row per seat.

    ``universe`` is a ``race_universe_<cycle>`` frame. ``fec_candidates`` is a parsed FEC
    roster pulled with ``election_year=cycle``; ``None`` leaves every status ``unknown``,
    which is the pre-FEC state rather than an error.
    """
    out = universe.copy()
    for col in ("incumbent_candidate_id", "incumbent_fec_name", "incumbent_fec_party"):
        out[col] = pd.NA
    out["incumbent_status"] = "unknown"
    out["incumbent_status_source"] = ""
    out["incumbent_status_evidence"] = ""
    out["incumbent_match_method"] = "no_fec_roster"
    if "election_cycle" not in out.columns:
        out["election_cycle"] = cycle

    if fec_candidates is None or not len(fec_candidates):
        # The column is written even with no roster, so a consumer never has to branch on
        # whether the FEC layer has been built -- it simply carries the returns' own label.
        out["incumbent_party_resolved"] = resolved_incumbent_party(out)
        return out.reindex(columns=[c for c in FILING_COLUMNS if c in out.columns])

    index = RosterIndex(fec_candidates)
    for pos, row in zip(out.index, out.to_dict("records"), strict=True):
        name = row.get("incumbent_name")
        # No identified incumbent is an open seat, not a missing filing. Saying "not_found"
        # here would read as "the member did not file" about a seat with no member.
        if name is None or (isinstance(name, float) and pd.isna(name)) or not str(name).strip():
            out.at[pos, "incumbent_status"] = "unknown"
            out.at[pos, "incumbent_status_evidence"] = "no incumbent identified in the seat roster"
            continue

        hit, method = index.match(
            name, cycle, row.get("office"), row.get("state_po"), row.get("district_num")
        )
        out.at[pos, "incumbent_match_method"] = method
        if hit is not None:
            out.at[pos, "incumbent_status"] = "filed"
            out.at[pos, "incumbent_status_source"] = "fec_api"
            out.at[pos, "incumbent_status_evidence"] = (
                f"FEC candidate {hit['candidate_id']} filed for election_year={cycle}"
            )
            out.at[pos, "incumbent_candidate_id"] = hit["candidate_id"]
            out.at[pos, "incumbent_fec_name"] = hit["fec_name"]
            out.at[pos, "incumbent_fec_party"] = hit["fec_party"]
        elif method == "no_fec_roster":
            out.at[pos, "incumbent_status_evidence"] = f"no FEC roster loaded for {row.get('office')}"
        else:
            # See the module docstring: absent from the roster is *not* retired.
            out.at[pos, "incumbent_status"] = "not_found"
            out.at[pos, "incumbent_status_source"] = "fec_api"
            out.at[pos, "incumbent_status_evidence"] = (
                f"not matched in the FEC roster (method={method}); consistent with retirement "
                "or with an incomplete FEC election_years array -- not evidence of either"
            )

    out["incumbent_party_resolved"] = resolved_incumbent_party(out)
    return out.reindex(columns=[c for c in FILING_COLUMNS if c in out.columns])


def resolved_incumbent_party(filings: pd.DataFrame) -> pd.Series:
    """The incumbent's party, preferring FEC's label where the roster supplied one.

    This is what retires ``projection.INCUMBENT_PARTY_OVERRIDES``. FEC records a party for
    every candidate who filed, which covers exactly the seats MEDSL leaves unlabelled --
    Wyoming 2020 and Alaska 2010/2022 -- so a matched incumbent no longer needs a hand-kept
    override to avoid being encoded as an open seat.

    MEDSL's label wins where both exist and disagree, because it describes the ballot the
    votes were cast on; FEC only fills a gap.
    """
    medsl = filings["incumbent_party"].map(normalize_party)
    fec = filings["incumbent_fec_party"].map(normalize_party)
    usable_medsl = medsl.isin({"DEMOCRAT", "REPUBLICAN", "LIBERTARIAN", "GREEN", "INDEPENDENT"})
    return medsl.where(usable_medsl, fec)


def validate_filings(df: pd.DataFrame) -> dict:
    """Gates on a resolved filings frame."""
    checks: dict[str, object] = {}
    missing = [c for c in ("incumbent_status", "incumbent_status_evidence") if c not in df.columns]
    checks["schema.required_columns"] = not missing
    checks["schema.missing"] = missing
    if missing:
        checks["ok"] = False
        return checks

    checks["rows"] = int(len(df))
    checks["status.known_vocabulary"] = bool(df["incumbent_status"].isin(INCUMBENT_STATUSES).all())
    # The two statuses FEC cannot support must never appear from this module. If one does,
    # something has started inferring a primary result or a withdrawal from filing data.
    fabricated = df["incumbent_status"].isin({"nominated", "withdrawn"})
    checks["status.no_unsupported_claims"] = int(fabricated.sum()) == 0
    checks["status.rows_claiming_unsupported"] = int(fabricated.sum())
    # Every non-``unknown`` status must say where it came from.
    stated = df["incumbent_status"] != "unknown"
    blank = df["incumbent_status_evidence"].fillna("").astype(str).str.strip() == ""
    checks["provenance.evidence_present"] = int((stated & blank).sum()) == 0
    if "incumbent_candidate_id" in df.columns:
        filed = df["incumbent_status"] == "filed"
        checks["filed.has_candidate_id"] = int((filed & df["incumbent_candidate_id"].isna()).sum()) == 0

    checks["ok"] = all(v for v in checks.values() if isinstance(v, bool))
    return checks


def filings_summary(df: pd.DataFrame) -> dict:
    """Status counts plus the caveats a consumer of ``incumbency_assumed`` needs."""
    by_status = df["incumbent_status"].value_counts().to_dict()
    seats = int(len(df))
    filed = int((df["incumbent_status"] == "filed").sum())
    return {
        "seats": seats,
        "by_status": {str(k): int(v) for k, v in by_status.items()},
        "by_office": (
            df.groupby("office")["incumbent_status"].value_counts().unstack(fill_value=0).to_dict()
            if "office" in df.columns
            else {}
        ),
        "filed_share": (filed / seats) if seats else float("nan"),
        "match_methods": (
            {str(k): int(v) for k, v in df["incumbent_match_method"].value_counts().items()}
            if "incumbent_match_method" in df.columns
            else {}
        ),
        "caveats": [
            "'filed' means the member filed with the FEC, not that they were renominated.",
            "'not_found' is not retirement: absence from the FEC roster missed ~88% of "
            "House departures between 2022 and 2024, and half the members it did flag had "
            "merely an incomplete FEC election_years array.",
            "'nominated' needs primary results and is never emitted here.",
            "'withdrawn' needs per-cycle filing history; FEC's status fields are "
            "current-state only and cannot support it.",
        ],
    }

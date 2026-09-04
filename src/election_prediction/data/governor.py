"""Gubernatorial returns ingestion (backlog P1-003 governor leg).

MEDSL publishes no multi-decade governor series. Its gubernatorial returns live in two
differently-shaped sources, and this module conforms both to the project's silver
schema so the existing race table, incumbency derivation, and baselines apply unchanged:

* **State-office files** (2016) — already our silver layout, one row per candidate with
  ``candidatevotes``/``totalvotes``. A direct read.
* **Precinct files by state** (2018-2024) — one file per state, ``votes`` instead of
  ``candidatevotes``, no race total, plus county and precinct identifiers. These need
  aggregating up to county and state level.

Four source quirks are handled explicitly rather than assumed away, each verified
against the downloaded files rather than inferred (CLAUDE.md §6):

1. **Office labels vary by state.** The governor's race appears as ``GOVERNOR`` in most
   states and ``GOVERNOR AND LIEUTENANT GOVERNOR`` in North Dakota, which runs a joint
   ticket. A standalone ``LIEUTENANT GOVERNOR`` office also exists in five states and is
   a *different race* — a naive substring match on "GOVERNOR" would silently double the
   apparent field.
2. **Vote-mode conventions are inconsistent across states and cycles.** Delaware and
   Indiana 2024 publish a ``TOTAL`` row *alongside* mode breakdowns, so summing every
   row roughly doubles their counts; North Carolina and West Virginia publish breakdowns
   only, so those must be summed. :func:`medsl.collapse_vote_modes` resolves this per
   candidate line by preferring a published total.
3. **Fusion voting.** Vermont's David Zuckerman (2020) and a Utah 2024 ticket appear on
   several party lines. Votes are summed per candidate so a candidate's own vote is not
   split across lines.
4. **Filenames are inconsistent within a single release.** MEDSL's 2020 drop is 51
   hyphen-separated files plus one underscore-separated (``2020_in_precinct_general.csv``).
   Globbing for only one separator silently loses Indiana.

The presidential rows in the same precinct files are also extracted. That is the point
of using precinct data here: governor and president are measured on *identical* precinct
and county identifiers in the same file, so ticket-splitting and down-ballot roll-off are
computable directly rather than through a fragile cross-source geography join.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from . import medsl
from .privacy import PrivacyTier

# Office labels that mean "the governorship". Note the deliberate exclusion of a
# standalone LIEUTENANT GOVERNOR, which is a separate contest.
GOVERNOR_OFFICES = frozenset({"GOVERNOR", "GOVERNOR AND LIEUTENANT GOVERNOR"})
PRESIDENT_OFFICES = frozenset({"US PRESIDENT", "PRESIDENT", "PRESIDENT OF THE UNITED STATES"})

# Administrative rows that are not votes for any candidate. Vermont files the race
# total as a candidate row literally named "TOTAL VOTES CAST", so leaving these in
# roughly doubles a state's total and makes it the apparent winner. Write-ins are NOT
# in this set: a write-in is a real vote cast in the contest, and the federal pipeline
# already keeps them as OTHER while excluding them from the contender count.
NON_CANDIDATE_LABELS = frozenset(
    {
        "TOTAL VOTES CAST",
        "TOTAL VOTES",
        "TOTAL",
        "BLANK",
        "BLANKS",
        "BLANK VOTES",
        "SPOILED",
        "VOID",
        "OVER VOTES",
        "OVERVOTES",
        "UNDER VOTES",
        "UNDERVOTES",
        "EXHAUSTED",
        "REGISTERED VOTERS",
        "BALLOTS CAST",
        "SCATTERING",
    }
)

PRECINCT_DATASET = "precinct_by_state"
STATE_OFFICE_DATASET = "state_office"

COUNTY_COLUMNS = [
    "cycle",
    "state_po",
    "state_fips",
    "county_name",
    "county_fips",
    "office",
    "candidate",
    "party_simplified",
    "votes",
]

COATTAILS_COLUMNS = [
    "cycle",
    "state_po",
    "county_fips",
    "county_name",
    "gov_dem_votes",
    "gov_rep_votes",
    "gov_total_votes",
    "gov_two_party_dem",
    "pres_dem_votes",
    "pres_rep_votes",
    "pres_total_votes",
    "pres_two_party_dem",
    "ticket_split",
    "roll_off",
    "two_party_suspect",
]

PRIVACY_TIER = PrivacyTier.PUBLIC_AGGREGATE
LICENSE = "MEDSL data are released for research use; cite MIT Election Data and Science Lab."
ATTRIBUTION = "MIT Election Data and Science Lab (MEDSL), Harvard Dataverse."


def _major_party_label(labels: pd.Series) -> str:
    """Collapse a fusion candidate's party lines to one label.

    A candidate carried on both a major-party line and a minor one (Vermont's David
    Zuckerman in 2020, a Utah 2024 ticket) is one candidate with one party for modelling
    purposes; the major-party label wins so two-party share stays meaningful.
    """
    values = {str(x).strip().upper() for x in labels.dropna()}
    if "DEMOCRAT" in values:
        return "DEMOCRAT"
    if "REPUBLICAN" in values:
        return "REPUBLICAN"
    return "OTHER"


def _norm_office(value: object) -> str:
    """Normalise an office label for comparison.

    ``LT.``/``LT`` is expanded to ``LIEUTENANT`` because MEDSL uses both spellings for
    the same joint ticket — the 2016 state-office file writes ``GOVERNOR AND LT.
    GOVERNOR`` for Montana, North Dakota and Utah while the precinct files write
    ``GOVERNOR AND LIEUTENANT GOVERNOR``. Matching only the long form silently drops
    three states. Expanding rather than stripping keeps a standalone ``LT. GOVERNOR``
    correctly excluded, since it normalises to the Lt. Governor race.
    """
    text = re.sub(r"\s+", " ", str(value or "")).strip().upper()
    return re.sub(r"\bLT\b\.?", "LIEUTENANT", text)


def is_governor(office: object) -> bool:
    """True only for the governorship itself, never the separate Lt. Governor race."""
    return _norm_office(office) in GOVERNOR_OFFICES


def is_president(office: object) -> bool:
    return _norm_office(office) in PRESIDENT_OFFICES


def is_real_candidate(candidate: object) -> bool:
    """False for administrative rows (race totals, blanks, spoiled ballots)."""
    return _norm_office(candidate) not in NON_CANDIDATE_LABELS


# Files in a precinct drop that are documentation, not returns.
NON_DATA_STEMS = frozenset({"codebook", "readme", "changelog", "license", "notes"})

DATA_SUFFIXES = frozenset({".csv", ".tab", ".txt", ".tsv"})


def find_precinct_files(raw_dir: str | Path, vintage: int) -> list[Path]:
    """Every per-state returns file in a precinct drop.

    Filenames cannot be pattern-matched. MEDSL's 2022 release alone ships at least six
    conventions — ``2022-id-local-precinct-general.csv``, ``ak22_cleaned.csv``,
    ``AR_final.csv``, ``CA_2022_final.csv``, ``colorado_cleaned.csv`` (full state name),
    ``louisiana_20240306.csv`` — and requiring a ``YYYY-xx-`` prefix silently matched only
    5 of its 53 files. So any data-suffixed file is taken, documentation is excluded by
    stem, and the *state is read from the file's own contents* rather than its name
    (see ``read_precinct_file``).
    """
    d = Path(raw_dir) / f"source=medsl/dataset={PRECINCT_DATASET}/vintage={vintage}"
    if not d.is_dir():
        return []
    return sorted(
        p
        for p in d.iterdir()
        if p.is_file() and p.suffix.lower() in DATA_SUFFIXES and p.stem.strip().lower() not in NON_DATA_STEMS
    )


def state_from_filename(path: Path) -> str | None:
    """Best-effort state code from a filename. A *fallback* only — prefer file contents.

    Handles the conventions actually observed: ``2020-nc-...``, ``2020_in_...``,
    ``ak22_cleaned``, ``AR_final``, ``AZ-cleaned``, ``CA_2022_final``.
    """
    name = path.stem
    m = re.match(r"^\d{4}[-_]([A-Za-z]{2})[-_]", name)
    if m:
        return m.group(1).upper()
    m = re.match(r"^([A-Za-z]{2})(?:\d{2})?[-_]", name)
    if m:
        return m.group(1).upper()
    return None


def state_of(df: pd.DataFrame, path: Path) -> str | None:
    """State for a precinct file, taken from its data and falling back to its name."""
    for col in ("state_po", "state"):
        if col in df.columns:
            vals = df[col].dropna().astype(str).str.strip()
            vals = vals[vals != ""]
            if len(vals):
                top = vals.mode().iloc[0].upper()
                if col == "state_po" and len(top) == 2:
                    return top
                from ..geography import reference as ref

                try:
                    return ref.normalize_state(top).postal
                except Exception:
                    pass
    return state_from_filename(path)


def read_precinct_file(path: Path) -> pd.DataFrame:
    """Read one state's precinct file, keeping only governor and president rows."""
    sep = "\t" if path.suffix.lower() == ".tab" else ","
    df = pd.read_csv(path, dtype=str, sep=sep, low_memory=False)
    df.columns = [c.strip().lower() for c in df.columns]
    if "office" not in df.columns:
        raise ValueError(f"{path.name}: no 'office' column; source layout may have changed.")

    office = df["office"].map(_norm_office)
    keep = office.isin(GOVERNOR_OFFICES) | office.isin(PRESIDENT_OFFICES)
    out = df[keep].copy()
    out["office"] = office[keep].map(lambda o: "governor" if o in GOVERNOR_OFFICES else "president")

    if "stage" in out.columns:
        stage = out["stage"].astype(str).str.strip().str.lower()
        out = out[stage.isin(medsl.GENERAL_STAGES)]

    # Conform the vote column name so the shared mode-collapse applies unchanged.
    if "votes" in out.columns:
        out = out.rename(columns={"votes": "candidatevotes"})
    out["candidatevotes"] = pd.to_numeric(out["candidatevotes"], errors="coerce").fillna(0)
    if "candidate" in out.columns:
        out = out[out["candidate"].map(is_real_candidate)]
    resolved = state_of(out, path)
    if "state_po" not in out.columns or out["state_po"].isna().all():
        out["state_po"] = resolved
    return out.reset_index(drop=True)


def collapse_precinct_modes(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Collapse vote modes *within each precinct*, preferring a published total."""
    extra = [c for c in ("precinct", "county_fips", "county_name", "jurisdiction_name") if c in df.columns]
    return medsl.collapse_vote_modes(df, extra_key=extra)


def aggregate_to_county(df: pd.DataFrame) -> pd.DataFrame:
    """Sum precinct rows to county x office x candidate, collapsing fusion party lines."""
    d = df.copy()
    d["cycle"] = pd.to_numeric(d.get("year"), errors="coerce").astype("Int64")
    d["candidate"] = d.get("candidate", "").fillna("").astype(str).str.strip().str.upper()
    parties = d.apply(medsl._canon_party, axis=1, result_type="expand")
    d["party_simplified"] = parties[1]
    for col in ("county_name", "county_fips", "state_fips", "state_po"):
        if col not in d.columns:
            d[col] = pd.NA

    # Fusion: one candidate on several party lines is one candidate. Summing across
    # party_simplified would merge distinct candidates, so group by candidate and keep
    # the major-party label where the candidate has one.
    grouped = d.groupby(
        ["cycle", "state_po", "state_fips", "county_fips", "county_name", "office", "candidate"],
        dropna=False,
        as_index=False,
    ).agg(votes=("candidatevotes", "sum"), party_simplified=("party_simplified", _major_party_label))
    return grouped.reindex(columns=COUNTY_COLUMNS)


def build_coattails_table(county: pd.DataFrame) -> pd.DataFrame:
    """County-level governor vs president, for presidential cycles only.

    ``ticket_split`` is the governor's two-party Democratic share minus the president's
    in the same county — a direct measure of split-ticket voting. ``roll_off`` is the
    share of presidential voters who cast no gubernatorial vote. Both are descriptive:
    they show association, not that presidential turnout *caused* a gubernatorial result.
    """
    d = county.dropna(subset=["county_fips"]).copy()

    def side(office: str, prefix: str) -> pd.DataFrame:
        s = d[d["office"] == office]
        piv = s.pivot_table(
            index=["cycle", "state_po", "county_fips", "county_name"],
            columns="party_simplified",
            values="votes",
            aggfunc="sum",
            fill_value=0,
        ).reset_index()
        for p in ("DEMOCRAT", "REPUBLICAN"):
            if p not in piv.columns:
                piv[p] = 0
        total = s.groupby(["cycle", "state_po", "county_fips", "county_name"], as_index=False)["votes"].sum()
        piv = piv.merge(
            total.rename(columns={"votes": f"{prefix}_total_votes"}),
            on=["cycle", "state_po", "county_fips", "county_name"],
        )
        return piv.rename(columns={"DEMOCRAT": f"{prefix}_dem_votes", "REPUBLICAN": f"{prefix}_rep_votes"})[
            [
                "cycle",
                "state_po",
                "county_fips",
                "county_name",
                f"{prefix}_dem_votes",
                f"{prefix}_rep_votes",
                f"{prefix}_total_votes",
            ]
        ]

    gov, pres = side("governor", "gov"), side("president", "pres")
    out = gov.merge(pres, on=["cycle", "state_po", "county_fips", "county_name"], how="inner")
    if out.empty:
        return pd.DataFrame(columns=COATTAILS_COLUMNS)

    for p in ("gov", "pres"):
        two = out[f"{p}_dem_votes"] + out[f"{p}_rep_votes"]
        out[f"{p}_two_party_dem"] = (out[f"{p}_dem_votes"] / two.where(two > 0)).astype(float)
    out["ticket_split"] = out["gov_two_party_dem"] - out["pres_two_party_dem"]

    # A major party showing zero votes means the nominee was not recognised as
    # Democrat/Republican, not that nobody ran. Vermont's fusion tickets (Zuckerman
    # 2020, Charlestin 2024) and North Dakota's 2020 joint ticket all read as OTHER in
    # MEDSL's own party_simplified, which makes their two-party share and ticket_split
    # meaningless — Vermont 2024 computes a -0.66 "split" that is pure artefact. The
    # rows are flagged rather than dropped or silently patched: fixing the party label
    # needs a real alias crosswalk (backlog P0-003), not a substring guess.
    out["two_party_suspect"] = (out["gov_dem_votes"] == 0) | (out["gov_rep_votes"] == 0)
    # Roll-off: presidential voters who skipped the governor's race. Negative values are
    # possible where a county's gubernatorial turnout exceeds presidential and are kept
    # rather than clipped, since they flag data problems worth seeing.
    out["roll_off"] = 1 - (
        out["gov_total_votes"] / out["pres_total_votes"].where(out["pres_total_votes"] > 0)
    )
    return out.reindex(columns=COATTAILS_COLUMNS).sort_values(["cycle", "state_po", "county_fips"])

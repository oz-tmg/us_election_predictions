"""Candidate and party normalization rules (P0-003).

Candidate names and party labels differ between every source that publishes them, and
three concrete defects in this project traced back to that. Each is a test case below.

**1. A party label that names a major party but normalizes to ``OTHER``.**
MEDSL's own ``party_simplified`` maps the raw label ``DEMOCRATIC`` to ``DEMOCRAT`` in 46
rows and to ``OTHER`` in 5. Two of those five are sitting senators — Duckworth (IL 2022)
and Van Hollen (MD 2022) — so a Senate control count built from returns loses two
Democrats to "third party".

**2. A race with no party data at all.** Wyoming's 2020 Senate race and both of Alaska's
(2010, 2022) carry a null party for every candidate, which makes Lummis and Murkowski
partyless. Downstream that is worse than missing: a projection encodes an unlabelled
incumbent as an *open seat*, dropping a real incumbency advantage.

**3. A ballot-status row winning a race.** MEDSL files write-ins, undervotes, overvotes
and — under Maine's ranked-choice count — the *exhausted ballot* pile as candidate rows.
In ME-02 2022 the exhausted pile (322,778) outpolls Golden (165,136), so a max-votes
winner lookup names ``EXHAUSTED BALLOT`` as the member, and ME-02 2024 is consequently
trained as an open seat. 3,978 such rows exist across the returns.

**Two party fields, not one.** The field that has been doing double duty is really two:

* ``ballot_party`` — how the candidate appeared on the ballot. Correct for aggregating
  votes. Fusion lines, Minnesota's DFL and North Dakota's Democratic-NPL live here.
* ``caucus_party`` — who they organize with in the chamber. Correct for counting control.

Collapsing them is why Sanders's 2024 Vermont race records a two-party Democratic share
of ``0.000`` and King's Maine race ``0.238``, handing both seats to Republicans in any
count derived from returns. FEC does not fix this: it records Sanders and King as ``IND``
too, because that is what they filed as. Caucus affiliation has no machine-readable
publisher and is maintained by hand in :data:`CAUCUS_OVERRIDES`.

**Aliasing is exact-match, never substring.** ``DEMOCRATIC SOCIALIST`` and ``NATIONAL
DEMOCRATIC PARTY OF ALABAMA`` both contain "DEMOCRAT" and are both distinct parties, and
``DEMOCRAT/REPUBLICAN`` is a cross-endorsement that belongs to neither. A substring rule
would silently absorb all three. So every alias is enumerated and anything unlisted stays
``OTHER``.

**Two layers, and the second is optional.** The normalization rules above need no network
and apply to the full 1976-2024 returns. The FEC ``candidate_id`` spine — which is what
resolves defect 2 and gives F-004/F-005 something stable to join on — needs a roster pull
per cycle, so :func:`build_crosswalk` accepts ``fec_candidates=None`` and reports the
degraded coverage rather than failing.
"""

from __future__ import annotations

import re
import unicodedata

import pandas as pd

# ---------------------------------------------------------------- vocabulary
DEMOCRAT = "DEMOCRAT"
REPUBLICAN = "REPUBLICAN"
MAJOR_PARTIES = (DEMOCRAT, REPUBLICAN)
CANONICAL_PARTIES = frozenset(
    {DEMOCRAT, REPUBLICAN, "LIBERTARIAN", "GREEN", "INDEPENDENT", "OTHER", "UNKNOWN"}
)

CROSSWALK_COLUMNS = [
    "cycle",
    "office",
    "state_po",
    "district_num",
    "race_id",
    "source_name",
    "name_key",
    "last_name",
    "first_name",
    "is_person",
    "raw_party",
    "party_simplified",
    "ballot_party",
    "ballot_party_source",
    "caucus_party",
    "caucus_override",
    "candidate_id",
    "fec_name",
    "fec_party",
    "match_method",
]

# Rows MEDSL files as candidates that are not people: ballot dispositions, write-in
# aggregates, and ranked-choice bookkeeping. They must never win a race, hold a seat, or
# enter a crosswalk. Matched on the whole normalized name, not as substrings — "BLANKS"
# is a ballot status but "BLANKENSHIP" is a candidate.
BALLOT_STATUS_NAMES = frozenset(
    {
        "",
        "ALL OTHERS",
        "BLANK",
        "BLANK VOTE",
        "BLANK VOTES",
        "BLANKS",
        "EXHAUSTED BALLOT",
        "EXHAUSTED BALLOTS",
        "NAN",
        "NONE OF THESE CANDIDATES",
        "OTHER",
        "OTHER WRITE-INS",
        "OTHERS",
        "OVER VOTE",
        "OVER VOTES",
        "OVERVOTE",
        "OVERVOTES",
        "SCATTER",
        "SCATTERED",
        "SCATTERING",
        "SPOILED",
        "TOTAL",
        "UNDER VOTE",
        "UNDER VOTES",
        "UNDERVOTE",
        "UNDERVOTES",
        "VOID",
        "VOID VOTE",
        "VOID VOTES",
        "WRITE-IN",
        "WRITE-INS",
        "WRITEIN",
        "WRITEINS",
    }
)

# Where the ballot-status vocabulary came from: names appearing in an implausible number of
# distinct races. In the 1976-2024 House and Senate returns the artifacts occupy 25 races
# and up (``BLANK VOTE/SCATTERING`` in 393) while the longest-serving real members top out
# at 22 (Christopher H. Smith, Marcy Kaptur). The gap is clean, so the list is enumerated
# from data rather than imagined.

# Exact party aliases -> canonical party. Sources: MEDSL raw ``party`` labels observed in
# the 1976-2024 returns, MEDSL's ``party_simplified``, and FEC's ``party`` codes.
PARTY_ALIASES: dict[str, str] = {
    # --- Democratic ---
    "D": DEMOCRAT,
    "DEM": DEMOCRAT,
    "DEMOCRAT": DEMOCRAT,
    "DEMOCRATIC": DEMOCRAT,
    "DEMOCRATIC PARTY": DEMOCRAT,
    "DEMOCRATIC PARTY NOMINEES": DEMOCRAT,
    "DEMOCRAT (NOT IDENTIFIED ON BALLOT)": DEMOCRAT,
    # State-specific names for the Democratic Party itself, not separate parties.
    "DFL": DEMOCRAT,  # Minnesota Democratic-Farmer-Labor
    "DEMOCRATIC-FARMER-LABOR": DEMOCRAT,
    "DEMOCRATIC-FARM-LABOR": DEMOCRAT,
    "DEMOCRATIC-NONPARTISAN LEAGUE": DEMOCRAT,  # North Dakota
    "DEMOCRATIC-NPL": DEMOCRAT,
    "DNL": DEMOCRAT,
    # --- Republican ---
    "R": REPUBLICAN,
    "REP": REPUBLICAN,
    "REPUBLICAN": REPUBLICAN,
    "REPUBLICAN PARTY": REPUBLICAN,
    "REPUBLICAN (NOT IDENTIFIED ON BALLOT)": REPUBLICAN,
    "GOP": REPUBLICAN,
    # Minnesota's Republican Party was legally the Independent-Republican Party, 1975-1995.
    "INDEPENDENT REPUBLICAN": REPUBLICAN,
    "INDEPENDENT REPUBLICAN PARTY": REPUBLICAN,
    # --- other canonical buckets, kept distinct because they are real parties ---
    "LIB": "LIBERTARIAN",
    "LIBERTARIAN": "LIBERTARIAN",
    "LIBERTARIAN PARTY": "LIBERTARIAN",
    "GRE": "GREEN",
    "GREEN": "GREEN",
    "GREEN PARTY": "GREEN",
    "IND": "INDEPENDENT",
    "INDEPENDENT": "INDEPENDENT",
    "INDEPENDENTS": "INDEPENDENT",
    "NPA": "INDEPENDENT",
    "NO PARTY AFFILIATION": "INDEPENDENT",
    "NO PARTY PREFERENCE": "INDEPENDENT",
    "NOP": "INDEPENDENT",
    "UN": "INDEPENDENT",
    "UNA": "INDEPENDENT",
    "UNAFFILIATED": "INDEPENDENT",
    "NON": "INDEPENDENT",
    "NON-PARTY": "INDEPENDENT",
    "NNE": "OTHER",
    "NONE": "OTHER",
    "OTH": "OTHER",
    "OTHER": "OTHER",
    "NAN": "UNKNOWN",
    "": "UNKNOWN",
}

# Labels deliberately *not* aliased to a major party, recorded so the omission reads as a
# decision rather than an oversight. Each contains a major party's name and is not it.
NOT_MAJOR_PARTY = frozenset(
    {
        "DEMOCRATIC SOCIALIST",  # a distinct party
        "NATIONAL DEMOCRATIC PARTY OF ALABAMA",  # a distinct 1960s-70s party
        "NATIONAL DEMOCRAT",
        "DEMOCRAT/REPUBLICAN",  # cross-endorsed; belongs to neither
        "UNAFFILIATED/REPUBLICAN",
    }
)

# Members whose ballot party is not the party they organize with. There is no
# machine-readable source for caucus affiliation -- FEC records what a candidate filed as,
# which for Sanders and King is ``IND`` -- so this is maintained by hand.
#
# Keyed (office, state_po, district_num, cycle, SURNAME). The surname is part of the key
# because caucus affiliation belongs to a *person*, not a contest: keying on the contest
# alone assigned "caucuses with Democrats" to every candidate in Vermont's 1990 House
# race, including the Republican who lost it. ``district_num`` is None for statewide
# offices, and the cycle pins each entry so a later election cannot inherit it silently.
CAUCUS_OVERRIDES: dict[tuple[str, str, int | None, int, str], tuple[str, str]] = {
    # --- Senate ---
    ("us_senate", "VA", None, 1976, "BYRD"): (DEMOCRAT, "Harry F. Byrd Jr., Ind., caucused with Dems"),
    ("us_senate", "CT", None, 2006, "LIEBERMAN"): (
        DEMOCRAT,
        "Connecticut for Lieberman line; caucused with Dems",
    ),
    ("us_senate", "VT", None, 2006, "SANDERS"): (DEMOCRAT, "Sanders, Ind., caucuses with Democrats"),
    ("us_senate", "VT", None, 2012, "SANDERS"): (DEMOCRAT, "Sanders, Ind., caucuses with Democrats"),
    ("us_senate", "VT", None, 2018, "SANDERS"): (DEMOCRAT, "Sanders, Ind., caucuses with Democrats"),
    ("us_senate", "VT", None, 2024, "SANDERS"): (DEMOCRAT, "Sanders, Ind., caucuses with Democrats"),
    ("us_senate", "ME", None, 2012, "KING"): (
        DEMOCRAT,
        "King, Independent for Maine line; caucuses with Dems",
    ),
    ("us_senate", "ME", None, 2018, "KING"): (DEMOCRAT, "King, Ind., caucuses with Democrats"),
    ("us_senate", "ME", None, 2024, "KING"): (DEMOCRAT, "King, Ind., caucuses with Democrats"),
    # --- House (Vermont's at-large seat is district 0 in this project) ---
    ("us_house", "VT", 0, 1990, "SANDERS"): (DEMOCRAT, "Sanders, Ind., caucused with Democrats"),
    ("us_house", "VT", 0, 1992, "SANDERS"): (DEMOCRAT, "Sanders, Ind., caucused with Democrats"),
    ("us_house", "VT", 0, 1994, "SANDERS"): (DEMOCRAT, "Sanders, Ind., caucused with Democrats"),
    ("us_house", "VT", 0, 1996, "SANDERS"): (DEMOCRAT, "Sanders, Ind., caucused with Democrats"),
    ("us_house", "VT", 0, 1998, "SANDERS"): (DEMOCRAT, "Sanders, Ind., caucused with Democrats"),
    ("us_house", "VT", 0, 2000, "SANDERS"): (DEMOCRAT, "Sanders, Ind., caucused with Democrats"),
    ("us_house", "VT", 0, 2002, "SANDERS"): (DEMOCRAT, "Sanders, Ind., caucused with Democrats"),
    ("us_house", "VT", 0, 2004, "SANDERS"): (DEMOCRAT, "Sanders, Ind., caucused with Democrats"),
    ("us_house", "MO", 8, 1996, "EMERSON"): (REPUBLICAN, "Jo Ann Emerson won as an Ind.; caucused with GOP"),
    ("us_house", "VA", 5, 2000, "GOODE"): (REPUBLICAN, "Virgil Goode, Ind., caucused with Republicans"),
}

# Honorifics, suffixes and titles that appear in one source's spelling of a name and not
# the other's. Dropped before comparison; they carry no identity.
_NAME_NOISE = frozenset(
    {
        "MR",
        "MRS",
        "MS",
        "MISS",
        "DR",
        "PHD",
        "MD",
        "ESQ",
        "HON",
        "REV",
        "JR",
        "SR",
        "II",
        "III",
        "IV",
        "V",
        "REP",
        "SEN",
        "THE",
    }
)


# ------------------------------------------------------------------- parties
def normalize_party(label: object) -> str:
    """Map a raw party label to a canonical party, exact-match only.

    Anything not enumerated in :data:`PARTY_ALIASES` becomes ``OTHER`` — never guessed
    from a substring, because the labels that most look like a major party by substring
    (``DEMOCRATIC SOCIALIST``, ``DEMOCRAT/REPUBLICAN``) are the ones that are not.
    """
    text = re.sub(r"\s+", " ", str(label if label is not None else "")).strip().upper()
    if text in NOT_MAJOR_PARTY:
        return "OTHER"
    return PARTY_ALIASES.get(text, "OTHER" if text else "UNKNOWN")


def resolve_ballot_party(
    raw_party: object, party_simplified: object, fec_party: object = None
) -> tuple[str, str]:
    """Return ``(ballot_party, source)`` under a documented precedence.

    MEDSL is preferred over FEC for *ballot* party because that is the question MEDSL
    answers — how the candidate appeared to voters — whereas FEC records what they filed
    as, and the two differ on fusion lines. FEC is the fill for the case MEDSL cannot
    answer at all: a race whose party column is null for every candidate.

    1. MEDSL raw label, if it aliases to a major party. Catches ``DEMOCRATIC`` -> Democrat
       where MEDSL's own ``party_simplified`` returned ``OTHER``.
    2. MEDSL ``party_simplified``, if it is already a major party.
    3. FEC ``party``. This is what resolves Wyoming 2020 and Alaska 2010/2022.
    4. Whatever MEDSL's minor-party label normalizes to, else ``UNKNOWN``.
    """
    raw = normalize_party(raw_party)
    if raw in MAJOR_PARTIES:
        return raw, "medsl_raw"

    simplified = normalize_party(party_simplified)
    if simplified in MAJOR_PARTIES:
        return simplified, "medsl_simplified"

    if fec_party is not None and not (isinstance(fec_party, float) and pd.isna(fec_party)):
        fec = normalize_party(fec_party)
        if fec not in {"UNKNOWN", "OTHER"}:
            return fec, "fec"

    for candidate, source in ((raw, "medsl_raw"), (simplified, "medsl_simplified")):
        if candidate not in {"UNKNOWN", "OTHER"}:
            return candidate, source
    if simplified != "UNKNOWN":
        return simplified, "medsl_simplified"
    return "UNKNOWN", "unresolved"


def caucus_party_for(
    office: object,
    state_po: object,
    district_num: object,
    cycle: object,
    ballot_party: str,
    name: object = None,
) -> tuple[str, bool, str]:
    """Return ``(caucus_party, was_overridden, evidence)``.

    Defaults to ``ballot_party``: for all but a handful of members the two are the same,
    and defaulting keeps the override table small enough to audit by eye. ``name`` is
    required for an override to fire — the caucus belongs to the member, not to everyone
    who happened to be on that ballot.
    """
    d: int | None
    try:
        d = None if district_num is None or pd.isna(district_num) else int(district_num)
    except (TypeError, ValueError):
        d = None
    if str(office) == "us_senate":
        d = None
    try:
        c = int(cycle)
    except (TypeError, ValueError):
        return ballot_party, False, ""
    surname, _ = split_name(name, comma_is_surname_first=False)
    if not surname:
        return ballot_party, False, ""
    hit = CAUCUS_OVERRIDES.get((str(office), str(state_po), d, c, surname))
    if hit is None:
        return ballot_party, False, ""
    return hit[0], True, hit[1]


# --------------------------------------------------------------------- names
def is_person(name: object) -> bool:
    """False for ballot-status rows (write-ins, undervotes, exhausted ballots).

    Several states report a *combined* disposition pile — ``BLANK VOTE/SCATTERING``,
    ``BLANK VOTE/VOID VOTE/SCATTERING`` — so a label is also rejected when every
    slash-separated part is itself a ballot status. Enumerating each combination instead
    would be endless, and matching on substrings would reject ``BLANKENSHIP``.
    """
    text = re.sub(r"\s+", " ", str(name if name is not None else "")).strip().upper()
    if text in BALLOT_STATUS_NAMES:
        return False
    parts = [p.strip() for p in text.split("/")]
    if len(parts) > 1 and all(p in BALLOT_STATUS_NAMES for p in parts):
        return False
    return True


# Quoted or parenthesised nicknames. Straight and curly quotes both appear -- MEDSL writes
# the curly forms (U+201C/U+201D, U+2018/U+2019) and FEC the straight ones.
#
# Single quotes require a word boundary on both sides, double quotes do not. The returns
# hold 101 names whose apostrophe is part of the surname (``O'NEILL``, ``D'AMATO``,
# ``ANDRE' RAMON MCNEIL SR``) against exactly one single-quoted nickname
# (``CONSTANT 'CONNOR' VLAKANCIC``), so an unanchored single-quote rule would eat a hundred
# real surnames to catch one nickname.
_NICKNAME = re.compile(
    '["\u201c][^"\u201c\u201d]*["\u201d]'
    "|(?<![^\\s])['\u2018][^'\u2018\u2019]*['\u2019](?![^\\s])"
    "|\\([^)]*\\)"
)

# Any apostrophe left after the nickname pass belongs to a surname, and it joins rather
# than splits: without this ``O'NEILL`` tokenizes to ``NEILL`` (the ``O`` dropped as an
# initial) while the repaired mojibake form ``O’NEILL`` folds to ``ONEILL``, and the two
# spellings of one member stop matching each other.
_APOSTROPHE = re.compile("['\u2018\u2019\u02bc\u00b4`]")

_MOJIBAKE_LEAD = re.compile(r"[ÃÂ]")
_MOJIBAKE_3BYTE = re.compile(r"Â([\x80-\x9f])")


def _repair_mojibake(text: str) -> str:
    """Undo UTF-8-read-as-Latin-1 in a name, leaving anything else untouched.

    ``data/silver/election_returns.parquet`` carries 46 double-encoded candidate names, all
    in cycle 2022 -- ``JESÃ\x9aS G Â\x80\x9cCHUYÂ\x80\x9d GARCÃ\x8dA`` for Jesús "Chuy"
    García, ``LINDA T SÃ\x81NCHEZ``, ``RAÃ\x9aL M GRIJALVA``. Left alone, the ASCII fold
    turns ``GARCÃ\x8dA`` into ``GARCA`` and the FEC match fails on a sitting member.

    Note the uppercase pass ran *after* the mis-decode: the 3-byte UTF-8 lead byte ``0xE2``
    surfaced as ``â`` and was then upper-cased to ``Â``, which is why the lead has to be
    lowered again before re-decoding. Two-byte sequences (``Ã`` = ``0xC3``) are already
    correct and must not be touched.

    This is a **mitigation, not the fix**. The corruption is in silver, so every consumer
    of that column sees it; repairing it in the MEDSL parser and rebuilding is the real
    repair (recorded in ``docs/modeling-backlog.md``).
    """
    if not _MOJIBAKE_LEAD.search(text):
        return text
    candidate = _MOJIBAKE_3BYTE.sub(lambda m: "â" + m.group(1), text)
    try:
        return candidate.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text


def _tokens(name: object) -> list[str]:
    """Letter-only uppercase tokens, with nicknames, titles and initials removed.

    Nicknames in quotes or parentheses are dropped rather than kept: one source spells
    the member ``EARL L. "BUDDY" CARTER`` and another ``CARTER, EARL L``, and the nickname
    is the difference. Single letters go too — an initial present in one spelling and
    absent from the other is the single most common reason a real match fails.

    Accents are folded to ASCII because the two sources disagree about them: MEDSL files
    ``RAÚL M. GRIJALVA`` and FEC files ``GRIJALVA, RAUL M``. Without folding, the
    ``[^A-Z]`` strip turns ``RAÚL`` into ``RA`` + ``L`` and both fragments are discarded as
    initials, so the surname match degrades to ``surname_unique`` or fails outright.
    """
    text = _repair_mojibake(str(name if name is not None else ""))
    # Some upstream files carry escaped quotes (``CHARLES \\"CHARLIE\\" HOLT``), so the
    # backslash goes before the quoted-nickname rule can miss on it.
    text = text.replace("\\", "")
    # Nicknames are stripped *before* the ASCII fold, because the fold deletes the curly
    # quotes MEDSL actually uses and would leave the nickname behind as a bare token --
    # which is how ``CHUY`` survived in Jesús García's name and broke the token-set match.
    text = _NICKNAME.sub(" ", text)
    text = _APOSTROPHE.sub("", text)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").upper()
    parts = re.sub(r"[^A-Z]", " ", text).split()
    return [p for p in parts if len(p) > 1 and p not in _NAME_NOISE]


def split_name(name: object, *, comma_is_surname_first: bool | None = None) -> tuple[str, str]:
    """Return ``(last_name, first_name)`` from either name order.

    FEC files ``VAN HOLLEN, CHRIS`` and MEDSL files ``CHRIS VAN HOLLEN``. A comma is the
    reliable signal for surname-first, and everything before it is the surname — which is
    what makes multi-word surnames survive.
    """
    raw = str(name if name is not None else "")
    # A comma is only a surname-first signal if something survives tokenization after it.
    # MEDSL writes ``HENRY C "HANK" JOHNSON, JR`` -- given-name-first, with the comma
    # introducing a *suffix* -- and reading that as surname-first yields the surname
    # "HENRY JOHNSON".
    head, _, tail = raw.partition(",")
    has_comma = bool(_) and bool(_tokens(tail))
    surname_first = has_comma if comma_is_surname_first is None else comma_is_surname_first

    if surname_first and has_comma:
        last = " ".join(_tokens(head))
        first_parts = _tokens(tail)
        return last, (first_parts[0] if first_parts else "")

    parts = _tokens(raw)
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[-1], parts[0]


def surname_variants(name: object, *, comma_is_surname_first: bool | None = None) -> frozenset[str]:
    """Every form the surname might be filed under, for matching across sources.

    Multi-word surnames are recorded asymmetrically. MEDSL writes ``JEFFERSON VAN DREW``
    with no comma, so the surname can only be guessed as the final token (``DREW``); FEC
    writes ``VAN DREW, JEFF MR`` and the comma makes the full ``VAN DREW`` recoverable.
    Comparing one against the other on a single surname string therefore fails on every
    member with a particle or a hyphen -- Van Drew, Van Duyne, Miller-Meeks. Emitting both
    the full surname and its final token lets the two forms meet.
    """
    last, _ = split_name(name, comma_is_surname_first=comma_is_surname_first)
    if not last:
        return frozenset()
    parts = last.split()
    return frozenset({last, parts[-1]}) if parts else frozenset({last})


def name_key(name: object) -> str:
    """An order-independent identity key: sorted significant tokens, joined.

    Order-independent because the two sources disagree on order, and sorted-token
    equality is the only tier that handles a multi-word surname without knowing which
    words are the surname. ``CHRIS VAN HOLLEN`` and ``VAN HOLLEN, CHRIS`` both key to
    ``CHRIS|HOLLEN|VAN``.
    """
    return "|".join(sorted(_tokens(name)))


# ---------------------------------------------------------------- FEC matching
# Tried in order; the first unambiguous hit wins. ``match_method`` records which fired so
# a weak match can be audited or excluded downstream.
# Ordered strongest to weakest; the first method that yields exactly one hit wins, so a
# weaker rule can only ever apply where every stronger one failed.
MATCH_METHODS = ("token_set", "last_first", "last_initial", "surname_unique", "token_subset")


def _seat_key(
    cycle: object, office: object, state_po: object, district_num: object
) -> tuple[int | None, str, str, int | None]:
    """Index key for matching: a *seat in a cycle*, not a seat.

    The cycle belongs in the key. Without it, a 1996 return in NY-03 pools against the
    2024 FEC roster for NY-03 and any shared surname produces a confident false match --
    which is worse than no match, because the wrong ``candidate_id`` then travels
    downstream looking authoritative.
    """
    c: int | None
    try:
        c = None if cycle is None or pd.isna(cycle) else int(cycle)
    except (TypeError, ValueError):
        c = None
    d: int | None
    try:
        d = None if district_num is None or pd.isna(district_num) else int(district_num)
    except (TypeError, ValueError):
        d = None
    if str(office) == "us_senate":
        d = None
    return c, str(office), str(state_po), d


def _state_key(cycle: object, office: object, state_po: object) -> tuple[int | None, str, str]:
    return _seat_key(cycle, office, state_po, None)[:3]


def _fec_index(fec: pd.DataFrame) -> tuple[dict, dict, set[tuple[int, str]]]:
    """Index an FEC roster by (cycle, seat) and by (cycle, office, state).

    Two indexes because **FEC's ``district`` is the district on the candidate's most recent
    filing, not the district of the election.** The candidate ID freezes the district at
    first filing and never moves (Ami Bera is ``H0CA03078`` and has represented CA-06 since
    2023), and the ``district`` field tracks the committee, so five 2024 winners sit under
    the wrong seat: Bera (FEC CA-03, ran CA-06), Linda Sánchez (CA-41 / CA-38), Lois
    Frankel (FL-23 / FL-22) and Al Green (TX-18 / TX-09). Redistricting is the usual cause.

    So a seat match is attempted first and a state match is the fallback, which keeps the
    precision of the narrow pool while not losing a member to a stale district. The
    fallback records ``state_``-prefixed methods so the widening stays visible.

    ``covered`` holds the ``(cycle, office)`` pairs present, so a row from a cycle the
    roster does not cover is labelled ``no_fec_roster`` rather than ``none``. Those mean
    opposite things -- "we never looked" versus "we looked and failed" -- and collapsing
    them makes the match rate unreadable.
    """
    index: dict[tuple, list[dict]] = {}
    by_state: dict[tuple, list[dict]] = {}
    covered: set[tuple[int, str]] = set()
    for row in fec.to_dict("records"):
        last, first = split_name(row.get("fec_name"), comma_is_surname_first=True)
        entry = {
            "candidate_id": row.get("candidate_id"),
            "fec_name": row.get("fec_name"),
            "fec_party": row.get("fec_party"),
            "key": name_key(row.get("fec_name")),
            "last": last,
            "lasts": surname_variants(row.get("fec_name"), comma_is_surname_first=True),
            "tokens": frozenset(_tokens(row.get("fec_name"))),
            "first": first,
        }
        cycle = row.get("election_year", row.get("cycle"))
        index.setdefault(
            _seat_key(cycle, row.get("office"), row.get("state_po"), row.get("district_num")), []
        ).append(entry)
        by_state.setdefault(_state_key(cycle, row.get("office"), row.get("state_po")), []).append(entry)
        try:
            covered.add((int(cycle), str(row.get("office"))))
        except (TypeError, ValueError):
            pass
    return index, by_state, covered


def _match_one(source_name: object, pool: list[dict]) -> tuple[dict | None, str]:
    """Match one source name against the FEC candidates for the same seat and cycle.

    An empty pool here means the roster covers this cycle but lists nobody for this seat --
    a genuine miss, not missing coverage, which the caller has already screened for.
    """
    if not pool:
        return None, "none"
    key = name_key(source_name)
    last, first = split_name(source_name, comma_is_surname_first=False)
    lasts = surname_variants(source_name, comma_is_surname_first=False)
    tokens = frozenset(_tokens(source_name))

    def _same_surname(e: dict) -> bool:
        return bool(lasts & e["lasts"])

    for method in MATCH_METHODS:
        if method == "token_set":
            hits = [e for e in pool if key and e["key"] == key]
        elif method == "last_first":
            hits = [e for e in pool if _same_surname(e) and first and e["first"] == first]
        elif method == "last_initial":
            hits = [e for e in pool if _same_surname(e) and first[:1] and e["first"][:1] == first[:1]]
        elif method == "surname_unique":
            hits = [e for e in pool if _same_surname(e)]
        else:
            # Every source token appears in the FEC name, but not the reverse: FEC carries
            # middle and married names the returns omit -- ``ARENHOLZ, ASHLEY HINSON`` for
            # the member the ballot calls ``ASHLEY HINSON``. Requiring at least two shared
            # tokens keeps a lone common surname from matching on its own, and this rule
            # runs last, so it only sees names all four stricter rules failed on.
            hits = [e for e in pool if tokens and tokens <= e["tokens"]] if len(tokens) >= 2 else []
        # An ambiguous hit is not a match. Two candidates sharing a surname in one seat is
        # rare but real, and guessing between them would put the wrong ID on a row
        # permanently, which is worse than leaving it unmatched and visible.
        if len(hits) == 1:
            return hits[0], method
        if len(hits) > 1:
            return None, f"ambiguous_{method}"
    return None, "none"


class RosterIndex:
    """A reusable FEC roster index, so every module matches names the same way.

    ``filings`` and ``fundraising`` both have to find a named member in an FEC roster, and
    reimplementing the two-pass seat-then-state search in each place would let them drift.
    """

    def __init__(self, fec_candidates: pd.DataFrame) -> None:
        self._seat, self._state, self.covered = _fec_index(fec_candidates)

    def covers(self, cycle: object, office: object) -> bool:
        try:
            return (int(cycle), str(office)) in self.covered
        except (TypeError, ValueError):
            return False

    def match(
        self, name: object, cycle: object, office: object, state_po: object, district_num: object
    ) -> tuple[dict | None, str]:
        """``(entry, match_method)`` for one name in one seat; see ``build_crosswalk``."""
        if not is_person(name):
            return None, "not_a_person"
        seat = _seat_key(cycle, office, state_po, district_num)
        if (seat[0], seat[1]) not in self.covered:
            return None, "no_fec_roster"
        hit, method = _match_one(name, self._seat.get(seat, []))
        if hit is None and method == "none":
            wide, wide_method = _match_one(name, self._state.get(_state_key(*seat[:3]), []))
            if wide is not None:
                return wide, f"state_{wide_method}"
        return hit, method


# ----------------------------------------------------------------- build
def build_crosswalk(
    returns: pd.DataFrame,
    fec_candidates: pd.DataFrame | None = None,
    *,
    offices: tuple[str, ...] = ("us_house", "us_senate"),
) -> pd.DataFrame:
    """One crosswalk row per candidate observation in ``returns``.

    ``fec_candidates`` is the parsed roster from :mod:`...data.fec`. Passing ``None`` (or a
    roster covering only some cycles) yields the normalization layer without the FEC ID
    spine; ``match_method`` records ``no_fec_roster`` for those rows so the gap is visible
    rather than looking like a failed match.
    """
    df = returns[returns["office"].isin(offices)].copy()
    if "stage" in df.columns:
        stage = df["stage"].astype(str).str.strip().str.lower()
        df = df[stage.isin({"gen", "general", "runoff", "gen runoff"})]

    if fec_candidates is not None and len(fec_candidates):
        index, by_state, covered = _fec_index(fec_candidates)
    else:
        index, by_state, covered = {}, {}, set()

    records = []
    for row in df.to_dict("records"):
        name = row.get("candidate")
        person = is_person(name)
        seat = _seat_key(row.get("cycle"), row.get("office"), row.get("state_po"), row.get("district_num"))

        if not person:
            hit, method = None, "not_a_person"
        elif (seat[0], seat[1]) not in covered:
            hit, method = None, "no_fec_roster"
        else:
            hit, method = _match_one(name, index.get(seat, []))
            if hit is None:
                # Widen to the whole state delegation only after the seat pool has failed,
                # because FEC's district can be stale (see _fec_index). An ambiguous seat
                # hit is not retried: two same-surname candidates in one seat stay
                # unresolved rather than being re-guessed against a larger pool.
                if method == "none":
                    wide, wide_method = _match_one(name, by_state.get(_state_key(*seat[:3]), []))
                    if wide is not None:
                        hit, method = wide, f"state_{wide_method}"

        ballot, source = resolve_ballot_party(
            row.get("party"), row.get("party_simplified"), hit["fec_party"] if hit else None
        )
        caucus, overridden, _ = caucus_party_for(
            row.get("office"),
            row.get("state_po"),
            row.get("district_num"),
            row.get("cycle"),
            ballot,
            name,
        )
        last, first = split_name(name, comma_is_surname_first=False)
        records.append(
            {
                "cycle": row.get("cycle"),
                "office": row.get("office"),
                "state_po": row.get("state_po"),
                "district_num": row.get("district_num"),
                "race_id": row.get("race_id"),
                "source_name": name,
                "name_key": name_key(name) if person else "",
                "last_name": last if person else "",
                "first_name": first if person else "",
                "is_person": person,
                "raw_party": row.get("party"),
                "party_simplified": row.get("party_simplified"),
                "ballot_party": ballot,
                "ballot_party_source": source,
                "caucus_party": caucus,
                "caucus_override": overridden,
                "candidate_id": hit["candidate_id"] if hit else pd.NA,
                "fec_name": hit["fec_name"] if hit else pd.NA,
                "fec_party": hit["fec_party"] if hit else pd.NA,
                "match_method": method,
            }
        )

    out = pd.DataFrame(records, columns=CROSSWALK_COLUMNS)
    return out.sort_values(["cycle", "office", "state_po", "district_num", "source_name"]).reset_index(
        drop=True
    )


def validate_crosswalk(cw: pd.DataFrame) -> dict:
    """Gates on a built crosswalk."""
    checks: dict[str, object] = {}
    missing = [c for c in CROSSWALK_COLUMNS if c not in cw.columns]
    checks["schema.required_columns"] = not missing
    checks["schema.missing"] = missing
    if missing:
        checks["ok"] = False
        return checks

    checks["rows"] = int(len(cw))
    checks["party.canonical"] = bool(cw["ballot_party"].isin(CANONICAL_PARTIES).all())
    checks["party.caucus_canonical"] = bool(cw["caucus_party"].isin(CANONICAL_PARTIES).all())
    # A ballot-status row must never carry an identity or a party claim.
    artifacts = ~cw["is_person"]
    checks["persons.artifacts_unmatched"] = int(cw.loc[artifacts, "candidate_id"].notna().sum()) == 0
    checks["persons.artifact_rows"] = int(artifacts.sum())
    # An override that fires on a row already carrying that party is dead weight and
    # probably a mistake in the key; an override on a *major*-party row is a red flag.
    bad_override = cw["caucus_override"] & cw["ballot_party"].isin(MAJOR_PARTIES)
    checks["caucus.overrides_only_on_minor_party"] = int(bad_override.sum()) == 0
    checks["caucus.override_rows"] = int(cw["caucus_override"].sum())
    checks["match.methods_known"] = bool(
        cw["match_method"]
        .isin(
            set(MATCH_METHODS)
            | {"none", "not_a_person", "no_fec_roster"}
            | {f"ambiguous_{m}" for m in MATCH_METHODS}
            | {f"state_{m}" for m in MATCH_METHODS}
            | {f"state_ambiguous_{m}" for m in MATCH_METHODS}
        )
        .all()
    )
    checks["ok"] = all(v for v in checks.values() if isinstance(v, bool))
    return checks


def crosswalk_summary(cw: pd.DataFrame) -> dict:
    """Coverage and match rates, for the data-quality report."""
    people = cw[cw["is_person"]]
    joinable = people[people["match_method"] != "no_fec_roster"]
    return {
        "rows": int(len(cw)),
        "ballot_status_rows_excluded": int((~cw["is_person"]).sum()),
        "party_by_source": cw["ballot_party_source"].value_counts().to_dict(),
        "party_unresolved": int((cw["ballot_party"] == "UNKNOWN").sum()),
        "caucus_overrides_applied": int(cw["caucus_override"].sum()),
        "fec_roster_cycles": sorted({int(c) for c in joinable["cycle"].dropna().unique()}),
        "fec_matched": int(joinable["candidate_id"].notna().sum()),
        "fec_match_rate": (float(joinable["candidate_id"].notna().mean()) if len(joinable) else float("nan")),
        "match_by_method": people["match_method"].value_counts().to_dict(),
    }


def resolve_race_winners(cw: pd.DataFrame, returns: pd.DataFrame) -> pd.DataFrame:
    """Winner of each race, with ballot-status rows excluded and party normalized.

    The reason this exists rather than a ``groupby(...).idxmax()`` at the call site: the
    largest vote pile in ME-02 2022 belongs to ``EXHAUSTED BALLOT``, so max-votes is only
    a winner lookup once non-people are removed.
    """
    votes = returns[["race_id", "candidate", "candidatevotes", "stage"]].copy()
    stage = votes["stage"].astype(str).str.strip().str.lower()
    # A runoff decides the seat, so it outranks the general it followed.
    votes["decisive_rank"] = stage.isin({"runoff", "gen runoff"}).astype(int)
    merged = cw.merge(
        votes, left_on=["race_id", "source_name"], right_on=["race_id", "candidate"], how="left"
    )
    people = merged[merged["is_person"]]
    # ``.head(1)`` rather than ``.first()``: GroupBy.first takes the first *non-null value
    # per column* independently, which stitches one row's ``source_name`` onto another
    # row's ``candidate_id``. In IA-01 2024 that returned Miller-Meeks (the winner) wearing
    # Bohannan's FEC identity, because Miller-Meeks was unmatched and Bohannan was not.
    return (
        people.sort_values(["decisive_rank", "candidatevotes"], ascending=False, na_position="last")
        .groupby("race_id", as_index=False, sort=False)
        .head(1)
        .sort_values("race_id")
        .reset_index(drop=True)
    )

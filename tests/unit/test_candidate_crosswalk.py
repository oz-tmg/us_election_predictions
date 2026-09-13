"""Candidate and party normalization (P0-003).

Every test here is a defect observed in the real 1976-2024 returns or the real FEC roster,
named so a regression says which one came back.
"""

from __future__ import annotations

import pandas as pd
import pytest

from election_prediction.features import candidate_crosswalk as cc


def _returns(rows: list[dict]) -> pd.DataFrame:
    base = {
        "race_id": "r1",
        "cycle": 2024,
        "office": "us_house",
        "state_po": "GA",
        "district_num": 1.0,
        "candidate": "JANE DOE",
        "party": "DEMOCRAT",
        "party_simplified": "DEMOCRAT",
        "candidatevotes": 1000,
        "stage": "gen",
    }
    return pd.DataFrame([{**base, **r} for r in rows])


def _roster(rows: list[dict]) -> pd.DataFrame:
    base = {
        "candidate_id": "H0GA01001",
        "fec_name": "DOE, JANE",
        "office": "us_house",
        "state_po": "GA",
        "district_num": 1,
        "fec_party": "DEM",
        "election_year": 2024,
        "cycle": 2024,
    }
    return pd.DataFrame([{**base, **r} for r in rows])


# ------------------------------------------------------------------ party aliasing
@pytest.mark.parametrize(
    "label,expected",
    [
        ("DEMOCRATIC", cc.DEMOCRAT),  # the label that lost Duckworth and Van Hollen
        ("DFL", cc.DEMOCRAT),  # Minnesota
        ("DEMOCRATIC-NPL", cc.DEMOCRAT),  # North Dakota
        ("INDEPENDENT REPUBLICAN", cc.REPUBLICAN),  # Minnesota's GOP, 1975-1995
        ("REP", cc.REPUBLICAN),
        ("NO PARTY AFFILIATION", "INDEPENDENT"),
        ("", "UNKNOWN"),
    ],
)
def test_state_party_names_alias_to_the_national_party(label, expected):
    assert cc.normalize_party(label) == expected


@pytest.mark.parametrize(
    "label", ["DEMOCRATIC SOCIALIST", "NATIONAL DEMOCRATIC PARTY OF ALABAMA", "DEMOCRAT/REPUBLICAN"]
)
def test_a_label_containing_a_major_party_name_is_not_that_party(label):
    """Exactly the labels a substring rule would absorb, and each is a different party."""
    assert cc.normalize_party(label) == "OTHER"


def test_an_unknown_label_is_never_guessed_into_a_major_party():
    assert cc.normalize_party("MOUNTAIN PARTY") == "OTHER"


# ------------------------------------------------------------------ ballot party
def test_the_raw_medsl_label_beats_its_own_simplified_column():
    """MEDSL maps DEMOCRATIC to OTHER in 5 rows; two of them are sitting senators."""
    party, source = cc.resolve_ballot_party("DEMOCRATIC", "OTHER")
    assert (party, source) == (cc.DEMOCRAT, "medsl_raw")


def test_fec_fills_a_race_with_no_party_data_at_all():
    """Wyoming 2020 and Alaska 2010/2022 carry a null party for every candidate."""
    party, source = cc.resolve_ballot_party(None, None, "REP")
    assert (party, source) == (cc.REPUBLICAN, "fec")


def test_a_party_stays_unresolved_rather_than_defaulting():
    assert cc.resolve_ballot_party(None, None, None) == ("UNKNOWN", "unresolved")


# ------------------------------------------------------------------ caucus party
def test_an_independent_who_caucuses_with_a_party_is_recorded_separately():
    """Sanders's 2024 two-party Dem share is 0.000; control counts need caucus_party."""
    ballot, _ = cc.resolve_ballot_party("INDEPENDENT", "OTHER")
    caucus, overridden, evidence = cc.caucus_party_for(
        "us_senate", "VT", None, 2024, ballot, "BERNIE SANDERS"
    )
    assert ballot == "INDEPENDENT"
    assert (caucus, overridden) == (cc.DEMOCRAT, True)
    assert evidence


def test_a_caucus_override_applies_to_the_member_not_to_the_race():
    """Keying only on the contest gave Sanders's Republican opponent caucus_party DEMOCRAT."""
    caucus, overridden, _ = cc.caucus_party_for("us_house", "VT", 0, 1990, cc.REPUBLICAN, "PETER SMITH")
    assert (caucus, overridden) == (cc.REPUBLICAN, False)


def test_an_override_does_not_leak_into_a_later_cycle():
    """Vermont's House seat: Sanders through 2004, somebody else after."""
    caucus, overridden, _ = cc.caucus_party_for("us_house", "VT", 0, 2006, "INDEPENDENT", "PETER WELCH")
    assert (caucus, overridden) == ("INDEPENDENT", False)


def test_caucus_party_defaults_to_ballot_party():
    assert cc.caucus_party_for("us_house", "GA", 1, 2024, cc.DEMOCRAT, "JANE DOE")[0] == cc.DEMOCRAT


# ------------------------------------------------------------------ ballot statuses
@pytest.mark.parametrize(
    "name",
    [
        "EXHAUSTED BALLOT",  # Maine's ranked-choice pile; outpolled Golden in ME-02 2022
        "WRITEIN",
        "OVER VOTE",
        "BLANK VOTE/SCATTERING",  # a combined disposition pile, 393 races
        "BLANK VOTE/VOID VOTE/SCATTERING",
        "ALL OTHERS",
        "",
    ],
)
def test_a_ballot_disposition_is_not_a_person(name):
    assert not cc.is_person(name)


@pytest.mark.parametrize("name", ["JOHN BLANKENSHIP", "TOTAL RECALL SMITH", "SCATTERGOOD JONES"])
def test_a_real_name_containing_a_status_word_is_still_a_person(name):
    """Why the rule matches whole names: BLANKS is a status, BLANKENSHIP is a candidate."""
    assert cc.is_person(name)


# ------------------------------------------------------------------ names
def test_the_two_sources_write_names_in_opposite_orders():
    assert cc.name_key("CHRIS VAN HOLLEN") == cc.name_key("VAN HOLLEN, CHRIS")


def test_a_nickname_is_dropped_from_the_key():
    assert cc.name_key('EARL L. "BUDDY" CARTER') == cc.name_key("CARTER, EARL L")


def test_a_curly_quoted_nickname_is_dropped_too():
    """MEDSL uses curly quotes; the ASCII fold deletes them and left CHUY as a token."""
    assert cc.name_key("HENRY C “HANK” JOHNSON, JR") == cc.name_key("JOHNSON, HENRY C JR")


def test_an_accent_does_not_break_a_match():
    assert cc.name_key("RAÚL M. GRIJALVA") == cc.name_key("GRIJALVA, RAUL M")


def test_a_double_encoded_name_is_repaired():
    """46 names in silver cycle 2022 are UTF-8 read as Latin-1, then upper-cased."""
    assert cc.name_key("JESÃ\x9aS G Â\x80\x9cCHUYÂ\x80\x9d GARCÃ\x8dA") == cc.name_key(
        "GARCIA, JESUS G"
    )


def test_an_apostrophe_surname_normalizes_the_same_either_way():
    """101 names carry an apostrophe surname against 1 single-quoted nickname."""
    assert cc.name_key("JOHN O'NEILL") == cc.name_key("O’NEILL, JOHN") == "JOHN|ONEILL"


def test_the_one_single_quoted_nickname_is_still_dropped():
    assert cc.name_key("CONSTANT 'CONNOR' VLAKANCIC") == cc.name_key("VLAKANCIC, CONSTANT")


def test_a_comma_before_a_suffix_is_not_a_surname_first_comma():
    assert cc.split_name("HENRY C JOHNSON, JR") == ("JOHNSON", "HENRY")


def test_a_multi_word_surname_survives_a_surname_first_spelling():
    assert cc.split_name("VAN HOLLEN, CHRIS", comma_is_surname_first=True)[0] == "VAN HOLLEN"


def test_a_particle_surname_is_matchable_from_either_spelling():
    """MEDSL cannot see that VAN DREW is one surname; FEC's comma can."""
    assert cc.surname_variants("JEFFERSON VAN DREW") & cc.surname_variants(
        "VAN DREW, JEFF MR", comma_is_surname_first=True
    )


# ------------------------------------------------------------------ the join
def test_a_candidate_id_is_attached_when_the_roster_covers_the_cycle():
    cw = cc.build_crosswalk(_returns([{}]), _roster([{}]))
    assert cw.iloc[0]["candidate_id"] == "H0GA01001"
    assert cw.iloc[0]["match_method"] == "token_set"


def test_a_stale_fec_district_still_finds_the_member():
    """FEC's district is the last filing's, not the seat run in: Bera is filed CA-03."""
    cw = cc.build_crosswalk(
        _returns([{"state_po": "CA", "district_num": 6.0, "candidate": "AMI BERA"}]),
        _roster([{"state_po": "CA", "district_num": 3, "fec_name": "BERA, AMERISH"}]),
    )
    assert cw.iloc[0]["candidate_id"] == "H0GA01001"
    assert cw.iloc[0]["match_method"].startswith("state_")


def test_a_married_or_added_surname_matches_on_the_token_subset():
    """FEC files ARENHOLZ, ASHLEY HINSON for the member the ballot calls ASHLEY HINSON."""
    cw = cc.build_crosswalk(
        _returns([{"candidate": "ASHLEY HINSON"}]),
        _roster([{"fec_name": "ARENHOLZ, ASHLEY HINSON"}]),
    )
    assert cw.iloc[0]["match_method"] == "token_subset"


def test_a_cycle_the_roster_does_not_cover_is_labelled_not_looked_at():
    """'no_fec_roster' and 'none' mean opposite things and must not be collapsed."""
    cw = cc.build_crosswalk(_returns([{"cycle": 1994}]), _roster([{}]))
    assert cw.iloc[0]["match_method"] == "no_fec_roster"
    assert pd.isna(cw.iloc[0]["candidate_id"])


def test_a_candidate_never_matches_a_different_cycle_in_the_same_seat():
    """Without the cycle in the key, a 1994 return matches the 2024 roster by surname."""
    cw = cc.build_crosswalk(
        _returns([{"cycle": 1994, "candidate": "JANE DOE"}]),
        _roster([{}, {"candidate_id": "H0GA01999", "election_year": 1994, "fec_name": "SMITH, BOB"}]),
    )
    assert pd.isna(cw.iloc[0]["candidate_id"])


def test_two_candidates_sharing_a_surname_are_left_unmatched():
    """Guessing puts a wrong candidate_id downstream permanently; ambiguity is safer."""
    cw = cc.build_crosswalk(
        _returns([{"candidate": "BOB ONDER"}]),
        _roster(
            [
                {"fec_name": "ONDER, ROBERT FOR JR."},
                {"candidate_id": "H0GA01002", "fec_name": "ONDER JR, ROBERT FRANK"},
            ]
        ),
    )
    assert pd.isna(cw.iloc[0]["candidate_id"])
    assert cw.iloc[0]["match_method"].startswith("ambiguous_")


def test_a_ballot_status_row_never_receives_an_identity():
    cw = cc.build_crosswalk(_returns([{"candidate": "EXHAUSTED BALLOT"}]), _roster([{}]))
    assert cw.iloc[0]["match_method"] == "not_a_person"
    assert pd.isna(cw.iloc[0]["candidate_id"])


def test_the_crosswalk_builds_without_any_fec_roster():
    cw = cc.build_crosswalk(_returns([{}]))
    assert cc.validate_crosswalk(cw)["ok"]
    assert cw.iloc[0]["ballot_party"] == cc.DEMOCRAT
    assert cw.iloc[0]["match_method"] == "no_fec_roster"


# ------------------------------------------------------------------ winners
def test_the_winner_is_the_top_person_not_the_top_vote_pile():
    """ME-02 2022: EXHAUSTED BALLOT polled 322,778 against Golden's 165,136."""
    returns = _returns(
        [
            {"candidate": "JARED F GOLDEN", "candidatevotes": 165136},
            {"candidate": "EXHAUSTED BALLOT", "candidatevotes": 322778, "party": None},
        ]
    )
    won = cc.resolve_race_winners(cc.build_crosswalk(returns), returns)
    assert won.iloc[0]["source_name"] == "JARED F GOLDEN"


def test_the_winner_row_is_one_candidate_not_a_blend_of_two():
    """GroupBy.first takes the first non-null *per column* and stitched two people."""
    returns = _returns(
        [
            {"candidate": "JANE DOE", "candidatevotes": 100},
            {"candidate": "MARY ROE", "candidatevotes": 900, "party": "REPUBLICAN"},
        ]
    )
    won = cc.resolve_race_winners(cc.build_crosswalk(returns, _roster([{}])), returns)
    row = won.iloc[0]
    assert row["source_name"] == "MARY ROE"
    # Jane Doe is the only candidate in the roster, so a blended row would show her ID.
    assert pd.isna(row["candidate_id"])


def test_a_runoff_outranks_the_general_it_followed():
    returns = _returns(
        [
            {"candidate": "JANE DOE", "candidatevotes": 900, "stage": "gen"},
            {"candidate": "MARY ROE", "candidatevotes": 100, "stage": "runoff"},
        ]
    )
    won = cc.resolve_race_winners(cc.build_crosswalk(returns), returns)
    assert won.iloc[0]["source_name"] == "MARY ROE"

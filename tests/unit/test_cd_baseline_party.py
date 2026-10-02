"""The party fallback: what it must catch, and the hazard it accepts."""

from __future__ import annotations

import pandas as pd

from election_prediction.features.cd_baseline import _major_party


def _rows(pairs):
    return pd.DataFrame(
        [{"party_detailed": d, "party_simplified": s} for d, s in pairs]
    )


def test_state_affiliate_labels_are_recovered():
    """The bug: MEDSL simplifies both of these to OTHER, zeroing a state's Democratic vote."""
    out = _major_party(_rows([("DEMOCRATIC FARMER LABOR", "OTHER"), ("DEMOCRATIC-NPL", "OTHER")]))
    assert list(out) == ["DEMOCRAT", "DEMOCRAT"]


def test_a_correct_simplified_label_is_still_honoured():
    out = _major_party(_rows([("DEMOCRAT", "DEMOCRAT"), ("REPUBLICAN", "REPUBLICAN")]))
    assert list(out) == ["DEMOCRAT", "REPUBLICAN"]


def test_genuine_third_parties_stay_other():
    out = _major_party(_rows([("LIBERTARIAN", "LIBERTARIAN"), ("GREEN", "OTHER"), ("INDEPENDENT", "OTHER")]))
    assert list(out) == ["OTHER", "OTHER", "OTHER"]


def test_the_accepted_hazard_is_a_substring_over_match():
    """A party merely CONTAINING 'democrat' is claimed, and that is deliberate.

    An allowlist of affiliate names would be tighter but needs updating whenever a state
    invents one, and silently under-counting a major party (the MN/ND bug) is far more
    damaging than over-claiming a minor line. The reconciliation gate in
    ``build_cd_baselines`` is the backstop: an over-match inflates a state's Democratic
    share and fails the check against its certified return. Empirically no 2020 state
    failed in that direction.
    """
    out = _major_party(_rows([("DEMOCRATIC SOCIALIST", "OTHER")]))
    assert list(out) == ["DEMOCRAT"]


def test_a_missing_simplified_column_does_not_crash():
    out = _major_party(pd.DataFrame([{"party_detailed": "DEMOCRATIC FARMER LABOR"}]))
    assert list(out) == ["DEMOCRAT"]

"""Bound the shrinkage factor from history — bound, never fit (NE-002).

The specials estimator says the environment moved; it cannot say how much of that movement
carries into a general election. That ratio is the shrinkage factor, and
``national_environment`` currently sweeps it as an assumption because nothing in one cycle
identifies it (see ``blog/posts/03-the-parameter-that-wasnt-there.md``).

History can narrow it. For each past cycle where both halves are observable — the specials
that ran during the cycle, and the general that followed — the realised ratio is

    realised_shrinkage = general_swing / specials_overperformance

Four such pairs exist in the modern era: 2017→18, 2019→20, 2021→22, 2023→24. That is four
observations of a quantity that varies by cycle, which is emphatically **not** enough to
estimate a parameter. It is enough to put a floor and a ceiling on one.

So this module returns an **interval with ``status = "bound"``**, never a point, and a test
fails if a scalar is ever returned. The distinction is the whole point and it is worth
stating plainly:

* A *fit* says "the shrinkage factor is 0.58 (se 0.11)" and invites you to use 0.58.
* A *bound* says "across four observed cycles it ran between 0.41 and 0.79, and four cycles
  cannot rule out that the next one sits outside that" — and invites you to sweep 0.41 to
  0.79 instead of 0.25 to 1.0.

Narrowing the sweep is the entire deliverable. On the current band, the Senate is
unresolvable precisely because the sweep is wide enough to straddle a coin flip; a tighter
sweep is the cheapest route to resolving it or to proving it cannot be resolved.

**The pairs are hand-compiled and not yet collected.** Like the plan-version register, every
row needs a source and a human. ``docs/shrinkage-calibration-worklist.md`` is the
compilation task; this module is the machinery that consumes it, and it refuses to run on
an empty or unsourced table rather than inventing a bound.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

PAIR_COLUMNS = [
    "pair_id",
    "specials_cycle",
    "general_cycle",
    "chamber",
    "specials_overperformance",
    "specials_n",
    "general_margin_swing",
    "source_url",
    "retrieved_on",
    "verified_by",
    "notes",
]

REQUIRED_NON_EMPTY = ["pair_id", "chamber", "source_url", "retrieved_on", "verified_by"]

# The four pairs the backlog names. Fewer than four is a partial compilation, not a bound.
EXPECTED_PAIRS = ("2017_2018", "2019_2020", "2021_2022", "2023_2024")

STATUS_BOUND = "bound"
STATUS_INSUFFICIENT = "insufficient"


class CalibrationError(ValueError):
    """The pair table cannot support a bound."""


@dataclass(frozen=True)
class ShrinkageBound:
    """An interval for the shrinkage factor. Never a point — see the module docstring."""

    status: str
    low: float | None
    high: float | None
    realised: pd.DataFrame | None
    n_pairs: int
    assumptions: list[str] = field(default_factory=list)
    caveats: list[str] = field(default_factory=list)
    provenance: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.status not in (STATUS_BOUND, STATUS_INSUFFICIENT):
            raise CalibrationError(f"unknown status {self.status!r}")

    def as_factors(self, *, n: int = 5) -> tuple[float, ...]:
        """The sweep this bound implies, for ``national_environment.from_specials``.

        Returns the endpoints and evenly spaced interior points. Deliberately returns a
        tuple of factors rather than a single number: the consumer must keep sweeping.
        """
        if self.status != STATUS_BOUND:
            raise CalibrationError(
                "no bound available; compile the calibration pairs "
                "(docs/shrinkage-calibration-worklist.md) before narrowing the sweep"
            )
        return tuple(round(float(x), 4) for x in np.linspace(self.low, self.high, n))

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "low": self.low,
            "high": self.high,
            "n_pairs": self.n_pairs,
            "realised": None if self.realised is None else self.realised.to_dict(orient="records"),
            "assumptions": list(self.assumptions),
            "caveats": list(self.caveats),
            "provenance": dict(self.provenance),
        }


def _blank(series: pd.Series) -> pd.Series:
    """True where a cell is empty, whatever shape 'empty' arrives in.

    pandas 3 stopped rendering a missing float as the string "nan" under ``astype(str)``,
    which silently defeated a string-comparison blank check here: an uncompiled column was
    reported as "not numeric" (a bug) instead of "not yet compiled" (a to-do). Test
    ``test_a_blank_cell_and_a_garbage_cell_are_reported_differently`` pins the distinction.
    """
    text = series.astype("string").fillna("").str.strip()
    return series.isna() | text.isin(["", "nan", "None", "<NA>"])


def validate_pairs(pairs: pd.DataFrame) -> None:
    """Every row must be sourced and checked, exactly as the plan-version register is."""
    missing_cols = [c for c in PAIR_COLUMNS if c not in pairs.columns]
    if missing_cols:
        raise CalibrationError(f"pair table is missing column(s) {missing_cols}")

    problems: list[str] = []
    for col in REQUIRED_NON_EMPTY:
        for _, row in pairs[_blank(pairs[col])].iterrows():
            problems.append(f"{row['pair_id'] or '<no pair_id>'}: empty {col}")

    # A blank cell is "not compiled yet" and a garbage cell is a mistake. Saying so
    # separately is the difference between a to-do and a bug.
    for col in ("specials_overperformance", "general_margin_swing"):
        blank = _blank(pairs[col])
        numeric = pd.to_numeric(pairs[col], errors="coerce")
        for _, row in pairs[blank].iterrows():
            problems.append(
                f"{row['pair_id']}: {col} is not yet compiled "
                "(see docs/shrinkage-calibration-worklist.md)"
            )
        for _, row in pairs[~blank & numeric.isna()].iterrows():
            problems.append(f"{row['pair_id']}: {col} is not numeric")

    zero = pairs[pd.to_numeric(pairs["specials_overperformance"], errors="coerce") == 0]
    for _, row in zero.iterrows():
        problems.append(f"{row['pair_id']}: specials_overperformance is zero; the ratio is undefined")

    if problems:
        raise CalibrationError("calibration pairs failed validation:\n  - " + "\n  - ".join(problems))


def calibration_pairs(pairs: pd.DataFrame) -> pd.DataFrame:
    """Realised shrinkage per cycle pair: general swing over specials overperformance."""
    validate_pairs(pairs)
    out = pairs.copy()
    out["specials_overperformance"] = pd.to_numeric(out["specials_overperformance"])
    out["general_margin_swing"] = pd.to_numeric(out["general_margin_swing"])
    out["realised_shrinkage"] = out["general_margin_swing"] / out["specials_overperformance"]
    return out[[*PAIR_COLUMNS, "realised_shrinkage"]].sort_values("pair_id").reset_index(drop=True)


def band_from_pairs(pairs: pd.DataFrame, *, min_pairs: int = 3) -> ShrinkageBound:
    """An interval for shrinkage, from the observed range across cycle pairs.

    The bound is the **observed min and max**, not a confidence interval. With four
    observations a confidence interval would be a distributional claim the data cannot
    support; the range is a statement about what has actually happened, which it can.
    """
    if pairs is None or not len(pairs):
        return ShrinkageBound(
            status=STATUS_INSUFFICIENT,
            low=None,
            high=None,
            realised=None,
            n_pairs=0,
            caveats=[
                "No calibration pairs compiled. See docs/shrinkage-calibration-worklist.md; "
                "until they exist the shrinkage sweep stays at its default width."
            ],
        )

    realised = calibration_pairs(pairs)
    n = len(realised)
    if n < min_pairs:
        return ShrinkageBound(
            status=STATUS_INSUFFICIENT,
            low=None,
            high=None,
            realised=realised,
            n_pairs=n,
            caveats=[f"only {n} pair(s) compiled; {min_pairs} are the minimum for a bound"],
        )

    values = realised["realised_shrinkage"]
    missing = sorted(set(EXPECTED_PAIRS) - set(realised["pair_id"]))
    return ShrinkageBound(
        status=STATUS_BOUND,
        low=float(values.min()),
        high=float(values.max()),
        realised=realised,
        n_pairs=n,
        assumptions=[
            "The bound is the observed range across cycle pairs, not a confidence interval: "
            f"{n} observations cannot support a distributional claim.",
            "Each pair's specials overperformance is computed through the same "
            "compute_overperformance path as the live estimate, so the bound and the "
            "estimate it constrains are measured the same way.",
        ],
        caveats=[
            f"{n} cycle pairs is a bound, never a fit. A future cycle can fall outside this "
            "range and nothing here rules that out.",
            "Midterm and presidential cycles are pooled. The relationship plausibly differs "
            "between them, and with four pairs it cannot be split without losing the bound.",
            "Specials are a non-random sample of seats in every cycle, so this bound inherits "
            "every selection caveat the live estimate carries.",
        ]
        + ([f"pairs not yet compiled: {missing}"] if missing else []),
        provenance={
            "source_id": "shrinkage_calibration_pairs",
            "pair_ids": realised["pair_id"].tolist(),
            "oldest_retrieved_on": str(realised["retrieved_on"].min()),
            "chambers": sorted(realised["chamber"].unique().tolist()),
        },
    )

"""Named scenarios: explicit, described adjustments laid over a projection.

A scenario is never an estimate. It states an assumption, applies it to per-seat means
*before* the correlated simulation (so chamber odds are re-simulated, not recounted), and
is exported with ``kind = scenario`` so it can never be mistaken for the projection.
"""

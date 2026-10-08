"""Prove the scoring path runs end to end, before the election rather than after.

The sealed forecast's whole value is out-of-sample evidence, and the machinery that collects
it had never been executed against real inputs. Election night is the wrong time to discover
that `score_preregistration` and the results ledger disagree about a column name.

So this rehearses the entire path on a *known* outcome — the 2024 House results, reshaped
into the 2026 ledger schema and scored against the sealed 2026 forecast. The resulting
metrics are **meaningless as a forecast evaluation**: the forecast is for 2026 and the
"outcome" is 2024. That is deliberate. What is being tested is whether the pipes connect:
snapshot -> validation -> ledger -> `certified_on` -> `to_actual` -> seal verification ->
metrics, with the registered ``as_of`` rule applied.

A green run here means that on the night, the only unknown is the data.

Run:  python scripts/dry_run_scoring.py
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pandas as pd

from election_prediction.data import results_2026 as r26
from election_prediction.evaluation import score_preregistration as sp
from election_prediction.geography import reference as ref

SEAL = Path("reports/preregistration_2026-11-03.json")


def main() -> int:
    if not SEAL.is_file():
        print(f"no sealed registration at {SEAL}")
        return 1

    returns = pd.read_parquet("data/silver/election_returns.parquet")
    house = returns[
        (returns["office"] == "us_house")
        & (returns["cycle"] == 2024)
        & (returns["party_simplified"].isin(["DEMOCRAT", "REPUBLICAN"]))
    ]
    wide = (
        house.assign(district_num=pd.to_numeric(house["district_num"], errors="coerce"))
        .dropna(subset=["district_num"])
        .pivot_table(
            index=["state_po", "district_num"],
            columns="party_simplified",
            values="candidatevotes",
            aggfunc="sum",
        )
        .fillna(0.0)
        .reset_index()
    )
    for party in ("DEMOCRAT", "REPUBLICAN"):
        if party not in wide.columns:
            wide[party] = 0.0

    snapshot = pd.DataFrame(
        {
            "state_po": wide["state_po"],
            "district_num": wide["district_num"].astype(int),
            "office": "us_house",
            "dem_votes": wide["DEMOCRAT"],
            "rep_votes": wide["REPUBLICAN"],
            "other_votes": 0,
            "certified": True,
            "source_url": "DRY RUN — 2024 certified returns standing in for 2026",
            "retrieved_on": "2026-11-05",
        }
    )

    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        # Two snapshots, so the certified_on derivation is exercised rather than trivial.
        half = len(snapshot) // 2
        r26.write_snapshot(snapshot.head(half), observed_on="2026-11-05", directory=directory)
        r26.write_snapshot(snapshot, observed_on="2026-11-12", directory=directory)

        ledger = r26.certification_ledger(r26.read_snapshots(directory))
        fips = {postal: ref.by_postal(postal).fips for postal in ref.STATES}
        act = r26.to_actual(ledger, state_fips=fips)

    print(
        f"ledger: {len(ledger)} seats, "
        f"{int(ledger['certified_on'].notna().sum())} with a certification date\n"
        f"  earliest certified_on: {ledger['certified_on'].min()}  "
        f"latest: {ledger['certified_on'].max()}"
    )

    seal = json.loads(SEAL.read_text())
    # No map has moved, so the void set is empty. Passing it explicitly rather than
    # defaulting it is the registered behaviour: a void seat needs a stated source, so
    # "nothing is void" has to be an assertion the caller makes.
    inputs = sp.ScoringInputs(registration=seal, actual=act, as_of="2026-11-20", void_geographies={})
    result = sp.score(inputs)

    print("\nscoring ran. Headline figures are MEANINGLESS (2024 outcome vs 2026 forecast):")
    print(json.dumps(_trim(result), indent=2, default=str)[:1800])
    print("\nDRY RUN PASSED — the path connects end to end.")
    return 0


def _trim(result: object, depth: int = 0) -> object:
    if isinstance(result, dict):
        return {
            k: _trim(v, depth + 1)
            for k, v in result.items()
            if depth < 2 and k not in {"per_seat", "seats", "predictions"}
        }
    if isinstance(result, list):
        return f"[{len(result)} items]"
    return result


if __name__ == "__main__":
    raise SystemExit(main())

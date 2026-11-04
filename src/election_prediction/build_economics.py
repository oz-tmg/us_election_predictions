"""Acquire registered ALFRED vintages and report the NE-004 cross-check."""

from __future__ import annotations

import argparse
import json
import time
from datetime import date
from pathlib import Path

import pandas as pd

from .config import load_dotenv
from .data import fred
from .features import national_fundamentals as features
from .models.baseline import economic_fundamentals as model


def build(*, as_of: str, start_cycle: int = 1980) -> dict:
    load_dotenv()
    output = Path("reports") / f"refresh_{as_of}"
    output.mkdir(parents=True, exist_ok=True)
    races = pd.read_parquet("data/gold/race_results.parquet")
    rows, missing = [], []
    for cycle in range(start_cycle, 2028, 2):
        cutoff = f"{cycle}-10-20"
        if pd.Timestamp(cutoff) > pd.Timestamp(as_of):
            continue
        observations = []
        for series_id in fred.SERIES:
            try:
                path = fred.download(series_id, vintage=cutoff)
                observations.append(fred.parse(path, series_id=series_id, vintage=cutoff))
            except fred.VintageUnavailable as exc:
                missing.append({"cycle": cycle, "series_id": series_id, "reason": str(exc)})
            time.sleep(0.1)
        frame = (
            pd.concat(observations, ignore_index=True)
            if observations
            else pd.DataFrame(columns=["series_id"])
        )
        row = {
            **features.political_features(races, cycle=cycle),
            **features.economic_features(frame, cycle=cycle, vintage=cutoff),
        }
        row["incumbent_share"] = features.target(
            races, cycle=cycle, white_house_party=row["white_house_party"]
        )
        rows.append(row)
        print(f"economics {cycle}: {len(frame)} observations", flush=True)
    panel = pd.DataFrame(rows)
    historical, live = panel[panel.cycle < 2026], panel[panel.cycle.eq(2026)]
    evaluation = model.evaluate(historical)
    estimate = model.estimate(historical, live, evaluation)
    panel.to_csv(output / "economic_panel.csv", index=False)
    result = {
        "as_of": as_of,
        "fixed_cutoff": "October 20",
        "evaluation": evaluation,
        "missing_vintages": missing,
        "estimate": estimate.to_dict(),
        "release_date_limit": "Exact release date unavailable in clipped point-in-time responses",
    }
    (output / "economic_cross_check.json").write_text(json.dumps(result, indent=2, default=str))
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", default=date.today().isoformat())
    parser.add_argument("--start-cycle", type=int, default=1980)
    args = parser.parse_args(argv)
    build(as_of=args.as_of, start_cycle=args.start_cycle)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

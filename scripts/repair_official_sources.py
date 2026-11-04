"""Acquire and validate registered official replacements without overwriting MEDSL raw files."""

import json
from datetime import date
from pathlib import Path

import pandas as pd

from election_prediction.data import official_repairs
from election_prediction.data.privacy import PrivacyTier
from election_prediction.data.public_sources import snapshot


def main() -> int:
    stamp = date.today().isoformat()
    output = Path(f"reports/refresh_{stamp}")
    output.mkdir(parents=True, exist_ok=True)
    path = snapshot(
        "https://sos.ks.gov/elections/24elec/2024-General-Election-President-Precinct-Level-Results.xlsx",
        Path(f"data/raw/source=kansas_sos/dataset=president_precinct_2024/snapshot={stamp}/results.xlsx"),
        source_id="ks_official_president_precinct_2024",
        owner="Kansas Secretary of State",
        expect="zip",
        tier=PrivacyTier.PUBLIC_SENSITIVE_AGGREGATE,
    )
    frame = official_repairs.kansas_2024(path, pd.read_parquet("data/silver/tiger_county_2024.parquet"))
    report = official_repairs.reconciliation(
        frame, pd.read_parquet("data/gold/race_results.parquet"), state="KS", cycle=2024
    )
    (output / "kansas_official_repair.json").write_text(json.dumps(report, indent=2))
    if report["reconciles"]:
        frame.to_parquet("data/bronze/official_ks_president_precinct_2024.parquet", index=False)
    print(json.dumps(report, indent=2))
    return 0 if report["reconciles"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

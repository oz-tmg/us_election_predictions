"""Run the complete-House chronological diagnostic without changing forecast parameters."""

import json
from pathlib import Path

import pandas as pd

from election_prediction.evaluation import chamber

output = Path("reports/refresh_2026-10-21")
output.mkdir(parents=True, exist_ok=True)
predictions, omitted = chamber.house_predictions(
    pd.read_parquet("data/gold/house_panel.parquet"),
    pd.read_parquet("data/gold/presidential_panel.parquet"),
    pd.read_parquet("data/gold/race_results.parquet"),
    canonical_winners=pd.read_parquet("data/gold/race_winners.parquet"),
)
predictions.to_csv(output / "full_chamber_predictions.csv", index=False)
(output / "full_chamber_evaluation.json").write_text(
    json.dumps(chamber.evaluate(predictions, omitted), indent=2)
)

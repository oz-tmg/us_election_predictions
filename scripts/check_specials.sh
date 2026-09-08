#!/usr/bin/env bash
# Validate the special-elections compilation. Run from the repo root.
set -euo pipefail
source .venv/bin/activate
python - <<'PY'
import sys; sys.path.insert(0, "src")
from election_prediction.data import special_elections as se
df = se.read_compiled("data/reference/special_elections_2025_2026.csv")
rep = se.validate_specials(df)
bad = [k for k, v in rep.items() if isinstance(v, bool) and not v]
print(f"rows={rep['rows']}  excluded={rep['exclusion.rows_excluded']}  valid={rep['ok']}")
if bad:
    print("failing gates:", ", ".join(bad))
    if rep.get("provenance.rows_without_source"):
        print(f"  rows missing source_url: {rep['provenance.rows_without_source']}")
    if rep.get("votes.rows_one_sided_but_included"):
        print(f"  one-sided rows still in the metric: {rep['votes.rows_one_sided_but_included']}")
    sys.exit(1)
out = se.compute_overperformance(df)
cols = ["special_id", "contest_format", "include_in_metric", "turnout_ratio",
        "special_margin", "baseline_margin", "overperformance"]
print(out[cols].round(4).to_string(index=False))
est = se.national_environment_estimate(out)
print()
for k, v in est.items():
    if k == "caveats":
        continue
    if k == "excluded":
        for sid, why in v.items():
            print(f"  excluded {sid}: {why}")
    else:
        print(f"  {k}: {v}")
PY

"""Read-only preflight for the operator-provisioned elections-data CI runner."""

from __future__ import annotations

import json
import os
from pathlib import Path

REQUIRED = [
    "silver/election_returns.parquet",
    "gold/race_results.parquet",
    "gold/house_panel.parquet",
    "gold/presidential_panel.parquet",
]


def check(root: Path | None) -> dict:
    if root is None:
        return {"ok": False, "reason": "ELECTION_DATA_ROOT/EP_DATA_ROOT is not configured"}
    root = root.resolve()
    # actions/checkout may clean its work directory. The data lake must be separate.
    workspace = os.getenv("GITHUB_WORKSPACE")
    if workspace and root.is_relative_to(Path(workspace).resolve()):
        return {"ok": False, "reason": "Live data root must be outside the disposable runner checkout"}
    missing = [name for name in REQUIRED if not (root / name).is_file()]
    return {
        "ok": not missing,
        "data_root": str(root),
        "missing": missing,
        "secret_values_examined": False,
        "data_modified": False,
    }


if __name__ == "__main__":
    value = os.getenv("EP_DATA_ROOT")
    report = check(Path(value) if value else None)
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["ok"] else 1)

#!/usr/bin/env python
"""Record 2026 cross-checks for states whose 2026 release format differs from 2024.

    python scripts/record_cross_checks.py --input-dir <dir of <ST>_crosscheck.json> --as-of 2026-11-13

A state whose 2026 files are laid out differently from its 2024 files cannot earn
``parser_tested_2024`` for the parser that reads 2026: that parser never saw certified
data. Two weaker checks stand in, and both must pass:

1. the state's 2024-layout parser reproduces the certified 2024 returns (the contest and
   party rules are right), and
2. the 2026-layout parser agrees, race by race, with a summary the state publishes
   separately from the parsed file (``state_extraction.cross_check``).

Such a state is recorded as ``parser_cross_checked_2026``. A state whose *same* parser
reproduced certified 2024 (``same_parser_2024``) is recorded as ``parser_tested_2024``.
The committed evidence keeps each race's status and checksums, not the unofficial counts.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, "src")

from election_prediction.data import results_sources  # noqa: E402

#: States whose registered 2026 parser itself reproduced certified 2024.
SAME_PARSER_2024 = {"MD"}


def evidence(check: dict) -> dict:
    kept = {k: v for k, v in check.items() if k != "rows_2026"}
    kept["races_2026"] = [
        {k: row[k] for k in ("office", "district_num", "status", "share_diff")}
        for row in check.get("rows_2026", [])
    ]
    return kept


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--input-dir", type=Path, required=True)
    ap.add_argument("--as-of", required=True)
    args = ap.parse_args(argv)
    output = Path("reports") / f"extraction_cross_check_{args.as_of}"
    output.mkdir(parents=True, exist_ok=True)
    summary: dict = {"as_of": args.as_of, "states": {}}
    for path in sorted(args.input_dir.glob("??_crosscheck.json")):
        check = json.loads(path.read_text())
        state = check["state"]
        passed = check["reconciliation_2024"]["passed"] and check["cross_check_2026"]["passed"]
        status = "manual_review_pending"
        if passed:
            status = "parser_tested_2024" if state in SAME_PARSER_2024 else "parser_cross_checked_2026"
        entry = {"extraction_status": status, **evidence(check)}
        if status == "parser_tested_2024":
            # Same key the rehearsal report uses: this parser itself reproduced certified 2024.
            entry["reconciliation"] = check["reconciliation_2024"]
        summary["states"][state] = entry
    summary_path = output / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n")

    catalog = pd.read_csv(results_sources.CATALOG, dtype=str).fillna("")
    for state, entry in summary["states"].items():
        if entry["extraction_status"] == "manual_review_pending":
            continue
        i = catalog.index[catalog.state_po == state][0]
        catalog.loc[i, "extraction_status"] = entry["extraction_status"]
        catalog.loc[i, "extraction_evidence"] = str(summary_path)
        catalog.loc[i, "download_access"] = "automated_ok"
    catalog.to_csv(results_sources.CATALOG, index=False)
    results_sources.load_catalog()  # the gate re-checks what was just written

    lines = [
        f"# 2026 extraction cross-checks ({args.as_of})",
        "",
        "These states publish 2026 results in a different layout from 2024. Their 2026 parser",
        "is checked against a summary the state publishes separately, which is weaker than a",
        "test against certified returns. Counts were unofficial when checked.",
        "",
        "| State | Status | 2024 layout vs certified 2024 | 2026 parser vs state summary |",
        "|---|---|---|---|",
    ]
    for state, e in summary["states"].items():
        lines.append(
            f"| {state} | `{e['extraction_status']}` | {e['reconciliation_2024']['status_counts']} | "
            f"{e['cross_check_2026']['status_counts']} |"
        )
    (output / "README.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

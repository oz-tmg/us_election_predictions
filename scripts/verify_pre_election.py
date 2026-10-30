"""Save local quality gates and reproducibility hashes without changing forecast parameters."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from election_prediction.data.manifest import sha256_file
from election_prediction.evaluation.score_preregistration import load_registration, verify_seal

SEALED = {
    "reports/preregistration_2026-11-03.json": (
        "a9986ff474fc82356f257de73e72981ff036293c31ea8a87c3541df1d649aeb5"
    ),
    "reports/preregistration_2026-11-03.md": (
        "05fab6c032cbb8c020c2097ad9b2c929bd53fddbd121d3e1ac6d34e9c882c708"
    ),
    "reports/preregistration_2026-11-03_seats.csv": (
        "61a1e569a053535543a45848772f6fba909d200dfba8a63467cb07dd96119723"
    ),
}


def fingerprints() -> dict[str, str]:
    files = subprocess.check_output(["git", "ls-files", "-co", "--exclude-standard"], text=True).splitlines()
    inputs = sorted(
        {
            Path(p)
            for p in files
            if Path(p).is_file()
            and (
                p.startswith(("src/", "scripts/", "tests/", "data/reference/", ".github/"))
                or p == "pyproject.toml"
            )
        }
    )
    return {str(p): sha256_file(p) for p in inputs}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise FileExistsError("preserve the prior verification; choose a new output path")
    verify_seal(load_registration("reports/preregistration_2026-11-03.json"))
    before = fingerprints()
    env = {**os.environ, "EP_REQUIRE_LIVE_DATA": "1", "EP_DATA_ROOT": str(Path("data").resolve())}
    commands = [
        [sys.executable, "-m", "ruff", "check", "."],
        [sys.executable, "-m", "ruff", "format", "--check", "."],
        [sys.executable, "-m", "mypy", "src/election_prediction"],
        [sys.executable, "-m", "pytest", "-q"],
        [sys.executable, "pipelines/validate/check_no_restricted_data.py", "--all"],
        [sys.executable, "scripts/check_live_runner.py"],
        [sys.executable, "scripts/dry_run_scoring.py"],
        [sys.executable, "-m", "election_prediction.build_results_2026", "--help"],
    ]
    results = []
    for command in commands:
        print("checking: " + " ".join(command), flush=True)
        result = subprocess.run(command, capture_output=True, text=True, env=env, timeout=900, check=False)
        results.append(
            {
                "command": command,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        )
        print(f"exit={result.returncode}", flush=True)
    hashes = fingerprints()
    seals = {p: sha256_file(p) for p in SEALED}
    report = {
        "checked_at": datetime.now(UTC).isoformat(),
        "checks": results,
        "all_checks_passed": all(r["returncode"] == 0 for r in results),
        "code_and_reference_unchanged_during_checks": before == hashes,
        "seal_hashes": seals,
        "seal_unchanged": seals == SEALED,
        "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "dirty_worktree": subprocess.check_output(["git", "status", "--porcelain"], text=True),
        "code_reference_sha256": hashes,
        "python": sys.version,
        "packages": {d.metadata["Name"]: d.version for d in importlib.metadata.distributions()},
        "production_snapshots": [
            str(p) for p in Path("data/raw/source=state_canvass/dataset=us_house_2026").glob("snapshot=*.csv")
        ],
        "not_a_november_freeze": True,
        "not_a_forecast_evaluation": True,
        "runner_deployed": False,
        "published": False,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x") as handle:
        json.dump(report, handle, indent=2)
    print(f"verification -> {args.out}")
    return (
        0
        if (
            report["all_checks_passed"]
            and report["seal_unchanged"]
            and report["code_and_reference_unchanged_during_checks"]
        )
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())

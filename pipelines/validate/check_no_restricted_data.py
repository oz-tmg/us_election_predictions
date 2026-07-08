#!/usr/bin/env python3
"""Pre-commit / CI guard: block restricted data (Tier 3-5) from entering the repo.

Enforces CLAUDE.md §5 and docs/data-governance-and-privacy.md. This is a *defense
in depth* companion to .gitignore: .gitignore stops accidental staging, this script
fails loudly if a restricted-looking file is nonetheless tracked or staged.

Usage:
    python pipelines/validate/check_no_restricted_data.py            # scan staged files
    python pipelines/validate/check_no_restricted_data.py --all      # scan whole tree

Exit code 0 = clean, 1 = violation found. Wire into .pre-commit-config or CI.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

# Filename patterns that indicate restricted personal / operational data.
RESTRICTED_NAME_PATTERNS = [
    r"voter[_-]?file", r"\bl2[_-]", r"targetsmart", r"catalist", r"datatrust",
    r"van[_-]?export", r"crm[_-]?export", r"canvass", r"respondent",
    r"person[_-]?scores", r"household[_-]?scores", r"\.van$", r"\.pii$",
    r"credentials", r"api[_-]?key", r"secrets\.", r"\.env(\.|$)",
]

# Bulk data belongs in the (git-ignored) data lake, not in Git.
BULK_DATA_EXT = {".parquet", ".geoparquet", ".shp", ".dbf", ".gpkg", ".zip", ".gz"}
FIXTURE_ALLOW = re.compile(r"tests/.*/fixtures/")

_name_re = re.compile("|".join(RESTRICTED_NAME_PATTERNS), re.IGNORECASE)


def _staged_files() -> list[str]:
    out = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
        capture_output=True, text=True,
    )
    return [f for f in out.stdout.splitlines() if f.strip()]


def _all_tracked_files() -> list[str]:
    out = subprocess.run(["git", "ls-files"], capture_output=True, text=True)
    return [f for f in out.stdout.splitlines() if f.strip()]


def scan(files: list[str]) -> list[str]:
    violations: list[str] = []
    for f in files:
        low = f.lower()
        if _name_re.search(low):
            violations.append(f"restricted-name: {f}")
            continue
        ext = Path(f).suffix.lower()
        if ext in BULK_DATA_EXT and not FIXTURE_ALLOW.search(f):
            violations.append(f"bulk-data-in-git: {f} (belongs in the data lake)")
    return violations


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--all", action="store_true", help="scan all tracked files, not just staged")
    args = ap.parse_args()

    files = _all_tracked_files() if args.all else _staged_files()
    violations = scan(files)
    if violations:
        print("BLOCKED: restricted or bulk data must not be committed (CLAUDE.md §5):", file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        print("\nStore Tier 3-5 data outside the public repo, encrypted, with hashed IDs.", file=sys.stderr)
        return 1
    print(f"OK: no restricted/bulk data in {len(files)} scanned file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

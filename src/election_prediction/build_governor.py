"""Gubernatorial returns build (``ep-build-governor``).

Deliberately a **separate** build from ``ep-build-p0/p1``. The governor sources are
newly ingested, multi-gigabyte, and shaped differently from the federal series, so
keeping them off the forecast build means an ingestion problem here cannot destabilise
the green federal pipeline.

    data/raw/source=medsl/dataset=state_office/vintage=2016/manual/  (state level)
    data/raw/source=medsl/dataset=precinct_by_state/vintage=YYYY/    (precinct level)
        -> per-state read (governor + president rows only)
        -> vote-mode collapse within precinct
        -> county aggregation (fusion party lines merged)
        -> data/gold/governor_county_returns.parquet
        -> data/gold/coattails_county.parquet          (presidential cycles only)
        -> data/silver/governor_returns.parquet        (state level)
        -> reports/governor_ingestion_report.md

Precinct files are read one state at a time and filtered to governor/president rows
immediately, so peak memory stays near a single state's file rather than the ~5 GB the
full corpus occupies on disk.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from .config import load_dotenv
from .data import governor

# Cycles whose precinct drops we expect. Missing ones are reported, not fatal — the
# 2018 and 2022 downloads may still be in progress.
PRECINCT_VINTAGES = (2018, 2020, 2022, 2024)
STATE_OFFICE_VINTAGES = (2016,)


def _read_state_office(base: Path, vintage: int) -> tuple[pd.DataFrame, str | None]:
    """Read a state-office file (already our silver-ish layout) for governor rows."""
    d = base / f"data/raw/source=medsl/dataset={governor.STATE_OFFICE_DATASET}/vintage={vintage}/manual"
    if not d.is_dir():
        return pd.DataFrame(), f"no directory {d}"
    candidates = [p for p in d.iterdir() if p.suffix.lower() in (".tab", ".csv")]
    if not candidates:
        return pd.DataFrame(), f"no data file in {d}"
    # Prefer the tab-delimited publication; both are the same table.
    path = sorted(candidates, key=lambda p: p.suffix.lower() != ".tab")[0]

    sep = "\t" if path.suffix.lower() == ".tab" else ","
    df = pd.read_csv(path, dtype=str, sep=sep, low_memory=False)
    df.columns = [c.strip().lower() for c in df.columns]
    df = df[df["office"].map(governor.is_governor)].copy()
    if df.empty:
        return pd.DataFrame(), f"{path.name}: no governor rows"
    df["office"] = "governor"
    df["cycle"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    df["candidatevotes"] = pd.to_numeric(df["candidatevotes"], errors="coerce").fillna(0)
    df = df[df["candidate"].map(governor.is_real_candidate)]
    return df, None


def _state_level(county: pd.DataFrame) -> pd.DataFrame:
    """Roll county rows up to one row per state x cycle x candidate."""
    if county.empty:
        return pd.DataFrame()
    gov = county[county["office"] == "governor"]
    return (
        gov.groupby(["cycle", "state_po", "state_fips", "candidate", "party_simplified"], dropna=False)[
            "votes"
        ]
        .sum()
        .reset_index()
        .sort_values(["cycle", "state_po", "votes"], ascending=[True, True, False])
    )


def build(base: Path, *, vintages: tuple[int, ...] = PRECINCT_VINTAGES) -> dict:
    base = Path(base)
    raw_dir = base / "data/raw"
    gold_dir, silver_dir, reports_dir = base / "data/gold", base / "data/silver", base / "reports"
    for d in (gold_dir, silver_dir, reports_dir):
        d.mkdir(parents=True, exist_ok=True)

    county_parts: list[pd.DataFrame] = []
    state_office_parts: list[pd.DataFrame] = []
    coverage: dict[int, dict] = {}
    warnings: list[str] = []

    # ---- state-office cycles (2016) -------------------------------------
    for vintage in STATE_OFFICE_VINTAGES:
        df, err = _read_state_office(base, vintage)
        if err:
            warnings.append(f"{vintage}: {err}")
            coverage[vintage] = {"level": "state_office", "states": 0, "status": "missing"}
            continue
        states = sorted(df["state_po"].dropna().unique())
        coverage[vintage] = {
            "level": "state_office",
            "states": len(states),
            "state_list": states,
            "counties": 0,
            "status": "ok",
        }
        print(f"[{vintage}] state-office: {len(df):,} governor rows across {len(states)} states")
        # State-office files carry no county identifier; they still belong in the
        # county-grain frame (with a null county) so the state rollup includes them.
        # Without this the cycle is counted in coverage but silently absent from every
        # output, which is worse than not reading it at all.
        state_office_parts.append(governor.aggregate_to_county(df))

    # ---- precinct cycles ------------------------------------------------
    for vintage in vintages:
        files = governor.find_precinct_files(raw_dir, vintage)
        if not files:
            warnings.append(f"{vintage}: no precinct files found (download may be pending)")
            coverage[vintage] = {"level": "precinct", "states": 0, "status": "missing"}
            continue

        print(f"[{vintage}] {len(files)} state files…", flush=True)
        parts, gov_states = [], set()
        for path in files:
            try:
                raw = governor.read_precinct_file(path)
            except Exception as e:  # a single malformed state must not sink the cycle
                warnings.append(f"{vintage}/{path.name}: {type(e).__name__}: {e}")
                continue
            if raw.empty:
                continue
            collapsed, _ = governor.collapse_precinct_modes(raw)
            county = governor.aggregate_to_county(collapsed)
            if county.empty:
                continue
            if (county["office"] == "governor").any():
                gov_states.add(governor.state_from_filename(path))
            parts.append(county)

        if not parts:
            coverage[vintage] = {"level": "precinct", "states": 0, "status": "no_usable_rows"}
            continue
        cycle_county = pd.concat(parts, ignore_index=True)
        county_parts.append(cycle_county)
        gov_rows = cycle_county[cycle_county["office"] == "governor"]
        coverage[vintage] = {
            "level": "precinct",
            "states": len(gov_states),
            "state_list": sorted(s for s in gov_states if s),
            "counties": int(gov_rows["county_fips"].nunique()),
            "status": "ok",
        }
        print(
            f"[{vintage}] governor in {len(gov_states)} states, "
            f"{gov_rows['county_fips'].nunique():,} counties"
        )

    if not county_parts and not state_office_parts:
        print("\nNo governor data processed — nothing written.", file=sys.stderr)
        return {"ok": False, "coverage": coverage, "warnings": warnings}

    county = pd.concat(county_parts + state_office_parts, ignore_index=True)
    county.to_parquet(gold_dir / "governor_county_returns.parquet", index=False)

    coattails = governor.build_coattails_table(county)
    coattails.to_parquet(gold_dir / "coattails_county.parquet", index=False)

    state = _state_level(county)
    state.to_parquet(silver_dir / "governor_returns.parquet", index=False)

    report = _write_report(coverage, coattails, state, warnings, reports_dir)
    print(f"\nGovernor ingestion report -> {report}")
    return {
        "ok": True,
        "coverage": coverage,
        "warnings": warnings,
        "county": county,
        "coattails": coattails,
        "state": state,
    }


def _write_report(
    coverage: dict, coattails: pd.DataFrame, state: pd.DataFrame, warnings: list[str], reports_dir: Path
) -> Path:
    lines = [
        "# Governor Ingestion Report",
        "",
        "> Tier 0 public aggregate (MEDSL). Historical returns only — no forecast is published.",
        "",
        "## Coverage",
        "",
        "| Cycle | Level | Governor states | Counties | Status |",
        "|---:|---|---:|---:|---|",
    ]
    for cycle in sorted(coverage):
        c = coverage[cycle]
        lines.append(
            f"| {cycle} | {c['level']} | {c.get('states', 0)} | {c.get('counties', 0):,} | {c['status']} |"
        )

    if not coattails.empty:
        lines += [
            "",
            "## County-level governor vs president (presidential cycles)",
            "",
            "`ticket_split` is the governor's two-party Democratic share minus the "
            "president's in the same county; `roll_off` is the share of presidential "
            "voters who cast no gubernatorial vote. Both are **descriptive associations**, "
            "not evidence that presidential turnout caused a gubernatorial result.",
            "",
            "| Cycle | Counties | Mean ticket split | Mean roll-off |",
            "|---:|---:|---:|---:|",
        ]
        for cycle, g in coattails.groupby("cycle"):
            ok = g[~g["two_party_suspect"]]
            lines.append(
                f"| {cycle} | {len(g):,} | {ok['ticket_split'].mean():+.4f} | {ok['roll_off'].mean():+.4f} |"
            )
        suspect = coattails[coattails["two_party_suspect"]]
        if len(suspect):
            pairs = sorted({(int(c), s) for c, s in zip(suspect["cycle"], suspect["state_po"], strict=True)})
            lines += [
                "",
                f"> ⚠️ **{len(suspect):,} counties across {len(pairs)} state-cycles are flagged "
                "`two_party_suspect`** and are excluded from the means above. A major party shows "
                "zero votes there because the nominee ran on a fusion or joint ticket that MEDSL's "
                "`party_simplified` records as OTHER — not because nobody ran. Affected: "
                + ", ".join(f"{s} {c}" for c, s in pairs)
                + ". Two-party share and `ticket_split` are meaningless for these rows; Vermont 2024 "
                "otherwise computes a -0.66 'split' that is pure artefact. Fixing this needs the "
                "candidate/party alias crosswalk (backlog P0-003), not a substring rule.",
            ]

    if warnings:
        lines += ["", "## Warnings", ""] + [f"- {w}" for w in warnings]

    lines += [
        "",
        "## Known limitations",
        "",
        "- Only ~11 states elect governors in presidential years, and that set skews small "
        "and rural, so on-cycle vs off-cycle comparisons rest on a small, non-random sample.",
        "- Counties are matched on `county_fips` within a cycle; no cross-cycle county "
        "boundary crosswalk is applied.",
        "- Coverage depends on which precinct drops have been downloaded; see the table above.",
        "",
    ]
    path = reports_dir / "governor_ingestion_report.md"
    path.write_text("\n".join(lines))
    return path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build gubernatorial returns and the coattails table.")
    ap.add_argument("--base", default=".", help="repo root (default: cwd)")
    ap.add_argument(
        "--vintages",
        default=",".join(str(v) for v in PRECINCT_VINTAGES),
        help="comma-separated precinct cycles to process",
    )
    args = ap.parse_args(argv)
    load_dotenv(Path(args.base) / ".env")
    vintages = tuple(int(v) for v in args.vintages.split(",") if v.strip())
    result = build(Path(args.base), vintages=vintages)
    return 0 if result["ok"] else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

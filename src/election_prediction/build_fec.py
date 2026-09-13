"""Build the FEC candidate layer: crosswalk (P0-003), filing status, and fundraising (F-004).

One command, three outputs, each with a validation report:

* ``data/gold/candidate_crosswalk.parquet`` — one row per candidate observation in the
  returns, carrying normalized ``ballot_party`` and ``caucus_party`` and, where a roster
  covers the cycle, an FEC ``candidate_id``.
* ``data/gold/incumbent_filings_<cycle>.parquet`` — filing evidence for the live cycle's
  seat roster, replacing a blanket ``incumbent_status = "unknown"``.
* ``data/gold/fundraising.parquet`` — the race-level Democratic/Republican receipts ratio.

Raw snapshots are cached, so a re-run without ``--refresh`` costs no API calls and
reproduces byte-for-byte from disk.
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

import pandas as pd

from .config import load_dotenv
from .data import fec
from .data.manifest import SourceManifest
from .data.privacy import PrivacyTier
from .features import candidate_crosswalk as cc
from .features import filings as fl
from .features import fundraising as fr

OFFICES = ("us_house", "us_senate")


def _manifest_for(path: Path, dataset: str, cycle: int, office: str, base: Path) -> Path:
    return SourceManifest.for_snapshot(
        raw_path=path,
        source_id="fec_api",
        dataset_name=f"OpenFEC {dataset} — {office} {cycle}",
        source_owner="Federal Election Commission",
        source_url=fec.FEC_API,
        privacy_tier=PrivacyTier.PUBLIC_AGGREGATE,
        license_or_terms=fec.LICENSE,
        permitted_use=(
            "Aggregate nonpartisan analysis of candidate filings and campaign finance "
            "totals: race-level fundraising ratios, incumbent filing status, and the "
            "candidate_id join key."
        ),
        prohibited_use=(
            "Itemized contributor records (Schedule A) are out of scope and off the endpoint "
            "allowlist. Never use FEC data for solicitation, list-building, marketing, "
            "harassment, or commercial targeting (CLAUDE.md §5)."
        ),
        office_coverage=[office],
        geography_coverage=["state", "district"],
        election_cycle=str(cycle),
        owner="project-owner (data steward)",
        acquisition_method="api",
        file_format="json",
        redistribution_allowed=True,
        contains_personal_data=False,
        required_attribution=fec.ATTRIBUTION,
        known_caveats=(
            "FEC election_years is incomplete: Keith Self (TX-03) won in 2022 and 2024 but "
            "is listed as [2002, 2026], so a roster pull is not exhaustive. candidate_status "
            "and candidate_inactive describe the present, not the requested cycle. The "
            "district field tracks the candidate's last filing, not the seat contested."
        ),
    ).write(base / "data/manifests")


def _load(dataset: str, parser, cycles: list[int], base: Path) -> pd.DataFrame:
    frames = []
    for cycle in cycles:
        for office in OFFICES:
            path = (
                base
                / f"data/raw/source=fec_api/dataset={dataset}/cycle={cycle}"
                / f"fec_{dataset}__{office}__{cycle}.json"
            )
            if path.is_file():
                frames.append(parser(path))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def build(
    *,
    base: Path = Path("."),
    cycles: list[int] | None = None,
    projection_cycle: int = 2026,
    refresh: bool = False,
    download: bool = True,
) -> dict:
    load_dotenv()
    base = Path(base)
    cycles = cycles or list(range(1980, projection_cycle + 2, 2))
    results: dict = {"cycles": cycles, "projection_cycle": projection_cycle}

    if download:
        for cycle in cycles:
            for office in OFFICES:
                for fn, dataset in (
                    (fec.download_candidates, "candidates"),
                    (fec.download_candidate_totals, "candidate_totals"),
                ):
                    path = fn(cycle, office, base / "data/raw", refresh=refresh)
                    _manifest_for(Path(path), dataset, cycle, office, base)

    gold = base / "data/gold"
    gold.mkdir(parents=True, exist_ok=True)

    # ---- candidates -----------------------------------------------------------
    candidates = _load("candidates", fec.parse_candidates, cycles, base)
    results["fec_candidates"] = {
        "rows": int(len(candidates)),
        "validation": fec.validate_candidates(candidates) if len(candidates) else {},
    }

    # ---- P0-003 crosswalk -----------------------------------------------------
    returns = pd.read_parquet(base / "data/silver/election_returns.parquet")
    crosswalk = cc.build_crosswalk(returns, candidates if len(candidates) else None)
    crosswalk.to_parquet(gold / "candidate_crosswalk.parquet", index=False)
    winners = cc.resolve_race_winners(crosswalk, returns)
    winners.to_parquet(gold / "race_winners.parquet", index=False)
    results["crosswalk"] = {
        "validation": cc.validate_crosswalk(crosswalk),
        "summary": cc.crosswalk_summary(crosswalk),
    }

    # ---- incumbent filing status ---------------------------------------------
    universe_path = base / f"data/gold/race_universe_{projection_cycle}.parquet"
    if universe_path.is_file():
        universe = pd.read_parquet(universe_path)
        live = candidates[candidates["election_year"] == projection_cycle] if len(candidates) else None
        resolved = fl.resolve_incumbent_status(
            universe, live if live is not None and len(live) else None, cycle=projection_cycle
        )
        resolved.to_parquet(gold / f"incumbent_filings_{projection_cycle}.parquet", index=False)
        results["filings"] = {
            "validation": fl.validate_filings(resolved),
            "summary": fl.filings_summary(resolved),
        }
    else:
        results["filings"] = {"skipped": f"{universe_path} not found"}

    # ---- F-004 fundraising ----------------------------------------------------
    totals = _load("candidate_totals", fec.parse_candidate_totals, cycles, base)
    if len(totals):
        funds = fr.build_fundraising(totals)
        funds.to_parquet(gold / "fundraising.parquet", index=False)
        results["fundraising"] = {
            "fec_validation": fec.validate_candidate_totals(totals),
            "validation": fr.validate_fundraising(funds),
            "summary": fr.fundraising_summary(funds),
        }
    else:
        results["fundraising"] = {"skipped": "no candidate_totals snapshots found"}

    report = base / "reports" / f"fec_build_{date.today().isoformat()}.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(results, indent=2, default=str))
    results["report_path"] = str(report)
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build the FEC candidate crosswalk, filings and fundraising."
    )
    parser.add_argument("--base", default=".", help="Project root")
    parser.add_argument("--projection-cycle", type=int, default=2026)
    parser.add_argument("--from-cycle", type=int, default=1980)
    parser.add_argument("--refresh", action="store_true", help="Re-download cached snapshots")
    parser.add_argument("--no-download", action="store_true", help="Build from cached snapshots only")
    args = parser.parse_args(argv)

    cycles = list(range(args.from_cycle, args.projection_cycle + 2, 2))
    out = build(
        base=Path(args.base),
        cycles=cycles,
        projection_cycle=args.projection_cycle,
        refresh=args.refresh,
        download=not args.no_download,
    )

    cw = out["crosswalk"]["summary"]
    print("\n=== FEC candidate layer ===")
    print(f"  Crosswalk rows: {cw['rows']} | FEC-matched {cw['fec_matched']} ({cw['fec_match_rate']:.1%})")
    print(
        f"  Party unresolved: {cw['party_unresolved']} | caucus overrides: {cw['caucus_overrides_applied']}"
    )
    if "summary" in out.get("filings", {}):
        f = out["filings"]["summary"]
        print(f"  Incumbent filings: {f['by_status']} across {f['seats']} seats")
    if "summary" in out.get("fundraising", {}):
        fu = out["fundraising"]["summary"]
        print(f"  Fundraising: {fu['usable_rows']}/{fu['rows']} usable races")
        print(f"    post-election coverage on {fu['post_election_coverage_rows']} rows (backtest leakage)")
    print(f"  Report -> {out['report_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

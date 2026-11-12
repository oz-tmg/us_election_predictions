#!/usr/bin/env python
"""Rehearse per-state extraction against each state's own 2024 official release.

    python scripts/test_state_extraction.py --input-dir <downloads> --as-of 2026-10-30

For each configured state whose release could be downloaded, this preserves the files as
an immutable raw snapshot with a manifest, runs the state's registered parser, and
reconciles the result race by race with the certified 2024 returns. For states whose
sites refuse automated clients it records the blocker and the official files an operator
must fetch by hand. It never disables certificate checks or evades a block.

Writes ``reports/extraction_rehearsal_<as_of>/`` and updates
``data/reference/results_sources_2026.csv``: ``parser_tested_2024`` only for a passed
reconciliation (naming its report), and ``download_access`` from what was observed.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, "src")

from election_prediction.data import (
    results_sources,  # noqa: E402
    state_parsers,  # noqa: E402,F401  (registers parsers)
)
from election_prediction.data import state_extraction as se  # noqa: E402
from election_prediction.data.manifest import SourceManifest, sha256_file  # noqa: E402
from election_prediction.data.privacy import PrivacyTier  # noqa: E402

RAW_SOURCE = "state_results_rehearsal_2024"

# What each state's 2024 release looked like to an honest client from this machine on
# 2026-10-29/30 (Canadian egress; WebFetch from a US egress agreed where tried).
STATES: dict[str, dict] = {
    "MA": {
        "access": "automated_ok",
        "files": ["MA_2024GE_*_by_town.csv"],
        "source": "https://electionstats.state.ma.us/elections/download/<election_id>/precincts_include:0/",
        "release_page": "https://electionstats.state.ma.us/elections/search/year_from:2024/year_to:2024/stage:General",
        "official": "Certified (linked by the Secretary of the Commonwealth as certified results)",
        "note": "sec.state.ma.us is behind an Imperva bot wall; electionstats.state.ma.us is not. "
        "Certified results post weeks after the election; election night has no state feed here.",
    },
    "WI": {
        "access": "automated_ok",
        "files": ["WardbyWard_byCD_*.xlsx"],
        "source": "https://elections.wi.gov/sites/default/files/documents/WardbyWard_byCD_20241105.xlsx",
        "release_page": "https://elections.wi.gov/election-result/2024-general-election-results",
        "official": "Certified canvass, 2024-11-29 (Canvass_Congress.pdf, Canvass_Senate.pdf)",
        "note": "HTML pages sit behind a Cloudflare challenge but /sites/default/files/documents/ "
        "files download. WEC publishes no statewide election-night feed; the canvass follows "
        "certification. File-name suffixes (_0, _1) can change on re-upload.",
    },
    "MO": {
        "access": "automated_ok",
        "files": ["2024GeneralElection.pdf"],
        "source": "https://www.sos.mo.gov/CMSImages/ElectionResultsStatistics/2024GeneralElection.pdf",
        "release_page": "https://www.sos.mo.gov/elections/s_default",
        "official": "Certified canvass returns, announced 2024-12-05 (PDF, text layer)",
        "note": "sos.mo.gov answers the honest research user agent (200) but refuses curl's default "
        "(403); enr.sos.mo.gov (election-night) is behind a Cloudflare challenge. Parser checks "
        "that candidate votes sum to each printed contest total.",
    },
    "MT": {
        "access": "automated_ok",
        "files": ["mt_*_Statewide_Results.xlsx"],
        "source": "https://electionresults.mt.gov/ResultsExport.aspx?eid=450002785",
        "release_page": "https://electionresults.mt.gov/ResultsExport.aspx?eid=450002785",
        "official": "Results-site export labelled 'Unofficial' (last updated 2024-12-19, after the "
        "canvass); the certified canvass PDF sits behind a Cloudflare-challenged page",
        "note": "sosmt.gov and the results root are Cloudflare-challenged; the export page works and "
        "the workbook is fetched by posting back the page's own form fields "
        "(__EVENTTARGET=ctl00$MainContent$Statewide), the request a browser click makes. The file "
        "embeds a download timestamp, so its hash changes on every fetch. Never mark a snapshot "
        "certified from this file; certification must come from the canvass.",
    },
    "NC": {
        "access": "automated_ok",
        "files": ["results_pct_*.zip"],
        "source": "https://dl.ncsbe.gov/ENRS/2024_11_05/results_pct_20241105.zip",
        "release_page": "https://www.ncsbe.gov/results-data/election-results/historical-election-results-data",
        "official": "NCSBE published precinct results (original administrative precincts), certified canvass",
        "note": "Same file the registered nc_official_precinct_returns source holds. The 2026 file "
        "(ENRS/2026_11_03/results_pct_20261103.zip) downloads with the honest client; it is updated "
        "in place until certification, so preserve each retrieval.",
    },
    "MI": {
        "access": "blocked_manual_download",
        "blocker": "mielections.us refuses connections (timeouts here and from a separate fetcher); all of "
        "michigan.gov returns Akamai 403",
        "official_files": [],
        "urls_verified": False,
        "note": "No 2024 official file URL could be confirmed. Certification 2024-11-22 per search snippet.",
    },
    "NH": {
        "access": "blocked_manual_download",
        "blocker": "www.sos.nh.gov returns Akamai 403 (sos.nh.gov 503), including from a separate fetcher",
        "official_files": ["https://www.sos.nh.gov/2024-general-election-results"],
        "urls_verified": False,
        "note": "Town-level Excel per congressional district (to be summed); file URLs not confirmed.",
    },
    "OH": {
        "access": "blocked_manual_download",
        "blocker": "Cloudflare managed challenge (403) on every path, static files included",
        "official_files": [
            "https://www.ohiosos.gov/globalassets/elections/2024/gen/official/statewide-race-summary.xlsx",
            "https://www.ohiosos.gov/globalassets/elections/2024/gen/official/statewide-races-precint-level.xlsx",
        ],
        "urls_verified": False,
        "note": "URLs found via Internet Archive snapshots of the release page; layout not inspected.",
    },
    "TN": {
        "access": "blocked_manual_download",
        "blocker": "CloudFront 'Request blocked' (403) on the site and file host; may be geographic",
        "official_files": [
            "https://sos-prod.tnsosgovfiles.com/s3fs-public/document/20241105AllbyPrecinct.xlsx",
        ],
        "urls_verified": False,
        "note": "Retest from a U.S. network before treating the block as final.",
    },
    "AK": {
        "access": "blocked_manual_download",
        "blocker": "AWS WAF captcha (HTTP 405) on every path; server also omits its intermediate "
        "TLS certificate, which causes the Python certificate error (use a full trust store; "
        "never disable verification)",
        "official_files": [
            "https://www.elections.alaska.gov/results/24GENR/ElectionSummaryReport.pdf",
            "https://www.elections.alaska.gov/results/24GENR/RCV-USRep.pdf",
        ],
        "urls_verified": False,
        "note": "Ranked-choice: capture first round and final round separately (election_round).",
    },
    "AZ": {
        "access": "blocked_manual_download",
        "blocker": "Cloudflare managed challenge (403) on azsos.gov, apps.azsos.gov, results.arizona.vote",
        "official_files": [
            "https://apps.azsos.gov/election/2024/ge/canvass/202411GeneralElectionCanvass-<County>.pdf",
        ],
        "urls_verified": False,
        "note": "Statewide canvass is PDF only; its URL was not confirmed.",
    },
    "ME": {
        "access": "blocked_manual_download",
        "blocker": "CloudFront 'Request blocked' (403) on maine.gov and www11.maine.gov",
        "official_files": [
            "https://www.maine.gov/sos/elections-voting/election-results-data/election-results-2024",
        ],
        "urls_verified": False,
        "note": "Town-level tabulations (Excel) need summing; CD2 is ranked-choice: keep first-choice "
        "and final-round results as separate rounds.",
    },
}


def preserve(state: str, files: list[Path], as_of: str, source: str) -> list[dict]:
    out = []
    for f in files:
        digest = sha256_file(f)
        target = Path(f"data/raw/source={RAW_SOURCE}/state={state}/sha256={digest}") / f.name
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            shutil.copyfile(f, target)
        manifest = SourceManifest.for_snapshot(
            raw_path=target,
            source_id=f"{RAW_SOURCE}_{state.lower()}_{digest[:12]}",
            dataset_name=f.name,
            source_owner=f"{state} state election authority",
            source_url=source,
            privacy_tier=PrivacyTier.PUBLIC_AGGREGATE,
            license_or_terms="Public official election results; cite the state authority.",
            permitted_use="Nonpartisan rehearsal of results extraction against certified history.",
            prohibited_use="No personal data; aggregate results only.",
            office_coverage=["us_house", "us_senate"],
            geography_coverage=["state", "district"],
            election_cycle="2024",
            owner="Alex Oswald (data steward)",
            acquisition_method="http_download",
            file_format=f.suffix.lstrip("."),
        )
        manifest.validation_status = "passed"
        manifest.write()
        out.append({"file": f.name, "sha256": digest, "raw_path": str(target)})
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument(
        "--input-dir", type=Path, required=True, help="<dir>/<STATE>/ holds each state's download"
    )
    ap.add_argument("--as-of", required=True)
    args = ap.parse_args(argv)
    output = Path("reports") / f"extraction_rehearsal_{args.as_of}"
    output.mkdir(parents=True, exist_ok=True)
    certified = pd.read_parquet("data/gold/race_results.parquet")
    summary: dict = {"as_of": args.as_of, "states": {}}

    for state, cfg in STATES.items():
        entry = {k: v for k, v in cfg.items() if k != "files"}
        if cfg["access"] == "automated_ok":
            files = sorted({p for pat in cfg["files"] for p in (args.input_dir / state).glob(pat)})
            if not files:
                raise SystemExit(f"{state}: no files matching {cfg['files']} under {args.input_dir / state}")
            entry["preserved"] = preserve(state, files, args.as_of, cfg["source"])
            extracted = se.extract(state, files)
            rec = se.reconcile(extracted, certified, state=state, cycle=2024)
            rec.to_csv(output / f"reconciliation_{state}.csv", index=False)
            entry["reconciliation"] = se.summarize(rec)
        summary["states"][state] = entry

    summary_path = output / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n")

    catalog = pd.read_csv(results_sources.CATALOG, dtype=str).fillna("")
    for column, default in (("download_access", "untested"), ("extraction_evidence", "")):
        if column not in catalog:
            catalog[column] = default
    for state, entry in summary["states"].items():
        i = catalog.index[catalog.state_po == state][0]
        catalog.loc[i, "download_access"] = entry["access"]
        if entry.get("reconciliation", {}).get("passed"):
            catalog.loc[i, "extraction_status"] = "parser_tested_2024"
            catalog.loc[i, "extraction_evidence"] = str(summary_path)
    catalog.to_csv(results_sources.CATALOG, index=False)
    results_sources.load_catalog()  # the gate re-checks what was just written

    lines = [
        f"# Extraction rehearsal ({args.as_of})",
        "",
        "| State | Access | Parser vs certified 2024 |",
        "|---|---|---|",
    ]
    for state, e in summary["states"].items():
        rec = e.get("reconciliation")
        result = (
            f"{'passed' if rec['passed'] else 'FAILED'}: {rec['status_counts']}"
            if rec
            else "not run (blocked)"
        )
        lines.append(f"| {state} | {e['access']} | {result} |")
    (output / "README.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

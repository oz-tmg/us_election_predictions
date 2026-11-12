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
    # Added 2026-11-12 from the second research pass (fetch logs under the scratch
    # extraction directory); the 15 tested states each have a 2026 fetcher.
    **{
        "WV": {
            "access": "automated_ok",
            "files": ["WV_2024_*summary.zip"],
            "source": "https://results.enr.clarityelections.com/WV/122766/356048/reports/summary.zip",
            "release_page": "https://results.enr.clarityelections.com/WV/122766/web.345435/#/summary (linked "
            "from "
            "https://sos.wv.gov/elections/election-data/historical-election-results-and-turnout)",
            "official": "official (banner 'Official Results'; websiteupdatedat 12/18/2024 8:58:00 AM EST)",
            "note": "2026 fetcher in data/state_fetchers.py; tested 2026-11-12.",
        },
        "UT": {
            "access": "automated_ok",
            "files": ["UT_2024_export-*.json"],
            "source": "https://electionresults.utah.gov/cdn/results/Utah/export-general11052024.json",
            "release_page": "https://electionresults.utah.gov/results/public/Utah/elections/general11052024",
            "official": "official (isOfficialResults=true; lastUpdated 2024-11-22T22:37:41Z; export regenerated "
            "2025-11-04)",
            "note": "2026 fetcher in data/state_fetchers.py; tested 2026-11-12.",
        },
        "VT": {
            "access": "automated_ok",
            "files": ["VT_2024_ENR_federal*.json"],
            "source": "https://static.electionresults.vermont.gov/elections/67a35c79-05a2-4ae3-a77d-97812256188b-f-20260611153112.json",
            "release_page": "https://electionresults.vermont.gov/ (GENERAL ELECTION 2024-11-05, guid "
            "67a35c79-05a2-4ae3-a77d-97812256188b)",
            "official": "official (isOfficial=true; lastUpdatedDate 06/11/2026 03:31 PM; carries an election "
            "note on a Bennington state-senate correction)",
            "note": "2026 fetcher in data/state_fetchers.py; tested 2026-11-12.",
        },
        "WY": {
            "access": "automated_ok",
            "files": ["WY_2024_*Results.zip"],
            "source": "https://sos.wyo.gov/Elections/Docs/2024/Results/General/2024_Wyoming_General_Results.zip",
            "release_page": "https://sos.wyo.gov/Elections/Docs/2024/2024GeneralResults.aspx",
            "official": "official/certified",
            "note": "2026 fetcher in data/state_fetchers.py; tested 2026-11-12.",
        },
        "MN": {
            "access": "automated_ok",
            "files": ["MN_2024_*.txt"],
            "source": "https://electionresultsfiles.sos.mn.gov/20241105/USHouseCty.txt",
            "release_page": "https://electionresults.sos.mn.gov/ (2024 General media files)",
            "official": "certified (post-canvass; Last-Modified 2024-12-19)",
            "note": "2026 fetcher in data/state_fetchers.py; tested 2026-11-12.",
        },
        "SC": {
            "access": "automated_ok",
            "files": ["SC_2024_*summary.zip"],
            "source": "https://www.enr-scvotes.org/SC/122436/359624/reports/summary.zip",
            "release_page": "https://www.enr-scvotes.org/SC/122436/web.345435/#/summary ('2024 General "
            "Election')",
            "official": "certified/final (ENR archived; detail.xml Timestamp '7/30/2025 10:46:52 AM EDT')",
            "note": "2026 fetcher in data/state_fetchers.py; tested 2026-11-12.",
        },
        "LA": {
            "access": "automated_ok",
            "files": ["LA_2024_*ByParish*.csv"],
            "source": "https://voterportal.sos.la.gov/ElectionResults/ElectionResults/Data?blob=20241105/csv/ByParish_67171.csv",
            "release_page": "https://voterportal.sos.la.gov/graphical (election 11/05/2024, PKElectionID 331)",
            "official": "certified (ResultsOfficial='1'); WriteTime 2026-01-10",
            "note": "2026 fetcher in data/state_fetchers.py; tested 2026-11-12.",
        },
        "GA": {
            "access": "automated_ok",
            "files": ["GA_2024_TotalVotes.xlsx"],
            "source": "https://results.sos.ga.gov/cdn/results/09378a07-e6cf-4f66-be7c-ca4aa534f99a/Total%20Votes%20Results_3675bf50-5eeb-4407-b538-c04b909ccd08.xlsx",
            "release_page": "https://results.sos.ga.gov/results/public/Georgia/elections/2024NovGen",
            "official": "CERTIFIED/OFFICIAL (isOfficialResults=true)",
            "note": "2026 fetcher in data/state_fetchers.py; tested 2026-11-12.",
        },
        "VA": {
            "access": "automated_ok",
            "files": ["VA_2024_ElectionResults.csv"],
            "source": "https://enr.elections.virginia.gov/cdn/results/d2c804ee-4ec2-46bb-91d7-5b41526eab03/Election%20Results_e5b689ae-a931-4b8a-a5f7-7392e9571c61.csv",
            "release_page": "https://enr.elections.virginia.gov/results/public/virginia/elections/2024NovemberGeneral",
            "official": "OFFICIAL/CERTIFIED (isOfficialResults=true)",
            "note": "2026 fetcher in data/state_fetchers.py; tested 2026-11-12.",
        },
        "CO": {
            "access": "automated_ok",
            "files": ["CO_2024_detailxml.zip"],
            "source": "https://results.enr.clarityelections.com/CO/122598/367167/reports/detailxml.zip",
            "release_page": "https://results.enr.clarityelections.com/CO/122598/ (EID 122598 '2024 General'); "
            "certified abstract: "
            "https://www.coloradosos.gov/pubs/elections/Results/Archives.html -> 2023-2024 "
            "Biennial abstract",
            "official": "Clarity ENR final (re-published 11/25/2025, after state certification 2024-12-06; not "
            "itself labeled 'certified'); Biennial Abstract PDF = official certified results "
            "(General Election from p.103)",
            "note": "2026 fetcher in data/state_fetchers.py; tested 2026-11-12.",
        },
        "PA": {
            "access": "automated_ok",
            "files": ["PA_2024_*.csv"],
            "source": "POST https://www.electionreturns.pa.gov/api/Reports/GenerateReport "
            'body={"ElectionID":105,"ElectionsubType":"G","OfficeIds":[1,2,11],"RetOfficeIds":[],"PartyIds":[],"DistrictIds":[],"CandidateIds":[],"CountyIds":[],"ReferendumIds":[],"ReferendumDetailIds":[],"ExportType":"C","ReportType":"C","FileName":"Official"}',
            "release_page": "https://www.electionreturns.pa.gov/ReportCenter/Reports (ElectionID 105 '2024 "
            "Presidential Election')",
            "official": "OFFICIAL (ElectionStatus='O')",
            "note": "2026 fetcher in data/state_fetchers.py; tested 2026-11-12.",
        },
        "AR": {
            "access": "automated_ok",
            "files": ["AR_2024_general_tally_*.json"],
            "source": "https://enr-results-api.totalresults.com/Contest/GetContestResults?cId=arkansas&electionID=1846&contestType=FED",
            "release_page": "https://arkansas.tally-enr.com/#election=1846 ; "
            "https://www.sos.arkansas.gov/elections/research/election-results",
            "official": "certified/official: Tally isOfficial=true, versionID v1-1, lastUpdated 2025-12-16 "
            "(legacy archive). SOS precinct XLSX is the certified precinct file.",
            "note": "2026 fetcher in data/state_fetchers.py; tested 2026-11-12.",
        },
        "DE": {
            "access": "automated_ok",
            "files": ["DE_2024_general_statewide_opendata.csv"],
            "source": "https://data.delaware.gov/resource/4hbv-7brf.csv?electiondate=2024-11-05T00:00:00.000",
            "release_page": "https://elections.delaware.gov/reports/GE2024.html (archive 'Results Report')",
            "official": "official: report shows 'OFFICIAL RESULTS', 'Data as of 11/12/2024 12:59:37'; open-data "
            "xmlreporttime 2024-11-12T12:59:37.",
            "note": "2026 fetcher in data/state_fetchers.py; tested 2026-11-12.",
        },
        "IN": {
            "access": "automated_ok",
            "files": ["IN_2024_*AllOfficeResults.csv"],
            "source": "https://enr.indianavoters.in.gov/archive/2024General/download/AllOfficeResults.csv",
            "release_page": "https://enr.indianavoters.in.gov/archive/2024General/index.html (same ENR app, "
            "archived; pattern follows the SOS-linked "
            "https://enr.indianavoters.in.gov/archive/2020General/index.html)",
            "official": "certified: archive settings.json Certified='T', VersionCode 20241213_160047, WriteTime "
            "2025-04-17T18:32:33",
            "note": "2026 fetcher in data/state_fetchers.py; tested 2026-11-12.",
        },
        "HI": {
            "access": "automated_ok",
            "files": ["HI_2024_*summary.txt"],
            "source": "https://files.hawaii.gov/elections/files/results/2024/General/summary.txt",
            "release_page": "https://elections.hawaii.gov/election-results/ (2024 General section: 'Certified "
            "Reports' / 'Certified Text Files', Last Updated November 27, 2024 10:15 am)",
            "official": "certified; statewide PDF 'SUMMARY REPORT Final', printed 11/13/2024 06:51:06 pm",
            "note": "2026 fetcher in data/state_fetchers.py; tested 2026-11-12.",
        },
        "KY": {
            "access": "blocked_manual_download",
            "blocker": "Azure firewall 403 / state board anti-scraping page on elect.ky.gov and vrsws.sos.ky.gov",
            "official_files": [],
            "urls_verified": False,
            "note": "Found 2026-11-12 by honest-client probe; manual browser download needed.",
        },
        "NY": {
            "access": "blocked_manual_download",
            "blocker": "Cloudflare challenge on all three state hosts",
            "official_files": [],
            "urls_verified": False,
            "note": "Found 2026-11-12 by honest-client probe; manual browser download needed.",
        },
        "NV": {
            "access": "blocked_manual_download",
            "blocker": "Imperva JavaScript challenge on silverstateelection.nv.gov and nvsos.gov",
            "official_files": [],
            "urls_verified": False,
            "note": "Found 2026-11-12 by honest-client probe; manual browser download needed.",
        },
        "OK": {
            "access": "blocked_manual_download",
            "blocker": "HTTP 403 on results.okelections.us",
            "official_files": [],
            "urls_verified": False,
            "note": "Found 2026-11-12 by honest-client probe; manual browser download needed.",
        },
        "FL": {
            "access": "blocked_manual_download",
            "blocker": "Cloudflare challenge on floridaelectionwatch.gov and dos.fl.gov (2026)",
            "official_files": [],
            "urls_verified": False,
            "note": "Found 2026-11-12 by honest-client probe; manual browser download needed.",
        },
        "KS": {
            "access": "blocked_manual_download",
            "blocker": "Cloudflare 403 on ent.sos.ks.gov (2026), apparently geographic",
            "official_files": [],
            "urls_verified": False,
            "note": "Found 2026-11-12 by honest-client probe; manual browser download needed.",
        },
        "NM": {
            "access": "blocked_manual_download",
            "blocker": "F5 403 on electionresults.sos.nm.gov (2026)",
            "official_files": [],
            "urls_verified": False,
            "note": "Found 2026-11-12 by honest-client probe; manual browser download needed.",
        },
        "RI": {
            "access": "blocked_manual_download",
            "blocker": "HTTP 403 on elections.ri.gov (2026)",
            "official_files": [],
            "urls_verified": False,
            "note": "Found 2026-11-12 by honest-client probe; manual browser download needed.",
        },
    },
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
        source_id = f"{RAW_SOURCE}_{state.lower()}_{digest[:12]}"
        if any(Path("data/manifests").glob(f"{source_id}__*.json")):
            # Same bytes already have a manifest: re-running must not add duplicates.
            out.append({"file": f.name, "sha256": digest, "raw_path": str(target)})
            continue
        manifest = SourceManifest.for_snapshot(
            raw_path=target,
            source_id=source_id,
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

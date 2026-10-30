"""Reverify sourced GA/NJ special counts, retaining other actual retrieval dates."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import pandas as pd
from pypdf import PdfReader

from election_prediction.data.manifest import sha256_file
from election_prediction.data.official_repairs import georgia_special

STAMP = "2026-10-21"
RAW = Path(f"data/raw/source=special_elections_compiled/snapshot={STAMP}")


def main() -> None:
    output = Path(f"reports/refresh_{STAMP}/special_source_refresh.json")
    if output.exists():
        raise FileExistsError("Dated source review already recorded; preserve it and use a new review date")
    output.parent.mkdir(parents=True, exist_ok=True)
    path = Path("data/reference/special_elections_2025_2026.csv")
    previous = RAW / f"sha256={sha256_file(path)}/specials-before.csv"
    previous.parent.mkdir(parents=True, exist_ok=True)
    if not previous.exists():
        shutil.copyfile(path, previous)
    frame = pd.read_csv(path, comment="#", dtype={"district": str}).fillna("")
    changes = []
    for special_id, filename, district in [
        ("2026-ga-cd13", "ga13.xlsx", 13),
        ("2026-ga-cd14-r1", "ga14.xlsx", 14),
        ("2026-ga-cd14-runoff", "ga14-april7.xlsx", 14),
    ]:
        values = georgia_special(RAW / filename, district=district)
        mask = frame.special_id.eq(special_id)
        old = frame.loc[mask, ["dem_votes", "rep_votes", "other_votes"]].iloc[0].to_dict()
        for key, value in values.items():
            frame.loc[mask, key] = value
        frame.loc[mask, "retrieved_on"] = STAMP
        changes.append(
            {
                "special_id": special_id,
                "before": old,
                "after": values,
                "source_snapshot": str(RAW / filename),
                "sha256": sha256_file(RAW / filename),
            }
        )
    runoff = frame.special_id.eq("2026-ga-cd14-runoff")
    frame.loc[runoff, "source_url"] = (
        "https://results.sos.ga.gov/cdn/results/09378a07-e6cf-4f66-be7c-ca4aa534f99a/"
        "Total%20Votes%20Results_109b2c95-792b-4621-a07a-cc993bc03180.xlsx"
    )
    frame.loc[runoff, "results_updated_on"] = "2026-04-14"
    frame.loc[runoff, "notes"] = (
        "Official April 7 API metadata and workbook verified; prior URL was March 10."
    )
    first = frame.special_id.eq("2026-ga-cd14-r1")
    frame.loc[first, "notes"] = (
        "Corrected D total: prior 54374 included 8228 State Senate 53 votes; superseded."
    )
    ga13 = frame.special_id.eq("2026-ga-cd13")
    frame.loc[ga13, "include_in_metric"] = "Y"
    frame.loc[ga13, "exclusion_reason"] = ""
    frame.loc[ga13, "results_updated_on"] = ""
    frame.loc[ga13, "notes"] = (
        "Official workbook verified: July 28 first round D=17760/R=2750; "
        "August 25 same-party runoff excluded; revision date unknown."
    )
    nj = frame.special_id.eq("2026-nj-cd11")
    # Extract aggregate totals only, not addresses present in the official PDF.
    text = "\n".join(
        p.extract_text(extraction_mode="layout") or "" for p in PdfReader(RAW / "nj11.pdf").pages
    )
    counts = [int(n.replace(",", "")) for n in re.findall(r"^\s*Total\s+([\d,]+)\s*$", text, re.M)]
    if counts[:4] != [81825, 53520, 625, 135970]:
        raise ValueError("NJ published totals changed; manual review required")
    frame.loc[nj, "retrieved_on"] = STAMP
    frame.loc[nj, "include_in_metric"] = "N"
    frame.loc[nj, "exclusion_reason"] = (
        "Special verified; same-map presidential baseline fails source-total reconciliation."
    )
    frame.loc[nj, "notes"] = (
        "May 14 canvass reconfirmed; excluded for baseline quality, independent of observed swing."
    )
    changes.append(
        {
            "special_id": "2026-nj-cd11",
            "special_counts_verified": True,
            "included": False,
            "reason": "unvalidated geographic baseline",
        }
    )
    headers = "\n".join(line for line in path.read_text().splitlines() if line.startswith("#"))
    path.write_text(headers + "\n" + frame.to_csv(index=False))
    output.write_text(
        json.dumps(
            {
                "as_of": STAMP,
                "changes": changes,
                "other_specials": "Not reverified; original retrieval dates retained",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

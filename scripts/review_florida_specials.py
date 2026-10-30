"""Reverify both Florida congressional special aggregates with exact source lineage."""

import json
import shutil
from pathlib import Path

import pandas as pd

from election_prediction.data.manifest import sha256_file
from election_prediction.data.official_repairs import florida_federal_specials
from election_prediction.data.public_sources import snapshot


def main() -> None:
    stamp = "2026-10-22"
    output = Path(f"reports/refresh_{stamp}/special_source_refresh.json")
    if output.exists():
        raise FileExistsError("preserve the dated source review")
    url = "https://results.elections.myflorida.com/SummaryRpt.asp?ElectionDate=4/1/2025&Race=FED&DATAMODE="
    raw = snapshot(
        url,
        Path(f"data/raw/source=special_elections_compiled/snapshot={stamp}/fl-federal.html"),
        source_id="special_elections_compiled",
        owner="Florida Division of Elections",
        expect="html",
        cycle="2025",
    )
    verified = florida_federal_specials(raw)
    reference = Path("data/reference/special_elections_2025_2026.csv")
    before = sha256_file(reference)
    preserved = raw.parent / f"sha256={before}/specials-before-fl-review.csv"
    preserved.parent.mkdir(parents=True, exist_ok=True)
    if not preserved.exists():
        shutil.copyfile(reference, preserved)
    frame = pd.read_csv(reference, comment="#", dtype={"district": str}).fillna("")
    changes = []
    for district, values in verified.items():
        key = f"2025-fl-cd{district:02d}"
        matching = frame.special_id.eq(key)
        if matching.sum() != 1:
            raise ValueError("Florida compiled contest identity mismatch")
        existing = frame.loc[matching, list(values)].iloc[0].astype(int).to_dict()
        if existing != values:
            raise ValueError(f"Florida totals changed; explicit source review required: {key}")
        frame.loc[matching, "source_url"] = url
        frame.loc[matching, "retrieved_on"] = stamp
        changes.append(
            {
                "special_id": key,
                "counts_verified": values,
                "raw_sha256": sha256_file(raw),
                "raw_path": str(raw),
                "source_url": url,
                "retrieved_on": stamp,
            }
        )
    comments = "\n".join(line for line in reference.read_text().splitlines() if line.startswith("#"))
    reference.write_text(comments + "\n" + frame.to_csv(index=False))
    output.write_text(
        json.dumps(
            {
                "as_of": stamp,
                "changes": changes,
                "previous_compilation_sha256": before,
                "other_specials": "Not reverified today; actual earlier dates retained",
            },
            indent=2,
        )
    )
    print(f"Verified {len(changes)} Florida specials; no counts changed")


if __name__ == "__main__":
    main()

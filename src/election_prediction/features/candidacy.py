"""Explicit ballot evidence, kept distinct from a candidate's FEC filing."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def attach(universe: pd.DataFrame, path: Path, *, as_of: str) -> tuple[pd.DataFrame, dict]:
    out = universe.copy()
    out["incumbent_running"] = pd.Series(pd.NA, index=out.index, dtype="boolean")
    for column in ("ballot_incumbent_dem", "ballot_incumbent_rep"):
        out[column] = pd.Series(pd.NA, index=out.index, dtype="Float64")
    for column in ("dem_nominee", "rep_nominee", "candidacy_source_url", "candidacy_retrieved_on"):
        out[column] = pd.Series(pd.NA, index=out.index, dtype="string")
    if not path.is_file():
        return out, {"verified": 0, "unknown": len(out)}
    evidence = pd.read_csv(path, dtype=str).fillna("")
    required = {"race_key", "incumbent_name", "incumbent_running", "source_url", "retrieved_on"}
    if not required.issubset(evidence):
        raise ValueError("candidacy evidence is missing required columns")
    if evidence[list(required)].eq("").any().any() or evidence.race_key.duplicated().any():
        raise ValueError("candidacy evidence needs unique races and complete provenance")
    evidence = evidence[pd.to_datetime(evidence.retrieved_on) <= pd.Timestamp(as_of)].copy()
    if not evidence.incumbent_running.isin(["True", "False"]).all():
        raise ValueError("incumbent_running must be True or False")
    for row in evidence.to_dict(orient="records"):
        matching = out.race_key.eq(row["race_key"])
        if matching.sum() != 1 or not out.loc[matching, "incumbent_name"].eq(row["incumbent_name"]).all():
            raise ValueError(f"candidacy evidence does not match current holder for {row['race_key']}")
        out.loc[matching, "incumbent_running"] = row["incumbent_running"] == "True"
        for column in ("ballot_incumbent_dem", "ballot_incumbent_rep"):
            if row.get(column):
                value = pd.to_numeric(row[column], errors="raise")
                if value not in (0, 1):
                    raise ValueError("ballot incumbent indicators must be binary")
                out.loc[matching, column] = value
        for column in ("dem_nominee", "rep_nominee"):
            if row.get(column):
                out.loc[matching, column] = row[column]
        out.loc[matching, "candidacy_source_url"] = row["source_url"]
        out.loc[matching, "candidacy_retrieved_on"] = row["retrieved_on"]
    return out, {
        "verified": len(evidence),
        "unknown": int(out.incumbent_running.isna().sum()),
        "known_not_running": int(out.incumbent_running.eq(False).sum()),
        "by_office": out.groupby("office").incumbent_running.count().to_dict(),
    }

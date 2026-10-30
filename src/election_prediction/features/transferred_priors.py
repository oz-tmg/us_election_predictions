"""Admit a live transferred prior only for its registered election and plan."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from ..data.manifest import sha256_file
from ..geography import reference
from ..models.baseline import projection
from . import plan_transfer, plan_versions


def attach(
    universe: pd.DataFrame, register_path: Path, *, cycle: int, plans: plan_versions.PlanVersions
) -> tuple[pd.DataFrame, list[dict]]:
    if not register_path.is_file():
        return universe, []
    register = pd.read_csv(register_path)
    out = universe.copy()
    provenance = []
    for row in register.to_dict(orient="records"):
        state = str(row["state_po"])
        if int(row["source_cycle"]) != cycle - 2 or int(row["target_cycle"]) != cycle:
            raise ValueError("transferred prior must use the preceding election and the target cycle")
        if str(row["plan_id"]) != plans.plan_id(state, cycle):
            raise ValueError(f"transferred prior for {state} has the wrong plan")
        path, report_path, calibration_path = [
            Path(row[k]) for k in ("table_path", "report_path", "calibration_path")
        ]
        for key, file in [
            ("table_sha256", path),
            ("report_sha256", report_path),
            ("calibration_sha256", calibration_path),
        ]:
            if str(row[key]) != sha256_file(file):
                raise ValueError(f"transferred prior input changed: {file}")
        report = json.loads(report_path.read_text())
        if not report.get("usability", {}).get("usable") or report["from_cycle"] != cycle - 2:
            raise ValueError("transferred prior failed its coverage gate")
        calibration = json.loads(calibration_path.read_text())
        sigma = plan_transfer.transfer_sigma_from_backtest(calibration["backtest"])
        table = pd.read_parquet(path)
        if set(table["state_po"]) != {state}:
            raise ValueError("transferred prior state does not match its register")
        expected = set(
            out.loc[out.office.eq("us_house") & out.state_po.eq(state), "district_num"].astype(int)
        )
        if set(table["new_district"].astype(int)) != expected or table["new_district"].duplicated().any():
            raise ValueError("transferred prior must cover exactly the current state's districts")
        state_fips = reference.by_postal(state).fips
        table["geography_id"] = table["new_district"].map(
            lambda d, fips=state_fips: f"state:{fips}|district:cong_{int(d):02d}"
        )
        if not table[projection.TRANSFERRED_PRIOR_COLUMN].between(0, 1).all():
            raise ValueError("transferred shares must be finite probabilities")
        table[projection.TRANSFER_SIGMA_COLUMN] = sigma
        for col in (projection.TRANSFERRED_PRIOR_COLUMN, projection.TRANSFER_SIGMA_COLUMN):
            mapping = table.set_index("geography_id")[col]
            out[col] = out.get(col, pd.Series(float("nan"), index=out.index)).where(
                ~out["geography_id"].isin(mapping.index), out["geography_id"].map(mapping)
            )
        provenance.append(
            {
                **row,
                "transfer_sigma": sigma,
                "confidence": table[list(plan_transfer.CONFIDENCE_COMPONENTS)].describe().to_dict(),
            }
        )
    return out, provenance

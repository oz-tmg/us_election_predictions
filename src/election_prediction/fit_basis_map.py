"""Fit and persist the presidential-to-House basis map (RD-003's second half).

``features/plan_transfer`` produces a presidential two-party share on new boundaries;
``projection.project_house`` consumes a House-basis share. This writes the conversion
between them, measured on district-cycles where both are observed, so that a transfer and a
projection cannot disagree about what basis a prior is on.

Run:  ep-fit-basis-map
Out:  reports/basis_map.json
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

import pandas as pd

from .models.baseline import basis_mapping


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--house-panel", type=Path, default=Path("data/gold/house_panel.parquet"))
    ap.add_argument("--gold-dir", type=Path, default=Path("data/gold"))
    ap.add_argument("--out", type=Path, default=Path("reports/basis_map.json"))
    ap.add_argument(
        "--cycles",
        type=int,
        nargs="*",
        default=list(basis_mapping.PRESIDENTIAL_CYCLES),
        help="presidential cycles with a built CD baseline",
    )
    args = ap.parse_args(argv)

    baselines = {}
    for cycle in args.cycles:
        path = args.gold_dir / f"cd_presidential_baseline_{cycle}.parquet"
        if path.is_file():
            baselines[cycle] = pd.read_parquet(path)
    if not baselines:
        print(f"no CD presidential baselines in {args.gold_dir}; run ep-build-cd-baselines first")
        return 1

    panel = basis_mapping.build_mapping_panel(pd.read_parquet(args.house_panel), baselines)
    fitted = basis_mapping.fit(panel)
    payload = {"fitted_on": date.today().isoformat(), **fitted.to_dict()}

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, default=str))

    loco = "n/a" if fitted.loco_residual_sd is None else f"{fitted.loco_residual_sd:.4f}"
    print(
        "Presidential lean -> House lean\n"
        f"  fitted on {fitted.n} contested district-cycles across {list(fitted.cycles)}\n"
        f"  intercept           {fitted.intercept:+.4f}\n"
        f"  slope               {fitted.slope:.4f}\n"
        f"  residual sd         {fitted.residual_sd:.4f}\n"
        f"  leave-one-cycle-out {loco}\n"
        f"  MAE                 {fitted.mae:.4f}\n"
        f"  -> {args.out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

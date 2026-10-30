"""Run-bundle contract: what one dashboard "run" is, and which audience may see it.

A bundle is a directory ``<root>/<tier>/<run_id>/`` holding ``run.json`` (this module's
``RunManifest``) and the tables it names. The dashboard lists bundles to let a reader cycle
through past projections, scenarios and historical results.

Tier is part of the contract, not a deployment setting. The 2026 projection is held, not
published (PROJECT_CONTEXT.md §13, 2026-09-30), so **only historical certified results may
be public**: a manifest that claims ``tier = public`` for any modelled kind raises at
construction. Publishing a projection is therefore a code change made against the §13
revisit triggers, never a flag flipped at deploy time.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path

BUNDLE_SCHEMA_VERSION = "1"
MANIFEST_NAME = "run.json"


class Tier(StrEnum):
    PUBLIC = "public"
    VAULT = "vault"


class RunKind(StrEnum):
    PREREGISTRATION = "preregistration"
    REFRESH = "refresh"
    SCENARIO = "scenario"
    BACKTEST = "backtest"
    CROSS_CHECK = "cross_check"
    HISTORICAL = "historical"


# The status line every chart of a run carries. Historical / modelled / certified are
# labelled distinctly (CLAUDE.md §5, §6).
KIND_LABELS: dict[RunKind, str] = {
    RunKind.PREREGISTRATION: "Pre-registered prediction — sealed, not published as a forecast",
    RunKind.REFRESH: "Internal refresh — modelled, not published as a forecast",
    RunKind.SCENARIO: "Scenario — conditional on the stated assumptions, not a forecast",
    RunKind.BACKTEST: "Historical backtest — out-of-sample by held-out cycle",
    RunKind.CROSS_CHECK: "Poll cross-check — compiled releases, not blended into the projection",
    RunKind.HISTORICAL: "Historical certified results",
}

PUBLIC_KINDS = frozenset({RunKind.HISTORICAL})

# Tables a bundle may contain, and the only columns each may carry. The exporter selects
# exactly these, so a candidate name, contributor field or precinct cell cannot reach the
# dashboard by riding along in a wider source table (CLAUDE.md §5, Tier 1-2 rules).
TABLE_COLUMNS: dict[str, tuple[str, ...]] = {
    "seats": (
        "assumption",
        "office",
        "geography_id",
        "state_po",
        "district_num",
        "mean_dem_share",
        "sigma",
        "dem_win_prob",
        "source",
        "boundary_confidence",
        "litigation_risk",
        "incumbent_party",
    ),
    # Hand-compiled poll toplines: facts and their citation only, no release prose.
    "polls": (
        "poll_id",
        "pollster",
        "sponsor",
        "office",
        "state_po",
        "field_start",
        "field_end",
        "published_on",
        "sample_size",
        "population",
        "mode",
        "dem_pct",
        "rep_pct",
        "two_party_dem_share",
        "source_url",
        "retrieved_on",
    ),
    # Certified county returns aggregated to named regions (no inference about voters).
    "region_history": (
        "region",
        "counties",
        "office",
        "cycle",
        "two_party_dem_share",
        "two_party_votes",
        "n_counties",
    ),
    # A scenario's per-district weights.
    "region_shares": ("new_district", "region_share", "two_party_votes", "dem_share"),
    "results": (
        "cycle",
        "office",
        "race_type",
        "geography_id",
        "state_po",
        "district_num",
        "two_party_dem_share",
        "winner_party",
        "uncontested_flag",
        "certified_flag",
        "source_id",
        "snapshot_date",
    ),
}


class BundleError(ValueError):
    """A bundle that breaks the contract. Raised, never repaired."""


@dataclass(frozen=True)
class RunManifest:
    run_id: str
    kind: RunKind
    tier: Tier
    title: str
    as_of: str
    summary: str
    tables: tuple[str, ...] = ()
    documents: tuple[str, ...] = ()
    offices: tuple[str, ...] = ()
    caveats: tuple[str, ...] = ()
    sources: dict[str, str] = field(default_factory=dict)
    source_git_commit: str | None = None
    exporter_git_commit: str | None = None
    exported_on: str | None = None
    schema_version: str = BUNDLE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", RunKind(self.kind))
        object.__setattr__(self, "tier", Tier(self.tier))
        if self.tier is Tier.PUBLIC and self.kind not in PUBLIC_KINDS:
            raise BundleError(
                f"run {self.run_id!r}: a {self.kind.value} run cannot be public. The 2026 "
                "projection is held (PROJECT_CONTEXT.md §13); only historical certified "
                "results are public."
            )
        if not self.run_id or "/" in self.run_id or self.run_id.startswith("."):
            raise BundleError(f"invalid run_id {self.run_id!r}")
        unknown = set(self.tables) - set(TABLE_COLUMNS)
        if unknown:
            raise BundleError(f"run {self.run_id!r}: unknown tables {sorted(unknown)}")
        if not self.summary.strip():
            raise BundleError(f"run {self.run_id!r}: a plain-language summary is required")

    @property
    def status_label(self) -> str:
        return KIND_LABELS[self.kind]

    def to_json(self) -> str:
        d = asdict(self)
        d["kind"] = self.kind.value
        d["tier"] = self.tier.value
        return json.dumps(d, indent=2, sort_keys=True) + "\n"

    @classmethod
    def from_json(cls, text: str) -> RunManifest:
        d = json.loads(text)
        if d.get("schema_version") != BUNDLE_SCHEMA_VERSION:
            raise BundleError(f"unsupported bundle schema {d.get('schema_version')!r}")
        for key in ("tables", "documents", "offices", "caveats"):
            d[key] = tuple(d.get(key, ()))
        return cls(**d)

    @classmethod
    def read(cls, bundle_dir: Path) -> RunManifest:
        manifest = cls.from_json((bundle_dir / MANIFEST_NAME).read_text())
        if manifest.run_id != bundle_dir.name:
            raise BundleError(f"{bundle_dir}: manifest run_id {manifest.run_id!r} != directory")
        return manifest

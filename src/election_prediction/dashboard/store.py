"""Read run bundles for one tier, from a local directory or a ``gs://`` prefix.

A store is bound to exactly one tier and refuses any bundle whose manifest names another,
so a vault bundle copied into the public bucket by mistake fails at startup instead of
being served. Bucket IAM is the first line (the public service account cannot read the
vault bucket); this check is the second.

Bundles are small (well under 1 MB each), so a ``gs://`` store is mirrored to a local cache
once at startup. New bundles appear when the service restarts — which a deploy does.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd

from election_prediction.dashboard.bundle import MANIFEST_NAME, BundleError, RunManifest, Tier


def _mirror_gcs(uri: str, dest: Path) -> Path:
    from google.cloud import storage  # imported lazily: local use needs no GCP libraries

    bucket_name, _, prefix = uri.removeprefix("gs://").partition("/")
    prefix = prefix.rstrip("/") + "/" if prefix else ""
    client = storage.Client()
    for blob in client.list_blobs(bucket_name, prefix=prefix):
        if blob.name.endswith("/"):
            continue
        target = dest / blob.name[len(prefix) :]
        target.parent.mkdir(parents=True, exist_ok=True)
        blob.download_to_filename(target)
    return dest


class BundleStore:
    def __init__(self, root: str | Path, tier: Tier, cache_dir: Path | None = None) -> None:
        self.tier = Tier(tier)
        root_str = str(root)
        if root_str.startswith("gs://"):
            cache = cache_dir or Path(tempfile.mkdtemp(prefix=f"ep-dash-{self.tier.value}-"))
            base = _mirror_gcs(root_str, cache)
        else:
            base = Path(root_str)
        # A local root holds both tiers side by side (``<root>/public``, ``<root>/vault``);
        # a bucket holds one tier at its top level.
        self.base = base / self.tier.value if (base / self.tier.value).is_dir() else base
        self._manifests = self._scan()

    def _scan(self) -> dict[str, RunManifest]:
        manifests: dict[str, RunManifest] = {}
        if not self.base.is_dir():
            return manifests
        for path in sorted(self.base.glob(f"*/{MANIFEST_NAME}")):
            m = RunManifest.read(path.parent)
            if m.tier is not self.tier:
                raise BundleError(f"{path}: a {m.tier.value} bundle found in the {self.tier.value} store")
            manifests[m.run_id] = m
        return manifests

    def runs(self) -> list[RunManifest]:
        """Newest first."""
        return sorted(self._manifests.values(), key=lambda m: (m.as_of, m.run_id), reverse=True)

    def manifest(self, run_id: str) -> RunManifest:
        try:
            return self._manifests[run_id]
        except KeyError:
            raise BundleError(f"no {self.tier.value} run {run_id!r}") from None

    def table(self, run_id: str, name: str) -> pd.DataFrame:
        m = self.manifest(run_id)
        if name not in m.tables:
            raise BundleError(f"run {run_id!r} has no table {name!r}")
        return pd.read_parquet(self.base / run_id / f"{name}.parquet")

    def document(self, run_id: str, name: str) -> Any:
        m = self.manifest(run_id)
        if name not in m.documents:
            raise BundleError(f"run {run_id!r} has no document {name!r}")
        return json.loads((self.base / run_id / f"{name}.json").read_text())

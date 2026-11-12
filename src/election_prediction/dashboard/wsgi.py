"""Entry points: gunicorn ``wsgi:create_server()`` (Cloud Run) and ``ep-dashboard`` (local).

Configuration is environment-only, so one container image serves both audiences:

    EP_DASH_TIER                 public | vault
    EP_DASH_PUBLIC_ROOT          bundle root for the public tier (local dir or gs://bucket)
    EP_DASH_VAULT_ROOT           bundle root for the vault tier (vault only)
    EP_DASH_ACCESS_TEAM_DOMAIN   e.g. savepoint.cloudflareaccess.com (vault only)
    EP_DASH_ACCESS_AUD           the Access application's AUD tag (vault only)
    EP_DASH_INSECURE_LOCAL=1     skip Access verification; refused on Cloud Run
"""

from __future__ import annotations

import argparse
import os
from collections.abc import Mapping, Sequence

from dash import Dash

from election_prediction.dashboard.access import AccessVerifier, insecure_local_allowed
from election_prediction.dashboard.app import create_app
from election_prediction.dashboard.bundle import Tier
from election_prediction.dashboard.store import BundleStore

DEFAULT_ROOT = "data/gold/dashboard_bundles"


def build_from_env(env: Mapping[str, str] = os.environ) -> Dash:
    tier = Tier(env.get("EP_DASH_TIER", "public"))
    public = BundleStore(env.get("EP_DASH_PUBLIC_ROOT", DEFAULT_ROOT), Tier.PUBLIC)
    if tier is Tier.PUBLIC:
        return create_app(tier, public)
    vault = BundleStore(env.get("EP_DASH_VAULT_ROOT", DEFAULT_ROOT), Tier.VAULT)
    if insecure_local_allowed(env):
        return create_app(tier, public, vault, insecure_local=True)
    verifier = AccessVerifier(
        team_domain=env.get("EP_DASH_ACCESS_TEAM_DOMAIN", ""),
        audience=env.get("EP_DASH_ACCESS_AUD", ""),
    )
    return create_app(tier, public, vault, verifier=verifier)


def create_server():  # gunicorn app factory: "election_prediction.dashboard.wsgi:create_server()"
    return build_from_env().server


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="ep-dashboard", description="Run the dashboard locally.")
    ap.add_argument("--tier", choices=[t.value for t in Tier], default="public")
    ap.add_argument("--root", default=DEFAULT_ROOT, help="local bundle root (both tiers)")
    ap.add_argument("--port", type=int, default=8050)
    args = ap.parse_args(argv)
    env = dict(os.environ)
    env.update(EP_DASH_TIER=args.tier, EP_DASH_PUBLIC_ROOT=args.root, EP_DASH_VAULT_ROOT=args.root)
    if args.tier == "vault":
        env["EP_DASH_INSECURE_LOCAL"] = "1"  # local only: refused under Cloud Run
    build_from_env(env).run(host="127.0.0.1", port=args.port, debug=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

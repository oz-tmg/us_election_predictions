#!/usr/bin/env bash
# Upload exported run bundles and restart the services so they load them
# (docs/deployment-plan.md, step 3). Bundles are immutable, so rsync never deletes.
#
#   ep-export-dashboard refresh reports/refresh_2026-10-22   # etc.
#   bash deploy/gcp/publish_bundles.sh
set -euo pipefail
source "$(dirname "$0")/env.sh"
ROOT="${1:-data/gold/dashboard_bundles}"

[ -d "$ROOT/public" ] && gcloud storage rsync --recursive "$ROOT/public" "gs://$PUBLIC_BUCKET"
[ -d "$ROOT/vault" ] && gcloud storage rsync --recursive "$ROOT/vault" "gs://$VAULT_BUCKET"

# A new revision re-reads the buckets at startup. Skipped if the services are not deployed yet.
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
for svc in dash-public dash-vault; do
  if gcloud run services describe "$svc" --region "$REGION" >/dev/null 2>&1; then
    gcloud run services update "$svc" --region "$REGION" --update-env-vars "EP_DASH_BUNDLES_AT=$STAMP"
  fi
done

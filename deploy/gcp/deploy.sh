#!/usr/bin/env bash
# Build the dashboard image with Cloud Build and deploy both Cloud Run services
# (docs/deployment-plan.md, step 4). Run from the repository root.
set -euo pipefail
source "$(dirname "$0")/env.sh"

TAG="$(git rev-parse --short HEAD)"
IMAGE="$REGION-docker.pkg.dev/$PROJECT_ID/$AR_REPO/dashboard:$TAG"
gcloud builds submit --tag "$IMAGE" .

# Both services allow unauthenticated invocation because Cloudflare (not a Google identity)
# calls them. The vault is protected by the Access JWT check inside the app, which also
# covers anyone who finds the run.app URL. Scale to zero; at most two instances.
common=(--image "$IMAGE" --region "$REGION" --allow-unauthenticated
        --min-instances 0 --max-instances 2 --cpu 1 --memory 1Gi --concurrency 40)

gcloud run deploy dash-public "${common[@]}" \
  --service-account "dash-public@$PROJECT_ID.iam.gserviceaccount.com" \
  --set-env-vars "EP_DASH_TIER=public,EP_DASH_PUBLIC_ROOT=gs://$PUBLIC_BUCKET"

gcloud run deploy dash-vault "${common[@]}" \
  --service-account "dash-vault@$PROJECT_ID.iam.gserviceaccount.com" \
  --set-env-vars "EP_DASH_TIER=vault,EP_DASH_PUBLIC_ROOT=gs://$PUBLIC_BUCKET,EP_DASH_VAULT_ROOT=gs://$VAULT_BUCKET,EP_DASH_ACCESS_TEAM_DOMAIN=$ACCESS_TEAM_DOMAIN,EP_DASH_ACCESS_AUD=$ACCESS_AUD"

echo
echo "Origins for deploy/cloudflare/wrangler.toml:"
for svc in dash-public dash-vault; do
  echo "  $svc: $(gcloud run services describe "$svc" --region "$REGION" --format 'value(status.url)')"
done

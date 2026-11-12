#!/usr/bin/env bash
# One-time GCP setup for the dashboard (docs/deployment-plan.md, step 2). Safe to re-run:
# each create is skipped if the resource exists.
#
#   cp deploy/gcp/env.example.sh deploy/gcp/env.sh && $EDITOR deploy/gcp/env.sh
#   gcloud auth login && gcloud config set project "$PROJECT_ID"
#   bash deploy/gcp/bootstrap.sh
set -euo pipefail
source "$(dirname "$0")/env.sh"

gcloud config set project "$PROJECT_ID"
gcloud services enable run.googleapis.com artifactregistry.googleapis.com \
  cloudbuild.googleapis.com storage.googleapis.com

# Two buckets, one per audience, so the boundary is IAM rather than a path convention.
# Public access prevention is enforced on BOTH: even the "public" tier is served by the
# app, never read directly from the bucket.
for bucket in "$PUBLIC_BUCKET" "$VAULT_BUCKET"; do
  if ! gcloud storage buckets describe "gs://$bucket" >/dev/null 2>&1; then
    gcloud storage buckets create "gs://$bucket" --location="$REGION" \
      --uniform-bucket-level-access --public-access-prevention
  fi
  gcloud storage buckets update "gs://$bucket" --versioning
done

# One service account per service. The public one can read only the public bucket.
for sa in dash-public dash-vault; do
  if ! gcloud iam service-accounts describe "$sa@$PROJECT_ID.iam.gserviceaccount.com" >/dev/null 2>&1; then
    gcloud iam service-accounts create "$sa" --display-name "Dashboard ($sa)"
  fi
done
gcloud storage buckets add-iam-policy-binding "gs://$PUBLIC_BUCKET" \
  --member "serviceAccount:dash-public@$PROJECT_ID.iam.gserviceaccount.com" --role roles/storage.objectViewer
gcloud storage buckets add-iam-policy-binding "gs://$PUBLIC_BUCKET" \
  --member "serviceAccount:dash-vault@$PROJECT_ID.iam.gserviceaccount.com" --role roles/storage.objectViewer
gcloud storage buckets add-iam-policy-binding "gs://$VAULT_BUCKET" \
  --member "serviceAccount:dash-vault@$PROJECT_ID.iam.gserviceaccount.com" --role roles/storage.objectViewer

if ! gcloud artifacts repositories describe "$AR_REPO" --location "$REGION" >/dev/null 2>&1; then
  gcloud artifacts repositories create "$AR_REPO" --repository-format docker --location "$REGION"
fi
# Keep the five newest images; Artifact Registry storage beyond 0.5 GB is billed.
cat > /tmp/ar-cleanup.json <<'JSON'
[{"name": "keep-recent", "action": {"type": "Keep"}, "mostRecentVersions": {"keepCount": 5}},
 {"name": "delete-old", "action": {"type": "Delete"}, "condition": {"olderThan": "30d"}}]
JSON
gcloud artifacts repositories set-cleanup-policies "$AR_REPO" --location "$REGION" \
  --policy /tmp/ar-cleanup.json --no-dry-run

echo
echo "Done. Next: set a billing budget alert (console: Billing > Budgets & alerts, \$5 and \$10),"
echo "then publish bundles (publish_bundles.sh) and deploy (deploy.sh)."

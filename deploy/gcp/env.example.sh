# Copy to deploy/gcp/env.sh (git-ignored) and edit. It holds names, not secrets.
# Sourced by bootstrap.sh, deploy.sh and publish_bundles.sh.
export PROJECT_ID="savepoint-elections"          # your GCP project id
export REGION="us-west1"                          # Oregon: near Vancouver, free-tier region
export PUBLIC_BUCKET="${PROJECT_ID}-dash-public"  # public-tier bundles
export VAULT_BUCKET="${PROJECT_ID}-dash-vault"    # vault-tier bundles
export AR_REPO="dashboard"                        # Artifact Registry repository
export ACCESS_TEAM_DOMAIN="yourteam.cloudflareaccess.com"
export ACCESS_AUD="paste-the-access-application-aud-tag"

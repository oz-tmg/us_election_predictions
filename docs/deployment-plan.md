# Dashboard deployment plan — GCP + Cloudflare

> **Status (2026-10-28):** code, container and deploy scripts are built and tested locally;
> nothing is deployed. Decision recorded in `PROJECT_CONTEXT.md` §13 (2026-10-28).
> Owner: AO.

## 1. What is being deployed

A Plotly Dash dashboard in two audiences, from one container image:

| Service | Hostname | Shows | Protection |
|---|---|---|---|
| `dash-public` | `elections.alexoswald.ca` | Historical certified results (MEDSL, Tier 0), method note | none needed |
| `dash-vault` | `elections-vault.alexoswald.ca` | 2026 projections (seal + refreshes + scenarios), seat band, chamber control, every race, backtest diagnostics, run registry | Cloudflare Access + in-app JWT verification |

**Why the 2026 projection is vault-only.** PROJECT_CONTEXT §13 (2026-09-30) holds the 2026
forecast. A public map of it would reverse that decision, so the bundle contract enforces it:
`RunManifest` raises if any modelled run (pre-registration, refresh, scenario, backtest)
claims `tier = public`. Publishing later is a code change made against the §13 revisit
triggers (post-election evaluation, RD-003 narrowing the redrawn seats, or NE-002 resolving
the Senate), not a deploy flag.

**Why `elections-vault.` and not `vault.elections.`** Cloudflare's free Universal SSL
certificate covers one level (`*.alexoswald.ca`); a second-level name needs a paid Advanced
Certificate.

## 2. Architecture

```
build artefacts (reports/, data/gold/)            ← existing builds, unchanged
        │  ep-export-dashboard  (src/election_prediction/dashboard/export.py)
        ▼
run bundles  data/gold/dashboard_bundles/{public,vault}/<run_id>/   (git-ignored, ~60 KB each)
        │  deploy/gcp/publish_bundles.sh  (gcloud storage rsync, never deletes)
        ▼
GCS  <project>-dash-public   <project>-dash-vault     (private buckets, PAP enforced, versioned)
        │  read at startup by each service's own service account
        ▼
Cloud Run  dash-public  ←SA can read public bucket only
           dash-vault   ←SA can read both; verifies Cf-Access-Jwt-Assertion on every request
        ▲
Cloudflare Worker (deploy/cloudflare/worker.js) — rewrites Host to the run.app origin
Cloudflare Access — in front of elections-vault.alexoswald.ca
Cloudflare DNS/TLS — alexoswald.ca zone (already hosted there)
```

**Run bundles are the only thing the dashboard reads.** Each is a `run.json` manifest
(kind, tier, as-of date, plain-language summary, caveats, SHA-256 of every source file, the
build's git commit) plus parquet/JSON tables restricted to a declared column allow-list, so
candidate names, contributor fields or precinct cells cannot ride along. The exporter
re-shapes; it never fits or simulates. Chamber probabilities and seat percentiles are copied
from the correlated simulation, never recomputed from per-seat probabilities (that would
treat seats as independent, CLAUDE.md §2.6).

**Defence in depth on the vault:**
1. Cloudflare Access login (email one-time PIN or Google), policy = named emails.
2. The app verifies the Access JWT's signature (team JWKS), audience (AUD tag) and issuer
   on every request, including Dash's internal `/_dash-*` routes. This is what stops the
   `*.run.app` URL from bypassing Cloudflare. `/healthz` is the only open path.
3. Separate buckets and service accounts: the public service cannot read vault data, and
   the public app is never constructed with a vault store (`create_app` raises).
4. A store refuses any bundle whose manifest tier differs from its own (a misfiled vault
   bundle fails startup rather than being served).
5. Vault responses: `Cache-Control: private, no-store`, `X-Robots-Tag: noindex`,
   `frame-ancestors 'none'`.
6. `EP_DASH_INSECURE_LOCAL=1` (dev bypass) is refused whenever `K_SERVICE` is set, i.e.
   on every Cloud Run revision.

## 3. Steps

**0. Local** (done, repeatable):
```bash
pip install -e ".[dev,dashboard]"
ep-export-dashboard preregistration reports/preregistration_2026-11-03.json
ep-export-dashboard refresh reports/refresh_2026-10-22        # once per refresh
ep-export-dashboard backtest reports/p1_results.json --as-of 2026-09-01
ep-export-dashboard history data/gold/race_results.parquet
ep-dashboard --tier vault      # http://127.0.0.1:8050, Access check bypassed locally
ep-dashboard --tier public
```
A scenario is exported with `refresh <dir> --kind scenario --run-id <name>`.

**1. GCP project.** Create a project with billing, install the gcloud CLI, then
`cp deploy/gcp/env.example.sh deploy/gcp/env.sh` and fill it in (`env.sh` is git-ignored).
Set a **billing budget alert at $5 and $10** in the console.

**2. Bootstrap** — `bash deploy/gcp/bootstrap.sh`: enables Run/Artifact Registry/Cloud
Build/Storage; creates both buckets (uniform access, public access prevention, versioning),
both service accounts with read-only bindings, and the image repository with a cleanup
policy.

**3. Publish bundles** — `bash deploy/gcp/publish_bundles.sh`.

**4. Deploy** — `bash deploy/gcp/deploy.sh`: Cloud Build builds the image (upload limited by
`.gcloudignore` to `pyproject.toml`, `README.md`, `Dockerfile`, `src/`), then deploys both
services: scale-to-zero, max 2 instances, 1 vCPU / 1 GiB. It prints the two `run.app`
origins.

**5. Cloudflare Access** — Zero Trust → Access → Applications → Self-hosted:
domain `elections-vault.alexoswald.ca`, policy *Allow* → emails = yours (+ reviewers).
Copy the **AUD tag** and team domain into `env.sh` and re-run `deploy.sh`.

**6. Cloudflare Worker + DNS** — `cp deploy/cloudflare/wrangler.toml.example
deploy/cloudflare/wrangler.toml`, paste the origins, `npx wrangler deploy`. Add proxied
(orange-cloud) DNS records for `elections` and `elections-vault`; the target is irrelevant
because the Worker route answers first (`AAAA 100::` is the convention).

**7. Verify** — `curl -I https://elections-vault.alexoswald.ca` redirects to the Access
login; `curl -I https://dash-vault-…run.app/` returns **403**; the public hostname serves.
Link from `www.alexoswald.ca` rather than embedding (Access cookies and third-party-cookie
blocking break iframes; the public service allows framing from alexoswald.ca if wanted).

## 4. Cost (estimates — check the GCP pricing calculator)

| Item | Expected |
|---|---|
| Cloud Run, two services, scale to zero, portfolio traffic | ≈ $0 (free tier); cold start a few seconds |
| Optional `--min-instances 1` on `dash-public` to remove cold starts | roughly $5–15/month |
| Cloud Storage, bundles (< 1 MB) | ≈ $0 |
| Artifact Registry (≤ 5 images kept) | ≈ $0–0.10 |
| Cloud Build | free tier |
| Cloudflare DNS, Worker (100k requests/day), Access (≤ 50 users) | $0 |

## 5. Phase 2 — the data platform (not yet built)

Independent of the dashboard, which never queries it:

- **Medallion lake in GCS.** A third bucket `<project>-elections-lake` (private, versioned,
  `raw/` under a retention policy; Autoclass or Coldline for `raw/`), mirrored with
  `gcloud storage rsync -r data/<layer> gs://…/<layer>`. ~13 GB raw, ~0.6 GB silver,
  ~9 MB gold. Many raw sources are registered as *no unrestricted redistribution*
  (`docs/dataset-registry.md`): a private bucket is storage, not redistribution, but the
  bucket must never be made public. **No Tier 3–5 data enters this GCP project at all**; if
  one is ever needed it goes to a separate project.
- **BigQuery.** Datasets `elections_silver`, `elections_gold`, `elections_manifests` in the
  same location as the bucket; load parquet with `bq load --source_format=PARQUET`; load
  TIGER district shapes into a `GEOGRAPHY` column for BigQuery GIS. At this volume it sits
  in the free tier (10 GB storage, 1 TB queried/month); set a per-query maximum bytes billed.
- **Automation.** Publish bundles from GitHub Actions using Workload Identity Federation
  (no service-account keys).

## 6. Known gaps

- **Light theme only.** Figures are drawn for the light surface; a dark theme needs its own
  validated figure template.
- **House geography.** The House view is a probability-ordered seat strip, not a district
  map: a geographic map needs 2026-plan district shapes for all nine redrawn states (only
  Texas's are collected, RD-003), and a cartogram layout would need a sourced, licensed hex
  grid. Both are follow-ups.
- **Governor and presidential projections** have no exported artefact yet (the governor
  model is unfitted); the bundle schema already accepts the offices.
- **Bundles load at startup.** New bundles need `publish_bundles.sh` (which rolls a new
  revision).
- **Results ledger (`ep-results-2026`).** Not yet exported. Once results certify, an
  *unofficial*/*certified* results bundle is the next exporter; it must keep the two labels
  distinct (CLAUDE.md §5).

## 7. Dependencies added (`[dashboard]` extra)

| Package | Licence | Use |
|---|---|---|
| dash | MIT | app framework |
| plotly | MIT | figures |
| gunicorn | MIT | WSGI server in the container |
| PyJWT + cryptography | MIT; Apache-2.0/BSD-3-Clause | Cloudflare Access JWT verification |
| google-cloud-storage | Apache-2.0 | reading bundles from GCS |

None is imported by modelling code. Record them in `docs/dependencies.md` when that file
lands on `main` (it is currently uncommitted on `feat/fec-candidate-layer`).

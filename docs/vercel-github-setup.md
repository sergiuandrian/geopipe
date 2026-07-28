# Connect GeoPipe (GitHub) → Vercel

Two supported paths. Prefer **A** for the simplest GitHub integration.

## A. Native Vercel ↔ GitHub (recommended)

1. Install the [Vercel GitHub App](https://github.com/apps/vercel) on the `sergiuandrian/geopipe` repo (or your account/org).
2. Import the repo in Vercel:
   - [Import GeoPipe](https://vercel.com/new/import?s=https://github.com/sergiuandrian/geopipe)
   - Or: [Clone & deploy](https://vercel.com/new/clone?repository-url=https://github.com/sergiuandrian/geopipe)
3. Keep **Root Directory** empty / `.` (repo root has `vercel.json` with Vite + FastAPI Services).
4. Framework: leave auto (Services from `vercel.json`).
5. After first deploy, set project env vars as needed:
   - `JWT_SECRET` (required for real auth)
   - `AUTH_REQUIRED` (`true` in production if you want login-only)
   - `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_PRO` (optional)
   - `SPATIAL_BACKEND` (default `geopackage`)
6. Push to `main` → production. Open a PR → preview deployment.

## B. GitHub Actions deploy (optional / CI-controlled)

Use when you want builds in GitHub Actions instead of (or in addition to) Vercel’s Git integration.

### 1. Create a Vercel token

[Vercel → Account Settings → Tokens](https://vercel.com/account/tokens) → create → copy.

### 2. Link the project once (local)

```bash
cd /path/to/geopipe
npx vercel@41 login
npx vercel@41 link --yes --project geopipe
cat .vercel/project.json   # orgId + projectId
```

### 3. Add GitHub Actions secrets

Repo → **Settings → Secrets and variables → Actions**:

| Secret | Value |
|---|---|
| `VERCEL_TOKEN` | token from step 1 |
| `VERCEL_ORG_ID` | `orgId` from `.vercel/project.json` |
| `VERCEL_PROJECT_ID` | `projectId` from `.vercel/project.json` |

### 4. Workflows in this repo

- `.github/workflows/vercel-production.yml` — push to `main` / manual
- `.github/workflows/vercel-preview.yml` — pull requests

If you use **only** Actions (not Vercel Git), disable automatic Git deploys in the Vercel project **Settings → Git**, or avoid installing the GitHub App.

## Verify

```bash
curl -sS https://YOUR_DEPLOYMENT.vercel.app/v1/bootstrap | head
# UI: open the deployment URL, upload sample-data/paris-sites.geojson
```

On Vercel, SQLite/GeoPackage live under `/tmp` (ephemeral per instance).

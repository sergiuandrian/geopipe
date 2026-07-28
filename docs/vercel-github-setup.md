# Connect GeoPipe (GitHub) → Vercel

Two supported paths. Prefer **A** (dashboard import). Do **not** use expired CLI device-login links from chat agents — those fail with `Invalid Compact JWS`.

## A. Native Vercel ↔ GitHub (recommended)

1. Open [vercel.com/login](https://vercel.com/login) in a normal browser and sign in (GitHub is fine).
2. Install the [Vercel GitHub App](https://github.com/apps/vercel) on `sergiuandrian/geopipe` (or your account/org).
3. Import the repo:
   - Go to [vercel.com/new](https://vercel.com/new)
   - Under **Import Git Repository**, choose **Continue with GitHub** and select `geopipe`
   - Direct import (after you’re logged in): [Import GeoPipe](https://vercel.com/new/import?s=https://github.com/sergiuandrian/geopipe)
4. Keep **Root Directory** empty / `.` (repo root has `vercel.json` with Vite + FastAPI Services).
5. Framework: leave auto (Services from `vercel.json`).
6. After first deploy, set project env vars as needed:
   - `JWT_SECRET` (required for real auth)
   - `AUTH_REQUIRED` (`true` in production if you want login-only)
   - `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_PRO` (optional)
   - `SPATIAL_BACKEND` (default `geopackage`)
7. Push to `main` → production. Open a PR → preview deployment.

### Troubleshooting access / deploy errors

| Symptom | Cause / fix |
|---|---|
| `Deployment failed` → docs link for project configuration | Invalid `vercel.json`. Services must not set top-level `memory` / `maxDuration` (Fluid compute). Use `functions` → `maxDuration` on the backend service instead. |
| `TypeError: …toSorted is not a function` on `vercel.com` | **Vercel dashboard bug/compat** — their UI uses `Array.prototype.toSorted` (needs Chrome/Edge 110+, Firefox 115+, Safari 16+). Update the browser, try another browser/profile, or disable broken extensions. This is **not** a GeoPipe error. |
| `Invalid Compact JWS` | Expired or broken CLI device-login code. Ignore agent device URLs; log in at [vercel.com/login](https://vercel.com/login) instead, then Import. |
| Device authorize page asks to log in again, then errors | Start over from the dashboard Import flow (path A). Don’t reuse old `user_code` links. |
| Import page doesn’t list `geopipe` | Install/authorize the [Vercel GitHub App](https://github.com/apps/vercel) for that repo, then refresh. |
| Platform outage | Check [vercel-status.com](https://www.vercel-status.com/). |

## B. GitHub Actions deploy (optional / CI-controlled)

Use when you want builds in GitHub Actions instead of (or in addition to) Vercel’s Git integration.

### 1. Create a Vercel token

[Vercel → Account Settings → Tokens](https://vercel.com/account/tokens) → create → copy.

### 2. Link the project once (local)

```bash
cd /path/to/geopipe
npx vercel@latest login
npx vercel@latest link --yes --project geopipe
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

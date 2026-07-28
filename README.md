# GeoPipe

Upload spatial data into **GeoPackage, DuckDB Spatial, SpatiaLite, or PostGIS**.
Serve a Feature API, vector tiles, and **agent tools** over MCP (HTTP / stdio / SSE) or OpenAI-compatible function calling.

Works with any MCP host or tool-calling agent — Claude Desktop, GitHub Copilot, Continue, custom LangChain/OpenAI agents, Cursor, etc.

## Scope

### Spatial backends
| Backend | Notes |
|---|---|
| `geopackage` | Default file store |
| `duckdb` | DuckDB + spatial extension |
| `spatialite` | SQLite/SpatiaLite via GDAL |
| `postgis` | Requires `POSTGIS_URL` |

### APIs
- `GET /v1/layers/{id}/features` — bbox GeoJSON
- `GET /v1/layers/{id}/tiles/{z}/{x}/{y}.mvt`
- `GET /v1/backends` — backend availability
- `GET /v1/mcp/tools` + `POST /v1/mcp/tools/{name}` — MCP HTTP tools
- `GET /v1/agents/tools` — OpenAI function-calling schema
- `GET /v1/mcp/sse` + `POST /v1/mcp/messages` — remote MCP-style transport
- `python -m app.mcp.stdio_server` — local stdio MCP bridge

## Quick start

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=. uvicorn app.main:app --reload --port 8000
```

```bash
cd frontend
npm install && npm run dev
```

Frontend map engine is **MapLibre GL** (Mapbox-class vector rendering). Optional:

```bash
# Use Mapbox Light tiles
export VITE_MAPBOX_TOKEN=pk....
# Or point at any MapLibre style URL
export VITE_MAP_STYLE=https://basemaps.cartocdn.com/gl/positron-gl-style/style.json
```

UI checks:

```bash
cd frontend
npm run test:e2e
```

Optional PostGIS:

```bash
docker compose up -d postgis
export POSTGIS_URL=postgresql+psycopg://geopipe:geopipe@127.0.0.1:5432/geopipe
export SPATIAL_BACKEND=postgis
```

Sample: `sample-data/paris-sites.geojson`

## Connect any agent

```bash
# Connector snippets for HTTP / OpenAI tools / MCP stdio / MCP SSE
curl http://127.0.0.1:8000/v1/agents/connectors -H "X-API-Key: $GEOPIPE_API_KEY"

# Stdio MCP bridge
cd backend
GEOPIPE_API_URL=http://127.0.0.1:8000 GEOPIPE_API_KEY=gp_... \
  PYTHONPATH=. python -m app.mcp.stdio_server
```

Tools: `list_layers`, `list_spatial_backends`, `query_features`, `layer_stats`, `buffer`, `intersect`, `crs_transform`

## Deploy (Vercel)

Frontend (Vite) and API (FastAPI) deploy together as [Vercel Services](https://vercel.com/docs/services/experimental) — one domain, `/v1/*` → backend, everything else → UI.

```bash
# One-time: link the repo (creates .vercel/)
npx vercel@41 link

# Production deploy
npx vercel@41 deploy --prod --yes
```

Or use the GitHub Action (`.github/workflows/deploy-vercel.yml`) after adding secrets:

- `VERCEL_TOKEN`
- `VERCEL_ORG_ID`
- `VERCEL_PROJECT_ID`

Set production env in the Vercel project as needed (`JWT_SECRET`, `AUTH_REQUIRED`, `STRIPE_*`, `SPATIAL_BACKEND`, …). On Vercel the API stores SQLite/GeoPackage under `/tmp` (ephemeral per instance).

```bash
# Optional: Deploy button
# https://vercel.com/new/clone?repository-url=https://github.com/sergiuandrian/geopipe
```

## Roadmap (next)

1. ~~Stripe billing + plan/usage limits~~
2. ~~Usage dashboard~~
3. ~~Real auth (beyond bootstrap API keys)~~
4. ~~Deploy to Vercel + browser UI verification~~
5. Multi-tenant PostGIS

## Auth & billing

Email/password accounts issue a JWT (`Authorization: Bearer …`). API keys remain the machine auth for Feature/MVT/MCP.

```bash
# Sign up
curl -X POST http://127.0.0.1:8000/v1/auth/signup \
  -H 'Content-Type: application/json' \
  -d '{"email":"you@example.com","password":"password123","name":"You"}'

# Usage dashboard
curl http://127.0.0.1:8000/v1/billing/usage -H "Authorization: Bearer $TOKEN"

# Stripe Checkout (requires STRIPE_* env) or local dev upgrade
curl -X POST http://127.0.0.1:8000/v1/billing/checkout -H "Authorization: Bearer $TOKEN"
curl -X POST http://127.0.0.1:8000/v1/billing/dev-upgrade -H "Authorization: Bearer $TOKEN"
```

Stripe webhook: `POST /v1/billing/webhook` (set `STRIPE_WEBHOOK_SECRET`).
Set `AUTH_REQUIRED=true` to disable anonymous bootstrap access.

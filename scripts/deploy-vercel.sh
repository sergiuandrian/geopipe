#!/usr/bin/env bash
# Link (if needed) and deploy GeoPipe to Vercel production.
set -euo pipefail
cd "$(dirname "$0")/.."

if ! npx --yes vercel@41 whoami >/dev/null 2>&1; then
  echo "Not logged in. Run: npx vercel@41 login"
  exit 1
fi

if [[ ! -f .vercel/project.json ]]; then
  echo "Linking Vercel project 'geopipe'…"
  npx --yes vercel@41 link --yes --project geopipe
fi

echo "org/project:"
python3 - <<'PY'
import json
from pathlib import Path
p = json.loads(Path(".vercel/project.json").read_text())
print(f"  VERCEL_ORG_ID={p.get('orgId')}")
print(f"  VERCEL_PROJECT_ID={p.get('projectId')}")
print("Add these + VERCEL_TOKEN as GitHub Actions secrets (see docs/vercel-github-setup.md).")
PY

npx --yes vercel@41 pull --yes --environment=production
npx --yes vercel@41 deploy --prod --yes

#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
npx --yes vercel@41 pull --yes --environment=production
npx --yes vercel@41 deploy --prod --yes

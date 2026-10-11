#!/usr/bin/env bash
# Walks through the simulated incident workflow against a RUNNING CloudRescue API.
# Local only: it calls the demo endpoints, which change in-memory state and nothing else.
# Usage: scripts/demo.sh            (override target: BASE_URL=http://127.0.0.1:8000)
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
TOKEN_HEADER=()
if [ -n "${CLOUDRESCUE_DEMO_TOKEN:-}" ]; then
  TOKEN_HEADER=(-H "X-Demo-Token: ${CLOUDRESCUE_DEMO_TOKEN}")
fi

command -v curl >/dev/null 2>&1 || { echo "curl is required" >&2; exit 2; }

http_code() { # method path [curl args...]
  local method="$1" path="$2"
  shift 2
  curl -sS -o /tmp/cloudrescue-demo.json -w '%{http_code}' -X "$method" "$@" "${BASE_URL}${path}"
}

show() {
  if command -v python3 >/dev/null 2>&1; then
    python3 -m json.tool </tmp/cloudrescue-demo.json
  else
    cat /tmp/cloudrescue-demo.json
  fi
}

step() { printf '\n== %s\n' "$*"; }

step "1. Status before (expect 200, simulated_service.state=healthy)"
code=$(http_code GET /api/status); echo "HTTP ${code}"; show

step "2. Simulate a failure (expect 201)"
code=$(http_code POST /api/demo/simulate-failure "${TOKEN_HEADER[@]}" \
  -H 'Content-Type: application/json' \
  -d '{"reason": "demo: simulated app crash", "severity": "high"}')
echo "HTTP ${code}"; show

step "3. Status during failure (expect 503: the SIMULATED service is unhealthy)"
code=$(http_code GET /api/status); echo "HTTP ${code}"; show

step "4. Recover (expect 200)"
code=$(http_code POST /api/demo/recover "${TOKEN_HEADER[@]}"); echo "HTTP ${code}"; show

step "5. Status after (expect 200)"
code=$(http_code GET /api/status); echo "HTTP ${code}"; show

step "6. Incident history (every entry is marked simulated)"
code=$(http_code GET /api/incidents); echo "HTTP ${code}"; show

echo
echo "Done. Nothing in AWS was touched; all state above is simulated and in memory."

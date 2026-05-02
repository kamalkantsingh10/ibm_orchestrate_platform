#!/usr/bin/env bash
# verify_demo.sh — smoke check the running demo (Story 1.5 AC #4 + Story 2.3 AC #12).
#
# Six checks. Each prints ✓/✗ + an actionable hint on failure. Exit 1 if
# any check fails. CI=1 skips the ADK runtime check (the agents container
# isn't typically brought up in CI).
#
# Usage:  bash tools/scripts/verify_demo.sh
#         CI=1 bash tools/scripts/verify_demo.sh   # skip ADK check

set -uo pipefail

# Repo root anchors: this script lives at tools/scripts/verify_demo.sh.
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SQLITE_DB="${ROOT}/data/cockpit.db"
API_BASE="${API_BASE:-http://localhost:8000}"
UI_BASE="${UI_BASE:-http://localhost:5173}"
ANALYST_ID="${DEMO_ANALYST_ID:-dc2aaaa3-555b-4636-89d0-6047dc205220}"

GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; NC='\033[0m'
ok()   { printf "  ${GREEN}✓${NC} %s\n" "$1"; }
fail() { printf "  ${RED}✗${NC} %s\n     ${YELLOW}hint:${NC} %s\n" "$1" "$2"; }

failures=0

# ─── Check 1: SQLite DB initialised ──────────────────────────────────────────
if python3 -c "import sqlite3; sqlite3.connect('${SQLITE_DB}')" 2>/dev/null; then
  ok "SQLite DB initialised at ${SQLITE_DB}"
else
  fail "SQLite DB not initialised (${SQLITE_DB})" "run: make migrate"
  failures=$((failures + 1))
fi

# ─── Check 2: cockpit-api /health ────────────────────────────────────────────
if curl -sf "${API_BASE}/health" >/dev/null; then
  ok "cockpit-api /health is reachable at ${API_BASE}"
else
  fail "cockpit-api /health is not reachable (${API_BASE}/health)" \
       "is \`make dev\` running in another terminal?"
  failures=$((failures + 1))
fi

# ─── Check 3: GET /v1/users/me with the analyst's header ─────────────────────
if curl -sf -H "X-Cockpit-Demo-User: ${ANALYST_ID}" \
        "${API_BASE}/v1/users/me" >/dev/null; then
  ok "cockpit-api /v1/users/me returns the analyst with header"
else
  fail "cockpit-api /v1/users/me failed (analyst id ${ANALYST_ID})" \
       "is the cockpit-api up and Story 1-4 merged? check ${API_BASE}/docs"
  failures=$((failures + 1))
fi

# ─── Check 4: GET /v1/cases returns the seeded case list (Story 2.3 + 2.4) ───
# Story 2.3 added the envelope check; Story 2.4 tightens it to require at
# least one ``case_`` substring (i.e. the seeded fixtures are present).
_cases_response="$(curl -sf -H "X-Cockpit-Demo-User: ${ANALYST_ID}" "${API_BASE}/v1/cases" 2>/dev/null || true)"
if [[ -n "${_cases_response}" ]] \
   && grep -q '"items":' <<<"${_cases_response}" \
   && grep -q '"case_' <<<"${_cases_response}"; then
  ok "cockpit-api /v1/cases returns the seeded case list"
else
  fail "cockpit-api /v1/cases is empty or unreachable" \
       "is the DB seeded? try: make seed (Story 2-4 fixtures)"
  failures=$((failures + 1))
fi

# ─── Check 5: cockpit-ui (Vite dev server) ───────────────────────────────────
if curl -sf "${UI_BASE}" >/dev/null; then
  ok "cockpit-ui is reachable at ${UI_BASE}"
else
  fail "cockpit-ui is not reachable (${UI_BASE})" \
       "is the Vite dev server up? check \`make dev\` output"
  failures=$((failures + 1))
fi

# ─── Check 6: ADK Developer Edition (skipped in CI) ──────────────────────────
if [[ "${CI:-}" == "1" ]]; then
  printf "  ${YELLOW}-${NC} ADK runtime check skipped (CI=1)\n"
else
  if (cd "${ROOT}/apps/agents" && poetry run orchestrate server status >/dev/null 2>&1); then
    ok "ADK Developer Edition reports running"
  else
    fail "ADK Developer Edition not running" \
         "run: make adk-up (one-time docker pull on first run)"
    failures=$((failures + 1))
  fi
fi

echo
if [[ ${failures} -eq 0 ]]; then
  printf "${GREEN}Demo verified — all checks passed.${NC}\n"
  exit 0
else
  printf "${RED}Demo verification failed: %d check(s) did not pass.${NC}\n" "${failures}"
  exit 1
fi

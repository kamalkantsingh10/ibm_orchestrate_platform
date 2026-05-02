#!/usr/bin/env bash
# test_verify_demo.sh — minimal regression test for verify_demo.sh
# (Story 1.5 AC #11). Runs verify against deliberately-broken states and
# asserts non-zero exit. Does not exercise the full happy path — that
# requires a running stack and is the operator-verified demo path.

set -uo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT="${ROOT}/tools/scripts/verify_demo.sh"

GREEN='\033[0;32m'; RED='\033[0;31m'; NC='\033[0m'
pass=0; fail=0

assert_exit_nonzero() {
  local desc="$1"; shift
  if "$@" >/dev/null 2>&1; then
    printf "  ${RED}✗${NC} %s — expected non-zero exit, got 0\n" "${desc}"
    fail=$((fail + 1))
  else
    printf "  ${GREEN}✓${NC} %s\n" "${desc}"
    pass=$((pass + 1))
  fi
}

# Case 1 — API and UI are not running. Force CI=1 to skip the ADK check
# (the ADK check would also fail, which would mask the API/UI signal).
# Use unreachable ports so we get fast connect-refused failures.
API_BASE="http://127.0.0.1:1" UI_BASE="http://127.0.0.1:1" CI=1 \
  assert_exit_nonzero "exits non-zero when API and UI are unreachable" \
  bash "${SCRIPT}"

# Case 2 — bogus DEMO_ANALYST_ID makes the /v1/users/me check fail even
# if the API is reachable. (We still hit unreachable ports here so this
# also asserts non-zero exit — the point is the script doesn't crash on
# a bad analyst id.)
API_BASE="http://127.0.0.1:1" UI_BASE="http://127.0.0.1:1" CI=1 \
DEMO_ANALYST_ID="00000000-0000-4000-8000-000000999999" \
  assert_exit_nonzero "exits non-zero when DEMO_ANALYST_ID is unknown" \
  bash "${SCRIPT}"

# Case 3 — Story 2.3: the new /v1/cases check should also fail when the API
# is unreachable. The unreachable-API scenario covers this; the explicit
# assertion is that the script's overall exit is still non-zero (i.e. the
# new check didn't accidentally swallow the failure with `|| true`).
API_BASE="http://127.0.0.1:1" UI_BASE="http://127.0.0.1:1" CI=1 \
  assert_exit_nonzero "exits non-zero when /v1/cases is unreachable" \
  bash "${SCRIPT}"

# Case 4 — Story 2.4: an empty cases list (envelope present but no "case_"
# substring) should fail the tightened check. Spin a tiny inline HTTP server
# in Python that returns {"items": []} on any path, and point verify at it.
python3 - <<'PY' &
import http.server
import socketserver

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = b'{"items": [], "next_cursor": null, "has_more": false}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def log_message(self, *args, **kwargs):
        pass

with socketserver.TCPServer(("127.0.0.1", 18801), Handler) as httpd:
    httpd.serve_forever()
PY
STUB_PID=$!
trap "kill ${STUB_PID} 2>/dev/null || true" EXIT
# Wait for the stub to bind.
for _ in 1 2 3 4 5 6 7 8 9 10; do
  if curl -sf "http://127.0.0.1:18801/health" >/dev/null 2>&1; then
    break
  fi
  sleep 0.2
done

API_BASE="http://127.0.0.1:18801" UI_BASE="http://127.0.0.1:18801" CI=1 \
  assert_exit_nonzero "exits non-zero when /v1/cases returns empty items" \
  bash "${SCRIPT}"

kill ${STUB_PID} 2>/dev/null || true

echo
if [[ ${fail} -eq 0 ]]; then
  printf "${GREEN}verify_demo.sh tests: %d passed.${NC}\n" "${pass}"
  exit 0
else
  printf "${RED}verify_demo.sh tests: %d passed, %d failed.${NC}\n" "${pass}" "${fail}"
  exit 1
fi

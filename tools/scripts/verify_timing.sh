#!/usr/bin/env bash
# verify_timing.sh — cold-start timing measurement (Story 1.5 AC #8).
#
# Measures wall-clock time of each phase of the bootstrap → migrate → seed →
# verify path and appends a row to cold-start-measurements.md so trends are
# visible across machines and over time.
#
# Does NOT run `make clean` first — the caller is expected to start from a
# realistic state (e.g. fresh clone, or `make clean` if a true cold start
# is desired). This is intentional: forcing `make clean` would destroy
# node_modules / .venv and inflate the timing past what a real fresh-clone
# user would see if they then re-ran.
#
# Usage:  bash tools/scripts/verify_timing.sh

set -uo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
LOG_FILE="${ROOT}/Documentation/implementation-artifacts/cold-start-measurements.md"

machine_id() {
  # Short identifier for the row's "Machine" column. uname-derived; no PII.
  printf "%s/%s" "$(uname -s)" "$(uname -m)"
}

phase() {
  # phase <label> <command...>  →  prints duration in seconds, runs cmd.
  local label="$1"; shift
  local start end
  start=$(date +%s)
  "$@" >/dev/null 2>&1
  end=$(date +%s)
  printf "%s" "$((end - start))"
}

echo ">>> Measuring cold-start timing (this is a measurement, not a clean run)"
echo ">>> If you want a true cold-start measurement, run \`make clean\` first."
echo

cd "${ROOT}"

# Capture each phase. Phases that have already been done in this checkout
# (e.g. node_modules already installed) will be near-zero — that's the point.
t_bootstrap=$(phase bootstrap make bootstrap)
t_migrate=$(phase migrate make migrate)
t_seed=$(phase seed make seed)
# verify needs the dev server up; this measurement skips it (run separately
# with `make verify` against a running stack). Record 0 here.
t_verify=0
t_total=$((t_bootstrap + t_migrate + t_seed + t_verify))

date_str=$(date -u +"%Y-%m-%d %H:%M UTC")
machine=$(machine_id)
notes="bootstrap-only re-measurement (no clean); CI=${CI:-0}; verify=skipped"

# Initialise the log file if missing.
if [[ ! -f "${LOG_FILE}" ]]; then
  cat > "${LOG_FILE}" <<EOF
# Cold-start measurements

Records of \`make verify-timing\` runs. Story 1.5 § AC #10 requires a fresh
clone reach the demo in ≤ 60 minutes. Use this log to spot regressions.

| Date | Machine | Bootstrap (s) | Migrate (s) | Seed (s) | Verify (s) | Total (s) | Notes |
|---|---|---:|---:|---:|---:|---:|---|
EOF
fi

printf "| %s | %s | %d | %d | %d | %d | %d | %s |\n" \
  "${date_str}" "${machine}" "${t_bootstrap}" "${t_migrate}" "${t_seed}" \
  "${t_verify}" "${t_total}" "${notes}" >> "${LOG_FILE}"

echo "Recorded:"
echo "  Bootstrap:  ${t_bootstrap}s"
echo "  Migrate:    ${t_migrate}s"
echo "  Seed:       ${t_seed}s"
echo "  Verify:     ${t_verify}s (skipped — run separately against live stack)"
echo "  Total:      ${t_total}s"
echo "Appended to ${LOG_FILE}"

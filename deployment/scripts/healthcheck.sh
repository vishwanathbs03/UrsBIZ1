#!/usr/bin/env bash
# =============================================================================
# healthcheck.sh — poll the public health endpoints.
#
# Usage:
#   deployment/scripts/healthcheck.sh                       # uses defaults
#   PROXY_URL=https://ursbiz.example.com healthcheck.sh     # public check
#
# The script hits the public URL (defaults to http://localhost:8080)
# and walks the stack: nginx -> frontend -> backend. A failure prints
# a clear, single-line diagnostic. The exit code reflects overall
# health so this script can be wired into an external monitor.
# =============================================================================

set -uo pipefail

PROXY_URL="${PROXY_URL:-http://localhost:8080}"
BACKEND_URL="${BACKEND_URL:-http://localhost:8001}"
TIMEOUT="${HEALTHCHECK_TIMEOUT:-5}"

PASS=0
FAIL=0

check() {
    local name="$1"
    local url="$2"
    local expect="$3"

    local body
    body="$(curl --silent --max-time "${TIMEOUT}" -o - -w '\n%{http_code}' "${url}" 2>/dev/null || true)"
    local code
    code="$(printf '%s' "${body}" | tail -n 1)"
    local payload
    payload="$(printf '%s' "${body}" | sed '$d')"

    if [ "${code}" = "${expect}" ]; then
        echo "[OK]   ${name} (${url}) -> ${code}"
        PASS=$((PASS + 1))
    else
        echo "[FAIL] ${name} (${url}) -> ${code} (expected ${expect})"
        if [ -n "${payload}" ]; then
            echo "       payload: ${payload}"
        fi
        FAIL=$((FAIL + 1))
    fi
}

echo "[healthcheck] proxy=${PROXY_URL} backend=${BACKEND_URL}"

# 1. Public health via the reverse proxy. This is the same path the
#    Docker healthcheck uses, so a green here = a green there.
check "proxy:backend /api/v1/health" "${PROXY_URL}/api/v1/health" "200"

# 2. Direct frontend health via the reverse proxy. Next's standalone
#    server returns 200 for the root and any prerendered page.
check "proxy:frontend /"             "${PROXY_URL}/"              "200"

# 3. Direct backend health (only useful when the host port 8001 is
#    published; usually it's not. Skipped silently on connection
#    refused so this script works against prod too.)
if curl --silent --max-time 2 -o /dev/null "${BACKEND_URL}/api/v1/health" 2>/dev/null; then
    check "backend direct /api/v1/health" "${BACKEND_URL}/api/v1/health" "200"
fi

echo "[healthcheck] pass=${PASS} fail=${FAIL}"

if [ "${FAIL}" -gt 0 ]; then
    exit 1
fi
exit 0

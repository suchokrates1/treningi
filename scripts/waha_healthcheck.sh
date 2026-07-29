#!/bin/bash
# WAHA session health check & auto-restart.
# Designed to run inside Docker Compose (scheduler service).
# Env:
#   WAHA_URL          default http://waha:3000
#   WHATSAPP_SESSION  default default
#   WAHA_API_KEY      required (from compose env_file)

set -u

WAHA_URL="${WAHA_URL:-http://waha:3000}"
SESSION="${WHATSAPP_SESSION:-default}"
API_KEY="${WAHA_API_KEY:-}"
LOCK_FILE="${WAHA_HEALTHCHECK_LOCK:-/tmp/waha-healthcheck.lock}"
LOG_PREFIX="[$(date '+%Y-%m-%d %H:%M:%S')]"

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
    exit 0
fi

log() {
    echo "$LOG_PREFIX $1"
}

if [ -z "$API_KEY" ]; then
    log "ERROR: WAHA_API_KEY not set"
    exit 1
fi

# Optional DNS readiness check (skip if getent missing)
if command -v getent >/dev/null 2>&1; then
    if ! getent hosts web.whatsapp.com >/dev/null 2>&1; then
        log "External DNS not ready; skipping session recovery"
        exit 0
    fi
fi

STATUS=$(curl -sf --max-time 10 \
    -H "X-Api-Key: $API_KEY" \
    "$WAHA_URL/api/sessions/$SESSION" 2>/dev/null | \
    python3 -c "import sys,json; print(json.load(sys.stdin).get('status', 'UNKNOWN'))" 2>/dev/null)

if [ -z "$STATUS" ]; then
    log "WAHA API unreachable; skipping session recovery"
    exit 0
fi

case "$STATUS" in
    WORKING|STARTING|SCAN_QR_CODE|AUTHENTICATING)
        exit 0
        ;;
    STOPPED|FAILED)
        log "Session status: $STATUS; attempting session start"
        ;;
    *)
        log "Session status: $STATUS; leaving unchanged"
        exit 0
        ;;
esac

RESULT=$(curl -sf --max-time 30 \
    -X POST \
    -H "X-Api-Key: $API_KEY" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"$SESSION\"}" \
    "$WAHA_URL/api/sessions/$SESSION/start" 2>&1) || {
    log "Session start request failed: $RESULT"
    exit 1
}

sleep 10
NEW_STATUS=$(curl -sf --max-time 10 \
    -H "X-Api-Key: $API_KEY" \
    "$WAHA_URL/api/sessions/$SESSION" 2>/dev/null | \
    python3 -c "import sys,json; print(json.load(sys.stdin).get('status', 'UNKNOWN'))" 2>/dev/null)

log "Session start requested. Status after 10s: ${NEW_STATUS:-UNKNOWN}"
exit 0

#!/bin/bash
# WAHA session health check & auto-restart script
# Checks if the WhatsApp session is WORKING. If STOPPED, tries to restart it.
# Run via cron every minute: */1 * * * * /home/suchokrates1/treningi/scripts/waha_healthcheck.sh >> /tmp/waha-healthcheck.log 2>&1

set -u

WAHA_URL="http://localhost:3001"
SESSION="default"
ENV_FILE="/home/suchokrates1/treningi/.env"
LOCK_FILE="/tmp/waha-healthcheck.lock"
LOG_PREFIX="[$(date '+%Y-%m-%d %H:%M:%S')]"

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
    exit 0
fi

log() {
    echo "$LOG_PREFIX $1"
}

if [ -f "$ENV_FILE" ]; then
    API_KEY=$(grep -E '^WAHA_API_KEY=' "$ENV_FILE" | cut -d'=' -f2- | tr -d '"' | tr -d "'")
else
    API_KEY=""
fi

if [ -z "$API_KEY" ]; then
    log "ERROR: WAHA_API_KEY not found in $ENV_FILE"
    exit 1
fi

if ! docker ps --format '{{.Names}}' | grep -qx tenis_waha; then
    log "WAHA container not running"
    exit 1
fi

if ! docker exec tenis_waha sh -lc "getent hosts web.whatsapp.com >/dev/null 2>&1"; then
    log "External DNS not ready inside tenis_waha; skipping session recovery"
    exit 0
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

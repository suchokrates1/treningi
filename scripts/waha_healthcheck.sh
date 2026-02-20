#!/bin/bash
# WAHA session health check & auto-restart script
# Checks if the WhatsApp session is WORKING. If STOPPED, tries to restart it.
# Run via cron every 5 minutes: */5 * * * * /home/suchokrates1/treningi/scripts/waha_healthcheck.sh >> /tmp/waha-healthcheck.log 2>&1

WAHA_URL="http://localhost:3001"
API_KEY="blindtenis2026"
SESSION="default"
LOG_PREFIX="[$(date '+%Y-%m-%d %H:%M:%S')]"

# Check if WAHA container is running
if ! docker ps --format '{{.Names}}' | grep -q tenis_waha; then
    echo "$LOG_PREFIX WAHA container not running — Docker should auto-restart it"
    exit 1
fi

# Get session status via API (with timeout)
STATUS=$(curl -sf --max-time 10 \
    -H "X-Api-Key: $API_KEY" \
    "$WAHA_URL/api/sessions/$SESSION" 2>/dev/null | \
    python3 -c "import sys,json; print(json.load(sys.stdin).get('status','UNKNOWN'))" 2>/dev/null)

if [ -z "$STATUS" ]; then
    echo "$LOG_PREFIX WAHA API unreachable — container may be starting up"
    exit 1
fi

if [ "$STATUS" = "WORKING" ]; then
    # All good, silent exit (no log spam)
    exit 0
fi

echo "$LOG_PREFIX Session status: $STATUS — attempting restart..."

# Try to start the session
RESULT=$(curl -sf --max-time 30 \
    -X POST \
    -H "X-Api-Key: $API_KEY" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"$SESSION\"}" \
    "$WAHA_URL/api/sessions/$SESSION/start" 2>&1)

if [ $? -eq 0 ]; then
    echo "$LOG_PREFIX Session restart initiated. Response: $RESULT"
    # Wait and verify
    sleep 15
    NEW_STATUS=$(curl -sf --max-time 10 \
        -H "X-Api-Key: $API_KEY" \
        "$WAHA_URL/api/sessions/$SESSION" 2>/dev/null | \
        python3 -c "import sys,json; print(json.load(sys.stdin).get('status','UNKNOWN'))" 2>/dev/null)
    echo "$LOG_PREFIX After restart, session status: $NEW_STATUS"
    
    if [ "$NEW_STATUS" != "WORKING" ]; then
        echo "$LOG_PREFIX Session still not WORKING — may need manual QR scan or container restart"
        # Last resort: restart the whole container
        echo "$LOG_PREFIX Attempting full container restart..."
        docker restart tenis_waha
        echo "$LOG_PREFIX Container restart initiated"
    fi
else
    echo "$LOG_PREFIX Failed to restart session: $RESULT"
    echo "$LOG_PREFIX Attempting full container restart..."
    docker restart tenis_waha
    echo "$LOG_PREFIX Container restart initiated"
fi

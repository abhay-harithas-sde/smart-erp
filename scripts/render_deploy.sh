#!/usr/bin/env bash
# Trigger a Render deploy and stream logs. Requires RENDER_API_KEY and SERVICE_ID.
set -euo pipefail
: ${RENDER_API_KEY:?Need to set RENDER_API_KEY}
: ${SERVICE_ID:?Need to set SERVICE_ID}
BRANCH=${BRANCH:-main}

echo "Triggering deploy for service $SERVICE_ID (branch $BRANCH)..."
resp=$(curl -s -X POST "https://api.render.com/v1/services/$SERVICE_ID/deploys" \
  -H "Authorization: Bearer $RENDER_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"branch\":\"$BRANCH\"}")

echo "$resp" | jq .
DEPLOY_ID=$(echo "$resp" | jq -r '.id')
if [ -z "$DEPLOY_ID" ] || [ "$DEPLOY_ID" = "null" ]; then
  echo "Failed to create deploy. Response:" >&2
  echo "$resp" >&2
  exit 2
fi

echo "Deploy created: $DEPLOY_ID"

echo "Polling deploy status (press Ctrl+C to stop)..."
while :; do
  status=$(curl -s -H "Authorization: Bearer $RENDER_API_KEY" "https://api.render.com/v1/services/$SERVICE_ID/deploys/$DEPLOY_ID" | jq -r '.status')
  echo "Status: $status"
  if [[ "$status" =~ ^(success|failed|cancelled)$ ]]; then
    break
  fi
  sleep 5
done

# Try fetch logs
echo "Fetching deploy logs (first 5000 chars)"
curl -s -H "Authorization: Bearer $RENDER_API_KEY" "https://api.render.com/v1/deploys/$DEPLOY_ID/logs" | sed -n '1,500p'

echo "Done."

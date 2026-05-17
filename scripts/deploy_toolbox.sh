#!/usr/bin/env bash
# Deploy the MCP Toolbox Cloud Run service with the SQLite seed file baked
# into the image. `toolbox-service/Dockerfile` expects
# `toolbox-service/data/netpulse.sqlite` to exist in its build context; this
# script stages that file from the canonical CSVs, then invokes
# `gcloud run deploy --source toolbox-service`, then cleans the staged copy.
#
# Usage: scripts/deploy_toolbox.sh [REGION]
#   REGION  Cloud Run region (default: asia-southeast2)
#
# Environment overrides:
#   SERVICE_NAME   Cloud Run service name (default: network-toolbox)
set -euo pipefail

cd "$(dirname "$0")/.."

REGION="${1:-asia-southeast2}"
SERVICE_NAME="${SERVICE_NAME:-network-toolbox}"
STAGE_DIR="toolbox-service/data"

echo "[deploy_toolbox] Building local SQLite via scripts/build_sqlite.py"
python3 scripts/build_sqlite.py --recreate

echo "[deploy_toolbox] Staging data/netpulse.sqlite into $STAGE_DIR"
mkdir -p "$STAGE_DIR"
cp data/netpulse.sqlite "$STAGE_DIR/netpulse.sqlite"

# Always clean the staged copy, even on failure — keeps the working tree pure.
cleanup() { rm -rf "$STAGE_DIR"; }
trap cleanup EXIT

echo "[deploy_toolbox] Deploying $SERVICE_NAME to Cloud Run ($REGION)"
gcloud run deploy "$SERVICE_NAME" \
    --source toolbox-service \
    --region "$REGION" \
    --allow-unauthenticated

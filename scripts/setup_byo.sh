#!/usr/bin/env bash
# setup_byo.sh — bootstrap a fresh GCP project against the NetPulse data contract.
#
# What it does:
#   1. Creates the BigQuery dataset + network_events table.
#   2. Creates the AlloyDB call_records + incident_tickets tables.
#   3. With --seed: also loads docs/seed-data/*.csv into all three tables.
#
# Required env (set before running):
#   GOOGLE_CLOUD_PROJECT  — GCP project that owns the BigQuery dataset
#   DATABASE_URL          — postgresql+pg8000://...; the AlloyDB instance must be reachable
#   GOOGLE_APPLICATION_CREDENTIALS  — ADC JSON for BigQuery
#
# Optional env (override the contract defaults):
#   BQ_DATASET            (default: telecom_network)
#   BQ_NETWORK_TABLE      (default: network_events)
#   BQ_LOCATION           (default: US)
#   AL_CALL_TABLE         (default: call_records)
#   AL_TICKET_TABLE       (default: incident_tickets)
#
# Usage:
#   bash scripts/setup_byo.sh           # tables only
#   bash scripts/setup_byo.sh --seed    # tables + seed data (destroys existing rows in seeded tables)
#
# Safe to re-run: table creation is idempotent. --seed always TRUNCATE+RELOADs the seeded tables.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SEED_FLAG=""

if [[ "${1:-}" == "--seed" ]]; then
    SEED_FLAG="--seed"
elif [[ -n "${1:-}" ]]; then
    echo "Unknown argument: $1" >&2
    echo "Usage: $0 [--seed]" >&2
    exit 64
fi

if [[ -z "${GOOGLE_CLOUD_PROJECT:-}" ]]; then
    echo "ERROR: GOOGLE_CLOUD_PROJECT must be exported" >&2
    exit 1
fi
if [[ -z "${DATABASE_URL:-}" ]]; then
    echo "ERROR: DATABASE_URL must be exported" >&2
    exit 1
fi

PYTHON="${PYTHON:-python3}"
if [[ -x "$REPO_ROOT/.venv/bin/python" ]]; then
    PYTHON="$REPO_ROOT/.venv/bin/python"
fi

echo "==> Using Python at: $PYTHON"
echo "==> GOOGLE_CLOUD_PROJECT=$GOOGLE_CLOUD_PROJECT"
echo "==> BQ_DATASET=${BQ_DATASET:-telecom_network} BQ_NETWORK_TABLE=${BQ_NETWORK_TABLE:-network_events}"
echo "==> AL_CALL_TABLE=${AL_CALL_TABLE:-call_records} AL_TICKET_TABLE=${AL_TICKET_TABLE:-incident_tickets}"
echo

echo "==> Step 1/2: BigQuery"
"$PYTHON" "$REPO_ROOT/scripts/setup_bigquery.py" $SEED_FLAG
echo

echo "==> Step 2/2: AlloyDB"
"$PYTHON" "$REPO_ROOT/setup_alloydb.py" $SEED_FLAG
echo

echo "==> Done. NetPulse data layer is ready."
echo "==> Next: deploy the agent + UI per README.md (Deployment section)."

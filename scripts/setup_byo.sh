#!/usr/bin/env bash
# setup_byo.sh — bootstrap a fresh GCP project against the NetPulse data contract.
#
# What it does:
#   1. Creates the BigQuery dataset + network_events table (DAY-partitioned on
#      started_at and clustered by region/severity since Phase 11).
#   2. Creates the AlloyDB call_records + incident_tickets tables.
#   3. With --seed: also loads docs/seed-data/*.csv into all three tables.
#   4. With --nl-setup: ALSO installs the alloydb_ai_nl extension, registers
#      call_records, generates schema context (3-5 min blocking step), and
#      creates the netpulse_nl_reader read-only role used by the MCP Toolbox.
#      Requires NL_READER_PASSWORD to be set in addition to DATABASE_URL.
#
# Required env (set before running):
#   GOOGLE_CLOUD_PROJECT            — GCP project that owns the BigQuery dataset
#   DATABASE_URL                    — postgresql+pg8000://...; AlloyDB superuser DSN
#   GOOGLE_APPLICATION_CREDENTIALS  — ADC JSON for BigQuery
#   NL_READER_PASSWORD              — only when passing --nl-setup; must satisfy
#                                     password.enforce_complexity (>=8 chars,
#                                     upper+lower+digit+special)
#
# Optional env (override the contract defaults):
#   BQ_DATASET            (default: telecom_network)
#   BQ_NETWORK_TABLE      (default: network_events)
#   BQ_LOCATION           (default: US)
#   AL_CALL_TABLE         (default: call_records)
#   AL_TICKET_TABLE       (default: incident_tickets)
#   NL_CONFIG_ID          (default: netpulse_cdr_config)
#   LLM_MODEL_ID          (default: gemini-2.5-flash:generateContent)
#
# Usage:
#   bash scripts/setup_byo.sh                       # tables only
#   bash scripts/setup_byo.sh --seed                # tables + seed data
#   bash scripts/setup_byo.sh --seed --nl-setup     # tables + seed + AlloyDB AI NL2SQL
#
# Safe to re-run: table creation is idempotent. --seed always TRUNCATE+RELOADs
# the seeded tables. --nl-setup is also idempotent — re-running re-applies the
# schema context (3-5 min) and refreshes the reader-role password.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SEED_FLAG=""
NL_SETUP=0

for arg in "$@"; do
    case "$arg" in
        --seed) SEED_FLAG="--seed" ;;
        --nl-setup) NL_SETUP=1 ;;
        *)
            echo "Unknown argument: $arg" >&2
            echo "Usage: $0 [--seed] [--nl-setup]" >&2
            exit 64
            ;;
    esac
done

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

TOTAL_STEPS=2
if [[ $NL_SETUP -eq 1 ]]; then TOTAL_STEPS=3; fi

echo "==> Step 1/$TOTAL_STEPS: BigQuery"
"$PYTHON" "$REPO_ROOT/scripts/setup_bigquery.py" $SEED_FLAG
echo

echo "==> Step 2/$TOTAL_STEPS: AlloyDB tables"
"$PYTHON" "$REPO_ROOT/setup_alloydb.py" $SEED_FLAG
echo

if [[ $NL_SETUP -eq 1 ]]; then
    if [[ -z "${NL_READER_PASSWORD:-}" ]]; then
        echo "ERROR: NL_READER_PASSWORD must be exported when using --nl-setup" >&2
        exit 1
    fi
    echo "==> Step 3/$TOTAL_STEPS: AlloyDB AI NL2SQL (3-5 min for schema context generation)"
    "$PYTHON" "$REPO_ROOT/scripts/setup_alloydb_nl.py"
    echo
fi

echo "==> Done. NetPulse data layer is ready."
echo "==> Next: deploy the agent + UI per README.md (Deployment section)."

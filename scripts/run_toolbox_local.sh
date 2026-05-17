#!/usr/bin/env bash
# Run the genai-toolbox binary locally against the SQLite-backed tools.yaml.
#
# Downloads the v0.23.0 binary on first run (cached at .toolbox/toolbox),
# then launches it bound to 127.0.0.1:5000 with toolbox-service/tools.yaml.
#
# Run from the repo root:
#   ./scripts/run_toolbox_local.sh
#
# Override via env:
#   TOOLBOX_VERSION  (default: 0.23.0)
#   TOOLBOX_PORT     (default: 5000)
#   TOOLBOX_HOST     (default: 127.0.0.1)
#
# Pre-flight:
#   data/netpulse.sqlite must exist. If missing, the script runs
#   `python3 scripts/build_sqlite.py` to materialize it.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

TOOLBOX_VERSION="${TOOLBOX_VERSION:-0.23.0}"
TOOLBOX_PORT="${TOOLBOX_PORT:-5000}"
TOOLBOX_HOST="${TOOLBOX_HOST:-127.0.0.1}"
TOOLBOX_DIR="$REPO_ROOT/.toolbox"
TOOLBOX_BIN="$TOOLBOX_DIR/toolbox"
TOOLS_FILE="$REPO_ROOT/toolbox-service/tools.yaml"
SQLITE_FILE="$REPO_ROOT/data/netpulse.sqlite"

# Detect OS/arch for the download URL.
case "$(uname -s)" in
  Linux)  os="linux"  ;;
  Darwin) os="darwin" ;;
  *) echo "Unsupported OS: $(uname -s)" >&2; exit 1 ;;
esac
case "$(uname -m)" in
  x86_64|amd64) arch="amd64" ;;
  arm64|aarch64) arch="arm64" ;;
  *) echo "Unsupported arch: $(uname -m)" >&2; exit 1 ;;
esac

DOWNLOAD_URL="https://storage.googleapis.com/genai-toolbox/v${TOOLBOX_VERSION}/${os}/${arch}/toolbox"

if [[ ! -x "$TOOLBOX_BIN" ]]; then
  echo "Downloading genai-toolbox v${TOOLBOX_VERSION} (${os}/${arch})..."
  mkdir -p "$TOOLBOX_DIR"
  curl -fL --retry 3 -o "$TOOLBOX_BIN" "$DOWNLOAD_URL"
  chmod +x "$TOOLBOX_BIN"
  echo "Cached at $TOOLBOX_BIN"
fi

if [[ ! -f "$SQLITE_FILE" ]]; then
  echo "SQLite file missing — running scripts/build_sqlite.py..."
  python3 "$REPO_ROOT/scripts/build_sqlite.py"
fi

echo "Starting toolbox on ${TOOLBOX_HOST}:${TOOLBOX_PORT} with $TOOLS_FILE"
exec "$TOOLBOX_BIN" \
  --tools-file "$TOOLS_FILE" \
  --address "$TOOLBOX_HOST" \
  --port "$TOOLBOX_PORT"

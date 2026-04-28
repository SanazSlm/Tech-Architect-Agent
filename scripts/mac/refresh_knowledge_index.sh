#!/usr/bin/env bash
# Weekly (or manual) refresh of the Houram local knowledge index.
# Intended for launchd; reads config from this repo's .env (TECH_ARCHITECT_KNOWLEDGE_CONFIG).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

log() {
  echo "[houram-index $(date '+%Y-%m-%d %H:%M:%S')] $*"
}

log "starting (repo: $REPO_ROOT)"

if [[ -f .venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

CONFIG="${TECH_ARCHITECT_KNOWLEDGE_CONFIG:-}"
if [[ -z "$CONFIG" ]]; then
  log "ERROR: Set TECH_ARCHITECT_KNOWLEDGE_CONFIG in $REPO_ROOT/.env (path to knowledge_sources.yaml)" >&2
  exit 1
fi

if [[ ! -f "$CONFIG" ]]; then
  log "ERROR: Config file not found: $CONFIG" >&2
  exit 1
fi

if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  log "ERROR: OPENAI_API_KEY is not set (add it to $REPO_ROOT/.env)" >&2
  exit 1
fi

if ! command -v tech-architect &>/dev/null; then
  log "ERROR: tech-architect not on PATH. Run: cd \"$REPO_ROOT\" && source .venv/bin/activate && pip install -e ." >&2
  exit 1
fi

tech-architect build-index --config "$CONFIG"
log "finished OK"

#!/usr/bin/env bash
# Install a user LaunchAgent that runs refresh_knowledge_index.sh on a weekly schedule.
# Requires: .env with OPENAI_API_KEY and TECH_ARCHITECT_KNOWLEDGE_CONFIG, and pip install -e .
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LABEL="com.houram.refresh-index"
PLIST_DEST="${HOME}/Library/LaunchAgents/${LABEL}.plist"
SCRIPT_PATH="${REPO_ROOT}/scripts/mac/refresh_knowledge_index.sh"
LOG_DIR="${HOME}/Library/Logs"
STDOUT_LOG="${LOG_DIR}/${LABEL}.out.log"
STDERR_LOG="${LOG_DIR}/${LABEL}.err.log"

# Weekday: 0 or 7 = Sunday (launchd). Hour 0-23, Minute 0-59.
WEEKDAY="${HOURAM_LAUNCH_WEEKDAY:-0}"
HOUR="${HOURAM_LAUNCH_HOUR:-6}"
MINUTE="${HOURAM_LAUNCH_MINUTE:-0}"

xml_escape() {
  local s=$1
  s="${s//&/&amp;}"
  s="${s//</&lt;}"
  s="${s//>/&gt;}"
  printf '%s' "$s"
}

if [[ ! -f "$REPO_ROOT/.env" ]]; then
  echo "Create $REPO_ROOT/.env from .env.example and set OPENAI_API_KEY and TECH_ARCHITECT_KNOWLEDGE_CONFIG." >&2
  exit 1
fi

if [[ ! -f "$SCRIPT_PATH" ]]; then
  echo "Missing script: $SCRIPT_PATH" >&2
  exit 1
fi

chmod +x "$SCRIPT_PATH"

mkdir -p "$LOG_DIR" "${HOME}/Library/LaunchAgents"

ESC_SCRIPT="$(xml_escape "$SCRIPT_PATH")"
ESC_REPO="$(xml_escape "$REPO_ROOT")"
ESC_OUT="$(xml_escape "$STDOUT_LOG")"
ESC_ERR="$(xml_escape "$STDERR_LOG")"

write_plist() {
  cat >"$PLIST_DEST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${LABEL}</string>
    <key>WorkingDirectory</key>
    <string>${ESC_REPO}</string>
    <key>ProgramArguments</key>
    <array>
        <string>${ESC_SCRIPT}</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Weekday</key>
        <integer>${WEEKDAY}</integer>
        <key>Hour</key>
        <integer>${HOUR}</integer>
        <key>Minute</key>
        <integer>${MINUTE}</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>${ESC_OUT}</string>
    <key>StandardErrorPath</key>
    <string>${ESC_ERR}</string>
    <key>ProcessType</key>
    <string>Background</string>
</dict>
</plist>
EOF
}

write_plist

UID_NUM="$(id -u)"
DOMAIN="gui/${UID_NUM}"

if launchctl print "${DOMAIN}/${LABEL}" &>/dev/null; then
  echo "Unloading existing job ${LABEL}..."
  launchctl bootout "${DOMAIN}/${LABEL}" 2>/dev/null || true
fi

echo "Installing ${PLIST_DEST}"
echo "  Program: ${SCRIPT_PATH}"
echo "  Schedule: weekday=${WEEKDAY} (0 or 7=Sun) at ${HOUR}:$(printf '%02d' "${MINUTE}")"
echo "  Logs: ${STDOUT_LOG} / ${STDERR_LOG}"
echo "  Override: HOURAM_LAUNCH_WEEKDAY HOURAM_LAUNCH_HOUR HOURAM_LAUNCH_MINUTE"

launchctl bootstrap "${DOMAIN}" "$PLIST_DEST"

echo "Done. Test once:"
echo "  launchctl kickstart -k ${DOMAIN}/${LABEL}"
echo "Or:"
echo "  \"${SCRIPT_PATH}\""

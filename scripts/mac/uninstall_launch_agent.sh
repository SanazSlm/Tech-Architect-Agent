#!/usr/bin/env bash
# Remove the Houram index refresh LaunchAgent from this Mac.
set -euo pipefail

LABEL="com.houram.refresh-index"
PLIST_DEST="${HOME}/Library/LaunchAgents/${LABEL}.plist"
UID_NUM="$(id -u)"
DOMAIN="gui/${UID_NUM}"

if launchctl print "${DOMAIN}/${LABEL}" &>/dev/null; then
  echo "Booting out ${LABEL}..."
  launchctl bootout "${DOMAIN}/${LABEL}" || true
fi

if [[ -f "$PLIST_DEST" ]]; then
  rm -f "$PLIST_DEST"
  echo "Removed $PLIST_DEST"
else
  echo "No plist at $PLIST_DEST"
fi

echo "Done."

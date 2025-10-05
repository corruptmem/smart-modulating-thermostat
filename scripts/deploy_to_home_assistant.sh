#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: deploy_to_home_assistant.sh [OPTIONS] [CONFIG_PATH]

Options:
  --reload-entry      Reload the modulating_thermostat config entries after syncing
  --reload-core       Call homeassistant.reload_core_config after syncing
  --help, -h          Show this help and exit

Arguments:
  CONFIG_PATH         Home Assistant config directory (local or user@host:/path). If omitted, HA_CONFIG_PATH is used.

Environment variables:
  HA_CONFIG_PATH      Default config path
  HA_BASE_URL         Base URL for Home Assistant API (e.g. http://homeassistant.local:8123)
  HA_TOKEN            Long-lived access token
  HA_RELOAD_DOMAIN    Domain for entry reload (default: modulating_thermostat)
USAGE
}

call_api() {
  local method="$1" endpoint="$2" data="${3:-}" http_body
  if [[ -z "${HA_BASE_URL:-}" || -z "${HA_TOKEN:-}" ]]; then
    echo "[reload] HA_BASE_URL and HA_TOKEN must be set" >&2
    return 1
  fi
  if ! command -v python3 >/dev/null 2>&1; then
    echo "[reload] python3 not available; skipping API call" >&2
    return 1
  fi
  python3 - "$method" "$endpoint" "$data" <<'PY'
import json
import os
import sys
import urllib.error
import urllib.request

method, endpoint, payload = sys.argv[1:4]
base = os.environ["HA_BASE_URL"].rstrip("/")
token = os.environ["HA_TOKEN"]

headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json",
}
if payload:
    data = payload.encode()
else:
    data = None

req = urllib.request.Request(
    f"{base}{endpoint}",
    headers=headers,
    data=data,
    method=method,
)
try:
    with urllib.request.urlopen(req) as resp:
        resp.read()
except urllib.error.URLError as exc:
    print(f"[reload] API call failed: {exc}", file=sys.stderr)
    sys.exit(1)
PY
}

reload_entries() {
  local domain="${HA_RELOAD_DOMAIN:-modulating_thermostat}"
  if [[ -z "${HA_BASE_URL:-}" || -z "${HA_TOKEN:-}" ]]; then
    echo "[reload] HA_BASE_URL and HA_TOKEN must be set for entry reload" >&2
    return 1
  fi
  if ! command -v python3 >/dev/null 2>&1; then
    echo "[reload] python3 not available; skipping entry reload" >&2
    return 1
  fi
  python3 - "$domain" <<'PY'
import json
import os
import sys
import urllib.error
import urllib.request

domain = sys.argv[1]
base = os.environ["HA_BASE_URL"].rstrip("/")
token = os.environ["HA_TOKEN"]
headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json",
}

entries_req = urllib.request.Request(
    f"{base}/api/config/config_entries/entry",
    headers=headers,
)
try:
    with urllib.request.urlopen(entries_req) as resp:
        entries = json.load(resp)
except urllib.error.URLError as exc:
    print(f"[reload] failed to list config entries: {exc}", file=sys.stderr)
    sys.exit(1)

filtered = [entry for entry in entries if entry.get("domain") == domain]
if not filtered:
    print(f"[reload] no entries found for domain '{domain}'", file=sys.stderr)
    sys.exit(1)

for entry in filtered:
    entry_id = entry["entry_id"]
    title = entry.get("title", "<unknown>")
    print(f"[reload] reloading config entry '{title}' ({entry_id})")
    reload_req = urllib.request.Request(
        f"{base}/api/config/config_entries/entry/{entry_id}/reload",
        headers=headers,
        data=b"{}",
        method="POST",
    )
    try:
        urllib.request.urlopen(reload_req).read()
    except urllib.error.URLError as exc:
        print(f"[reload] failed to reload entry {entry_id}: {exc}", file=sys.stderr)
        sys.exit(1)
print("[reload] entry reload completed")
PY
}

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
SRC_DIR="${REPO_ROOT}/custom_components/modulating_thermostat"
if [[ ! -d "${SRC_DIR}" ]]; then
  echo "Error: source directory '${SRC_DIR}' missing" >&2
  exit 1
fi

RELOAD_ENTRY=false
RELOAD_CORE=false
TARGET_PATH=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --reload-entry)
      RELOAD_ENTRY=true
      shift
      ;;
    --reload-core)
      RELOAD_CORE=true
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    --*)
      echo "Unknown option: $1" >&2
      usage
      exit 1
      ;;
    *)
      if [[ -n "${TARGET_PATH}" ]]; then
        echo "Multiple target paths provided" >&2
        usage
        exit 1
      fi
      TARGET_PATH="$1"
      shift
      ;;
  esac
done

if [[ -z "${TARGET_PATH}" ]]; then
  TARGET_PATH="${HA_CONFIG_PATH:-}"
fi

if [[ -z "${TARGET_PATH}" ]]; then
  echo "Error: no config path provided. Use argument or HA_CONFIG_PATH." >&2
  usage
  exit 1
fi

sync_local() {
  local dest_root="$1"
  local dest_dir="${dest_root%/}/custom_components/modulating_thermostat"
  echo "[deploy] syncing locally to ${dest_dir}"
  rm -rf "${dest_dir}"
  mkdir -p "${dest_dir}"
  if command -v rsync >/dev/null 2>&1; then
    rsync -a "${SRC_DIR}/" "${dest_dir}/"
  else
    if cp -a "${SRC_DIR}/" "${dest_dir}/" 2>/dev/null; then
      :
    else
      cp -R "${SRC_DIR}/." "${dest_dir}/"
    fi
  fi
}

sync_remote() {
  local ssh_target="$1"
  local remote_root="$2"
  local remote_dir="${remote_root%/}/custom_components/modulating_thermostat"
  echo "[deploy] syncing remotely to ${ssh_target}:${remote_dir}"
  ssh "${ssh_target}" "rm -rf '"${remote_dir}"' && mkdir -p '"${remote_dir}"'"
  tar -C "${SRC_DIR}" -czf - . | ssh "${ssh_target}" "tar -xzf - -C '"${remote_dir}"'"
}

if [[ "${TARGET_PATH}" == *:* ]]; then
  DEST_HOST="${TARGET_PATH%%:*}"
  DEST_PATH="${TARGET_PATH#*:}"
  sync_remote "${DEST_HOST}" "${DEST_PATH}"
else
  sync_local "${TARGET_PATH}"
fi

if [[ "${RELOAD_CORE}" == true ]]; then
  echo "[reload] calling homeassistant.reload_core_config"
  call_api POST "/api/services/homeassistant/reload_core_config" "{}" || echo "[reload] core reload failed"
fi

if [[ "${RELOAD_ENTRY}" == true ]]; then
  reload_entries || echo "[reload] entry reload skipped"
fi

echo "[deploy] done"

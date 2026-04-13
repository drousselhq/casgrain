#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT_DIR="$ROOT_DIR/fixtures/ios-smoke/CasgrainSmoke.xcodeproj"
SCHEME="CasgrainSmoke"
ARTIFACT_DIR="${ARTIFACT_DIR:-$ROOT_DIR/artifacts/ios-smoke}"
DERIVED_DATA="$ARTIFACT_DIR/DerivedData"
RESULT_BUNDLE="$ARTIFACT_DIR/CasgrainSmoke.xcresult"
LOG_FILE="$ARTIFACT_DIR/xcodebuild.log"
SIM_INFO_FILE="$ARTIFACT_DIR/simulator.json"

require_macos_xcode() {
  if [[ "$(uname -s)" != "Darwin" ]]; then
    echo "scripts/ios_smoke.sh requires macOS with Xcode and iOS Simulator support." >&2
    exit 1
  fi

  local missing=()
  for tool in python3 xcodebuild xcrun; do
    if ! command -v "$tool" >/dev/null 2>&1; then
      missing+=("$tool")
    fi
  done

  if (( ${#missing[@]} > 0 )); then
    echo "Missing required tool(s): ${missing[*]}" >&2
    exit 1
  fi
}

mkdir -p "$ARTIFACT_DIR"
require_macos_xcode

choose_simulator() {
  python3 - <<'PY'
import json
import re
import subprocess

runtimes = json.loads(subprocess.check_output(["xcrun", "simctl", "list", "runtimes", "-j"], text=True))["runtimes"]
devices = json.loads(subprocess.check_output(["xcrun", "simctl", "list", "devices", "available", "-j"], text=True))["devices"]

available_ios = [
    runtime for runtime in runtimes
    if runtime.get("isAvailable") and runtime.get("name", "").startswith("iOS ")
]
if not available_ios:
    raise SystemExit("No available iOS runtime found")

def version_key(name: str):
    match = re.search(r"iOS (\d+(?:\.\d+)*)", name)
    if not match:
        return ()
    return tuple(int(part) for part in match.group(1).split("."))

available_ios.sort(key=lambda runtime: version_key(runtime.get("name", "")))
runtime = available_ios[-1]
candidates = [
    device for device in devices.get(runtime["identifier"], [])
    if device.get("isAvailable") and device.get("name", "").startswith("iPhone")
]
if not candidates:
    candidates = [
        device for device in devices.get(runtime["identifier"], [])
        if device.get("isAvailable")
    ]
if not candidates:
    raise SystemExit(f"No available simulator devices found for {runtime['identifier']}")

candidates.sort(key=lambda device: device.get("name", ""))
selected = candidates[0]
print(json.dumps({
    "runtime": runtime["identifier"],
    "runtime_name": runtime.get("name"),
    "device_name": selected.get("name"),
    "udid": selected["udid"],
}, indent=2))
PY
}

SIM_JSON="$(choose_simulator)"
printf '%s\n' "$SIM_JSON" | tee "$SIM_INFO_FILE"
SIM_UDID="$(python3 - "$SIM_INFO_FILE" <<'PY'
import json
import sys
from pathlib import Path
print(json.loads(Path(sys.argv[1]).read_text())["udid"])
PY
)"
trap 'xcrun simctl shutdown "$SIM_UDID" >/dev/null 2>&1 || true' EXIT

xcrun simctl boot "$SIM_UDID" >/dev/null 2>&1 || true
xcrun simctl bootstatus "$SIM_UDID" -b

xcodebuild test \
  -project "$PROJECT_DIR" \
  -scheme "$SCHEME" \
  -destination "platform=iOS Simulator,id=$SIM_UDID" \
  -only-testing:CasgrainSmokeUITests/CasgrainSmokeUITests/testTapChangesVisibleStateAndCapturesScreenshot \
  -resultBundlePath "$RESULT_BUNDLE" \
  -derivedDataPath "$DERIVED_DATA" \
  CODE_SIGNING_ALLOWED=NO \
  CODE_SIGNING_REQUIRED=NO \
  | tee "$LOG_FILE"

echo "$RESULT_BUNDLE"

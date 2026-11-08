#!/usr/bin/env bash
set -euo pipefail
WORK_ROOT="/home/runner/work"
PACKAGE="com.pbl.remake"

# Bound every adb call: an unresponsive emulator/adb server must fail with
# diagnostics instead of keeping the Actions step alive until its outer timeout.
adb() {
  local limit=30
  case "${1:-}" in
    wait-for-device) limit=180 ;;
    install) limit=300 ;;       # A first install of a 56 MB Godot APK can be slow on a cold emulator.
    logcat|exec-out) limit=60 ;;
    shell)
      case "${2:-}" in
        monkey) limit=90 ;;
        settings|dumpsys) limit=60 ;;
      esac
      ;;
  esac
  timeout --foreground "${limit}s" adb "$@"
}
APK="$(find "$WORK_ROOT" -type f -path '*/Pokemon_Battle_Lab_Remake/build/Pokemon_Battle_Lab_Remake-debug.apk' -print -quit)"
if [[ -z "$APK" || ! -s "$APK" ]]; then
  echo "::error::Built APK was not found under $WORK_ROOT"
  find "$WORK_ROOT" -maxdepth 5 -type f -name '*.apk' -print || true
  exit 1
fi
OUT="$(dirname "$APK")"
# Preserve evidence even when the emulator smoke test is killed by its timeout.
collect_startup_diagnostics() {
  local status=$?
  mkdir -p "$OUT"
  echo "Collecting logcat, screenshot, ANR, CPU and app memory diagnostics..."
  adb logcat -d -v threadtime > "$OUT/android-startup-logcat.txt" 2>&1 || true
  adb exec-out screencap -p > "$OUT/android-startup.png" 2>/dev/null || true
  adb shell dumpsys activity lastanr > "$OUT/android-last-anr.txt" 2>&1 || true
  adb shell dumpsys cpuinfo > "$OUT/android-cpuinfo.txt" 2>&1 || true
  adb shell dumpsys meminfo "$PACKAGE" > "$OUT/android-app-meminfo.txt" 2>&1 || true
  echo "Collected Android startup diagnostics (exit=$status)."
}
trap collect_startup_diagnostics EXIT
trap 'exit 124' TERM INT
echo "Using APK: $APK"

echo "Waiting for emulator device..."
adb wait-for-device
echo "ADB transport detected; waiting for emulator to become fully online."
DEVICE_STATE=""
for attempt in $(seq 1 90); do
  DEVICE_STATE="$(adb devices | awk '$1 ~ /^emulator-/ {print $2; exit}' || true)"
  [[ "$DEVICE_STATE" == "device" ]] && break
  if (( attempt % 10 == 0 )); then
    echo "Emulator ADB state is '${DEVICE_STATE:-missing}' (attempt $attempt/90)."
  fi
  sleep 2
done
if [[ "$DEVICE_STATE" != "device" ]]; then
  adb devices || true
  echo "::error::Emulator ADB transport did not become online within 180 seconds."
  exit 1
fi
echo "Emulator is online; waiting for Android boot completion."
BOOT_COMPLETED=""
for attempt in $(seq 1 150); do
  BOOT_COMPLETED="$(adb shell getprop sys.boot_completed 2>/dev/null | tr -d '\r' || true)"
  [[ "$BOOT_COMPLETED" == "1" ]] && break
  sleep 2
done
if [[ "$BOOT_COMPLETED" != "1" ]]; then
  echo "::error::Android emulator did not finish booting within 300 seconds."
  exit 1
fi

# Acknowledge immersive-mode education before the first landscape launch.
adb shell settings put secure immersive_mode_confirmations confirmed || true
adb shell settings put global window_animation_scale 0 || true
adb shell settings put global transition_animation_scale 0 || true
adb shell settings put global animator_duration_scale 0 || true
# Let first-boot package manager, telephony and SystemUI work settle.
sleep 45
echo "Clearing logcat before APK installation..."
adb logcat -c
echo "Installing APK (up to 300 seconds on a cold emulator)..."
adb install -r "$APK"
echo "APK installation completed; verifying package and launching app."
adb shell pm path "$PACKAGE" | grep -q '^package:'
adb shell monkey -p "$PACKAGE" 1

# Android may display system ANR and immersive education dialogs on first boot.
# Find their actual button bounds instead of sending BACK (which does not
# dismiss the "Process system isn't responding" dialog).
dismiss_blocking_dialogs() {
  local pass ui_xml click
  for pass in $(seq 1 5); do
    timeout 12s adb shell uiautomator dump /sdcard/window.xml >/dev/null 2>&1 || {
      sleep 1
      continue
    }
    ui_xml="$(adb shell cat /sdcard/window.xml 2>/dev/null | tr -d '\r' || true)"
    click="$(printf '%s' "$ui_xml" | python3 -c '
import re, sys, xml.etree.ElementTree as ET
raw = sys.stdin.read()
try:
    root = ET.fromstring(raw)
except ET.ParseError:
    raise SystemExit(0)
wanted = ("GOT IT", "Wait", "Wait for app")
for label in wanted:
    for node in root.iter():
        if node.attrib.get("text", "").strip().casefold() == label.casefold():
            match = re.search(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", node.attrib.get("bounds", ""))
            if match:
                x1, y1, x2, y2 = map(int, match.groups())
                print(f"{label}|{(x1+x2)//2}|{(y1+y2)//2}")
                raise SystemExit(0)
' )"
    [[ -z "$click" ]] && return 0
    IFS='|' read -r label x y <<< "$click"
    echo "Dismissing Android system prompt: $label at ($x,$y)"
    adb shell input tap "$x" "$y" || true
    sleep 4
  done
}

APP_PID=""
ACTIVITY_READY=""
for attempt in $(seq 1 120); do
  APP_PID="$(adb shell pidof "$PACKAGE" 2>/dev/null | tr -d '\r' || true)"
  if [[ -n "$APP_PID" ]] && adb shell dumpsys activity activities 2>/dev/null | grep -E "mResumedActivity.*$PACKAGE|topResumedActivity=.*$PACKAGE" >/dev/null; then
    ACTIVITY_READY="yes"
    break
  fi
  # A system ANR dialog can steal foreground focus before Godot's activity
  # becomes resumed. Dismiss it while waiting, not only after readiness.
  if (( attempt % 10 == 0 )); then
    echo "Foreground activity not ready (attempt $attempt); checking for Android system dialogs."
    dismiss_blocking_dialogs
  fi
  sleep 1
done
if [[ -z "$APP_PID" || -z "$ACTIVITY_READY" ]]; then
  adb logcat -d -v threadtime > "$OUT/android-startup-logcat.txt"
  echo "::error::$PACKAGE did not reach a resumed foreground activity within 120 seconds."
  grep -E "$PACKAGE|ANR in|FATAL EXCEPTION|Fatal signal" "$OUT/android-startup-logcat.txt" | tail -n 120 || true
  exit 1
fi

# Let Godot's renderer initialize after Android has resumed the activity.
sleep 35
dismiss_blocking_dialogs
timeout --foreground 90s python3 -m pip install --user --disable-pip-version-check --retries 1 --timeout 10 pillow
SCREEN_OK=""
for attempt in $(seq 1 10); do
  adb exec-out screencap -p > "$OUT/android-startup.png"
  if python3 - "$OUT/android-startup.png" <<'PY'
from PIL import Image
import sys
image = Image.open(sys.argv[1]).convert("RGB")
pixels = list(image.getdata())
green = sum(1 for p in pixels if all(abs(p[i] - (183, 201, 154)[i]) <= 12 for i in range(3)))
colors = len(set(pixels))
print(f"Startup screenshot: {image.size}, unique_colors={colors}, GBA_background_pixels={green}")
sys.exit(0 if green >= 500 and colors >= 30 else 2)
PY
  then
    SCREEN_OK="yes"
    break
  fi
  echo "Game background not visible yet; checking for a blocking Android prompt before retry $attempt."
  dismiss_blocking_dialogs
  sleep 6
done

adb logcat -d -v threadtime > "$OUT/android-startup-logcat.txt"
if [[ -z "$SCREEN_OK" ]]; then
  echo "::error::The game background did not render visibly after 10 screenshot attempts."
  grep -E "$PACKAGE|ANR in|FATAL EXCEPTION|Fatal signal|Process system" "$OUT/android-startup-logcat.txt" | tail -n 160 || true
  exit 1
fi

APP_PID_AFTER="$(adb shell pidof "$PACKAGE" 2>/dev/null | tr -d '\r' || true)"
if [[ -z "$APP_PID_AFTER" ]]; then
  echo "::error::The game process exited after rendering its startup screen."
  exit 1
fi
if ! adb shell dumpsys activity activities 2>/dev/null | grep -E "mResumedActivity.*$PACKAGE|topResumedActivity=.*$PACKAGE" >/dev/null; then
  echo "::error::The game is no longer the resumed foreground activity."
  exit 1
fi
MAIN_PID="${APP_PID_AFTER%% *}"
if grep -E "FATAL EXCEPTION.*$PACKAGE|Process: $PACKAGE([[:space:]]|$)|Fatal signal [0-9]+ .*pid $MAIN_PID" "$OUT/android-startup-logcat.txt"; then
  echo "::error::Android reported a fatal crash in $PACKAGE."
  exit 1
fi
echo "Android install/launch/render smoke test passed: pid=$APP_PID_AFTER, foreground activity=$PACKAGE"

#!/usr/bin/env bash
set -euo pipefail
WORK_ROOT="/home/runner/work"
PACKAGE="com.pbl.remake"
APK="$(find "$WORK_ROOT" -type f -path '*/Pokemon_Battle_Lab_Remake/build/Pokemon_Battle_Lab_Remake-debug.apk' -print -quit)"
if [[ -z "$APK" || ! -s "$APK" ]]; then
  echo "::error::Built APK was not found under $WORK_ROOT"
  find "$WORK_ROOT" -maxdepth 5 -type f -name '*.apk' -print || true
  exit 1
fi
OUT="$(dirname "$APK")"
echo "Using APK: $APK"

# Allow Android system services to settle before installing the app.
adb wait-for-device
BOOT_COMPLETED=""
for attempt in $(seq 1 120); do
  BOOT_COMPLETED="$(adb shell getprop sys.boot_completed 2>/dev/null | tr -d '\r' || true)"
  [[ "$BOOT_COMPLETED" == "1" ]] && break
  sleep 2
done
if [[ "$BOOT_COMPLETED" != "1" ]]; then
  echo "::error::Android emulator did not finish booting within 240 seconds."
  exit 1
fi
sleep 30
adb logcat -c
adb install -r "$APK"
adb shell pm path "$PACKAGE" | grep -q '^package:'
adb shell monkey -p "$PACKAGE" 1

# Godot can need substantially longer than 8 seconds on a cold API 34 emulator.
APP_PID=""
ACTIVITY_READY=""
for attempt in $(seq 1 90); do
  APP_PID="$(adb shell pidof "$PACKAGE" | tr -d '\r' || true)"
  if [[ -n "$APP_PID" ]] && adb shell dumpsys activity activities 2>/dev/null | grep -E "mResumedActivity.*$PACKAGE|topResumedActivity=.*$PACKAGE" >/dev/null; then
    ACTIVITY_READY="yes"
    break
  fi
  sleep 1
done
adb logcat -d -v threadtime > "$OUT/android-startup-logcat.txt"
if [[ -z "$APP_PID" || -z "$ACTIVITY_READY" ]]; then
  echo "::error::$PACKAGE did not reach a resumed foreground activity within 90 seconds."
  grep -E "$PACKAGE|ANR in|FATAL EXCEPTION|Fatal signal" "$OUT/android-startup-logcat.txt" | tail -n 100 || true
  exit 1
fi

sleep 8
python3 -m pip install --user pillow
adb exec-out screencap -p > "$OUT/android-startup.png"
set +e
python3 - "$OUT/android-startup.png" <<'PY'
from PIL import Image
import sys
image = Image.open(sys.argv[1]).convert("RGB")
pixels = list(image.getdata())
green = sum(1 for p in pixels if all(abs(p[i] - (183, 201, 154)[i]) <= 12 for i in range(3)))
colors = len(set(pixels))
print(f"Startup screenshot: {image.size}, unique_colors={colors}, GBA_background_pixels={green}")
sys.exit(0 if green >= 500 and colors >= 30 else 2)
PY
SCREEN_RESULT=$?
set -e
if [[ "$SCREEN_RESULT" -eq 2 ]]; then
  echo "Initial screenshot appears obscured; dismissing a possible unrelated emulator system dialog and retrying."
  adb shell input keyevent 4 || true
  sleep 5
  adb exec-out screencap -p > "$OUT/android-startup.png"
  python3 - "$OUT/android-startup.png" <<'PY'
from PIL import Image
import sys
image = Image.open(sys.argv[1]).convert("RGB")
pixels = list(image.getdata())
green = sum(1 for p in pixels if all(abs(p[i] - (183, 201, 154)[i]) <= 12 for i in range(3)))
colors = len(set(pixels))
print(f"Retry screenshot: {image.size}, unique_colors={colors}, GBA_background_pixels={green}")
if green < 500 or colors < 30:
    print("::error::The game UI is still obscured or failed to render.")
    sys.exit(1)
PY
elif [[ "$SCREEN_RESULT" -ne 0 ]]; then
  exit "$SCREEN_RESULT"
fi

adb logcat -d -v threadtime > "$OUT/android-startup-logcat.txt"
# Ignore fatal events from unrelated Android emulator services.
if grep -E "Process: $PACKAGE([[:space:]]|$)|Fatal signal [0-9]+ \\(SIG[^)]*\\).*$PACKAGE" "$OUT/android-startup-logcat.txt"; then
  echo "::error::Android reported a fatal crash in $PACKAGE."
  exit 1
fi
echo "Android install/launch smoke test passed: pid=$APP_PID, foreground activity=$PACKAGE"

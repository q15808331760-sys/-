#!/usr/bin/env bash
set -euo pipefail

WORK_ROOT="/home/runner/work"
APK="$(find "$WORK_ROOT" -type f -path '*/Pokemon_Battle_Lab_Remake/build/Pokemon_Battle_Lab_Remake-debug.apk' -print -quit)"
if [[ -z "$APK" || ! -s "$APK" ]]; then
  echo "::error::Built APK was not found under $WORK_ROOT"
  find "$WORK_ROOT" -maxdepth 5 -type f -name '*.apk' -print || true
  exit 1
fi
OUT="$(dirname "$APK")"
echo "Using APK: $APK"
adb logcat -c
adb install -r "$APK"
adb shell monkey -p com.pbl.remake 1
sleep 8
adb exec-out screencap -p > "$OUT/android-startup.png"
adb logcat -d -v threadtime > "$OUT/android-startup-logcat.txt"
python3 -m pip install --user pillow
python3 - "$OUT/android-startup.png" <<'PY'
from PIL import Image
import sys

image = Image.open(sys.argv[1]).convert("RGB")
pixels = list(image.getdata())
gba_green = (183, 201, 154)
green_pixels = sum(
    1 for pixel in pixels
    if all(abs(pixel[channel] - gba_green[channel]) <= 12 for channel in range(3))
)
unique_colors = len(set(pixels))
print(f"Startup screenshot: {image.size}, unique_colors={unique_colors}, GBA_background_pixels={green_pixels}")
if green_pixels < 500 or unique_colors < 30:
    print("::error::The main UI did not render its expected GBA background; see startup logcat.")
    sys.exit(1)
PY

#!/usr/bin/env bash
# Native (arm64) VideOCR runner — extracts the Chinese hardcoded-subtitle line
# into an SRT using PaddleOCR PP-OCRv5 server models.
#
# Usage:  ./ocr_cn.sh <video> <output.srt> [crop_y] [crop_height] [time_start] [time_end]
# Example:./ocr_cn.sh test/test.mp4 test/test_cn.srt 600 72
#
# Tune crop_y/crop_height to the Chinese line's pixel band for your video
# (defaults below are calibrated for the 1280x720 sample).

set -euo pipefail
cd "$(dirname "$0")"

VIDEO="${1:?need video path}"
OUT="${2:?need output srt path}"
CROP_Y="${3:-600}"
CROP_H="${4:-72}"
TSTART="${5:-0:00}"
TEND="${6:-}"

ARGS=(
  --video_path "$VIDEO"
  --output "$OUT"
  --lang ch
  --use_server_model true
  --crop_x 0 --crop_y "$CROP_Y" --crop_width 1280 --crop_height "$CROP_H"
  --frames_to_skip 3
  --time_start "$TSTART"
)
[ -n "$TEND" ] && ARGS+=(--time_end "$TEND")

conda run -n videocr --no-capture-output python CLI/videocr_cli.py "${ARGS[@]}"

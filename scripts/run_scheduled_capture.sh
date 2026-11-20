#!/bin/bash
# Daily results capture, run by launchd (deploy/launchd/). One observation per UTC day.
#
# Runs scripts/capture_daily.py from this checkout with its own virtualenv, then writes
# the interim scorecard for the same UTC day. It commits and pushes nothing: the capture
# index (reports/captures/), the scorecard and any new attestation rows are left in the
# working tree for the operator to review and commit.
#
# Exit status: 0 captured (or the day's observation already existed), 1 captured with
# at least one failed state (see the log), anything else means nothing was captured.
set -u
REPO="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="${HOME}/Library/Logs/elections-capture"
mkdir -p "$LOG_DIR"
DAY="$(date -u +%F)"
LOG="$LOG_DIR/capture_${DAY}.log"
SLOT="data/raw/source=state_canvass/dataset=us_house_2026/snapshot=${DAY}.csv"
cd "$REPO" || exit 3
{
  echo "=== $(date -u +%FT%TZ) scheduled capture; branch $(git rev-parse --abbrev-ref HEAD) @ $(git rev-parse --short HEAD)"
  if [ ! -x .venv/bin/python ] || [ ! -f scripts/capture_daily.py ]; then
    echo "missing .venv or scripts/capture_daily.py in $REPO; nothing captured"
    exit 3
  fi
  if [ -f "$SLOT" ]; then
    echo "the ${DAY} UTC observation already exists; nothing to do"
    exit 0
  fi
  .venv/bin/python scripts/capture_daily.py
  status=$?
  echo "capture exit status: $status"
  if [ -f "$SLOT" ] && [ ! -f "reports/scorecards/scorecard_asof_${DAY}.json" ]; then
    .venv/bin/python scripts/interim_scorecard.py --as-of "$DAY" || echo "scorecard not written"
  fi
  exit "$status"
} >>"$LOG" 2>&1

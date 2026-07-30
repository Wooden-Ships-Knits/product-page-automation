#!/bin/sh
# Hourly fetch loop for the Docker `fetch` service.
# Runs cron_fetch.py once an hour, but ONLY during the local-time window
# [FETCH_START_HOUR .. FETCH_END_HOUR] inclusive. Local time = the TZ env var.
#
# Env:
#   TZ               timezone for the window (e.g. Asia/Jakarta). Default: container tz.
#   FETCH_START_HOUR first hour to run (0-23). Default 8.
#   FETCH_END_HOUR   last hour to run  (0-23). Default 20.
#   PPA_FETCH_LOG    log file (shared volume). Default /data/logs/cron_fetch.log.
#
# Note: uses `sleep 3600`, so runs land ~hourly but not exactly on :00. For exact
# on-the-hour scheduling, use supercronic with `0 8-20 * * *` instead (see README).

LOG="${PPA_FETCH_LOG:-/data/logs/cron_fetch.log}"
START="${FETCH_START_HOUR:-8}"
END="${FETCH_END_HOUR:-20}"

mkdir -p "$(dirname "$LOG")"
echo "===== fetch loop started (window ${START}-${END}, TZ=${TZ:-container-default}) =====" >> "$LOG"

while true; do
  H=$(date +%-H)   # current hour, no leading zero, in $TZ
  if [ "$H" -ge "$START" ] && [ "$H" -le "$END" ]; then
    echo "----- fetch $(date '+%Y-%m-%d %H:%M:%S %Z') -----" >> "$LOG"
    python cron_fetch.py >> "$LOG" 2>&1   # errors are logged; loop keeps going
  fi
  sleep 3600
done

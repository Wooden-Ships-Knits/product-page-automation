#!/bin/sh
# Nightly fetch loop for the Docker `fetch` service.
# Sleeps until the next FETCH_AT (local time = the TZ env var), runs cron_fetch.py once,
# and repeats. The per-product PP SY LIST sync is done in real time by webhook_receiver.py;
# this full snapshot is only the safety net for missed webhooks (and refreshes Links storage).
#
# Env:
#   TZ            timezone for FETCH_AT (e.g. Asia/Makassar). Default: container tz.
#   FETCH_AT      time of day to run, HH:MM. Default 00:00.
#   PPA_FETCH_LOG log file (shared volume). Default /data/logs/cron_fetch.log.
#
# Does NOT run at container start — only at FETCH_AT. For a one-off run:
#   docker compose exec fetch python cron_fetch.py

LOG="${PPA_FETCH_LOG:-/data/logs/cron_fetch.log}"
AT="${FETCH_AT:-00:00}"

mkdir -p "$(dirname "$LOG")"
echo "===== nightly fetch loop started (daily at ${AT}, TZ=${TZ:-container-default}) =====" >> "$LOG"

while true; do
  NOW=$(date +%s)
  NEXT=$(date -d "today ${AT}" +%s)
  if [ "$NEXT" -le "$NOW" ]; then
    NEXT=$(date -d "tomorrow ${AT}" +%s)
  fi
  echo "next fetch: $(date -d "@${NEXT}" '+%Y-%m-%d %H:%M %Z')" >> "$LOG"
  sleep $((NEXT - NOW))

  echo "----- fetch $(date '+%Y-%m-%d %H:%M:%S %Z') -----" >> "$LOG"
  python cron_fetch.py >> "$LOG" 2>&1   # errors are logged; loop keeps going
  sleep 60                              # never run twice for the same FETCH_AT
done

#!/bin/sh
# Healthy when the last run succeeded and the last good one is recent enough. Waits
# for the first run after start, so `docker compose up --wait` reports its result.
[ -n "${SCHEDULE:-}" ] || exit 0
data=${MARQUEEFIN_DATA:-/data}
state=${MARQUEEFIN_STATE:-/tmp}
result=$state/run.result
if [ -f "$state/first-run" ]; then
  while [ ! -f "$result" ]; do sleep 2; done
fi
if [ -f "$result" ]; then
  [ "$(cat "$result")" = ok ] || exit 1
  mark=$data/.last-success
else
  mark=$state/started  # RUN_ON_START=0 and nothing has run yet
fi
minutes=$(( ${HEALTH_MAX_AGE_HOURS:-26} * 60 ))
[ -n "$(find "$mark" -mmin "-$minutes" 2>/dev/null)" ]

#!/bin/sh
# Without SCHEDULE: one run, then exit. With it: once at start (RUN_ON_START), then
# supercronic, which never overlaps runs.
set -eu
# Overridden by tests/test_docker_scripts.py
app=${MARQUEEFIN_APP:-/app}
state=${MARQUEEFIN_STATE:-/tmp}

if [ -z "${SCHEDULE:-}" ]; then
  exec "$app/docker/run.sh" "$@"
fi

touch "$state/started"  # the health check's clock until the first good run
printf '%s %s/docker/run.sh\n' "$SCHEDULE" "$app" > "$state/crontab"
echo "⏰ Scheduled: '$SCHEDULE' (${TZ:-UTC})"
if [ "${RUN_ON_START:-1}" = "1" ]; then
  touch "$state/first-run"  # the health check waits for this run's result
  "$app/docker/run.sh" || echo "🔁 First run failed; trying again on schedule." >&2
fi
# tini is PID 1 and reaps
exec supercronic -passthrough-logs -no-reap "$state/crontab"

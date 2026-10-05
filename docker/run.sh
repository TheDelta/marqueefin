#!/bin/sh
# One run: export, upload (UPLOAD_HOST), report failures and skips to Gotify
set -u
# Overridden by tests/test_docker_scripts.py
app=${MARQUEEFIN_APP:-/app}
data=${MARQUEEFIN_DATA:-/data}
state=${MARQUEEFIN_STATE:-/tmp}
cd "$data" || exit 1
log=$state/run.log
: > "$log"

# Logs to the container and $log; returns the step's status, not tee's
step() {
  { "$@"; echo $? > "$state/step.rc"; } 2>&1 | tee -a "$log"
  return "$(cat "$state/step.rc")"
}

notify() {  # notify <title> <priority>: the end of the log to Gotify
  title=$1 priority=$2
  tail -n 25 "$log" | python "$app/docker/notify.py" "$title" "$priority" || true
  return 0
}

fail() {
  reason=$1
  echo "❌ Run failed: $reason" >&2
  echo failed > "$state/run.result"  # read by the health check
  notify "Marqueefin: $reason" 8
  exit 1
}

# shellcheck disable=SC2086  # EXPORT_ARGS is meant to split into separate flags
step python "$app/export.py" ${EXPORT_ARGS:-} "$@" || fail "export failed"

if [ -n "${UPLOAD_HOST:-}" ]; then
  step "$app/docker/upload.sh" "$EXPORT_OUTPUT" || fail "upload failed"
fi

if grep -qE "Skipping |couldn't be downloaded" "$log"; then
  grep -E "Skipping |couldn't be downloaded" "$log" > "$state/warnings"
  cp "$state/warnings" "$log"
  notify "Marqueefin: finished with warnings" 5
fi
touch "$data/.last-success"
echo ok > "$state/run.result"

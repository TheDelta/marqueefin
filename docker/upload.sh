#!/bin/sh
# Upload under a temporary name, then rename (atomic on OpenSSH): the web server
# never serves half a page.
set -eu
file=$1
: "${UPLOAD_USER:?UPLOAD_USER is not set}"
key=${UPLOAD_KEY_FILE:-/run/secrets/upload_key}
known=${UPLOAD_KNOWN_HOSTS:-/run/secrets/upload_known_hosts}
dir=${UPLOAD_DIR:-.}
name=${UPLOAD_FILENAME:-index.html}

if [ ! -r "$key" ]; then
  echo "❌ Upload: can't read the SSH key at $key" >&2; exit 1
fi
# Pinned host key: no trust on first use
if [ ! -r "$known" ]; then
  echo "❌ Upload: can't read known_hosts at $known (see docker/README.md)" >&2; exit 1
fi

# ssh refuses a key that others can read, and mounted secrets often are
tmpkey=$(mktemp)
trap 'rm -f "$tmpkey"' EXIT
cp "$key" "$tmpkey"
chmod 600 "$tmpkey"

echo "📤 Uploading to ${UPLOAD_USER}@${UPLOAD_HOST}:${dir}/${name}..."
# "@": no command echo; errors still show
sftp -b - -q -F /dev/null -i "$tmpkey" -P "${UPLOAD_PORT:-22}" \
  -o BatchMode=yes -o IdentitiesOnly=yes \
  -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$known" \
  -o ConnectTimeout=20 -o ServerAliveInterval=15 \
  "${UPLOAD_USER}@${UPLOAD_HOST}" <<EOF
@put "$file" "$dir/.$name.part"
@rename "$dir/.$name.part" "$dir/$name"
EOF
echo "✅ Uploaded $(du -h "$file" | cut -f1)"

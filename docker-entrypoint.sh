#!/bin/sh
set -e

PUID="${PUID:-1000}"
PGID="${PGID:-1000}"

# When started as root, hand ownership of the data mount to the runtime user
# and drop privileges. When started as a regular user, just run the command.
if [ "$(id -u)" = "0" ]; then
    mkdir -p /app/data
    chown -R "${PUID}:${PGID}" /app/data || true
    exec gosu "${PUID}:${PGID}" "$@"
fi

exec "$@"

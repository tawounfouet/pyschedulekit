#!/usr/bin/env bash
set -euo pipefail

: "${PYSCHEDULEKIT_TEST_POSTGRES_DSN:?PYSCHEDULEKIT_TEST_POSTGRES_DSN is required}"
: "${PYSCHEDULEKIT_TEST_POSTGRES_MAJOR:?PYSCHEDULEKIT_TEST_POSTGRES_MAJOR is required}"

image="postgres:${PYSCHEDULEKIT_TEST_POSTGRES_MAJOR}-alpine"
container="$(
  docker ps --format '{{.ID}} {{.Image}}' |
    awk -v image="${image}" '$2 == image {print $1; exit}'
)"

if [[ -z "${container}" ]]; then
  echo "Unable to find running PostgreSQL service container for ${image}." >&2
  exit 1
fi

backup="$(mktemp --suffix=.pyschedulekit.dump)"
cleanup() {
  rm -f "${backup}"
}
trap cleanup EXIT

python scripts/qualification/postgres_backup_restore_probe.py seed

docker exec "${container}"   pg_dump   --username postgres   --dbname pyschedulekit   --format custom   --no-owner   --no-privileges > "${backup}"

test -s "${backup}"
sha256sum "${backup}"

if ! docker exec -i "${container}" pg_restore --list < "${backup}" |
  grep -q "TABLE public schedules"; then
  echo "Backup inventory does not contain the schedules table." >&2
  exit 1
fi

docker exec "${container}"   psql   --username postgres   --dbname pyschedulekit   --set ON_ERROR_STOP=1   --command "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"

docker exec -i "${container}"   pg_restore   --username postgres   --dbname pyschedulekit   --no-owner   --no-privileges < "${backup}"

python scripts/qualification/postgres_backup_restore_probe.py verify

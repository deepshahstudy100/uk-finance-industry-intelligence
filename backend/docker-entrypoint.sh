#!/bin/sh
set -e
# Only the API container runs migrations (RUN_MIGRATIONS=1) to avoid races with the worker.
if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then
  echo "Applying database migrations"
  alembic upgrade head
fi
exec "$@"

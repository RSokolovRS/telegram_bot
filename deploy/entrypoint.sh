#!/usr/bin/env sh
set -eu

until nc -z postgres 5432; do
  echo "Waiting for postgres..."
  sleep 1
done

alembic upgrade head
exec python -m app.main

#!/bin/sh
set -e

# Require DJANGO_SECRET_KEY in production; allow a dev fallback for local Docker runs
if [ -z "${DJANGO_SECRET_KEY:-}" ]; then
  if [ "${NODE_ENV:-}" = "production" ]; then
    echo "ERROR: DJANGO_SECRET_KEY must be set in production."
    exit 1
  fi
  export DJANGO_SECRET_KEY="django-insecure-local-dev-key-not-for-production"
  echo "WARNING: DJANGO_SECRET_KEY not set. Using built-in dev key."
fi

# Run database migrations (skip if DJANGO_MIGRATE=0)
if [ "${DJANGO_MIGRATE:-1}" != "0" ]; then
  echo "Running migrations..."
  python manage.py migrate --noinput || true
fi

# Collect static files (skip if DJANGO_COLLECTSTATIC=0)
if [ "${DJANGO_COLLECTSTATIC:-1}" != "0" ]; then
  echo "Collecting static files..."
  python manage.py collectstatic --noinput || true
fi

# Execute the CMD
exec "$@"

#!/bin/sh
set -e

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

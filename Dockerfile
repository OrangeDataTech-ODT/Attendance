FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN useradd --create-home appuser

# Install Python deps
COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r /app/requirements.txt \
    && pip install --no-cache-dir gunicorn

# Copy project
COPY . /app

RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Entrypoint handles migrations/collectstatic then execs the CMD
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

ENV DJANGO_SETTINGS_MODULE=dj_project.settings
ENV PORT=8000

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["gunicorn", "dj_project.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]

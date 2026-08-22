FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_NO_INTERACTION=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir poetry

COPY pyproject.toml poetry.lock ./
RUN poetry install --no-root --only main

COPY . .

EXPOSE 8000

# Production-oriented default (used as-is by a plain `docker build`/cloud deploy
# like Render): migrate, seed the idempotent demo data, collect static files for
# whitenoise, then serve via gunicorn instead of the dev server. $PORT falls
# back to 8000 for a Render-style host that injects it, or a manual run without
# one. Local Docker Compose dev overrides this entirely (see docker-compose.yml)
# to get autoreload + DEBUG instead.
#
# --worker-class gthread --workers 2 --threads 4: plain sync gunicorn (the
# default, 1 worker) would let a single open SSE connection (see
# apps.ticketing.sse) block every other request on the whole process for as
# long as it stayed open. Threaded workers let each process serve several
# requests concurrently — a stream sitting in its poll loop no longer starves
# everyone else. gthread ships with gunicorn itself, no extra dependency.
CMD ["sh", "-c", "python manage.py migrate && python manage.py seed_demo_data && python manage.py collectstatic --noinput && gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --worker-class gthread --workers 2 --threads 4"]

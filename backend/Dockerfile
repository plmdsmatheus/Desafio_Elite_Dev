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
CMD ["sh", "-c", "python manage.py migrate && python manage.py seed_demo_data && python manage.py collectstatic --noinput && gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000}"]

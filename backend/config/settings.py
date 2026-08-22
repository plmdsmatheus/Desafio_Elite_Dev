"""
Django settings for config project.
"""

from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
    CORS_ALLOWED_ORIGINS=(list, ["http://localhost:5173"]),
)
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY", default="django-insecure-change-me-in-.env")
DEBUG = env("DJANGO_DEBUG")
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS")


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "drf_spectacular_sidecar",
    "corsheaders",
    "apps.accounts",
    "apps.catalog",
    "apps.events",
    "apps.ticketing",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # Serves collected static files directly from the app process (admin CSS,
    # DRF browsable API, drf-spectacular's Swagger UI assets) — no separate
    # static host/CDN needed on a single-dyno deploy like Render's free tier.
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

# API URLs don't use a trailing slash; disabling this avoids a 301 redirect on
# POST/PATCH when the client gets the slash wrong (which can turn into a GET).
APPEND_SLASH = False

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# Database
# Reads a single DATABASE_URL (e.g. postgres://user:pass@host:5432/dbname) so
# the same settings work identically in Docker Compose and outside it.

DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
    )
}


# Custom user model (accounts.User) — role-based: organizer / customer / gate.
AUTH_USER_MODEL = "accounts.User"


# Password validation

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True


# Static files (CSS, JavaScript, Images)

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# Django REST Framework

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_RENDERER_CLASSES": (
        "rest_framework.renderers.JSONRenderer",
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    # 6 casa com o carrossel de "até 6 eventos" na home do frontend — a página 1
    # (carrossel) e as páginas seguintes (grade estática) usam o mesmo tamanho,
    # então nenhum evento fica escondido entre um modo de exibição e outro.
    "PAGE_SIZE": 6,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Plataforma de Eventos e Ingressos — API",
    "DESCRIPTION": (
        "Organizador publica eventos a partir de um catálogo externo (Ticketmaster/TMDb), "
        "cliente reserva/paga (simulado)/recebe ingresso com QR, portaria valida na entrada.\n\n"
        "Autenticação: `POST /api/auth/login` devolve um par de tokens JWT. Clique em "
        "**Authorize** e cole `Bearer <access_token>` pra testar os endpoints protegidos."
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    # Serves Swagger UI/ReDoc assets locally (staticfiles) instead of a CDN.
    "SWAGGER_UI_DIST": "SIDECAR",
    "SWAGGER_UI_FAVICON_HREF": "SIDECAR",
    "REDOC_DIST": "SIDECAR",
    "SERVE_PERMISSIONS": ["rest_framework.permissions.AllowAny"],
    "COMPONENT_SPLIT_REQUEST": True,
    # Several models have their own "status" choices — without this the generator
    # gives the schema components generic names like "Status361Enum".
    "ENUM_NAME_OVERRIDES": {
        "UserRoleEnum": "apps.accounts.models.UserRole.choices",
        "EventCategoryEnum": "apps.events.models.EventCategory.choices",
        "EventSourceProviderEnum": "apps.events.models.EventSourceProvider.choices",
        "EventStatusEnum": "apps.events.models.EventStatus.choices",
        "EventAgeRatingEnum": "apps.events.models.EventAgeRating.choices",
        "ReservationStatusEnum": "apps.ticketing.models.ReservationStatus.choices",
        "PaymentStatusEnum": "apps.ticketing.models.PaymentStatus.choices",
        "TicketStatusEnum": "apps.ticketing.models.TicketStatus.choices",
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=1),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}


# CORS (the React/Vite frontend runs on a different origin in dev)

CORS_ALLOWED_ORIGINS = env("CORS_ALLOWED_ORIGINS")
CORS_ALLOW_CREDENTIALS = True


# External catalog APIs (proxied server-side so keys never reach the client)

TICKETMASTER_API_KEY = env("TICKETMASTER_API_KEY", default="")
TMDB_API_KEY = env("TMDB_API_KEY", default="")
TMDB_API_READ_ACCESS_TOKEN = env("TMDB_API_READ_ACCESS_TOKEN", default="")

# Front-end base URL, used to build shareable ticket links.
FRONTEND_BASE_URL = env("FRONTEND_BASE_URL", default="http://localhost:5173")

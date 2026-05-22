import os
from pathlib import Path
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "insecure-secret-key")
DJANGO_DB_SCHEMA = os.getenv("DJANGO_DB_SCHEMA", "capalti")

DEBUG = os.getenv("DJANGO_DEBUG", "True").lower() == "true"

ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS", "*").split(",")

APP_DB_NAME = os.getenv("APP_DB_NAME") or os.getenv("ERP_DB_NAME")
APP_DB_USER = os.getenv("APP_DB_USER") or os.getenv("ERP_DB_USER")
APP_DB_PASS = os.getenv("APP_DB_PASS") or os.getenv("ERP_DB_PASS")
APP_DB_HOST = os.getenv("APP_DB_HOST") or os.getenv("ERP_DB_HOST")
APP_DB_PORT = os.getenv("APP_DB_PORT") or os.getenv("ERP_DB_PORT")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "rest_framework_simplejwt",
    "apps.accounts.apps.AccountsConfig",
    "apps.customers",
    "apps.workorders",
    "apps.commissions",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "sgos.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "sgos.wsgi.application"
ASGI_APPLICATION = "sgos.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": APP_DB_NAME,
        "USER": APP_DB_USER,
        "PASSWORD": APP_DB_PASS,
        "HOST": APP_DB_HOST,
        "PORT": APP_DB_PORT,
    },
    "erp": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("ERP_DB_NAME"),
        "USER": os.getenv("ERP_DB_USER"),
        "PASSWORD": os.getenv("ERP_DB_PASS"),
        "HOST": os.getenv("ERP_DB_HOST"),
        "PORT": os.getenv("ERP_DB_PORT"),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "AUTH_HEADER_TYPES": ("Bearer",),
}

CORS_ALLOW_ALL_ORIGINS = True

AUTHENTICATION_BACKENDS = (
    "apps.accounts.ldap_backend.DynamicLDAPBackend",
    "django.contrib.auth.backends.ModelBackend",
)

LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/dashboard/"
LOGOUT_REDIRECT_URL = "/login/"

SUPERADMIN_USERNAMES = [
    u.strip().lower()
    for u in os.getenv("DJANGO_SUPERADMINS", "").split(",")
    if u.strip()
]

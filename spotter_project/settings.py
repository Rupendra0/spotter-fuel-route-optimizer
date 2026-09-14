import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env
load_dotenv(BASE_DIR / '.env')

SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-spotter-route-optimizer-eval-key-2026-xyz')

DEBUG = os.getenv('DEBUG', 'True').lower() in ('true', '1', 't')

ALLOWED_HOSTS = [host.strip() for host in os.getenv('ALLOWED_HOSTS', '*').split(',') if host.strip()]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party apps
    'rest_framework',
    'drf_spectacular',

    # Local apps
    'routes.apps.RoutesConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'spotter_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'routes' / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'spotter_project.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Django REST Framework Configuration
REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'Spotter Fuel Route Optimization API',
    'DESCRIPTION': 'Optimal route planning and fuel stop scheduling API for commercial transport.',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}

# Caching Configuration (LocMemCache for ultra-fast local in-memory caching)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'spotter-route-cache',
        'TIMEOUT': int(os.getenv('CACHE_TTL_SECONDS', 86400)),
    }
}

# Routing & Geocoding External API Configuration
ROUTING_API_URL = os.getenv('ROUTING_API_URL', 'https://router.project-osrm.org/route/v1/driving/')
GEOCODING_API_URL = os.getenv('GEOCODING_API_URL', 'https://nominatim.openstreetmap.org/search')
GEOCODING_USER_AGENT = os.getenv('GEOCODING_USER_AGENT', 'SpotterFuelOptimizer/1.0 (hiring-assessment)')

# Vehicle & Route Optimization Constraints
ROUTE_STATION_RADIUS_MILES = float(os.getenv('ROUTE_STATION_RADIUS_MILES', 15.0))
VEHICLE_MAX_RANGE_MILES = float(os.getenv('VEHICLE_MAX_RANGE_MILES', 500.0))
VEHICLE_MPG = float(os.getenv('VEHICLE_MPG', 10.0))
VEHICLE_TANK_CAPACITY_GALLONS = float(os.getenv('VEHICLE_TANK_CAPACITY_GALLONS', 50.0))
CACHE_TTL_SECONDS = int(os.getenv('CACHE_TTL_SECONDS', 86400))

# Logging Configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '[%(asctime)s] %(levelname)s [%(name)s:%(lineno)s] %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'standard',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'routes': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

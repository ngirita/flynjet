# settings.py - PRODUCTION READY

import os
import ssl
from pathlib import Path
from decouple import config
import dj_database_url
from datetime import timedelta

BASE_DIR = Path(__file__).resolve().parent.parent

# ========== LOAD FROM ENVIRONMENT ==========
SECRET_KEY = config('SECRET_KEY', default='django-insecure-build-time-key-do-not-use-in-production')
DEBUG = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1').split(',')
SITE_URL = config('SITE_URL', default='https://flynjet.com')

# Remove the print statement in production (optional, but safe to keep)
if DEBUG:
    print(f"\n{'='*60}")
    print(f"SITE_URL is set to: {SITE_URL}")
    print(f"{'='*60}\n")

# Fix SSL certificate verification for Windows
try:
    ssl._create_default_https_context = ssl._create_unverified_context
except AttributeError:
    pass

# ========== INSTALLED APPS ==========
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    'django.contrib.humanize',
    
    'rest_framework',
    'corsheaders',
    'import_export',
    'django_filters',
    'imagekit',
    'admin_interface',
    'colorfield',
    'advanced_filters',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'drf_yasg',
    'channels',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'allauth.socialaccount.providers.facebook',
    'allauth.socialaccount.providers.linkedin_oauth2',
    'django_otp',
    'django_otp.plugins.otp_totp',
    'django_otp.plugins.otp_static',
    'two_factor',
    'storages',
    'prometheus_client',
    'defender',
    
    # Phase 1 Apps
    'apps.accounts',
    'apps.airports',
    'apps.bookings',
    'apps.payments',
    'apps.fleet',
    'apps.core',

    # Health check
    'health_check',
    'health_check.contrib.celery',
    'health_check.contrib.psutil',
    'health_check.contrib.redis',
    
    # Phase 2 Apps
    'apps.tracking',
    'apps.chat',
    'apps.documents',
    'apps.reviews',
    'apps.disputes',
    'apps.marketing',
    'apps.analytics',
    'apps.compliance',
    'apps.integrations',
]

# Add debug toolbar only in development
if DEBUG:
    INSTALLED_APPS.append('debug_toolbar')

# ========== MIDDLEWARE ==========
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django_otp.middleware.OTPMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'apps.core.middleware.AuditMiddleware',
    'apps.core.middleware.TimezoneMiddleware',
    'apps.core.middleware.RateLimitMiddleware',
    'defender.middleware.FailedLoginMiddleware',
]

# Add debug toolbar middleware only in development
if DEBUG:
    MIDDLEWARE.insert(1, 'debug_toolbar.middleware.DebugToolbarMiddleware')

ROOT_URLCONF = 'flynjet.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.core.context_processors.site_settings',
                'apps.core.context_processors.notifications',
                'apps.core.context_processors.footer_data',
                'apps.core.context_processors.payment_methods',
                'apps.core.context_processors.social_links',
            ],
        },
    },
]

WSGI_APPLICATION = 'flynjet.wsgi.application'
ASGI_APPLICATION = 'flynjet.asgi.application'

# ========== DATABASE - PRODUCTION READY ==========
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME', 'flynjet_db'),
        'USER': config('DB_USER', 'postgres'),
        'PASSWORD': config('DB_PASSWORD', ''),
        'HOST': config('DB_HOST', 'localhost'),
        'PORT': config('DB_PORT', '5432'),
        'CONN_MAX_AGE': config('DB_CONN_MAX_AGE', default=0, cast=int),
        'CONN_HEALTH_CHECKS': config('DB_CONN_HEALTH_CHECKS', default=True, cast=bool),
        'OPTIONS': {
            'connect_timeout': 10,
            'sslmode': 'disable',
            'keepalives': 1,
            'keepalives_idle': 30,
            'keepalives_interval': 10,
            'keepalives_count': 5,
        }
    }
}

# ========== REDIS CACHE ==========
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': config('REDIS_URL', 'redis://localhost:6379/0'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'CONNECTION_POOL_CLASS': 'redis.BlockingConnectionPool',
            'CONNECTION_POOL_CLASS_KWARGS': {
                'max_connections': 50,
                'timeout': 20,
            },
            'MAX_CONNECTIONS': 1000,
            'PICKLE_VERSION': -1,
            'SOCKET_CONNECT_TIMEOUT': 5,
            'SOCKET_TIMEOUT': 5,
            'RETRY_ON_TIMEOUT': True,
        },
        'KEY_PREFIX': 'flynjet',
        'TIMEOUT': 300,
    }
}

# Redis configuration for defender
DEFENDER_REDIS_URL = config('REDIS_URL', 'redis://localhost:6379/0')
DEFENDER_LOCK_OUT = True
DEFENDER_COOLOFF_TIME = 300
DEFENDER_LOGIN_FAILURE_LIMIT = 5

# ========== SESSION SETTINGS ==========
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_COOKIE_AGE = 86400
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'

# ========== AUTH ==========
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
    {'NAME': 'apps.accounts.validators.UppercaseValidator'},
    {'NAME': 'apps.accounts.validators.LowercaseValidator'},
    {'NAME': 'apps.accounts.validators.NumberValidator'},
    {'NAME': 'apps.accounts.validators.SymbolValidator'},
]

AUTH_USER_MODEL = 'accounts.User'

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
    'apps.accounts.backends.EmailOrUsernameBackend',
]

# ========== REST FRAMEWORK ==========
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticatedOrReadOnly'],
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
        'apps.core.throttles.BurstRateThrottle',
        'apps.core.throttles.SustainedRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/day',
        'user': '1000/day',
        'burst': '60/minute',
        'sustained': '1000/hour',
    },
    'EXCEPTION_HANDLER': 'apps.core.exceptions.custom_exception_handler',
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer', 'JWT'),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
}

# ========== CORS ==========
CORS_ALLOWED_ORIGINS = config('CORS_ALLOWED_ORIGINS', default='https://flynjet.com,https://www.flynjet.com').split(',')
CORS_ALLOW_CREDENTIALS = True

CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = 'Lax'
CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS

# ========== STATIC & MEDIA ==========
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

FILE_UPLOAD_MAX_MEMORY_SIZE = 10485760
DATA_UPLOAD_MAX_MEMORY_SIZE = 10485760

# ========== EMAIL SETTINGS ==========
EMAIL_BACKEND = config('EMAIL_BACKEND', default='django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_USE_SSL = config('EMAIL_USE_SSL', default=False, cast=bool)
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default=EMAIL_HOST_USER)

# ========== REDIS FOR CELERY ==========
CELERY_BROKER_URL = config('REDIS_URL', 'redis://localhost:6379/1')
CELERY_RESULT_BACKEND = config('REDIS_URL', 'redis://localhost:6379/1')
CELERY_ACCEPT_CONTENT = ['application/json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE

# ========== CHANNELS ==========
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [config('REDIS_URL', 'redis://localhost:6379/2')],
        },
    },
}

# ========== ALLAUTH ==========
SITE_ID = 1
ACCOUNT_SIGNUP_FIELDS = ['email*', 'password1*', 'password2*']
ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_EMAIL_VERIFICATION = 'optional'
ACCOUNT_LOGOUT_ON_PASSWORD_CHANGE = True
ACCOUNT_SESSION_REMEMBER = True
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_RATE_LIMITS = {'login_failed': '5/300s'}

ACCOUNT_ADAPTER = 'apps.accounts.adapters.CustomAccountAdapter'
SOCIALACCOUNT_ADAPTER = 'apps.accounts.adapters.CustomSocialAccountAdapter'

SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': ['profile', 'email'],
        'AUTH_PARAMS': {'access_type': 'online'},
        'VERIFIED_EMAIL': True,
        'APP': {
            'client_id': config('GOOGLE_CLIENT_ID', ''),
            'secret': config('GOOGLE_SECRET', ''),
        }
    },
    'facebook': {
        'METHOD': 'oauth2',
        'SCOPE': ['email', 'public_profile'],
        'AUTH_PARAMS': {'auth_type': 'reauthenticate'},
        'FIELDS': ['id', 'email', 'first_name', 'last_name'],
        'VERIFIED_EMAIL': True,
        'APP': {
            'client_id': config('FACEBOOK_APP_ID', ''),
            'secret': config('FACEBOOK_APP_SECRET', ''),
        }
    },
    'linkedin_oauth2': {
        'SCOPE': ['r_emailaddress', 'r_liteprofile'],
        'PROFILE_FIELDS': ['id', 'first-name', 'last-name', 'email-address', 'picture-url', 'public-profile-url'],
        'APP': {
            'client_id': config('LINKEDIN_CLIENT_ID', ''),
            'secret': config('LINKEDIN_SECRET', ''),
        }
    }
}

TWO_FACTOR_PATCH_ADMIN = True
TWO_FACTOR_REMEMBER_COOKIE_AGE = 60 * 60 * 24 * 30

# ========== PAYMENT GATEWAYS ==========
PAYSTACK_PUBLIC_KEY = config('PAYSTACK_PUBLIC_KEY', default='')
PAYSTACK_SECRET_KEY = config('PAYSTACK_SECRET_KEY', default='')
PAYSTACK_PAYMENT_URL = 'https://api.paystack.co'
PAYSTACK_CALLBACK_URL = config('PAYSTACK_CALLBACK_URL', default='https://flynjet.com/payments/verify/')

# Bank Transfer Details (from env or database)
BANK_NAME = config('BANK_NAME', default='FlynJet Limited')
BANK_ACCOUNT_NAME = config('BANK_ACCOUNT_NAME', default='FlynJet Operations')
BANK_ACCOUNT_NUMBER = config('BANK_ACCOUNT_NUMBER', default='')
BANK_SWIFT_CODE = config('BANK_SWIFT_CODE', default='')
BANK_ROUTING_NUMBER = config('BANK_ROUTING_NUMBER', default='')

# Crypto Wallet Addresses
TRUST_WALLET_BTC = config('TRUST_WALLET_BTC', default='')
TRUST_WALLET_USDT_ERC20 = config('TRUST_WALLET_USDT_ERC20', default='')
TRUST_WALLET_USDT_TRC20 = config('TRUST_WALLET_USDT_TRC20', default='')

ACTIVE_PAYMENT_GATEWAY = 'paystack'

# Crypto Settings
WEB3_PROVIDER_URI = config('WEB3_PROVIDER_URI', default='')
USDT_CONTRACT_ADDRESS = config('USDT_CONTRACT_ADDRESS', default='')
BITCOIN_NETWORK = config('BITCOIN_NETWORK', default='mainnet')

# Remove debug prints in production
if DEBUG:
    print("=" * 60)
    print("PAYMENT SETTINGS LOADED:")
    print(f"Paystack Secret Key: {PAYSTACK_SECRET_KEY[:10]}..." if PAYSTACK_SECRET_KEY else "Not set")
    print(f"Bank Account: {BANK_ACCOUNT_NUMBER}")
    print(f"BTC Wallet: {TRUST_WALLET_BTC[:15]}..." if TRUST_WALLET_BTC else "Not set")
    print("=" * 60)

# ========== LOGGING ==========
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {asctime} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO' if not DEBUG else 'DEBUG',
        },
        'apps.payments': {
            'handlers': ['console'],
            'level': 'INFO' if not DEBUG else 'DEBUG',
        },
    },
}

# Add file logging only in development
if DEBUG:
    LOGGING['handlers']['file'] = {
        'level': 'DEBUG',
        'class': 'logging.FileHandler',
        'filename': BASE_DIR / 'logs' / 'django.log',
        'formatter': 'verbose',
    }
    LOGGING['loggers']['django']['handlers'].append('file')
    LOGGING['loggers']['apps.payments']['handlers'].append('file')
    LOGS_DIR = BASE_DIR / 'logs'
    LOGS_DIR.mkdir(exist_ok=True)

# ========== SECURITY ==========
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG
SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', default=False, cast=bool)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

RATELIMIT_ENABLE = True
RATELIMIT_USE_CACHE = 'default'

ADMIN_INTERFACE_SETTINGS = {
    'show_fieldsets_as_tabs': True,
    'show_inlines_as_tabs': True,
}

ADMIN_EMAIL = config('ADMIN_EMAIL', default='info@flynjet.com')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

TWILIO_ACCOUNT_SID = config('TWILIO_ACCOUNT_SID', '')
TWILIO_AUTH_TOKEN = config('TWILIO_AUTH_TOKEN', '')
TWILIO_PHONE_NUMBER = config('TWILIO_PHONE_NUMBER', '')

SENDGRID_API_KEY = config('SENDGRID_API_KEY', '')
GOOGLE_MAPS_API_KEY = config('GOOGLE_MAPS_API_KEY', '')
USE_OPENSTREETMAP = True

# Authentication URLs
LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'

# Debug toolbar settings (only in development)
if DEBUG:
    INTERNAL_IPS = ['127.0.0.1', 'localhost']
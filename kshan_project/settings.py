import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Storage & Runtime directories
STORAGE_DIR = BASE_DIR / "storage"
EVENTS_STORAGE_DIR = STORAGE_DIR / "events"
TEMP_STORAGE_DIR = STORAGE_DIR / "temporary"
LOGS_DIR = BASE_DIR / "logs"

for d in [STORAGE_DIR, EVENTS_STORAGE_DIR, TEMP_STORAGE_DIR, LOGS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Cloudflare R2 / S3 Configuration
R2_ENABLED = os.getenv('R2_ENABLED', 'False').lower() in ('true', '1', 't')
R2_ACCESS_KEY_ID = os.getenv('R2_ACCESS_KEY_ID', '')
R2_SECRET_ACCESS_KEY = os.getenv('R2_SECRET_ACCESS_KEY', '')
R2_BUCKET_NAME = os.getenv('R2_BUCKET_NAME', 'kshan')
R2_ENDPOINT_URL = os.getenv('R2_ENDPOINT_URL', '')
R2_ACCOUNT_ID = os.getenv('R2_ACCOUNT_ID', '')

# Razorpay Payment Gateway Configuration
RAZORPAY_KEY_ID = os.getenv('RAZORPAY_KEY_ID', '')
RAZORPAY_KEY_SECRET = os.getenv('RAZORPAY_KEY_SECRET', '')
RAZORPAY_WEBHOOK_SECRET = os.getenv('RAZORPAY_WEBHOOK_SECRET', '')
RAZORPAY_CURRENCY = os.getenv('RAZORPAY_CURRENCY', 'INR')

# Meta WhatsApp Cloud API Configuration
META_WA_PHONE_NUMBER_ID = os.getenv('META_WA_PHONE_NUMBER_ID', '')
META_WA_ACCESS_TOKEN = os.getenv('META_WA_ACCESS_TOKEN', '')
META_WA_API_VERSION = os.getenv('META_WA_API_VERSION', 'v21.0')
META_WA_OTP_TEMPLATE_NAME = os.getenv('META_WA_OTP_TEMPLATE_NAME', '')

# Firebase Configuration
FIREBASE_API_KEY = os.getenv('FIREBASE_API_KEY', '')
FIREBASE_AUTH_DOMAIN = os.getenv('FIREBASE_AUTH_DOMAIN', '')
FIREBASE_PROJECT_ID = os.getenv('FIREBASE_PROJECT_ID', '')
FIREBASE_STORAGE_BUCKET = os.getenv('FIREBASE_STORAGE_BUCKET', '')
FIREBASE_MESSAGING_SENDER_ID = os.getenv('FIREBASE_MESSAGING_SENDER_ID', '')
FIREBASE_APP_ID = os.getenv('FIREBASE_APP_ID', '')

# Security & Secret Key
DEBUG = os.getenv('DEBUG', 'False').lower() in ('true', '1', 't')

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY')
if not SECRET_KEY:
    if DEBUG or 'test' in sys.argv or 'check' in sys.argv:
        SECRET_KEY = 'django-insecure-kshan-dev-local-fallback-key-strictly-for-testing-only'
    else:
        raise ValueError("CRITICAL: DJANGO_SECRET_KEY environment variable is mandatory in production!")

# Host Configuration
_allowed_hosts_raw = os.getenv('ALLOWED_HOSTS', '')
if _allowed_hosts_raw:
    ALLOWED_HOSTS = [h.strip() for h in _allowed_hosts_raw.split(',') if h.strip()]
else:
    ALLOWED_HOSTS = ['*'] if DEBUG else ['localhost', '127.0.0.1', 'kshan.online', '.kshan.online']

# Application definition
INSTALLED_APPS = [
    'daphne',
    'channels',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'gallery.apps.GalleryConfig',
    'faceshare',
]

ASGI_APPLICATION = 'kshan_project.asgi.application'

# Channel Layers Configuration
REDIS_URL = os.getenv('REDIS_URL', '')
if REDIS_URL:
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels_redis.core.RedisChannelLayer',
            'CONFIG': {
                "hosts": [REDIS_URL],
            },
        },
    }
else:
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels.layers.InMemoryChannelLayer'
        }
    }

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'kshan_project.urls'

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
            ],
        },
    },
]

WSGI_APPLICATION = 'kshan_project.wsgi.application'

# Database Configuration
DATABASE_URL = os.getenv('DATABASE_URL', '')
if DATABASE_URL:
    try:
        import dj_database_url
        db_config = dj_database_url.parse(DATABASE_URL, conn_max_age=600, ssl_require=not DEBUG)
        db_config.setdefault('OPTIONS', {})
        db_config['OPTIONS']['connect_timeout'] = 30
        db_config['OPTIONS']['options'] = '-c statement_timeout=0'
        DATABASES = {
            'default': db_config
        }
    except Exception:
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': BASE_DIR / 'db.sqlite3',
                'OPTIONS': {
                    'timeout': 30,
                }
            }
        }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
            'OPTIONS': {
                'timeout': 30,
            }
        }
    }

# Session Configuration
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
SESSION_COOKIE_AGE = 86400 * 30          # 30 days
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

# HTTPS & Transport Security (Strict in production, relaxed for local dev)
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    CSRF_COOKIE_HTTPONLY = False
    CSRF_COOKIE_SAMESITE = 'Lax'
    SECURE_SSL_REDIRECT = os.getenv('SECURE_SSL_REDIRECT', 'True').lower() in ('true', '1', 't')
    SECURE_HSTS_SECONDS = int(os.getenv('SECURE_HSTS_SECONDS', '31536000')) # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
else:
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    CSRF_COOKIE_HTTPONLY = False
    CSRF_COOKIE_SAMESITE = 'Lax'
    SECURE_SSL_REDIRECT = False
    SECURE_HSTS_SECONDS = 0
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

USE_X_FORWARDED_HOST = True
USE_X_FORWARDED_PORT = True

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

# CSRF Trusted Origins
_csrf_origins_raw = os.getenv('CSRF_TRUSTED_ORIGINS', '')
if _csrf_origins_raw:
    CSRF_TRUSTED_ORIGINS = [o.strip() for o in _csrf_origins_raw.split(',') if o.strip()]
else:
    CSRF_TRUSTED_ORIGINS = [
        'https://kshan.online',
        'https://*.kshan.online',
        'https://www.kshan.online',
        'https://*.onrender.com',
        'https://*.awsapprunner.com',
        'https://*.hf.space',
        'https://*.trycloudflare.com',
        'http://localhost:8000',
        'http://127.0.0.1:8000',
        'http://localhost:1212',
        'http://127.0.0.1:1212',
    ]

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'storage'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Upload Limits & Configuration for High-Res Event Batches (Supports 1GB+ Multi-Gigabyte Uploads)
DATA_UPLOAD_MAX_MEMORY_SIZE = 250 * 1024 * 1024       # 250 MB max payload in single request
FILE_UPLOAD_MAX_MEMORY_SIZE = 25 * 1024 * 1024        # 25 MB in-memory buffer before streaming to temp disk
DATA_UPLOAD_MAX_NUMBER_FIELDS = 10000                 # Max multipart form fields
DATA_UPLOAD_MAX_NUMBER_FILES = 10000                  # Max files in request payload
MAX_PHOTO_UPLOAD_FILE_SIZE = 100 * 1024 * 1024        # 100 MB max single photo file (DSLR RAW/High-Res)
MAX_SELFIE_UPLOAD_FILE_SIZE = 25 * 1024 * 1024        # 25 MB max selfie file
MAX_IMAGE_PIXELS = 150_000_000                        # Pillow decompression limit (150MP)
MAX_PHOTOS_PER_BATCH = 500                            # Max photos in a single upload request batch

# Face Recognition Settings
INSIGHTFACE_MODEL_NAME = os.getenv('INSIGHTFACE_MODEL', 'buffalo_s')
FACE_MATCH_THRESHOLD = float(os.getenv('FACE_MATCH_THRESHOLD', '0.40')) # Calibrated ArcFace cosine threshold
MIN_DET_SCORE = float(os.getenv('MIN_DET_SCORE', '0.40'))               # Detection confidence score threshold
MIN_FACE_SIZE = int(os.getenv('MIN_FACE_SIZE', '25'))                   # Minimum face width/height in pixels
DETECTION_SIZE = (640, 640)                                             # Standard InsightFace input size
THUMBNAIL_MAX_SIZE = 500
SUPPORTED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}
SUPPORTED_MIME_TYPES = {'image/jpeg', 'image/png', 'image/webp'}

# FaceShare Peer-to-Peer Settings
FACESHARE_ROOM_TTL_MINUTES = int(os.getenv('FACESHARE_ROOM_TTL_MINUTES', '60'))
FACESHARE_MAX_PHOTOS = int(os.getenv('FACESHARE_MAX_PHOTOS', '300'))
FACESHARE_MAX_PARTICIPANTS = int(os.getenv('FACESHARE_MAX_PARTICIPANTS', '15'))
FACESHARE_MATCH_THRESHOLD = float(os.getenv('FACESHARE_MATCH_THRESHOLD', '0.62'))

# WebRTC STUN/TURN Configuration
WEBRTC_STUN_URL = os.getenv('WEBRTC_STUN_URL', 'stun:stun.l.google.com:19302')
WEBRTC_TURN_URL = os.getenv('WEBRTC_TURN_URL', '')
WEBRTC_TURN_USERNAME = os.getenv('WEBRTC_TURN_USERNAME', '')
WEBRTC_TURN_CREDENTIAL = os.getenv('WEBRTC_TURN_CREDENTIAL', '')

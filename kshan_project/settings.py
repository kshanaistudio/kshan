import os
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
R2_BUCKET_NAME = os.getenv('R2_BUCKET_NAME', 'kshan-database')
R2_ENDPOINT_URL = os.getenv('R2_ENDPOINT_URL', '')

# Razorpay Payment Gateway Configuration
RAZORPAY_KEY_ID = os.getenv('RAZORPAY_KEY_ID', '')
RAZORPAY_KEY_SECRET = os.getenv('RAZORPAY_KEY_SECRET', '')
RAZORPAY_CURRENCY = os.getenv('RAZORPAY_CURRENCY', 'INR')

# Meta WhatsApp Cloud API Configuration
META_WA_PHONE_NUMBER_ID = os.getenv('META_WA_PHONE_NUMBER_ID', '')
META_WA_ACCESS_TOKEN = os.getenv('META_WA_ACCESS_TOKEN', '')
META_WA_API_VERSION = os.getenv('META_WA_API_VERSION', 'v21.0')
META_WA_OTP_TEMPLATE_NAME = os.getenv('META_WA_OTP_TEMPLATE_NAME', '')

# Security & Secret Key
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'django-insecure-kshan-face-gallery-key-2026-x99a!b')
DEBUG = os.getenv('DEBUG', 'False').lower() in ('true', '1', 't')
ALLOWED_HOSTS = ['*']

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

# Channel Layers Configuration (In-Memory default, Redis fallback if env configured)
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

# Database (Supabase PostgreSQL / SQLite fallback)
DATABASE_URL = os.getenv('DATABASE_URL', '')
if DATABASE_URL:
    try:
        import dj_database_url
        db_config = dj_database_url.parse(DATABASE_URL, conn_max_age=600, ssl_require=True)
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


# Session Configuration — persistent DB-backed sessions that survive Render restarts
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
SESSION_COOKIE_AGE = 86400 * 30          # 30 days
SESSION_COOKIE_SECURE = False             # Allow both HTTP and HTTPS
SESSION_COOKIE_HTTPONLY = True
SESSION_SAVE_EVERY_REQUEST = True         # Refresh session on every request
SESSION_EXPIRE_AT_BROWSER_CLOSE = False   # Keep session even after closing browser

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

# CSRF Trusted Origins (Allows Render, Hugging Face, AWS App Runner & Cloudflare domains)
CSRF_TRUSTED_ORIGINS = [
    'https://*.awsapprunner.com',
    'https://*.onrender.com',
    'https://*.hf.space',
    'https://*.trycloudflare.com',
    'https://*.azurewebsites.net',
    'https://*.elasticbeanstalk.com',
    'https://kshan.online',
    'https://*.kshan.online',
    'https://www.kshan.online',
    'http://kshan.online',
    'http://*.kshan.online',
    'http://www.kshan.online',
    'http://13.204.43.143',
    'http://localhost:1212',
    'http://127.0.0.1:1212',
    'http://0.0.0.0:1212',
    'http://0.0.0.0:7860',
    'http://localhost:7860'
]

# Cloudflare Proxy SSL Headers & Host trust
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True
USE_X_FORWARDED_PORT = True
CSRF_COOKIE_HTTPONLY = False
CSRF_USE_SESSIONS = False


# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'storage'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Multi-Gigabyte Upload Configuration (Supports large 5GB+ wedding batches)
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024 * 1024  # 10 GB
FILE_UPLOAD_MAX_MEMORY_SIZE = 100 * 1024 * 1024        # 100 MB per file in-memory buffer before streaming to disk
DATA_UPLOAD_MAX_NUMBER_FIELDS = 10000                  # Support up to 10,000 files in one payload

# Face Recognition Settings
# buffalo_s = lightweight model (~150MB RAM) — fast and accurate on CPU
# buffalo_l = large model (~500MB RAM) — needs 2GB+ RAM
INSIGHTFACE_MODEL_NAME = os.getenv('INSIGHTFACE_MODEL', 'buffalo_s')
FACE_MATCH_THRESHOLD = 0.40           # Calibrated ArcFace cosine threshold for event photography
MIN_DET_SCORE = 0.40                  # Detection confidence score threshold for candid / angled faces
MIN_FACE_SIZE = 25                    # Minimum face width/height in pixels
DETECTION_SIZE = (640, 640)           # Standard InsightFace input size for maximum detection accuracy
THUMBNAIL_MAX_SIZE = 500
SUPPORTED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}

# FaceShare Peer-to-Peer Settings
FACESHARE_ROOM_TTL_MINUTES = int(os.getenv('FACESHARE_ROOM_TTL_MINUTES', '60'))
FACESHARE_MAX_PHOTOS = int(os.getenv('FACESHARE_MAX_PHOTOS', '300'))
FACESHARE_MAX_PARTICIPANTS = int(os.getenv('FACESHARE_MAX_PARTICIPANTS', '15'))
FACESHARE_MATCH_THRESHOLD = float(os.getenv('FACESHARE_MATCH_THRESHOLD', '0.62'))

# WebRTC STUN/TURN Configuration (Default Google STUN, custom TURN via env)
WEBRTC_STUN_URL = os.getenv('WEBRTC_STUN_URL', 'stun:stun.l.google.com:19302')
WEBRTC_TURN_URL = os.getenv('WEBRTC_TURN_URL', '')
WEBRTC_TURN_USERNAME = os.getenv('WEBRTC_TURN_USERNAME', '')
WEBRTC_TURN_CREDENTIAL = os.getenv('WEBRTC_TURN_CREDENTIAL', '')

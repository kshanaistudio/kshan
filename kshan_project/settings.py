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
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'gallery.apps.GalleryConfig',
]

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

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
        'OPTIONS': {
            'timeout': 30,
        }
    }
}

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

# CSRF Trusted Origins (Allows Render, Hugging Face, & Cloudflare domains)
CSRF_TRUSTED_ORIGINS = [
    'https://*.onrender.com',
    'https://*.hf.space',
    'https://*.trycloudflare.com',
    'http://localhost:1212',
    'http://127.0.0.1:1212',
    'http://0.0.0.0:1212',
    'http://0.0.0.0:7860',
    'http://localhost:7860'
]

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'storage'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Multi-Gigabyte Upload Configuration (Supports large 5GB+ wedding batches)
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024 * 1024  # 10 GB
FILE_UPLOAD_MAX_MEMORY_SIZE = 100 * 1024 * 1024        # 100 MB per file in-memory buffer before streaming to disk
DATA_UPLOAD_MAX_NUMBER_FIELDS = 10000                  # Support up to 10,000 files in one payload

# Face Recognition Settings
INSIGHTFACE_MODEL_NAME = "buffalo_l"  # ResNet-50 ArcFace (99.83% accuracy)
FACE_MATCH_THRESHOLD = 0.44           # Calibrated ArcFace cosine threshold for event photography
MIN_DET_SCORE = 0.50                  # Detection confidence score threshold
MIN_FACE_SIZE = 30                    # Minimum face width/height in pixels
DETECTION_SIZE = (640, 640)
THUMBNAIL_MAX_SIZE = 500
SUPPORTED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}

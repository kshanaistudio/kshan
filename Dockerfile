FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000 \
    FACE_RECOGNITION_ENABLED=True \
    INSIGHTFACE_MODEL=buffalo_s

WORKDIR /app

# Install system dependencies for OpenCV, InsightFace, and libGL
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . /app/

# Create storage directories
RUN mkdir -p /app/storage/events /app/storage/temporary /app/logs

EXPOSE 8000

# Migrate, create admin, collect static, then start gunicorn
CMD sh -c "python manage.py migrate --noinput && python manage.py create_admin && python manage.py collectstatic --noinput && gunicorn --bind 0.0.0.0:${PORT:-8000} --workers 1 --threads 4 --timeout 300 --keep-alive 75 --graceful-timeout 30 --max-requests 500 --max-requests-jitter 50 kshan_project.wsgi:application"

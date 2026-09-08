FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000 \
    FACE_RECOGNITION_ENABLED=True \
    INSIGHTFACE_MODEL=buffalo_s

# Install system dependencies with retries and force IPv4 to prevent EC2 networking hangs
RUN apt-get update -o Acquire::ForceIPv4=true -o Acquire::Retries=3 && \
    apt-get install -y --no-install-recommends \
        build-essential \
        libglib2.0-0 \
        libgomp1 \
        git \
        curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python requirements
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . /app/

# Create storage directories
RUN mkdir -p /app/storage/events /app/storage/temporary /app/logs

EXPOSE 8000

# Migrate, collect static, then start gunicorn
# t2.micro = 1GB RAM: 1 worker to stay within limits
CMD sh -c "python manage.py migrate --noinput && python manage.py collectstatic --noinput && gunicorn --bind 0.0.0.0:${PORT:-8000} --workers 1 --threads 4 --timeout 300 --keep-alive 75 --graceful-timeout 30 --max-requests 500 --max-requests-jitter 50 kshan_project.wsgi:application"

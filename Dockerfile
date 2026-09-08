FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    git \
    curl \
    ffmpeg \
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

ENV PYTHONUNBUFFERED=1
ENV PORT=8000
ENV FACE_RECOGNITION_ENABLED=True
ENV INSIGHTFACE_MODEL=buffalo_s

EXPOSE 8000

# Migrate, collect static, then start gunicorn
CMD sh -c "python manage.py migrate --noinput && python manage.py collectstatic --noinput && gunicorn --bind 0.0.0.0:${PORT:-8000} --workers 2 --threads 4 --timeout 300 --keep-alive 75 --graceful-timeout 30 --max-requests 500 --max-requests-jitter 50 kshan_project.wsgi:application"

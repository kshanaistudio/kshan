FROM python:3.11-slim

# System dependencies for OpenCV, InsightFace, and Pillow
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python requirements
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . /app/

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=10000

EXPOSE 10000

# Run migrations, collect static, and start Gunicorn binding to dynamic Render $PORT
CMD sh -c "python manage.py migrate --noinput && python manage.py collectstatic --noinput && gunicorn --bind 0.0.0.0:${PORT:-10000} --workers 1 --threads 4 --timeout 180 kshan_project.wsgi:application"


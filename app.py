import os
import sys
import subprocess
import time

print("Starting KSHAN Production Django Server on Hugging Face Spaces...")

# Run migrations
subprocess.run([sys.executable, "manage.py", "migrate"], check=False)

# Collect static files
subprocess.run([sys.executable, "manage.py", "collectstatic", "--noinput"], check=False)

# Port 7860 is Hugging Face Spaces standard web port
port = os.environ.get("PORT", "7860")

print(f"Launching Gunicorn WSGI Server on 0.0.0.0:{port}...")
cmd = [
    sys.executable, "-m", "gunicorn",
    "--bind", f"0.0.0.0:{port}",
    "--workers", "2",
    "--threads", "4",
    "--timeout", "180",
    "kshan_project.wsgi:application"
]

subprocess.run(cmd)

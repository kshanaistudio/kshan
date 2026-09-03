#!/usr/bin/env bash
# Render build script for KSHAN
set -o errexit

pip install --upgrade pip
pip install -r requirements.txt

python manage.py migrate
python manage.py collectstatic --no-input

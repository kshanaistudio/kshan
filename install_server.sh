#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# KSHAN AI Photo Suite — Automated Production Installer (Python 3.11)
# ═══════════════════════════════════════════════════════════════════
set -e

echo ""
echo "══════════════════════════════════════════════════════════════"
echo "  🚀 KSHAN Automated Production Deployment"
echo "══════════════════════════════════════════════════════════════"
echo ""

APP_DIR="/home/ubuntu/kshan"
MINICONDA_DIR="/home/ubuntu/miniconda"
ENV_DIR="$MINICONDA_DIR/envs/kshan"

# 1. Clean old caches & lock files
echo "▶ [1/6] Cleaning disk and legacy processes..."
sudo pkill -9 -f gunicorn 2>/dev/null || true
sudo pkill -9 -f python 2>/dev/null || true
rm -rf /home/ubuntu/tmp /tmp/* ~/.cache/pip

# 2. Install Miniconda if not already installed
if [ ! -d "$MINICONDA_DIR" ]; then
    echo "▶ [2/6] Downloading & installing lightweight Miniconda..."
    wget -q https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O /tmp/miniconda.sh
    bash /tmp/miniconda.sh -b -p "$MINICONDA_DIR"
    rm -f /tmp/miniconda.sh
else
    echo "▶ [2/6] Miniconda already installed."
fi

# 3. Create Python 3.11 Conda Environment
if [ ! -d "$ENV_DIR" ]; then
    echo "▶ [3/6] Creating Python 3.11 environment (via conda-forge)..."
    "$MINICONDA_DIR/bin/conda" create -y -c conda-forge --override-channels -n kshan python=3.11
else
    echo "▶ [3/6] Python 3.11 environment exists."
fi

# 4. Install all dependencies using Python 3.11 binaries
echo "▶ [4/6] Installing dependencies with Python 3.11 pre-built wheels..."
"$ENV_DIR/bin/pip" install --upgrade pip setuptools wheel
"$ENV_DIR/bin/pip" install --no-cache-dir -r "$APP_DIR/requirements.txt"

# 5. Database migrations & static files
echo "▶ [5/6] Applying migrations and collecting static files..."
cd "$APP_DIR"

if [ ! -f "$APP_DIR/.env" ]; then
    cp "$APP_DIR/.env.example" "$APP_DIR/.env"
fi

"$ENV_DIR/bin/python" manage.py migrate --noinput
"$ENV_DIR/bin/python" manage.py collectstatic --noinput

# 6. Configure & start systemd service
echo "▶ [6/6] Configuring systemd service on port 80..."
sudo tee /etc/systemd/system/kshan.service > /dev/null << EOF
[Unit]
Description=KSHAN AI Photo Suite Gunicorn Service
After=network.target

[Service]
User=ubuntu
Group=ubuntu
WorkingDirectory=$APP_DIR
EnvironmentFile=$APP_DIR/.env
Environment="PORT=80"
Environment="PATH=$ENV_DIR/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
AmbientCapabilities=CAP_NET_BIND_SERVICE
CapabilityBoundingSet=CAP_NET_BIND_SERVICE
ExecStart=$ENV_DIR/bin/gunicorn --bind 0.0.0.0:80 --workers 1 --threads 4 --timeout 300 --keep-alive 75 --graceful-timeout 30 --max-requests 500 --max-requests-jitter 50 kshan_project.wsgi:application
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable kshan
sudo systemctl restart kshan

echo ""
echo "══════════════════════════════════════════════════════════════"
echo "  ✅ KSHAN is LIVE and Running!"
echo "══════════════════════════════════════════════════════════════"
PUBLIC_IP=\$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || curl -s ifconfig.me 2>/dev/null || echo "YOUR_IP")
echo "  🌐 URL:  http://\$PUBLIC_IP"
echo ""
sudo systemctl status kshan --no-pager

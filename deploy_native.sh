#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# KSHAN AI Photo Suite — Direct Native Deployment (No Docker)
# Optimized for AWS EC2 t2.micro (1GB RAM Ubuntu 22.04)
# ═══════════════════════════════════════════════════════════════════
set -e

echo ""
echo "══════════════════════════════════════════════════════════════"
echo "  🚀 KSHAN Native Setup (Direct Python 3 + Systemd Service)"
echo "══════════════════════════════════════════════════════════════"
echo ""

# 1. Free up disk space (clean all docker leftovers)
echo "▶ [1/7] Cleaning up unused disk space..."
sudo systemctl stop docker 2>/dev/null || true
sudo apt purge -y docker-ce docker-ce-cli containerd.io docker.io docker-compose 2>/dev/null || true
sudo rm -rf /var/lib/docker /var/lib/containerd
sudo apt autoremove -y
sudo apt clean

# 2. Add 2GB Swap (critical for 1GB RAM)
echo "▶ [2/7] Checking 2GB swap space..."
if [ ! -f /swapfile ]; then
    sudo fallocate -l 2G /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
    echo 'vm.swappiness=10' | sudo tee -a /etc/sysctl.conf
    sudo sysctl -p
    echo "   ✅ 2GB swap active"
else
    echo "   ✅ Swap already present"
fi

# 3. Install System Packages
echo "▶ [3/7] Installing Python 3, pip, venv, and build tools..."
sudo apt update
sudo apt install -y python3-pip python3-venv python3-dev build-essential libglib2.0-0 libgomp1 git curl

# 4. Prepare App Directory
REPO_DIR="/home/ubuntu/kshan"
cd "$REPO_DIR"

# 5. Virtual Environment & Dependencies
echo "▶ [4/7] Setting up Python virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

source venv/bin/activate
echo "   Installing requirements (takes ~2-3 mins)..."
pip install --upgrade pip
pip install -r requirements.txt

# 6. Django database migrate and static files
echo "▶ [5/7] Running database migrations and collecting static files..."
python manage.py migrate --noinput
python manage.py collectstatic --noinput

# 7. Create Systemd Service (Auto-starts & Restarts on boot)
echo "▶ [6/7] Creating systemd service for Kshan..."
sudo tee /etc/systemd/system/kshan.service << 'EOF'
[Unit]
Description=KSHAN AI Photo Suite Gunicorn Service
After=network.target

[Service]
User=ubuntu
Group=ubuntu
WorkingDirectory=/home/ubuntu/kshan
EnvironmentFile=/home/ubuntu/kshan/.env
Environment="PORT=80"
Environment="PATH=/home/ubuntu/kshan/venv/bin"
AmbientCapabilities=CAP_NET_BIND_SERVICE
CapabilityBoundingSet=CAP_NET_BIND_SERVICE
ExecStart=/home/ubuntu/kshan/venv/bin/gunicorn --bind 0.0.0.0:80 --workers 1 --threads 4 --timeout 300 --keep-alive 75 --graceful-timeout 30 --max-requests 500 --max-requests-jitter 50 kshan_project.wsgi:application
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Grant port 80 permission to gunicorn without root or bind via authbind/systemd
sudo systemctl daemon-reload
sudo systemctl enable kshan
sudo systemctl restart kshan

echo ""
echo "══════════════════════════════════════════════════════════════"
echo "  ✅ KSHAN is LIVE (Native Mode without Docker)!"
echo "══════════════════════════════════════════════════════════════"
PUBLIC_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || curl -s ifconfig.me 2>/dev/null || echo "YOUR_IP")
echo "  🌐 URL:          http://$PUBLIC_IP"
echo "  📊 Status:       sudo systemctl status kshan"
echo "  📜 Live Logs:    sudo journalctl -u kshan -f"
echo "  🔄 Restart:      sudo systemctl restart kshan"
echo ""

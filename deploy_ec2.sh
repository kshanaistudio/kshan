#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# KSHAN AI Photo Suite — AWS EC2 Setup (Ubuntu 22.04)
# Run this ON your EC2 instance after SSH-ing in:
#   ssh -i your-key.pem ubuntu@YOUR_EC2_IP
#   bash deploy_ec2.sh
# ═══════════════════════════════════════════════════════════════════
set -e

echo ""
echo "══════════════════════════════════════════════"
echo "  🚀 KSHAN — AWS Deploy Script"
echo "══════════════════════════════════════════════"
echo ""

# ── 1. System Update ────────────────────────────────────────────────
echo "▶ [1/8] Updating system packages..."
sudo apt update && sudo apt upgrade -y

# ── 2. Add 2GB Swap ────────────────────────────────────────────────
echo "▶ [2/8] Setting up 2GB swap file..."
if [ ! -f /swapfile ]; then
    sudo fallocate -l 2G /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
    echo 'vm.swappiness=10' | sudo tee -a /etc/sysctl.conf
    sudo sysctl -p
    echo "   ✅ 2GB swap created"
else
    echo "   ✅ Swap already exists — skipping"
fi

# ── 3. Install Docker ───────────────────────────────────────────────
echo "▶ [3/8] Installing Docker & tools..."
sudo apt install -y docker.io docker-compose-v2 git curl ufw 2>/dev/null || sudo apt install -y docker.io docker-compose git curl ufw
sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker $USER

# Determine compose command
if docker compose version >/dev/null 2>&1; then
    DOCKER_COMPOSE="sudo docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
    DOCKER_COMPOSE="sudo docker-compose"
else
    sudo apt install -y docker-compose-v2 2>/dev/null || true
    DOCKER_COMPOSE="sudo docker compose"
fi

# ── 4. Firewall ─────────────────────────────────────────────────────
echo "▶ [4/8] Configuring firewall..."
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable

# ── 5. Clone / Pull repo ────────────────────────────────────────────
echo "▶ [5/8] Getting latest code..."
REPO_DIR="/home/ubuntu/kshan"

if [ -d "$REPO_DIR/.git" ]; then
    echo "   Repo exists — pulling latest..."
    cd "$REPO_DIR"
    git pull origin main
else
    echo "   Cloning fresh..."
    git clone https://github.com/kshanaistudio/kshan.git "$REPO_DIR"
    cd "$REPO_DIR"
fi

# ── 6. Check .env ───────────────────────────────────────────────────
echo "▶ [6/8] Checking .env configuration..."
if [ ! -f "$REPO_DIR/.env" ]; then
    echo "   ⚠️  .env not found! Creating template from .env.example..."
    cp "$REPO_DIR/.env.example" "$REPO_DIR/.env"
    echo "   ❗ IMPORTANT: Please edit $REPO_DIR/.env with your real credentials before launching!"
else
    echo "   ✅ .env found"
fi

# ── 7. Build & launch ───────────────────────────────────────────────
echo "▶ [7/8] Building Docker image and launching..."
cd "$REPO_DIR"
$DOCKER_COMPOSE down --remove-orphans 2>/dev/null || true
$DOCKER_COMPOSE up -d --build

# ── 8. Verify & show info ───────────────────────────────────────────
echo ""
echo "▶ [8/8] Waiting 20s for server to start..."
sleep 20

echo ""
echo "Container status:"
$DOCKER_COMPOSE ps

echo ""
echo "Recent logs:"
$DOCKER_COMPOSE logs --tail=25 web

PUBLIC_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || curl -s ifconfig.me 2>/dev/null || echo "YOUR_IP")

echo ""
echo "════════════════════════════════════════════════"
echo "  ✅  KSHAN Deployment Complete!"
echo "════════════════════════════════════════════════"
echo ""
echo "  🌐  URL:       http://$PUBLIC_IP"
echo ""
echo "  Useful commands:"
echo "  ┌─ View live logs:  cd ~/kshan && sudo docker compose logs -f web"
echo "  ├─ Restart app:    cd ~/kshan && sudo docker compose restart web"
echo "  ├─ Update & redeploy: cd ~/kshan && git pull && sudo docker compose up -d --build"
echo "  └─ Check memory:   free -h"
echo ""

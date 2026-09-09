#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# KSHAN AI Photo Suite — AWS EC2 Free Tier (t2.micro Ubuntu 22.04)
# Run this ON your EC2 instance after SSH-ing in:
#   ssh -i your-key.pem ubuntu@YOUR_EC2_IP
#   bash deploy_ec2.sh
# ═══════════════════════════════════════════════════════════════════
set -e

echo ""
echo "══════════════════════════════════════════════"
echo "  🚀 KSHAN — AWS Free Tier Deploy (t2.micro)"
echo "══════════════════════════════════════════════"
echo ""

# ── 1. System Update ────────────────────────────────────────────────
echo "▶ [1/8] Updating system packages..."
sudo apt update && sudo apt upgrade -y

# ── 2. Add 2GB Swap (CRITICAL for t2.micro 1GB RAM) ────────────────
# InsightFace buffalo_s needs ~300MB. Without swap, a memory spike
# during face detection will OOM-kill the container.
echo "▶ [2/8] Setting up 2GB swap file..."
if [ ! -f /swapfile ]; then
    sudo fallocate -l 2G /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    # Make swap permanent across reboots
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
    # Tune swappiness: prefer RAM, use swap only as safety net
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

# ── 6. Create .env if missing ───────────────────────────────────────
echo "▶ [6/8] Checking .env..."
if [ ! -f "$REPO_DIR/.env" ]; then
    echo "   ⚠️  Creating .env with your credentials..."
    cat > "$REPO_DIR/.env" << 'ENVEOF'
# Django
DJANGO_SECRET_KEY=kshan-aws-prod-key-change-this-abc123xyz
DEBUG=False

# Database (Local SQLite)
DATABASE_URL=


# Firebase
FIREBASE_API_KEY=AIzaSyC0oJJ-j9nRAu6Hw55j21MGh2FgYH3nl6E
FIREBASE_AUTH_DOMAIN=kshanai.firebaseapp.com
FIREBASE_PROJECT_ID=kshanai
FIREBASE_STORAGE_BUCKET=kshanai.firebasestorage.app
FIREBASE_MESSAGING_SENDER_ID=670415123364
FIREBASE_APP_ID=1:670415123364:web:2483260fa09f10c01b0731

# Cloudflare R2 Storage
R2_ENABLED=True
R2_ACCESS_KEY_ID=413a841c58484ffb5a89f6f285a762ed
R2_SECRET_ACCESS_KEY=65a1b26c5a4cad9d68744508d968a6c1e82d8e73865cca9c4de975b762276431
R2_BUCKET_NAME=kshan
R2_ENDPOINT_URL=https://2454357021a59b9543557e633d183fcf.r2.cloudflarestorage.com
R2_ACCOUNT_ID=2454357021a59b9543557e633d183fcf

# Razorpay
RAZORPAY_KEY_ID=rzp_test_TWIs8CzYn94gAH
RAZORPAY_KEY_SECRET=nW0haPAjGN9toRSDwBqYWvlP
RAZORPAY_CURRENCY=INR

# Face Detection (buffalo_s works on 1GB RAM free tier)
FACE_RECOGNITION_ENABLED=True
INSIGHTFACE_MODEL=buffalo_s
ENVEOF
    echo "   ✅ .env created"
else
    echo "   ✅ .env already exists"
fi

# ── 7. Build & launch ───────────────────────────────────────────────
echo "▶ [7/8] Building Docker image and launching..."
echo "   (First build takes 5-10 min — downloading Python packages + InsightFace model)"
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
echo "  ✅  KSHAN is LIVE on AWS!"
echo "════════════════════════════════════════════════"
echo ""
echo "  🌐  URL:       http://$PUBLIC_IP"
echo "  👤  Admin:     username=thepranit  password=Debug@45"
echo "  💾  Storage:   Docker named volume (persistent)"
echo "  🗄️   Database:  Supabase PostgreSQL"
echo "  ☁️   Photos:    Cloudflare R2"
echo "  🧠  AI Model:  InsightFace buffalo_s (1GB safe)"
echo "  💿  Swap:      2GB (prevents OOM kills)"
echo ""
echo "  Useful commands:"
echo "  ┌─ View live logs:  cd ~/kshan && sudo docker-compose logs -f web"
echo "  ├─ Restart app:    cd ~/kshan && sudo docker-compose restart web"
echo "  ├─ Update & redeploy: cd ~/kshan && git pull && sudo docker-compose up -d --build"
echo "  └─ Check memory:   free -h"
echo ""

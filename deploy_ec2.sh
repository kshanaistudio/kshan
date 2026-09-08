#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# KSHAN AI Photo Suite — AWS EC2 Ubuntu 22.04 Deploy Script
# Run this ON your EC2 instance after SSH-ing in
# Usage: bash deploy_ec2.sh
# ═══════════════════════════════════════════════════════════════════
set -e

echo ""
echo "══════════════════════════════════════════"
echo "  🚀 KSHAN AWS EC2 Production Deploy"
echo "══════════════════════════════════════════"
echo ""

# ── 1. System Update ────────────────────────────────────────────────
echo "▶ Step 1: Updating system packages..."
sudo apt update && sudo apt upgrade -y

# ── 2. Install Docker ───────────────────────────────────────────────
echo "▶ Step 2: Installing Docker..."
sudo apt install -y docker.io docker-compose git curl ufw

sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker $USER

# ── 3. Firewall ─────────────────────────────────────────────────────
echo "▶ Step 3: Configuring firewall..."
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable

# ── 4. Clone / Update Repo ──────────────────────────────────────────
echo "▶ Step 4: Getting latest code from GitHub..."
REPO_DIR="/home/ubuntu/kshan"

if [ -d "$REPO_DIR/.git" ]; then
    echo "   Repo exists — pulling latest..."
    cd "$REPO_DIR"
    git pull origin main
else
    echo "   Cloning repo..."
    git clone https://github.com/kshanaistudio/kshan.git "$REPO_DIR"
    cd "$REPO_DIR"
fi

# ── 5. Create .env if not present ───────────────────────────────────
if [ ! -f "$REPO_DIR/.env" ]; then
    echo ""
    echo "⚠️  No .env file found! Creating template..."
    cat > "$REPO_DIR/.env" << 'ENVEOF'
# Django
DJANGO_SECRET_KEY=change-this-to-a-long-random-string-in-production
DEBUG=False

# Supabase PostgreSQL
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@db.rndharbouyewlfooykxl.supabase.co:5432/postgres

# Firebase
FIREBASE_API_KEY=AIzaSyC0oJJ-j9nRAu6Hw55j21MGh2FgYH3nl6E
FIREBASE_AUTH_DOMAIN=kshanai.firebaseapp.com
FIREBASE_PROJECT_ID=kshanai

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

# Face Detection
FACE_RECOGNITION_ENABLED=True
INSIGHTFACE_MODEL=buffalo_s
ENVEOF
    echo "   ✅ .env template created. Edit it if needed: nano $REPO_DIR/.env"
fi

# ── 6. Build & Start Docker ─────────────────────────────────────────
echo ""
echo "▶ Step 6: Building Docker image and starting containers..."
echo "   (This takes 3-5 minutes the first time — downloading InsightFace model)"
cd "$REPO_DIR"
sudo docker-compose down --remove-orphans 2>/dev/null || true
sudo docker-compose up -d --build

# ── 7. Wait for startup ─────────────────────────────────────────────
echo ""
echo "▶ Step 7: Waiting for server to start..."
sleep 15

# ── 8. Check status ─────────────────────────────────────────────────
echo ""
echo "▶ Step 8: Checking container status..."
sudo docker-compose ps

echo ""
echo "▶ Step 9: Checking logs..."
sudo docker-compose logs --tail=30 web

# ── 9. Get public IP ────────────────────────────────────────────────
PUBLIC_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || echo "unknown")

echo ""
echo "══════════════════════════════════════════"
echo "  ✅ KSHAN is now running on AWS EC2!"
echo "══════════════════════════════════════════"
echo ""
echo "  🌐 Access your app at: http://$PUBLIC_IP"
echo "  📁 Storage: Docker named volume (persistent)"
echo "  🗄️  Database: Supabase PostgreSQL"
echo "  ☁️  Photos: Cloudflare R2"
echo ""
echo "  Useful commands:"
echo "  - View logs:    sudo docker-compose logs -f web"
echo "  - Restart:      sudo docker-compose restart web"
echo "  - Update code:  git pull && sudo docker-compose up -d --build"
echo "  - Stop:         sudo docker-compose down"
echo ""

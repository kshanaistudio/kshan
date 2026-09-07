#!/bin/bash
set -e

echo "=================================================="
echo "🚀 Setting up KSHAN on AWS Ubuntu Instance"
echo "=================================================="

# 1. Update packages
sudo apt update && sudo apt upgrade -y

# 2. Install Docker & Docker Compose
sudo apt install -y docker.io docker-compose git curl ufw

# 3. Enable Docker service & permissions
sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker $USER

# 4. Open firewall ports (SSH + HTTP + HTTPS)
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable

echo "=================================================="
echo "✅ Server setup complete!"
echo "Next step: Run 'docker-compose up -d --build'"
echo "=================================================="

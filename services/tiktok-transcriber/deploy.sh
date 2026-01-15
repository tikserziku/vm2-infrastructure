#!/bin/bash
# TikTok Transcriber Deployment Script for Oracle VM

echo "========================================="
echo "   TikTok Transcriber Deployment"
echo "========================================="
echo ""

# Update system
echo "[1/7] Updating system packages..."
sudo apt-get update -y
sudo apt-get upgrade -y

# Install required packages
echo "[2/7] Installing required packages..."
sudo apt-get install -y python3 python3-pip python3-venv ffmpeg git curl wget

# Create virtual environment
echo "[3/7] Creating Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
echo "[4/7] Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Install yt-dlp
echo "[5/7] Installing yt-dlp..."
sudo curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o /usr/local/bin/yt-dlp
sudo chmod a+rx /usr/local/bin/yt-dlp

# Setup directories
echo "[6/7] Setting up directories..."
mkdir -p downloads
mkdir -p logs
mkdir -p temp
mkdir -p credentials
mkdir -p static/html
mkdir -p templates

# Start with PM2
echo "[7/7] Setting up PM2..."
sudo npm install -g pm2
pm2 delete tiktok-transcriber 2>/dev/null || true

# Create ecosystem file
cat > ecosystem.config.js << 'EOF'
module.exports = {
  apps: [{
    name: 'tiktok-transcriber',
    script: 'app.py',
    interpreter: './venv/bin/python3',
    instances: 1,
    autorestart: true,
    watch: false,
    max_memory_restart: '1G',
    env: {
      PORT: 10000,
      HOST: '0.0.0.0',
      FLASK_ENV: 'production',
      FLASK_DEBUG: '0'
    }
  }]
};
EOF

echo ""
echo "========================================="
echo "   Deployment Complete!"
echo "========================================="
echo ""
echo "To start the application:"
echo "  pm2 start ecosystem.config.js"
echo "  pm2 save"
echo "  pm2 startup"
echo ""


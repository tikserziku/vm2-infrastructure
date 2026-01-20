#!/bin/bash
# ============================================
# INSTALL ORACLE ADMIN API v2.0 on VM2
# ============================================
# 
# Этот скрипт установит backend для MCP Hub на VM2
# После установки MCP Hub (fly.dev) сможет управлять VM2
#
# Запуск: curl -sSL https://raw.githubusercontent.com/tikserziku/vm2-infrastructure/main/vm2-services/setup_admin_api.sh | bash
# ============================================

set -e

echo "🚀 Installing Oracle Admin API v2.0 on VM2..."

# 1. Create directories
echo "📁 Creating directories..."
mkdir -p /home/ubuntu/services
mkdir -p /home/ubuntu/logs

# 2. Install Python dependencies
echo "📦 Installing dependencies..."
pip3 install flask --break-system-packages 2>/dev/null || pip3 install flask

# 3. Download the API file from GitHub
echo "📄 Downloading oracle-admin-api.py..."
curl -sSL https://raw.githubusercontent.com/tikserziku/vm2-infrastructure/main/vm2-services/oracle-admin-api.py -o /home/ubuntu/oracle-admin-api.py
chmod +x /home/ubuntu/oracle-admin-api.py

# 4. Create systemd service
echo "⚙️ Creating systemd service..."
sudo tee /etc/systemd/system/oracle-admin-api.service > /dev/null << 'SYSTEMD'
[Unit]
Description=Oracle Admin API v2.0
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu
ExecStart=/usr/bin/python3 /home/ubuntu/oracle-admin-api.py
Restart=always
RestartSec=5
Environment=ADMIN_PORT=5001

[Install]
WantedBy=multi-user.target
SYSTEMD

# 5. Enable and start service
echo "🔄 Starting service..."
sudo systemctl daemon-reload
sudo systemctl enable oracle-admin-api
sudo systemctl restart oracle-admin-api

# 6. Wait and check
sleep 3
echo "✅ Checking service..."
if curl -s http://localhost:5001/health | grep -q "ok"; then
    echo "✅ Oracle Admin API is running!"
    echo ""
    echo "📍 Local: http://localhost:5001"
    echo "📍 Public: http://158.180.56.74:5001"
    echo ""
    echo "🔧 Test endpoints:"
    echo "   curl http://localhost:5001/health"
    echo "   curl http://localhost:5001/services/list"
    echo "   curl http://localhost:5001/system/stats"
else
    echo "❌ Service failed to start. Check logs:"
    echo "   sudo journalctl -u oracle-admin-api -n 50"
fi

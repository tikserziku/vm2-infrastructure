#!/bin/bash
# VM2 Recovery Setup Script
# Запускать на VM2 (158.180.56.74)

echo "🔧 VM2 Recovery Setup"
echo "===================="

# 1. Скачать vm_controller.py
echo "📥 Downloading VM Controller..."
curl -sL https://raw.githubusercontent.com/tikserziku/vm2-infrastructure/main/vm2-services/vm_controller.py -o ~/vm_controller.py
chmod +x ~/vm_controller.py

# 2. Установить зависимости
echo "📦 Installing dependencies..."
pip3 install flask requests --break-system-packages 2>/dev/null || pip3 install flask requests

# 3. Создать systemd сервис
echo "⚙️ Creating systemd service..."
sudo tee /etc/systemd/system/vm-controller.service > /dev/null << 'EOF'
[Unit]
Description=VM Controller - Manage VM1 from VM2
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu
ExecStart=/usr/bin/python3 /home/ubuntu/vm_controller.py
Restart=always
RestartSec=5
Environment=VM_CONTROLLER_KEY=vm-controller-2026

[Install]
WantedBy=multi-user.target
EOF

# 4. Запустить
echo "🚀 Starting VM Controller..."
sudo systemctl daemon-reload
sudo systemctl enable vm-controller
sudo systemctl start vm-controller

# 5. Проверить
sleep 2
if systemctl is-active --quiet vm-controller; then
    echo "✅ VM Controller running on port 5100"
    echo ""
    echo "🔗 Test: curl http://localhost:5100/health"
    echo ""
    curl -s http://localhost:5100/health | python3 -m json.tool 2>/dev/null || curl -s http://localhost:5100/health
else
    echo "❌ Failed to start. Check logs:"
    echo "   journalctl -u vm-controller -n 20"
fi

echo ""
echo "📋 Next steps:"
echo "1. Check if OCI CLI is installed: which oci"
echo "2. If not: pip3 install oci-cli --break-system-packages"
echo "3. Configure: oci setup config"
echo "4. Get VM1 OCID from Oracle Console"
echo "5. Add to service: sudo systemctl edit vm-controller"
echo "   Add: Environment=VM1_INSTANCE_OCID=ocid1.instance..."
echo "6. Restart: sudo systemctl restart vm-controller"

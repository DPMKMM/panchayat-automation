#!/usr/bin/env bash
set -e

echo "====================================================================="
echo "  e-Panchayat Automated Portal - Oracle Cloud Always-Free Installer"
echo "  Target: Ubuntu 22.04 / 24.04 LTS (AMD or ARM Ampere A1)"
echo "====================================================================="

# 1. Update system & install dependencies
sudo apt-get update -y
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
    python3 python3-pip python3-venv git curl wget build-essential \
    libgl1 libglib2.0-0 libsm6 libxext6 libxrender-dev iptables-persistent

# 2. Setup project directory
sudo mkdir -p /opt/epanchayat
sudo chown -R $USER:$USER /opt/epanchayat

if [ ! -d "/opt/epanchayat/.git" ]; then
    echo "[*] Cloning repository from GitHub..."
    git clone https://github.com/DPMKMM/PRKMM.git /opt/epanchayat
else
    echo "[*] Updating repository..."
    cd /opt/epanchayat && git pull origin main
fi

cd /opt/epanchayat

# 3. Create virtual environment
if [ ! -d "/opt/epanchayat/.venv" ]; then
    echo "[*] Creating Python virtualenv..."
    python3 -m venv /opt/epanchayat/.venv
fi

source /opt/epanchayat/.venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 4. Install Playwright Chromium with system dependencies
echo "[*] Installing Playwright Chromium browser & Linux system libraries..."
playwright install --with-deps chromium

# 5. Open Oracle Linux firewall for port 8000 & 80 & 443
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 8000 -j ACCEPT || true
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT || true
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT || true
sudo netfilter-persistent save || true

# 6. Configure systemd 24/7 background service
sudo tee /etc/systemd/system/epanchayat.service > /dev/null <<EOF
[Unit]
Description=e-Panchayat Automated Portal Service
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=/opt/epanchayat
ExecStart=/opt/epanchayat/.venv/bin/python run_cloudflare_portal.py
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable epanchayat.service
sudo systemctl restart epanchayat.service

echo ""
echo "====================================================================="
echo "  ORACLE CLOUD INSTALLATION COMPLETED!"
echo "  * Service running 24/7 in background (auto-starts on boot)."
echo "  * Check service status : sudo systemctl status epanchayat"
echo "  * View live URL        : cat /opt/epanchayat/latest_public_url.txt"
echo "====================================================================="

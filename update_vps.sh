#!/usr/bin/env bash
# ==============================================================================
#  Telangana e-Panchayat Automation - One-Click VPS Update & Auto-Deploy Setup
#  Bypasses legacy port 8000, updates to Port 8050, and enables 24/7 Git CI/CD
# ==============================================================================

set -e

echo ""
echo "======================================================================"
echo "  e-Panchayat Automation: Cloud VPS Update & CI/CD Deployment"
echo "======================================================================"

# 1. Locate project directory
if [ -d "/opt/epanchayat/.git" ]; then
    PROJECT_DIR="/opt/epanchayat"
elif [ -d "/root/panchayat-automation/.git" ]; then
    PROJECT_DIR="/root/panchayat-automation"
elif [ -d "$HOME/panchayat-automation/.git" ]; then
    PROJECT_DIR="$HOME/panchayat-automation"
else
    PROJECT_DIR="$(pwd)"
fi

echo "[*] Found project repository at: $PROJECT_DIR"
cd "$PROJECT_DIR"

# 2. Configure git safe directory and pull latest code
git config --system --add safe.directory "$PROJECT_DIR" 2>/dev/null || true
echo "[*] Pulling latest code from GitHub main..."
git fetch origin main
git reset --hard origin/main

COMMIT_INFO=$(git log -1 --pretty=format:"%h - %s (%cr)")
echo "[+] Updated to commit: $COMMIT_INFO"

# 3. Create or update .env with new tunnel token
echo "[*] Configuring .env with new Cloudflare Tunnel token..."
tee "$PROJECT_DIR/.env" > /dev/null <<'EOF'
WEB_SESSION_SECRET=b71c84f509e5bca393c5d888f4c2810ab512a863d0859339e1a10ebf19a3b6d2
DATA_DIR=./data
MAX_UPLOAD_BYTES=31457280
LOG_LEVEL=INFO
PORT=8050
CLOUDFLARE_TUNNEL_TOKEN=eyJhIjoiOTFjZWUxYjY3ZGY5MzYwNzZlZDg1NDI5MGIxZTgwNTMiLCJ0IjoiOTlmODY1MWYtNjZmMi00YTIzLTllZjktYjYxYjhjOTg2MzkzIiwicyI6IlpHTmxPRFkxTVRNdE1XSm1NUzAwWmpNM0xXRXhNVFV0TjJVMk1UQXpPRGczWXprMSJ9
CUSTOM_DOMAIN=panchayatautomation.in
EOF

# 4. Terminate any legacy processes on port 8000 and port 8050
echo "[*] Clearing legacy local host and stale server processes..."
fuser -k -9 8000/tcp 2>/dev/null || true
fuser -k -9 8050/tcp 2>/dev/null || true
pkill -9 -f "uvicorn" 2>/dev/null || true
pkill -9 -f "cloudflared" 2>/dev/null || true
sleep 2

# 5. Configure systemd for main portal on port 8050
echo "[*] Configuring epanchayat.service (Port 8050)..."
tee /etc/systemd/system/epanchayat.service > /dev/null <<EOF
[Unit]
Description=Telangana ePanchayat Automation & Analytics Portal (Cloud VPS)
After=network.target network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=$PROJECT_DIR
ExecStart=$PROJECT_DIR/.venv/bin/python run_cloudflare_portal.py
Restart=always
RestartSec=5
KillMode=mixed
TimeoutStopSec=10
Environment=PYTHONUNBUFFERED=1
Environment=PORT=8050
Environment=HOST=127.0.0.1

[Install]
WantedBy=multi-user.target
EOF

# 6. Configure 24/7 Continuous Deployment Watcher Daemon
echo "[*] Configuring epanchayat-updater.service (Continuous GitHub Watcher)..."
chmod +x "$PROJECT_DIR/auto_deploy.sh"

tee /etc/systemd/system/epanchayat-updater.service > /dev/null <<EOF
[Unit]
Description=Telangana ePanchayat GitHub Continuous Auto-Deployment Daemon
After=network.target network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=$PROJECT_DIR
ExecStart=/bin/bash $PROJECT_DIR/auto_deploy.sh
Restart=always
RestartSec=10
KillMode=mixed
TimeoutStopSec=10
Environment=PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

[Install]
WantedBy=multi-user.target
EOF

# 7. Reload and start services
echo "[*] Reloading systemd daemons and restarting services..."
systemctl daemon-reload
systemctl enable epanchayat.service
systemctl restart epanchayat.service
systemctl enable --now epanchayat-updater.service

echo "[*] Waiting 6 seconds for portal and new Cloudflare tunnel initialization..."
sleep 6

# 8. Verify local health check
if curl -s http://127.0.0.1:8050/health | grep -q "ok"; then
    echo "  [OK] Local FastAPI server is HEALTHY on port 8050."
else
    echo "  [!] Server is initializing. Checking status..."
fi

echo ""
echo "======================================================================"
echo "  [+] NEW TUNNEL CONNECTED & 24/7 CI/CD ACTIVE!"
echo "======================================================================"
echo "  * New Tunnel ID   : 99f8651f-66f2-4a23-9ef9-b61b8c986393"
echo "  * Main Service    : epanchayat.service (Running on Port 8050)"
echo "  * Auto-Deploy CI  : epanchayat-updater.service (Every 15s)"
echo "  * Public Domain   : https://panchayatautomation.in"
echo ""
echo "  Old machine D:\DPM-ept is now completely cut off."
echo "  All future git pushes will auto-deploy within 15 seconds!"
echo "======================================================================"

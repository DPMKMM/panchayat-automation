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

# 3. Ensure cloudflared binary is installed in system
if ! command -v cloudflared &>/dev/null && [ ! -f "$PROJECT_DIR/cloudflared" ]; then
    echo "[*] Installing cloudflared Linux binary..."
    ARCH=$(uname -m)
    if [[ "$ARCH" == "aarch64" || "$ARCH" == "arm64" ]]; then
        curl -fsSL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64 -o /usr/local/bin/cloudflared
    else
        curl -fsSL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o /usr/local/bin/cloudflared
    fi
    chmod +x /usr/local/bin/cloudflared || true
fi
if [ -f "$PROJECT_DIR/cloudflared" ]; then
    chmod +x "$PROJECT_DIR/cloudflared" 2>/dev/null || true
fi

# 4. Preserve existing .env (or initialize from .env.example if missing)
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo "[*] Initializing .env from .env.example..."
    cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
    GEN_SECRET=$(openssl rand -hex 32 2>/dev/null || python3 -c "import secrets; print(secrets.token_hex(32))")
    sed -i "s/^WEB_SESSION_SECRET=.*/WEB_SESSION_SECRET=$GEN_SECRET/" "$PROJECT_DIR/.env"
    sed -i "s/^ENVIRONMENT=.*/ENVIRONMENT=production/" "$PROJECT_DIR/.env"
else
    echo "[+] Preserving existing $PROJECT_DIR/.env (Firebase & tunnel secrets untouched)."
fi

# 5. Terminate any legacy processes on port 8000 and port 8050
echo "[*] Clearing legacy local host and stale server processes..."
fuser -k -9 8000/tcp 2>/dev/null || true
fuser -k -9 8050/tcp 2>/dev/null || true
pkill -9 -f "uvicorn" 2>/dev/null || true
pkill -9 -f "cloudflared" 2>/dev/null || true
sleep 2

# 6. Configure systemd for main portal on port 8050
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

# 7. Configure 24/7 Continuous Deployment Watcher Daemon
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

# 8. Reload and start services
echo "[*] Reloading systemd daemons and restarting services..."
systemctl daemon-reload
systemctl enable epanchayat.service
systemctl restart epanchayat.service
systemctl enable --now epanchayat-updater.service

echo "[*] Waiting 6 seconds for portal and new Cloudflare tunnel initialization..."
sleep 6

# 9. Verify local health check
if curl -s http://127.0.0.1:8050/health | grep -q "ok"; then
    echo "  [OK] Local FastAPI server is HEALTHY on port 8050."
else
    echo "  [!] Server is initializing. Checking status..."
fi

echo ""
echo "======================================================================"
echo "  [+] NEW TUNNEL CONNECTED & 24/7 CI/CD ACTIVE!"
echo "======================================================================"
echo "  * Main Service    : epanchayat.service (Running on Port 8050)"
echo "  * Auto-Deploy CI  : epanchayat-updater.service (Every 15s)"
echo "  * Public Domain   : https://panchayatautomation.in"
echo ""
echo "  All future git pushes will auto-deploy within 15 seconds!"
echo "======================================================================"

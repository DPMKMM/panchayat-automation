#!/usr/bin/env bash
# ==============================================================================
#  Telangana e-Panchayat Automation & Analytics Portal
#  Oracle Cloud Infrastructure (Always Free Tier - Hyderabad / Mumbai)
#  Automated 1-Click Production Setup & 24/7/365 High-Availability Daemon
# ==============================================================================
set -e

# Ensure core utilities (sudo, curl, git) exist on minimal images
if ! command -v sudo &>/dev/null || ! command -v curl &>/dev/null; then
    echo "[*] Installing fundamental tools (sudo, curl, git)..."
    apt-get update -y && apt-get install -y sudo curl git
fi

# Detect actual non-root user (e.g., ubuntu on Oracle Cloud)
ACTUAL_USER="${SUDO_USER:-$USER}"
if [ -z "$ACTUAL_USER" ] || [ "$ACTUAL_USER" = "root" ]; then
    if id "ubuntu" &>/dev/null; then
        ACTUAL_USER="ubuntu"
    else
        ACTUAL_USER="root"
    fi
fi
USER_HOME=$(eval echo "~$ACTUAL_USER")

echo "====================================================================="
echo "  e-Panchayat Automated Portal - Cloud 24/7 Production Setup"
echo "  Target: Ubuntu 22.04 / 24.04 LTS (India Datacenter)"
echo "  Running as system user: $ACTUAL_USER"
echo "====================================================================="

# 0. Setup Swap Space (if supported by virtualization environment)
echo "[*] Checking swap memory configuration..."
if swapon --show 2>/dev/null | grep -q 'swap'; then
    echo "[+] Swap is already active on host."
else
    echo "[*] Setting up swap space..."
    rm -f /swapfile 2>/dev/null || true
    fallocate -l 4G /swapfile 2>/dev/null || dd if=/dev/zero of=/swapfile bs=1M count=4096 status=none 2>/dev/null || true
    if [ -f /swapfile ]; then
        chmod 600 /swapfile 2>/dev/null || true
        mkswap /swapfile 2>/dev/null || true
        if swapon /swapfile 2>/dev/null; then
            echo "[+] 4GB swap memory enabled successfully."
            if ! grep -q '/swapfile' /etc/fstab 2>/dev/null; then
                echo '/swapfile none swap sw 0 0' >> /etc/fstab 2>/dev/null || true
            fi
        else
            echo "[*] Notice: Swap is managed by host kernel (LXC/Container). Recovering disk space..."
            rm -f /swapfile 2>/dev/null || true
        fi
    fi
fi

# Configure server timezone to Indian Standard Time (IST)
echo "[*] Setting server timezone to Asia/Kolkata (IST)..."
sudo timedatectl set-timezone Asia/Kolkata 2>/dev/null || sudo ln -sf /usr/share/zoneinfo/Asia/Kolkata /etc/localtime 2>/dev/null || true

# 1. Update system & install required packages
echo "[*] Updating apt packages and installing system libraries..."
sudo apt-get update -y
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
    python3 python3-pip python3-venv git curl wget build-essential jq cron \
    libgl1 libglib2.0-0 libsm6 libxext6 libxrender-dev iptables-persistent || true
sudo systemctl enable --now cron 2>/dev/null || true

# System graphic and audio libraries (handles Ubuntu 22.04 & 24.04 time_t naming)
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
    libgbm1 libpango-1.0-0 libcairo2 libasound2 libasound2t64 2>/dev/null || true

# 2. Architecture detection & cloudflared binary installation
ARCH=$(uname -m)
echo "[*] Detected CPU Architecture: $ARCH"
CLOUDFLARED_BIN="/usr/local/bin/cloudflared"

if [ ! -f "$CLOUDFLARED_BIN" ] || [ ! -s "$CLOUDFLARED_BIN" ]; then
    echo "[*] Installing Cloudflare Tunnel daemon for $ARCH..."
    if [[ "$ARCH" == "aarch64" || "$ARCH" == "arm64" ]]; then
        CF_URL="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64"
    else
        CF_URL="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"
    fi
    sudo curl -fsSL "$CF_URL" -o "$CLOUDFLARED_BIN"
    sudo chmod +x "$CLOUDFLARED_BIN"
    echo "[+] cloudflared installed to $CLOUDFLARED_BIN"
else
    echo "[+] cloudflared already present at $CLOUDFLARED_BIN"
fi

# 3. Setup Project Directory & Git Repository
PROJECT_DIR="/opt/epanchayat"
echo "[*] Setting up project directory at $PROJECT_DIR..."
sudo mkdir -p "$PROJECT_DIR"
sudo chown -R "$ACTUAL_USER":"$ACTUAL_USER" "$PROJECT_DIR"

if [ ! -d "$PROJECT_DIR/.git" ]; then
    echo "[*] Cloning production repository from GitHub..."
    sudo -u "$ACTUAL_USER" git clone https://github.com/DPMKMM/panchayat-automation.git "$PROJECT_DIR"
else
    echo "[*] Updating existing repository from GitHub main..."
    cd "$PROJECT_DIR"
    sudo -u "$ACTUAL_USER" git fetch origin main
    sudo -u "$ACTUAL_USER" git reset --hard origin/main
fi

cd "$PROJECT_DIR"

# 4. Configure .env safely without hardcoded secrets
echo "[*] Checking production .env configuration..."
ENV_FILE="$PROJECT_DIR/.env"
if [ ! -f "$ENV_FILE" ]; then
    sudo -u "$ACTUAL_USER" cp "$PROJECT_DIR/.env.example" "$ENV_FILE"
    GEN_SECRET=$(openssl rand -hex 32 2>/dev/null || python3 -c "import secrets; print(secrets.token_hex(32))")
    sudo -u "$ACTUAL_USER" sed -i "s/^WEB_SESSION_SECRET=.*/WEB_SESSION_SECRET=$GEN_SECRET/" "$ENV_FILE"
    sudo -u "$ACTUAL_USER" sed -i "s/^ENVIRONMENT=.*/ENVIRONMENT=production/" "$ENV_FILE"
    echo "[*] Created $ENV_FILE from .env.example. Populate FIREBASE_SERVICE_ACCOUNT_PATH, ADMIN_EMAILS, and CLOUDFLARE_TUNNEL_TOKEN."
else
    echo "[+] Preserving existing $ENV_FILE configuration."
fi

# 5. Setup Python Virtual Environment
echo "[*] Creating Python virtual environment..."
if [ ! -d "$PROJECT_DIR/.venv" ]; then
    sudo -u "$ACTUAL_USER" python3 -m venv "$PROJECT_DIR/.venv"
fi

sudo -u "$ACTUAL_USER" "$PROJECT_DIR/.venv/bin/pip" install --upgrade pip setuptools wheel
echo "[*] Installing Python dependencies..."
sudo -u "$ACTUAL_USER" "$PROJECT_DIR/.venv/bin/pip" install -r "$PROJECT_DIR/requirements.txt"

# 6. Install Playwright Headless Chromium
echo "[*] Installing Playwright Chromium browser & OS dependencies..."
sudo -u "$ACTUAL_USER" "$PROJECT_DIR/.venv/bin/python" -m playwright install-deps chromium 2>/dev/null || true
sudo -u "$ACTUAL_USER" "$PROJECT_DIR/.venv/bin/python" -m playwright install chromium

# 7. Configure Linux firewall rules (iptables)
echo "[*] Configuring host firewall rules..."
sudo iptables -I INPUT -p tcp --dport 8050 -j ACCEPT 2>/dev/null || true
sudo iptables -I INPUT -p tcp --dport 80 -j ACCEPT 2>/dev/null || true
sudo iptables -I INPUT -p tcp --dport 443 -j ACCEPT 2>/dev/null || true
sudo netfilter-persistent save 2>/dev/null || true

# 8. Setup 24/7 Systemd Service
echo "[*] Configuring systemd background daemon (/etc/systemd/system/epanchayat.service)..."
sudo tee /etc/systemd/system/epanchayat.service > /dev/null <<EOF
[Unit]
Description=Telangana ePanchayat Automation & Analytics Portal (24/7 Cloud Host)
After=network.target network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$ACTUAL_USER
WorkingDirectory=$PROJECT_DIR
ExecStart=$PROJECT_DIR/.venv/bin/python run_cloudflare_portal.py
Restart=always
RestartSec=5
KillMode=mixed
TimeoutStopSec=10
Environment=PYTHONUNBUFFERED=1
Environment=PORT=8050
Environment=HOST=0.0.0.0

[Install]
WantedBy=multi-user.target
EOF

# 9. Setup Auto-Pull & 24/7 Continuous Deployment Daemon
echo "[*] Installing 24/7 continuous deployment watcher daemon..."
sudo git config --system --add safe.directory "$PROJECT_DIR" 2>/dev/null || true
sudo chmod +x "$PROJECT_DIR/auto_deploy.sh" 2>/dev/null || true

sudo tee /etc/systemd/system/epanchayat-updater.service > /dev/null <<EOF
[Unit]
Description=Telangana ePanchayat Automatic GitHub Continuous Deployment Watcher
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

# Fallback cron job for auto-pull
sudo tee /usr/local/bin/epanchayat-autopull.sh > /dev/null <<'EOF'
#!/usr/bin/env bash
git config --system --add safe.directory /opt/epanchayat 2>/dev/null || true
cd /opt/epanchayat || exit 1
git fetch origin main -q 2>/dev/null || exit 0
LOCAL_HASH=$(git rev-parse HEAD 2>/dev/null)
REMOTE_HASH=$(git rev-parse origin/main 2>/dev/null)

if [ -n "$LOCAL_HASH" ] && [ -n "$REMOTE_HASH" ] && [ "$LOCAL_HASH" != "$REMOTE_HASH" ]; then
    echo "[$(date)] New update detected on GitHub main! Pulling changes..."
    git reset --hard origin/main
    .venv/bin/pip install -r requirements.txt -q 2>/dev/null || true
    systemctl restart epanchayat.service
    echo "[$(date)] Successfully updated and restarted epanchayat service."
fi
EOF
sudo chmod +x /usr/local/bin/epanchayat-autopull.sh

CRON_LINE="* * * * * /usr/local/bin/epanchayat-autopull.sh >> /var/log/epanchayat-autopull.log 2>&1"
(crontab -l 2>/dev/null | grep -v "epanchayat-autopull.sh" ; echo "$CRON_LINE") | crontab -

# 10. Enable & Start Services
sudo systemctl daemon-reload
sudo systemctl enable epanchayat.service
sudo systemctl enable --now epanchayat-updater.service 2>/dev/null || true
sudo systemctl restart epanchayat.service

echo ""
echo "====================================================================="
echo "  [+] PRODUCTION CLOUD HOST INSTALLATION COMPLETED SUCCESSFULLY!"
echo "====================================================================="
echo "  * Public Domain  : https://panchayatautomation.in"
echo "  * Alternate URL  : https://www.panchayatautomation.in"
echo "  * Local Port     : http://127.0.0.1:8050/"
echo "  * 24/7 Daemon    : epanchayat.service (Enabled on boot)"
echo "  * Continuous CI  : GitHub auto-pull active every 60s"
echo "====================================================================="
echo ""
echo "[*] Waiting for services to initialize..."
HEALTHY=false
for i in {1..15}; do
    if curl -s http://127.0.0.1:8050/health | grep -q "ok"; then
        HEALTHY=true
        break
    fi
    sleep 1
done

if [ "$HEALTHY" = true ]; then
    echo "  [OK] Local FastAPI server is HEALTHY on port 8050."
else
    echo "  [*] Service is initializing in background..."
fi

sudo systemctl status epanchayat --no-pager -l

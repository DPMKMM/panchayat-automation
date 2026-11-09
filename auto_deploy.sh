#!/usr/bin/env bash
# ==============================================================================
#  Telangana e-Panchayat Automation - 24/7 Continuous Deployment Watcher
#  Checks GitHub main every 15 seconds and automatically updates the server
# ==============================================================================

# Auto-detect project directory
if [ -d "/opt/epanchayat/.git" ]; then
    PROJECT_DIR="/opt/epanchayat"
elif [ -d "/root/panchayat-automation/.git" ]; then
    PROJECT_DIR="/root/panchayat-automation"
elif [ -d "$HOME/panchayat-automation/.git" ]; then
    PROJECT_DIR="$HOME/panchayat-automation"
else
    PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fi

BRANCH="main"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] [Deploy] Continuous Deployment Watcher active in $PROJECT_DIR"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] [Deploy] Monitoring GitHub repository branch: $BRANCH"

git config --system --add safe.directory "$PROJECT_DIR" 2>/dev/null || true
cd "$PROJECT_DIR" || exit 1

while true; do
    sleep 15

    # Quietly fetch origin main
    if ! git fetch origin "$BRANCH" --quiet 2>/dev/null; then
        continue
    fi

    LOCAL_HASH=$(git rev-parse HEAD 2>/dev/null)
    REMOTE_HASH=$(git rev-parse "origin/$BRANCH" 2>/dev/null)

    if [ -n "$LOCAL_HASH" ] && [ -n "$REMOTE_HASH" ] && [ "$LOCAL_HASH" != "$REMOTE_HASH" ]; then
        COMMIT_MSG=$(git log -1 --pretty=format:"%h - %s" "origin/$BRANCH" 2>/dev/null)
        echo ""
        echo "========================================================================"
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] [Deploy] New commit detected on GitHub $BRANCH!"
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] [Deploy] Commit: $COMMIT_MSG"
        echo "========================================================================"

        # Hard reset to match remote main exactly
        git reset --hard "origin/$BRANCH"

        # Update dependencies if requirements.txt changed
        if git diff --name-only "$LOCAL_HASH" "$REMOTE_HASH" | grep -q "requirements.txt"; then
            echo "[$(date '+%Y-%m-%d %H:%M:%S')] [Deploy] requirements.txt changed. Installing dependencies..."
            "$PROJECT_DIR/.venv/bin/pip" install -r "$PROJECT_DIR/requirements.txt" --quiet 2>/dev/null || true
        fi

        # Terminate any lingering uvicorn processes on 8000 & 8050
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] [Deploy] Stopping stale servers on ports 8000 and 8050..."
        fuser -k -9 8050/tcp 2>/dev/null || true
        fuser -k -9 8000/tcp 2>/dev/null || true
        pkill -9 -f "uvicorn" 2>/dev/null || true
        pkill -9 -f "python.*app:app" 2>/dev/null || true
        sleep 2

        # Restart the main application service
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] [Deploy] Restarting epanchayat.service..."
        systemctl restart epanchayat.service

        echo "[$(date '+%Y-%m-%d %H:%M:%S')] [Deploy] Deployment complete! Live on $(git rev-parse --short HEAD)."
        echo "========================================================================"
    fi
done

#!/usr/bin/env bash
# ==============================================================================
#  Telangana e-Panchayat Automation - 24/7 Continuous Deployment Watcher
#  Checks GitHub main every 30 seconds and automatically updates the server
# ==============================================================================

PROJECT_DIR="/opt/epanchayat"
BRANCH="main"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] [Deploy] e-Panchayat Continuous Deployment Watcher started."
echo "[$(date '+%Y-%m-%d %H:%M:%S')] [Deploy] Monitoring GitHub repository: DPMKMM/panchayat-automation (branch: $BRANCH)"

# Ensure git trusts the repository directory regardless of user
git config --system --add safe.directory "$PROJECT_DIR" 2>/dev/null || true
cd "$PROJECT_DIR" || exit 1

while true; do
    sleep 30

    # Fetch latest remote commits quietly
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

        # If requirements.txt was modified in this update, update pip dependencies
        if git diff --name-only "$LOCAL_HASH" "$REMOTE_HASH" | grep -q "requirements.txt"; then
            echo "[$(date '+%Y-%m-%d %H:%M:%S')] [Deploy] requirements.txt changed. Installing dependencies..."
            "$PROJECT_DIR/.venv/bin/pip" install -r "$PROJECT_DIR/requirements.txt" --quiet 2>/dev/null || true
        fi

        # Restart the main application service
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] [Deploy] Restarting epanchayat.service..."
        systemctl restart epanchayat.service

        echo "[$(date '+%Y-%m-%d %H:%M:%S')] [Deploy] Deployment complete! Live on $(git rev-parse --short HEAD)."
        echo "========================================================================"
    fi
done

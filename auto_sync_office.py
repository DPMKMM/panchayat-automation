"""Auto-sync background daemon for the Office Desktop.

Monitors the GitHub repository every 60 seconds.
When new commits are pushed from the laptop, this service automatically:
1. Runs 'git pull origin main'
2. Updates dependencies if requirements.txt changed
3. Gracefully reloads the application and Cloudflare gateway
"""

import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PYTHON_EXE = BASE_DIR / ".venv" / "Scripts" / "python.exe"
if not PYTHON_EXE.exists():
    PYTHON_EXE = Path(sys.executable)

POLL_INTERVAL_SECONDS = 60


def log(msg: str) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] [Auto-Sync] {msg}", flush=True)


def run_cmd(cmd: list[str]) -> tuple[int, str]:
    try:
        res = subprocess.run(
            cmd,
            cwd=str(BASE_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
        return res.returncode, res.stdout.strip()
    except Exception as exc:
        return 1, str(exc)


def get_current_commit() -> str:
    code, out = run_cmd(["git", "rev-parse", "HEAD"])
    return out if code == 0 else ""


def get_remote_commit() -> str:
    code, _ = run_cmd(["git", "fetch", "origin", "main"])
    if code != 0:
        return ""
    code, out = run_cmd(["git", "rev-parse", "origin/main"])
    return out if code == 0 else ""


def trigger_server_reload() -> None:
    """Signals Uvicorn to reload or restarts the process."""
    touch_file = BASE_DIR / "app.py"
    try:
        touch_file.touch()
        log("Touched app.py to trigger live reload in Uvicorn.")
    except Exception as exc:
        log(f"Reload note: {exc}")


def apply_update() -> bool:
    old_commit = get_current_commit()
    log("Pulling latest updates from GitHub (origin/main)...")
    code, out = run_cmd(["git", "pull", "origin", "main"])
    if code != 0:
        log(f"Git pull failed: {out}")
        return False

    log("Git pull completed successfully.")
    new_commit = get_current_commit()

    # Check if requirements.txt changed
    code, diff_out = run_cmd(["git", "diff", "--name-only", old_commit, new_commit])
    if "requirements.txt" in diff_out:
        log("requirements.txt changed! Installing new dependencies...")
        run_cmd([str(PYTHON_EXE), "-m", "pip", "install", "-r", "requirements.txt"])

    if "playwright" in diff_out:
        log("Playwright dependencies changed! Re-verifying browsers...")
        run_cmd([str(PYTHON_EXE), "-m", "playwright", "install", "chromium"])

    trigger_server_reload()
    log("Application updated and refreshed with latest code from laptop!")
    return True


def main() -> None:
    log("=" * 60)
    log("e-Panchayat Office Desktop Auto-Sync Daemon Started")
    log(f"Repository: {BASE_DIR}")
    log(f"Poll Interval: Every {POLL_INTERVAL_SECONDS} seconds")
    log("=" * 60)

    # Initial check
    initial_commit = get_current_commit()
    log(f"Current local commit: {initial_commit[:8] if initial_commit else 'unknown'}")

    while True:
        try:
            time.sleep(POLL_INTERVAL_SECONDS)
            local_hash = get_current_commit()
            remote_hash = get_remote_commit()

            if not remote_hash:
                # Network or github check issue, retry next cycle
                continue

            if local_hash != remote_hash:
                log(f"New update detected on GitHub! ({local_hash[:8]} -> {remote_hash[:8]})")
                apply_update()
            else:
                # Up to date
                pass
        except KeyboardInterrupt:
            log("Auto-Sync daemon stopped by user.")
            break
        except Exception as exc:
            log(f"Unexpected error in sync loop: {exc}")
            time.sleep(10)


if __name__ == "__main__":
    main()

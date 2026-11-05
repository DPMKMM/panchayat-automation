"""Auto-sync background daemon for the Office Desktop.

Monitors the GitHub repository every 60 seconds.
When new commits are pushed from the laptop, this service automatically:
1. Runs 'git fetch origin main' and 'git reset --hard origin/main'
2. Cleans any stale lock files (e.g. OneDrive index locks)
3. Updates dependencies if requirements.txt changed
4. Restarts the local Uvicorn web server so the new code takes effect immediately
"""

import os
import shutil
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

# Prevent Git from hanging on interactive prompts in background
ENV = os.environ.copy()
ENV["GIT_TERMINAL_PROMPT"] = "0"
ENV["GIT_ASKPASS"] = "echo"


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
            env=ENV,
        )
        return res.returncode, res.stdout.strip()
    except Exception as exc:
        return 1, str(exc)


def remove_stale_git_locks() -> None:
    """Removes stale .lock files that OneDrive sync might leave behind."""
    git_dir = BASE_DIR / ".git"
    if not git_dir.exists():
        return
    lock_files = [
        git_dir / "index.lock",
        git_dir / "refs" / "remotes" / "origin" / "main.lock",
        git_dir / "FETCH_HEAD.lock",
        git_dir / "HEAD.lock",
    ]
    for lf in lock_files:
        try:
            if lf.exists():
                lf.unlink()
                log(f"Removed stale lock file: {lf.name}")
        except Exception:
            pass


def configure_git_environment() -> None:
    """Ensures Git safe directory and sane defaults are configured."""
    # Fix 'dubious ownership' which occurs frequently in OneDrive or cross-machine folders
    run_cmd(["git", "config", "--global", "--add", "safe.directory", "*"])
    run_cmd(["git", "config", "safe.directory", "*"])
    remove_stale_git_locks()


def get_current_commit() -> str:
    code, out = run_cmd(["git", "rev-parse", "HEAD"])
    return out if code == 0 else ""


def get_remote_commit() -> tuple[str, str]:
    """Fetches origin/main and returns (commit_hash, error_message)."""
    remove_stale_git_locks()
    code, out = run_cmd(["git", "fetch", "origin", "main"])
    if code != 0:
        # Check if dubious ownership was the reason
        if "dubious ownership" in out:
            run_cmd(["git", "config", "--global", "--add", "safe.directory", "*"])
            code, out = run_cmd(["git", "fetch", "origin", "main"])
        if code != 0:
            return "", out

    code, hash_out = run_cmd(["git", "rev-parse", "origin/main"])
    return (hash_out, "") if code == 0 else ("", hash_out)


def restart_local_server() -> None:
    """Terminates old Uvicorn process on port 8000 and restarts it."""
    log("Refreshing local server on port 8000...")
    # Kill process on port 8000
    kill_cmd = (
        "Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | "
        "Select-Object -ExpandProperty OwningProcess -Unique | "
        "ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }"
    )
    run_cmd(["powershell", "-NoProfile", "-Command", kill_cmd])
    time.sleep(1.5)

    # Launch Uvicorn in background
    try:
        subprocess.Popen(
            [str(PYTHON_EXE), "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", "8000"],
            cwd=str(BASE_DIR),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=ENV,
        )
        log("[+] Local Uvicorn server restarted with latest code on port 8000.")
    except Exception as exc:
        log(f"[!] Warning restarting server: {exc}")


def apply_update() -> bool:
    old_commit = get_current_commit()
    log(f"Starting repository update from GitHub (origin/main)...")

    # 1. Force fetch and hard reset to guarantee clean sync without merge conflicts
    remove_stale_git_locks()
    code, fetch_out = run_cmd(["git", "fetch", "--all", "--prune"])
    if code != 0:
        log(f"Git fetch error: {fetch_out}")

    code, reset_out = run_cmd(["git", "reset", "--hard", "origin/main"])
    if code != 0:
        log(f"Git reset failed: {reset_out}. Trying git pull as fallback...")
        code, pull_out = run_cmd(["git", "pull", "origin", "main"])
        if code != 0:
            log(f"Git pull also failed: {pull_out}")
            return False

    new_commit = get_current_commit()
    log(f"Git synchronized successfully! ({old_commit[:8]} -> {new_commit[:8]})")

    # 2. Check if requirements.txt changed
    if old_commit and new_commit and old_commit != new_commit:
        code, diff_out = run_cmd(["git", "diff", "--name-only", old_commit, new_commit])
        if "requirements.txt" in diff_out:
            log("requirements.txt changed! Installing new dependencies...")
            run_cmd([str(PYTHON_EXE), "-m", "pip", "install", "-r", "requirements.txt", "--quiet"])

        if "playwright" in diff_out:
            log("Playwright changed! Ensuring browsers are installed...")
            run_cmd([str(PYTHON_EXE), "-m", "playwright", "install", "chromium"])

    # 3. Touch app.py and restart Uvicorn
    touch_file = BASE_DIR / "app.py"
    try:
        touch_file.touch()
    except Exception:
        pass

    restart_local_server()
    log("==============================================================")
    log(f"SUCCESS: System updated to commit {new_commit[:8]}!")
    log("Live application is refreshed and running latest code.")
    log("==============================================================")
    return True


def check_and_sync(first_run: bool = False) -> None:
    local_hash = get_current_commit()
    local_short = local_hash[:8] if local_hash else "unknown"

    if first_run:
        log(f"Current local commit: {local_short}")

    log("Checking GitHub for updates (origin/main)...")
    remote_hash, err = get_remote_commit()

    if not remote_hash:
        log(f"[!] GitHub check note: Could not reach origin/main. Error: {err or 'Unknown'}")
        log("    (Will automatically retry on next cycle in 60s)")
        return

    remote_short = remote_hash[:8]

    if local_hash != remote_hash:
        log(f"[*] NEW UPDATE FOUND on GitHub! Local: {local_short} -> Remote: {remote_short}")
        apply_update()
    else:
        log(f"[+] Synchronized. Local commit {local_short} is up to date with GitHub.")


def main() -> None:
    log("=" * 62)
    log("  e-Panchayat Office Desktop Auto-Sync Daemon v2.0")
    log(f"  Repository: {BASE_DIR}")
    log(f"  Poll Interval: Every {POLL_INTERVAL_SECONDS} seconds")
    log("=" * 62)

    configure_git_environment()

    # Perform immediate check right on startup (do not wait 60s!)
    try:
        check_and_sync(first_run=True)
    except Exception as exc:
        log(f"Error during initial sync check: {exc}")

    # Polling loop
    while True:
        try:
            time.sleep(POLL_INTERVAL_SECONDS)
            check_and_sync(first_run=False)
        except KeyboardInterrupt:
            log("Auto-Sync daemon stopped by user.")
            break
        except Exception as exc:
            log(f"Unexpected error in sync loop: {exc}")
            time.sleep(10)


if __name__ == "__main__":
    main()

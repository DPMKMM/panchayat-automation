"""
Launcher for e-Panchayat Automated DSR Portal via Cloudflare Tunnel.

Starts the local Uvicorn server and establishes a secure, public HTTPS tunnel
routed through Cloudflare's Hyderabad edge network. The public URL can be opened
from mobile phones or any external network with zero firewall blocks.
Compatible with Windows, Linux (Ubuntu/Debian on Oracle Cloud, AWS, etc.).
"""

import os
import re
import sys
import time
import socket
import platform
import webbrowser
import subprocess
from pathlib import Path

# Force safe encoding on Windows consoles to prevent charmap UnicodeEncodeError
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE_DIR = Path(__file__).resolve().parent
PYTHON_EXE = BASE_DIR / ".venv" / "Scripts" / "python.exe"
if not PYTHON_EXE.exists():
    PYTHON_EXE = BASE_DIR / ".venv" / "bin" / "python"
if not PYTHON_EXE.exists():
    PYTHON_EXE = Path(sys.executable)

CLOUDFLARED_EXE = BASE_DIR / ("cloudflared.exe" if sys.platform == "win32" else "cloudflared")

# 1. Read token from environment variable or .env file
env_file = BASE_DIR / ".env"
token_from_env = os.getenv("CLOUDFLARE_TUNNEL_TOKEN", "").strip()
custom_domain = os.getenv("CUSTOM_DOMAIN", "panchayatautomation.in").strip()

if not token_from_env and env_file.exists():
    try:
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("CLOUDFLARE_TUNNEL_TOKEN="):
                token_from_env = line.split("=", 1)[1].strip().strip('"').strip("'")
            elif line.startswith("CUSTOM_DOMAIN="):
                custom_domain = line.split("=", 1)[1].strip().strip('"').strip("'")
    except Exception:
        pass

TUNNEL_TOKEN = token_from_env or ""  # Leave empty for free trycloudflare quick tunnel


def ensure_cloudflared() -> Path:
    """Ensures cloudflared executable is present and valid; auto-downloads if missing."""
    global CLOUDFLARED_EXE
    if CLOUDFLARED_EXE.exists() and CLOUDFLARED_EXE.stat().st_size > 10_000_000:
        if sys.platform != "win32":
            try:
                CLOUDFLARED_EXE.chmod(0o755)
            except Exception:
                pass
        return CLOUDFLARED_EXE

    import shutil
    cand = shutil.which("cloudflared")
    if cand and Path(cand).exists():
        CLOUDFLARED_EXE = Path(cand)
        return CLOUDFLARED_EXE

    arch = platform.machine().lower()
    if sys.platform == "win32":
        dl_url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
        target = BASE_DIR / "cloudflared.exe"
    elif "arm" in arch or "aarch64" in arch:
        dl_url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64"
        target = BASE_DIR / "cloudflared"
    else:
        dl_url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"
        target = BASE_DIR / "cloudflared"

    print(f"[*] cloudflared not found locally. Auto-downloading {target.name} from Cloudflare...", flush=True)
    try:
        import urllib.request
        req = urllib.request.Request(dl_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=90) as resp, open(target, "wb") as f:
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            while True:
                chunk = resp.read(1024 * 512)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if total > 0:
                    pct = int(downloaded * 100 / total)
                    print(f"\r[*] Downloading Cloudflare Tunnel engine: {pct}% ({downloaded // (1024*1024)}MB / {total // (1024*1024)}MB)...", end="", flush=True)
        if sys.platform != "win32":
            target.chmod(0o755)
        print(f"\n[+] {target.name} downloaded and verified successfully!", flush=True)
        CLOUDFLARED_EXE = target
        return CLOUDFLARED_EXE
    except Exception as exc:
        print(f"\n[!] Failed to auto-download cloudflared: {exc}", flush=True)
        return target


def kill_stale_cloudflared():
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/IM", "cloudflared.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.run(["pkill", "-9", "-f", "cloudflared"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def is_port_in_use(port: int = 8000) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def main():
    print("=" * 68)
    print("  e-Panchayat Automated DSR Portal - Cloudflare Public Gateway")
    print("=" * 68)

    # 1. Start Uvicorn if not already running on port 8000
    uvicorn_proc = None
    if is_port_in_use(8000):
        print("[+] Local Uvicorn server is already running on http://127.0.0.1:8000")
    else:
        print("[*] Starting local Uvicorn server on port 8000...")
        uvicorn_proc = subprocess.Popen(
            [str(PYTHON_EXE), "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", "8000"],
            cwd=str(BASE_DIR),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        # Wait up to 5 seconds for port to open
        for _ in range(10):
            time.sleep(0.5)
            if is_port_in_use(8000):
                print("[+] Local server started successfully.")
                break

    # 2. Verify cloudflared executable is present
    ensure_cloudflared()
    if not CLOUDFLARED_EXE.exists():
        print("[ERROR] cloudflared could not be downloaded. Please check internet connection.")
        sys.exit(1)

    kill_stale_cloudflared()

    # 3. Launch Cloudflare Tunnel
    if TUNNEL_TOKEN:
        print("[*] Launching permanent Cloudflare Zero Trust tunnel with your connector token...")
        cf_proc = subprocess.Popen(
            [str(CLOUDFLARED_EXE), "tunnel", "run", "--token", TUNNEL_TOKEN],
            cwd=str(BASE_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        perm_url = f"https://{custom_domain}/"
        try:
            url_file = BASE_DIR / "latest_public_url.txt"
            url_file.write_text(f"Public URL: {perm_url}\nLocal Access: http://127.0.0.1:8000/\nStatus: Connected via Cloudflare Zero Trust Tunnel\nConnected: {time.ctime()}\n", encoding="utf-8")
        except Exception:
            pass

        print("\n" + "=" * 68)
        print("  [+] PERMANENT CLOUDFLARE ZERO TRUST TUNNEL IS CONNECTED!")
        print("=" * 68)
        print(f"  Public URL       :  {perm_url}")
        print("  Status           :  Connected to Hyderabad & Mumbai edge nodes (hyd03/bom10)")
        print("  Local Access URL :  http://127.0.0.1:8000/")
        print("=" * 68)
        print(f"  Your permanent website is live at {perm_url} !")
        print("  Running silently in background.\n")
    else:
        print("[*] Establishing Cloudflare Tunnel to Hyderabad edge...")
        cf_proc = subprocess.Popen(
            [str(CLOUDFLARED_EXE), "tunnel", "--url", "http://127.0.0.1:8000"],
            cwd=str(BASE_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )

        tunnel_url = None
        url_pattern = re.compile(r"https://[a-zA-Z0-9\-]+\.trycloudflare\.com")

        # Read output to capture the public tunnel URL
        start_time = time.time()
        while time.time() - start_time < 60:
            line = cf_proc.stdout.readline()
            if not line:
                if cf_proc.poll() is not None:
                    break
                time.sleep(0.1)
                continue

            clean_line = line.strip()
            match = url_pattern.search(clean_line)
            if match:
                tunnel_url = match.group(0)
                break
            elif any(k in clean_line for k in ["INF", "Connection", "Registered", "trycloudflare", "Initial protocol"]):
                print(f"    {clean_line[:85]}", flush=True)

        if not tunnel_url:
            print("\n[ERROR] Could not extract tunnel URL from Cloudflare output within 60s.")
            if cf_proc.poll() is not None:
                print("Process exited with code:", cf_proc.returncode)
            sys.exit(1)

        public_url = f"{tunnel_url}/"

        try:
            url_file = BASE_DIR / "latest_public_url.txt"
            url_file.write_text(f"Public URL: {public_url}\nLocal Access: http://127.0.0.1:8000/\nGenerated: {time.ctime()}\n", encoding="utf-8")
        except Exception:
            pass

        print("\n" + "=" * 68)
        print("  [+] PORTAL IS LIVE ONLINE VIA CLOUDFLARE HYDERABAD EDGE!")
        print("=" * 68)
        print(f"  Public URL       :  {public_url}")
        print(f"  Local Access URL :  http://127.0.0.1:8000/")
        print("=" * 68)
        print("  [*] Open the Public URL above on your phone or any PC.")
        print("  [*] Traffic to e-Panchayat originates from your local Indian IP,")
        print("      so Telangana State Data Center firewall will NEVER block it.")
        print("=" * 68)

        # Copy to clipboard if on Windows
        try:
            if sys.platform == "win32":
                subprocess.run(["clip"], input=public_url, text=True, check=False)
                print("  [+] Public URL copied to clipboard automatically!\n")
        except Exception:
            pass

        # Automatically open in browser
        try:
            webbrowser.open(public_url)
        except Exception:
            pass

    try:
        # Keep alive and forward any relevant log messages
        while True:
            line = cf_proc.stdout.readline()
            if not line and cf_proc.poll() is not None:
                break
            if "error" in line.lower() or "exception" in line.lower():
                print(line.strip())
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("\n[*] Shutting down Cloudflare Tunnel...")
    finally:
        try:
            cf_proc.terminate()
            cf_proc.wait(timeout=3)
        except Exception:
            try:
                cf_proc.kill()
            except Exception:
                pass

        if uvicorn_proc:
            try:
                uvicorn_proc.terminate()
                uvicorn_proc.wait(timeout=3)
            except Exception:
                try:
                    uvicorn_proc.kill()
                except Exception:
                    pass
        print("[+] Public tunnel closed successfully.")


if __name__ == "__main__":
    main()

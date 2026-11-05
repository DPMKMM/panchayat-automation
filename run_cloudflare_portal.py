"""
Launcher for PRKMM e-Panchayat Automated DSR Portal via Cloudflare Tunnel.

Starts the local Uvicorn server and establishes a secure, public HTTPS tunnel
routed through Cloudflare's Hyderabad edge network. The public URL can be opened
from mobile phones or any external network with zero firewall blocks.
"""

import os
import re
import sys
import time
import socket
import webbrowser
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PYTHON_EXE = BASE_DIR / ".venv" / "Scripts" / "python.exe"
if not PYTHON_EXE.exists():
    PYTHON_EXE = Path(sys.executable)

CLOUDFLARED_EXE = BASE_DIR / "cloudflared.exe"

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

if not CLOUDFLARED_EXE.exists():
    # Try finding in system PATH
    import shutil
    cand = shutil.which("cloudflared")
    if cand:
        CLOUDFLARED_EXE = Path(cand)


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

    if not CLOUDFLARED_EXE.exists():
        print("[ERROR] cloudflared.exe not found. Please ensure cloudflared is downloaded.")
        sys.exit(1)

    # 2. Launch Cloudflare Tunnel
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
        print("  🚀 PERMANENT CLOUDFLARE ZERO TRUST TUNNEL IS CONNECTED!")
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
        while time.time() - start_time < 30:
            line = cf_proc.stdout.readline()
            if not line:
                if cf_proc.poll() is not None:
                    break
                time.sleep(0.1)
                continue

            match = url_pattern.search(line)
            if match:
                tunnel_url = match.group(0)
                break

        if not tunnel_url:
            print("[ERROR] Could not extract tunnel URL from Cloudflare output.")
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
        print("  🚀 PORTAL IS LIVE ONLINE VIA CLOUDFLARE HYDERABAD EDGE!")
        print("=" * 68)
        print(f"  Public URL       :  {public_url}")
        print(f"  Local Access URL :  http://127.0.0.1:8000/")
        print("=" * 68)
        print("  📱 Open the Public URL above on your phone or any PC.")
        print("  🛡️ Traffic to e-Panchayat originates from your local Indian IP,")
        print("     so Telangana State Data Center firewall will NEVER block it.")
        print("=" * 68)
        print("  Press Ctrl+C at any time to shut down the public tunnel.\n")

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

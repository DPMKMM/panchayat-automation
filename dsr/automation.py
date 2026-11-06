"""
e-Panchayat Telangana (EPTS) Automated Login & Report Downloader
Module: automate_epts/epts_automation.py

Features:
- Persistent browser session in automate_epts/browser_profile
- Automated login with ddddocr captcha solving
- OTP reception via automate_epts/otp.txt or prompt
- Interactive command execution via automate_epts/command.txt or CLI
- File downloads saved in automate_epts/downloads/
"""

import os
import sys
import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import ddddocr

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
DATA_DIR = ROOT_DIR / "data"
DOWNLOADS_DIR = DATA_DIR / "downloads"
CONFIG_FILE = BASE_DIR / "config.json"
CAPTCHA_CACHE_FILE = DATA_DIR / "temp_captcha.png"
OTP_FILE = DATA_DIR / "otp.txt"
COMMAND_FILE = DATA_DIR / "command.txt"
OTP_SCREENSHOT = DATA_DIR / "otp_screen.png"
DASHBOARD_SCREENSHOT = DATA_DIR / "dashboard_screen.png"
CURRENT_SCREENSHOT = DATA_DIR / "current_screen.png"
PROFILE_DIR = DATA_DIR / "browser_profiles" / "default"

DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
PROFILE_DIR.mkdir(parents=True, exist_ok=True)


def load_config():
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_config(config_data):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config_data, f, indent=4)


class EPTSAutomation:
    def __init__(self, headless=False, profile_dir=None, downloads_dir=None):
        self.headless = headless
        self.profile_dir = Path(profile_dir) if profile_dir else PROFILE_DIR
        self.downloads_dir = Path(downloads_dir) if downloads_dir else DOWNLOADS_DIR
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self.downloads_dir.mkdir(parents=True, exist_ok=True)
        self.playwright = None
        self.context = None
        self.page = None
        self.ocr = ddddocr.DdddOcr(show_ad=False)

    def start_browser(self):
        print(f"[*] Launching Chrome with persistent profile at {self.profile_dir} (Headless: {self.headless})...", flush=True)
        self.playwright = sync_playwright().start()
        launch_args = ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu", "--disable-blink-features=AutomationControlled"]
        try:
            self.context = self.playwright.chromium.launch_persistent_context(
                user_data_dir=str(self.profile_dir),
                channel="chrome",
                headless=self.headless,
                accept_downloads=True,
                downloads_path=str(self.downloads_dir),
                args=launch_args,
            )
        except Exception as e:
            print(f"[-] Chrome channel launch failed ({e}), attempting msedge channel...", flush=True)
            try:
                self.context = self.playwright.chromium.launch_persistent_context(
                    user_data_dir=str(self.profile_dir),
                    channel="msedge",
                    headless=self.headless,
                    accept_downloads=True,
                    downloads_path=str(self.downloads_dir),
                    args=launch_args,
                )
            except Exception as e_edge:
                print(f"[-] msedge channel launch failed ({e_edge}), falling back to default Chromium...", flush=True)
                self.context = self.playwright.chromium.launch_persistent_context(
                    user_data_dir=str(self.profile_dir),
                    headless=self.headless,
                    accept_downloads=True,
                    downloads_path=str(self.downloads_dir),
                    args=launch_args,
                )
        self.page = self.context.pages[0] if self.context.pages else self.context.new_page()

    def is_logged_in(self):
        try:
            print("[*] Checking if active session already exists...", flush=True)
            self.page.goto("https://epanchayat.telangana.gov.in/deptLoginVerified", wait_until="domcontentloaded", timeout=15000)
            time.sleep(1)
            if "deptLoginVerified" in self.page.url and "Office ID:" in self.page.content():
                print("[+] Active session verified! Already logged in.", flush=True)
                self.page.screenshot(path=str(DASHBOARD_SCREENSHOT))
                return True
        except Exception as e:
            print(f"[-] Session check note: {e}", flush=True)
        return False

    def navigate_home(self):
        url = "https://epanchayat.telangana.gov.in/cs"
        print(f"[*] Navigating to {url} ...", flush=True)
        self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
        time.sleep(1)

    def open_department_login_modal(self):
        print("[*] Opening 'Department Login' modal...", flush=True)
        dept_link = self.page.locator("a:has-text('Department Login')").first
        dept_link.wait_for(state="visible", timeout=10000)
        dept_link.click()
        self.page.wait_for_selector("#userId", state="visible", timeout=10000)
        print("[+] Department Login modal is open.", flush=True)

    def solve_captcha(self, retries=5):
        for attempt in range(1, retries + 1):
            time.sleep(0.5)
            captcha_img = self.page.locator("#img1")
            captcha_img.wait_for(state="visible", timeout=5000)
            img_bytes = captcha_img.screenshot()
            
            with open(CAPTCHA_CACHE_FILE, "wb") as f:
                f.write(img_bytes)
                
            code = self.ocr.classification(img_bytes)
            code = code.strip().replace(" ", "").lower()
            if len(code) >= 4:
                print(f"[+] Captcha auto-detected (attempt {attempt}): {code}", flush=True)
                return code
            else:
                print(f"[-] Low confidence on captcha '{code}', refreshing...", flush=True)
                refresh_btn = self.page.locator("button.fa-refresh").first
                if refresh_btn.is_visible():
                    try:
                        with self.page.expect_response(lambda r: "CaptchaServlet" in r.url, timeout=5000):
                            refresh_btn.click()
                    except Exception:
                        refresh_btn.click()
                time.sleep(1)
        return ""

    def submit_credentials_and_generate_otp(self, username, password):
        max_attempts = 5
        for attempt in range(1, max_attempts + 1):
            print(f"[*] Entering credentials (attempt {attempt})...", flush=True)
            self.page.fill("#userId", username)
            self.page.fill("#npwd", password)
            
            captcha_text = self.solve_captcha()
            print(f"[*] Filling captcha field: {captcha_text}", flush=True)
            self.page.fill("#cp", captcha_text)
            
            # Clear previous error message if present
            self.page.evaluate("() => { const el = document.getElementById('pvals'); if(el) el.innerText = ''; }")
            
            print("[*] Clicking 'Generate OTP to Login'...", flush=True)
            submit_btn = self.page.locator("#submit1")
            
            try:
                with self.page.expect_navigation(timeout=10000):
                    submit_btn.click()
            except Exception:
                time.sleep(2)
            
            # Check if OTP screen reached
            if "login" in self.page.url.lower() or self.page.locator("#otp").is_visible() or self.page.locator("input[placeholder*='otp' i]").is_visible():
                print("[+] OTP generation triggered successfully! Reached OTP verification screen.", flush=True)
                time.sleep(1)
                self.page.screenshot(path=str(OTP_SCREENSHOT))
                print(f"[+] Saved OTP screen to {OTP_SCREENSHOT}", flush=True)
                return True

            pvals = self.page.locator("#pvals")
            error_text = pvals.inner_text().strip() if pvals.is_visible() else ""
            
            if "invalid captcha" in error_text.lower():
                print(f"[-] Captcha rejected by server. Retrying with fresh captcha...", flush=True)
                # Re-open modal if needed
                if not self.page.locator("#userId").is_visible():
                    self.open_department_login_modal()
                else:
                    refresh_btn = self.page.locator("button.fa-refresh").first
                    if refresh_btn.is_visible():
                        try:
                            with self.page.expect_response(lambda r: "CaptchaServlet" in r.url, timeout=5000):
                                refresh_btn.click()
                        except Exception:
                            refresh_btn.click()
                        time.sleep(1)
                continue
            
            if error_text:
                print(f"[!] Server message: {error_text}", flush=True)
                if "invalid user" in error_text.lower() or "password" in error_text.lower():
                    raise ValueError(f"Login failed: {error_text}")
                
        raise RuntimeError("Failed to generate OTP after multiple captcha attempts.")

    def prompt_and_validate_otp(self, otp_code=None):
        print("[*] Waiting for OTP input screen...", flush=True)
        
        if OTP_FILE.exists():
            try:
                OTP_FILE.unlink()
            except Exception:
                pass

        try:
            self.page.wait_for_selector("#otp, input[placeholder*='otp' i]", state="visible", timeout=15000)
        except PlaywrightTimeoutError:
            print("[!] Note: Checking page URL:", self.page.url, flush=True)

        if not otp_code:
            print("\n" + "="*55, flush=True)
            print(">>> A 6-digit OTP has been sent to your registered mobile.", flush=True)
            print(f">>> Write OTP to {OTP_FILE} or enter it here.", flush=True)
            print("="*55 + "\n", flush=True)
            
            start_wait = time.time()
            while time.time() - start_wait < 300:
                if OTP_FILE.exists():
                    val = OTP_FILE.read_text(encoding="utf-8").strip()
                    if len(val) == 6 and val.isdigit():
                        otp_code = val
                        print(f"[+] Received OTP from {OTP_FILE}: {otp_code}", flush=True)
                        break
                time.sleep(1)

        if not otp_code:
            raise TimeoutError("Timed out waiting for OTP entry.")

        print(f"[*] Entering OTP: {otp_code} ...", flush=True)
        if self.page.locator("#otp").is_visible():
            self.page.fill("#otp", otp_code)
        else:
            self.page.fill("input[placeholder*='otp' i]", otp_code)

        time.sleep(0.5)
        print("[*] Clicking 'Validate OTP'...", flush=True)
        validate_btn = self.page.locator("button:has-text('Validate OTP'), input[value='Validate OTP']").first
        validate_btn.click()

        print("[*] Validating OTP on portal...", flush=True)
        time.sleep(4)

        current_url = self.page.url
        print(f"[+] Current URL after OTP validation: {current_url}", flush=True)
        self.page.screenshot(path=str(DASHBOARD_SCREENSHOT))
        print(f"[+] Saved dashboard screenshot to {DASHBOARD_SCREENSHOT}", flush=True)

        try:
            self.context.storage_state(path=str(STORAGE_STATE_FILE))
            print(f"[+] Session state saved to {STORAGE_STATE_FILE}", flush=True)
        except Exception as e:
            print(f"[-] Note on saving storage state: {e}", flush=True)
        return True

    def ensure_logged_in(self):
        self.start_browser()
        if self.is_logged_in():
            return True

        config = load_config()
        username = config.get("username", "")
        password = config.get("password")
        if not password:
            raise ValueError("Password not found in config.json")

        self.navigate_home()
        self.open_department_login_modal()
        self.submit_credentials_and_generate_otp(username, password)
        self.prompt_and_validate_otp()
        return True

    def select_menu(self, menu_name):
        print(f"[*] Selecting menu item: '{menu_name}' ...", flush=True)
        # Check if direct text match exists
        target = self.page.locator(f"text='{menu_name}'").first
        if not target.is_visible():
            target = self.page.locator(f"a:has-text('{menu_name}')").first
            
        target.wait_for(state="visible", timeout=10000)
        
        # Hover to see if dropdown expands, or click
        target.hover()
        time.sleep(0.5)
        target.click()
        time.sleep(2)
        
        self.page.screenshot(path=str(CURRENT_SCREENSHOT))
        print(f"[+] Clicked '{menu_name}'. Current URL: {self.page.url}", flush=True)
        print(f"[+] Screenshot saved to {CURRENT_SCREENSHOT}", flush=True)

    def close(self):
        if self.context:
            self.context.close()
        if self.playwright:
            self.playwright.stop()


def main():
    print("=" * 60)
    print(" e-Panchayat Telangana (EPTS) Automated Report Downloader")
    print("=" * 60)
    
    app = EPTSAutomation(headless=False)
    try:
        app.ensure_logged_in()
        
        print("\n" + "="*60, flush=True)
        print("[READY] Browser is active and logged in!", flush=True)
        print(f"Listening for commands in {COMMAND_FILE} ...", flush=True)
        print("="*60, flush=True)
        
        if COMMAND_FILE.exists():
            try:
                COMMAND_FILE.unlink()
            except Exception:
                pass

        while True:
            cmd = None
            if COMMAND_FILE.exists():
                try:
                    cmd = COMMAND_FILE.read_text(encoding="utf-8").strip()
                    COMMAND_FILE.unlink()
                except Exception:
                    pass

            if not cmd:
                time.sleep(1)
                continue

            print(f"\n[COMMAND] Executing: {cmd}", flush=True)
            if cmd.lower() in ["exit", "quit", "q"]:
                break
            elif cmd.lower().startswith("select "):
                menu_name = cmd[7:].strip()
                app.select_menu(menu_name)
            elif cmd.lower() == "url":
                print("Current page URL:", app.page.url, flush=True)
            elif cmd.lower().startswith("goto "):
                target_url = cmd[5:].strip()
                print(f"Navigating to {target_url}...", flush=True)
                app.page.goto(target_url)
                time.sleep(2)
                app.page.screenshot(path=str(CURRENT_SCREENSHOT))
            elif cmd.lower() == "screenshot":
                app.page.screenshot(path=str(CURRENT_SCREENSHOT))
                print(f"Saved screenshot to {CURRENT_SCREENSHOT}", flush=True)
            elif cmd.lower().startswith("download "):
                target_url = cmd[9:].strip()
                print(f"Downloading from {target_url}...", flush=True)
                with app.page.expect_download() as download_info:
                    app.page.goto(target_url)
                download = download_info.value
                dest = DOWNLOADS_DIR / download.suggested_filename
                download.save_as(str(dest))
                print(f"[+] Report downloaded: {dest}", flush=True)
            elif cmd.lower().startswith("click "):
                selector = cmd[6:].strip()
                print(f"Clicking selector: {selector} ...", flush=True)
                app.page.click(selector)
                time.sleep(2)
                app.page.screenshot(path=str(CURRENT_SCREENSHOT))
            else:
                print(f"Unknown command: '{cmd}'", flush=True)
                
    except Exception as e:
        print(f"\n[ERROR] Automation encountered an error: {e}", flush=True)
        import traceback
        traceback.print_exc()
    finally:
        print("[*] Closing browser session...", flush=True)
        app.close()
        print("[+] Done.", flush=True)


if __name__ == "__main__":
    main()

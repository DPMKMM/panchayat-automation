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
import re
import threading
import time
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import ddddocr

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
try:
    from core.config import get_data_dir, get_debug_dir, get_downloads_dir, PROFILES_DIR, SESSIONS_DIR
    DATA_DIR = get_data_dir()
    DEBUG_DIR = get_debug_dir()
    DOWNLOADS_DIR = get_downloads_dir()
    PROFILE_DIR = PROFILES_DIR / "default"
    STORAGE_STATE_FILE = SESSIONS_DIR / "storage_state.json"
except Exception:
    DATA_DIR = ROOT_DIR / "data"
    DEBUG_DIR = DATA_DIR / "debug"
    DOWNLOADS_DIR = DATA_DIR / "downloads"
    PROFILE_DIR = DATA_DIR / "browser_profiles" / "default"
    STORAGE_STATE_FILE = DATA_DIR / "sessions" / "storage_state.json"

CONFIG_FILE = BASE_DIR / "config.json"
CAPTCHA_CACHE_FILE = DEBUG_DIR / "temp_captcha.png"
OTP_FILE = DATA_DIR / "otp.txt"
COMMAND_FILE = DATA_DIR / "command.txt"
OTP_SCREENSHOT = DEBUG_DIR / "otp_screen.png"
DASHBOARD_SCREENSHOT = DEBUG_DIR / "dashboard_screen.png"
CURRENT_SCREENSHOT = DEBUG_DIR / "current_screen.png"

DEBUG_DIR.mkdir(parents=True, exist_ok=True)
DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
PROFILE_DIR.mkdir(parents=True, exist_ok=True)

_OCR_LOCK = threading.Lock()
_SHARED_OCR = None


def get_shared_ocr():
    """Return a cached thread-safe DdddOcr instance so logins skip the ~4s cold ONNX load."""
    global _SHARED_OCR
    if _SHARED_OCR is None:
        with _OCR_LOCK:
            if _SHARED_OCR is None:
                _SHARED_OCR = ddddocr.DdddOcr(show_ad=False)
    return _SHARED_OCR


def warm_ocr() -> None:
    """Best-effort background warmup for DdddOcr at server startup."""
    try:
        get_shared_ocr()
    except Exception:
        pass


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
    def __init__(self, headless=False, profile_dir=None, downloads_dir=None, on_status=None):
        self.headless = headless
        self.profile_dir = Path(profile_dir) if profile_dir else PROFILE_DIR
        self.downloads_dir = Path(downloads_dir) if downloads_dir else DOWNLOADS_DIR
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self.downloads_dir.mkdir(parents=True, exist_ok=True)
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.ocr = get_shared_ocr()
        self.otp_message = ""
        self.on_status = on_status

    def _emit(self, message: str) -> None:
        print(message, flush=True)
        if callable(self.on_status):
            try:
                self.on_status(message)
            except Exception:
                pass

    def start_browser(self):
        print(f"[*] Launching browser (Headless: {self.headless})...", flush=True)
        self._emit("Opening Browser")
        self.playwright = sync_playwright().start()
        launch_args = [
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--disable-blink-features=AutomationControlled",
            "--disable-extensions",
            "--disable-background-networking",
            "--disable-background-timer-throttling",
            "--disable-renderer-backgrounding",
            "--disable-backgrounding-occluded-windows",
            "--renderer-process-limit=1",
            "--disable-sync",
            "--no-first-run",
        ]
        # Headless mode uses fast Chromium launch + isolated context restoring saved EPTS storage state if present.
        if self.headless:
            try:
                self.browser = self.playwright.chromium.launch(
                    headless=True,
                    downloads_path=str(self.downloads_dir),
                    args=launch_args,
                )
                ctx_kwargs = {"accept_downloads": True}
                ss_file = self.profile_dir / "storage_state.json"
                if ss_file.exists() and ss_file.stat().st_size > 10:
                    try:
                        json.loads(ss_file.read_text(encoding="utf-8"))
                        ctx_kwargs["storage_state"] = str(ss_file)
                    except Exception:
                        pass
                self.context = self.browser.new_context(**ctx_kwargs)
                self.page = self.context.new_page()
                return
            except Exception as exc:
                print(f"[-] Fast bundled Chromium launch failed ({exc}), trying persistent channels...", flush=True)

        channels = ["chrome", "msedge", None]
        last_err = None
        for ch in channels:
            try:
                kwargs = dict(
                    user_data_dir=str(self.profile_dir),
                    headless=self.headless,
                    accept_downloads=True,
                    downloads_path=str(self.downloads_dir),
                    args=launch_args,
                )
                if ch:
                    kwargs["channel"] = ch
                self.context = self.playwright.chromium.launch_persistent_context(**kwargs)
                break
            except Exception as exc:
                last_err = exc
                print(f"[-] Browser launch ({ch or 'bundled-chromium'}) failed ({exc}), trying fallback...", flush=True)
        if self.context is None:
            raise last_err or RuntimeError("Failed to launch Chromium browser context.")
        self.page = self.context.pages[0] if self.context.pages else self.context.new_page()

    def is_logged_in(self):
        try:
            print("[*] Checking if active session already exists...", flush=True)
            self.page.goto("https://epanchayat.telangana.gov.in/deptLoginVerified", wait_until="domcontentloaded", timeout=15000)
            if "deptLoginVerified" in self.page.url and "Office ID:" in self.page.content():
                print("[+] Active session verified! Already logged in.", flush=True)
                if os.getenv("EPTS_SAVE_DEBUG_SCREENSHOTS") == "1":
                    self.page.screenshot(path=str(DASHBOARD_SCREENSHOT))
                return True
        except Exception as e:
            print(f"[-] Session check note: {e}", flush=True)
        return False

    def navigate_home(self):
        url = "https://epanchayat.telangana.gov.in/cs"
        print(f"[*] Navigating to {url} ...", flush=True)
        self.page.goto(url, wait_until="domcontentloaded", timeout=15000)

    def open_department_login_modal(self):
        print("[*] Opening 'Department Login' modal...", flush=True)
        dept_link = self.page.locator("a:has-text('Department Login')").first
        dept_link.wait_for(state="visible", timeout=10000)
        dept_link.click()
        self.page.wait_for_selector("#userId", state="visible", timeout=10000)
        print("[+] Department Login modal is open.", flush=True)
        self._emit("Browser Opened")

    def _refresh_captcha(self) -> None:
        refresh_btn = self.page.locator("button.fa-refresh, .fa-refresh").first
        if not refresh_btn.is_visible():
            return
        try:
            with self.page.expect_response(lambda r: "CaptchaServlet" in r.url, timeout=4000):
                refresh_btn.click()
        except Exception:
            try:
                refresh_btn.click()
            except Exception:
                pass
        time.sleep(0.25)

    def solve_captcha(self, retries=5):
        self._emit("Solving Captcha")
        save_dbg = os.getenv("EPTS_SAVE_DEBUG_SCREENSHOTS") == "1"
        best_code = ""
        for attempt in range(1, retries + 1):
            captcha_img = self.page.locator("#img1")
            captcha_img.wait_for(state="visible", timeout=8000)
            try:
                self.page.wait_for_function(
                    "() => { const img = document.getElementById('img1'); return !!(img && img.complete && img.naturalWidth > 0); }",
                    timeout=4000,
                )
            except Exception:
                pass
            img_bytes = captcha_img.screenshot(timeout=5000)

            if save_dbg:
                with open(CAPTCHA_CACHE_FILE, "wb") as f:
                    f.write(img_bytes)

            with _OCR_LOCK:
                code = self.ocr.classification(img_bytes)
            code = re.sub(r"[^a-z0-9]", "", str(code or "").lower())
            if len(code) > len(best_code):
                best_code = code
            min_len = 6 if attempt < retries else 4
            if len(code) >= min_len:
                print(f"[+] Captcha auto-detected (attempt {attempt}): {code}", flush=True)
                return code
            print(f"[-] Low confidence on captcha '{code}', refreshing...", flush=True)
            self._emit("Refreshing Captcha")
            self._refresh_captcha()
        return best_code

    def _is_otp_screen_visible(self) -> bool:
        try:
            return bool(self.page.evaluate("""() => {
                const otpEl = document.querySelector("#otp, input[id*='otp' i], input[name*='otp' i], input[placeholder*='otp' i], button[value*='Validate OTP' i], input[value*='Validate OTP' i]");
                if (otpEl && (otpEl.offsetParent !== null || otpEl.getBoundingClientRect().width > 0)) return true;
                const pvals = document.getElementById('pvals');
                const txt = pvals ? (pvals.innerText || '').trim() : '';
                if (/otp\\s+(has\\s+been\\s+)?sent|registered\\s+mobile|enter\\s+otp/i.test(txt)) return true;
                const bodyTxt = document.body ? (document.body.innerText || '') : '';
                return /otp\\s+has\\s+been\\s+sent\\s+to\\s+your\\s+registered\\s+mobile/i.test(bodyTxt);
            }"""))
        except Exception:
            return False

    def _wait_for_otp_or_login_error(self, timeout_ms: int = 18000) -> tuple[bool, str]:
        """Poll safely across POST reload for either visible OTP screen/notice or #pvals error."""
        deadline = time.time() + (timeout_ms / 1000.0)
        while time.time() < deadline:
            try:
                outcome_handle = self.page.wait_for_function(
                    """() => {
                        if (!document.body || document.readyState === 'loading') return false;
                        const otpEl = document.querySelector("#otp, input[id*='otp' i], input[name*='otp' i], input[placeholder*='otp' i], input[value*='Validate OTP' i]");
                        if (otpEl && (otpEl.offsetParent !== null || otpEl.getBoundingClientRect().width > 0)) {
                            return 'otp';
                        }
                        const pvals = document.getElementById('pvals');
                        const err = pvals ? (pvals.innerText || '').trim() : '';
                        if (err) {
                            if (/otp\\s+(has\\s+been\\s+)?sent|registered\\s+mobile|enter\\s+otp/i.test(err)) {
                                return 'otp';
                            }
                            return 'error:' + err;
                        }
                        const bodyTxt = document.body ? (document.body.innerText || '') : '';
                        if (/otp\\s+has\\s+been\\s+sent\\s+to\\s+your\\s+registered\\s+mobile/i.test(bodyTxt)) {
                            return 'otp';
                        }
                        return false;
                    }""",
                    timeout=max(1000, int((deadline - time.time()) * 1000)),
                )
                outcome = str(outcome_handle.json_value() or "")
                if outcome == "otp":
                    return True, ""
                if outcome.startswith("error:"):
                    return False, outcome[6:].strip()
            except Exception as exc:
                low_exc = str(exc).lower()
                if any(k in low_exc for k in ("execution context", "navigation", "destroyed", "detached", "specified id")):
                    try:
                        self.page.wait_for_load_state("domcontentloaded", timeout=5000)
                    except Exception:
                        pass
                    time.sleep(0.25)
                    continue
                break

        if self._is_otp_screen_visible():
            return True, ""
        try:
            pvals = self.page.locator("#pvals")
            err = pvals.inner_text().strip() if pvals.is_visible() else ""
            if err and re.search(r"otp\s+(has\s+been\s+)?sent|registered\s+mobile|enter\s+otp", err, re.I):
                return True, ""
        except Exception:
            err = ""
        return False, err

    def get_dynamic_otp_message(self) -> str:
        """Scrapes the live dynamic OTP notice from the e-Panchayat page, e.g.
        'A 6 digit OTP has been sent to your registered mobile number xxxxxx5586. Enter OTP to continue.'"""
        if not self.page:
            return ""
        try:
            text = self.page.evaluate("""() => {
                if (!document.body) return '';
                const pvals = document.getElementById('pvals');
                if (pvals && /registered mobile/i.test(pvals.innerText || '')) {
                    return pvals.innerText.trim();
                }
                const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
                let node;
                while ((node = walker.nextNode())) {
                    const val = (node.nodeValue || '').trim();
                    if (/OTP has been sent to your registered mobile/i.test(val)) {
                        return val;
                    }
                }
                const allEls = document.querySelectorAll('p, div, span, font, b, strong, label, h4, h5');
                for (const el of allEls) {
                    const t = (el.innerText || '').trim();
                    if (/OTP has been sent to your registered mobile/i.test(t)) {
                        return t;
                    }
                }
                const bodyText = document.body ? document.body.innerText : '';
                const m = bodyText.match(/A \\d+ digit OTP has been sent to your registered mobile number [^\\.\\n\\r<]+\\.?\\s*(?:Enter OTP to continue\\.?)?/i);
                return m ? m[0] : '';
            }""")
            if text:
                return text.strip()

            content = self.page.content()
            m = re.search(
                r"A\s+\d+\s+digit\s+OTP\s+has\s+been\s+sent\s+to\s+your\s+registered\s+mobile\s+number\s+([xX\d]+)\.?\s*(?:Enter\s+OTP\s+to\s+continue\.?)?",
                content,
                re.IGNORECASE,
            )
            if m:
                return m.group(0).strip()

            m2 = re.search(r"registered mobile number\s+([xX\d]{6,12})", content, re.IGNORECASE)
            if m2:
                return f"A 6 digit OTP has been sent to your registered mobile number {m2.group(1)}. Enter OTP to continue."
        except Exception as exc:
            print(f"[!] Note extracting dynamic OTP text: {exc}", flush=True)
        return ""

    def submit_credentials_and_generate_otp(self, username, password):
        max_attempts = 5
        for attempt in range(1, max_attempts + 1):
            if self._is_otp_screen_visible():
                self._emit("OTP Sent")
                self.otp_message = self.get_dynamic_otp_message()
                return True
            try:
                if not self.page.locator("#userId").is_visible():
                    self.open_department_login_modal()
            except Exception:
                self.open_department_login_modal()

            print(f"[*] Entering credentials (attempt {attempt})...", flush=True)
            self._emit("Entering User ID & Password")
            self.page.fill("#userId", username)
            self.page.fill("#npwd", password)

            captcha_text = self.solve_captcha()
            if not captcha_text:
                if attempt < max_attempts:
                    self._refresh_captcha()
                    continue
                raise RuntimeError("Could not read portal captcha image cleanly.")

            print(f"[*] Filling captcha field ({captcha_text}) & clicking 'Generate OTP to Login'...", flush=True)
            self._emit("Logging In")
            self.page.fill("#cp", captcha_text)

            # Clear previous error message if present
            self.page.evaluate("() => { const el = document.getElementById('pvals'); if(el) el.innerText = ''; }")
            self.page.locator("#submit1").click()

            reached_otp, error_text = self._wait_for_otp_or_login_error(timeout_ms=18000)

            if reached_otp:
                print("[+] OTP generation triggered successfully! Reached OTP verification screen.", flush=True)
                self._emit("OTP Sent")
                self.otp_message = self.get_dynamic_otp_message()
                if not self.otp_message:
                    try:
                        self.page.wait_for_function(
                            "() => Boolean(document.body && /registered mobile/i.test(document.body.innerText || ''))",
                            timeout=1500,
                        )
                        self.otp_message = self.get_dynamic_otp_message()
                    except Exception:
                        pass
                if self.otp_message:
                    print(f"[+] Dynamic OTP Notice captured: {self.otp_message}", flush=True)
                if os.getenv("EPTS_SAVE_DEBUG_SCREENSHOTS") == "1":
                    self.page.screenshot(path=str(OTP_SCREENSHOT))
                return True

            low_err = error_text.lower()
            if "captcha" in low_err:
                print(f"[-] Captcha rejected by server ({error_text}). Retrying with fresh captcha...", flush=True)
                self._emit("Retrying Captcha")
                if not self.page.locator("#userId").is_visible():
                    self.open_department_login_modal()
                else:
                    self._refresh_captcha()
                continue

            if error_text:
                print(f"[!] Server message: {error_text}", flush=True)
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

        print("[*] Clicking 'Validate OTP'...", flush=True)
        self.page.evaluate("() => { const el = document.getElementById('pvals'); if (el) el.innerText = ''; }")
        validate_btn = self.page.locator("button:has-text('Validate OTP'), input[value='Validate OTP']").first
        validate_btn.click()

        print("[*] Validating OTP on portal...", flush=True)
        try:
            self.page.wait_for_function(
                """() => {
                    const url = window.location.href || '';
                    const txt = (document.body && document.body.innerText) || '';
                    if (url.includes('deptLoginVerified') || txt.includes('Office ID:')) return 'ok';
                    const pvals = document.getElementById('pvals');
                    if (pvals && (pvals.innerText || '').trim()) return 'err';
                    return false;
                }""",
                timeout=12000,
            )
        except Exception:
            pass

        current_url = self.page.url
        print(f"[+] Current URL after OTP validation: {current_url}", flush=True)
        if os.getenv("EPTS_SAVE_DEBUG_SCREENSHOTS") == "1":
            self.page.screenshot(path=str(DASHBOARD_SCREENSHOT))

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

    def save_storage_state(self, path: Path | str | None = None) -> Path | None:
        """Persist active browser cookies & storage cleanly for background restart recovery."""
        if not getattr(self, "context", None):
            return None
        target = Path(path) if path else (self.profile_dir / "storage_state.json")
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            self.context.storage_state(path=str(target))
            return target
        except Exception as exc:
            print(f"[-] Note on saving storage state: {exc}", flush=True)
            return None

    def _find_visible_menu_item(self, menu_name: str):
        for sel in (f"text='{menu_name}'", f"a:has-text('{menu_name}')"):
            loc = self.page.locator(sel).first
            try:
                if loc.is_visible(timeout=1500):
                    return loc
            except Exception:
                pass
        return None

    def _assert_authenticated_portal_page(self) -> None:
        cur_url = str(getattr(self.page, "url", "") or "").lower()
        login_visible = False
        try:
            login_visible = self.page.locator("a:has-text('Department Login')").first.is_visible(timeout=500)
        except Exception:
            login_visible = False
        if login_visible or ("/cs" in cur_url and "deptloginverified" not in cur_url):
            raise PermissionError(
                "e-Panchayat portal session has expired. Please complete Department Login & OTP again."
            )

    def select_menu(self, menu_name):
        print(f"[*] Selecting menu item: '{menu_name}' ...", flush=True)
        self._assert_authenticated_portal_page()
        target = self._find_visible_menu_item(menu_name)
        if target is None:
            print(f"[*] Menu '{menu_name}' not visible on current view; refreshing deptLoginVerified...", flush=True)
            self.page.goto("https://epanchayat.telangana.gov.in/deptLoginVerified", wait_until="domcontentloaded", timeout=15000)
            time.sleep(1.0)
            self._assert_authenticated_portal_page()
            target = self._find_visible_menu_item(menu_name)

        if target is None:
            target = self.page.locator(f"a:has-text('{menu_name}')").first
            target.wait_for(state="visible", timeout=10000)

        target.hover()
        time.sleep(0.5)
        target.click()
        time.sleep(2)

        if os.getenv("EPTS_SAVE_DEBUG_SCREENSHOTS") == "1":
            try:
                self.page.screenshot(path=str(CURRENT_SCREENSHOT))
            except Exception:
                pass
        print(f"[+] Clicked '{menu_name}'. Current URL: {self.page.url}", flush=True)

    def close(self):
        for attr in ("context", "browser", "playwright"):
            obj = getattr(self, attr, None)
            if obj is not None:
                try:
                    if attr == "playwright":
                        obj.stop()
                    else:
                        obj.close()
                except Exception:
                    pass
                setattr(self, attr, None)
        self.page = None


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

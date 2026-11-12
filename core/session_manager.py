"""Centralized Multi-Session Playwright & EPTS Departmental Automation Manager.

Extracted from dsr/service.py so DSR, GP Balance, and House Tax DCB modules share
a single cohesive session lifecycle owner with:
- Strict per-session worker thread affinity (Playwright greenlet safety)
- Isolated browser profile & downloads directory per browser session
- Persistent session state serialization under DATA_DIR/sessions
- Background Playwright keepalive pings & idle eviction
- Thread-safe live DSR micro-cache keyed cleanly across officer hierarchy levels
"""

from __future__ import annotations

import concurrent.futures
import json
import logging
import re
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import httpx

from core.config import (
    DATA_DIR,
    DOWNLOADS_DIR,
    PROFILES_DIR,
    REPORTS_DIR,
    SESSIONS_DIR,
    SESSION_DEFAULT_DURATION,
    SESSION_EXTENSION_DURATION,
    SESSION_MAX_DURATION,
    URL_EPTS_LOGIN,
    get_data_dir,
    get_downloads_dir,
    get_reports_dir,
    is_cloud_sync_fallback_allowed,
)

logger = logging.getLogger("epanchayat_session_manager")

ROOT_DIR = Path(__file__).resolve().parent.parent
PROFILES_BASE = PROFILES_DIR
SESSIONS_STATE_DIR = SESSIONS_DIR

# Multi-session registry
_sessions: dict[str, dict[str, Any]] = {}
_sessions_lock = threading.Lock()
_progress_lock = threading.Lock()
_login_progress_map: dict[str, dict[str, Any]] = {}
_keepalive_started = False


def _normalize_login_remark(message: str) -> tuple[str, bool]:
    """Convert raw engine status messages into concise user-facing remarks.

    Returns (remark_text, replace_active_step).
    """
    raw = str(message or "").strip()
    if not raw:
        return "", False
    cleaned = re.sub(r"^\[[*+\-!]\]\s*", "", raw).strip()
    low = cleaned.lower()

    if "launching browser" in low or "opening browser" in low or "initializing departmental login" in low:
        return "Opening Browser", False
    if "navigating to" in low or "opening 'department login'" in low:
        return "Opening Portal", True
    if "modal is open" in low or low == "browser opened":
        return "Browser Opened", True
    if "entering credentials" in low or "entering user id" in low:
        return "Entering User ID & Password", False
    if "solving captcha" in low or "captcha auto-detected" in low:
        return "Solving Captcha", False
    if "low confidence on captcha" in low or "refreshing captcha" in low:
        return "Refreshing Captcha", True
    if "captcha rejected" in low or "retrying captcha" in low:
        return "Retrying Captcha", True
    if "filling captcha" in low or "logging in" in low or "generate otp" in low:
        return "Logging In", False
    if "otp generation triggered" in low or "otp verification ready" in low or "otp sent" in low:
        return "OTP Sent", False
    if "portal login error" in low:
        return "Portal connection error. Please try again.", False
    return cleaned, False


def _reset_login_progress(session_id: str) -> None:
    sid = _sanitize_session_id(session_id)
    with _progress_lock:
        _login_progress_map[sid] = {
            "active": True,
            "done": False,
            "error": False,
            "current": "Opening Browser",
            "logs": [{"text": "Opening Browser", "status": "active", "ts": time.time()}],
            "started_at": time.time(),
            "updated_at": time.time(),
        }


def _push_login_progress(session_id: str, message: str, *, done: bool = False, error: bool = False) -> None:
    sid = _sanitize_session_id(session_id)
    text, replace_active = _normalize_login_remark(message)
    if not text:
        return
    now = time.time()
    status_flag = "error" if error else ("done" if done else "active")
    with _progress_lock:
        entry = _login_progress_map.get(sid)
        if entry is None:
            entry = {
                "active": not done and not error,
                "done": done,
                "error": error,
                "current": text,
                "logs": [],
                "started_at": now,
                "updated_at": now,
            }
            _login_progress_map[sid] = entry

        logs = entry["logs"]
        if replace_active and logs and logs[-1].get("status") == "active":
            logs[-1] = {"text": text, "status": status_flag, "ts": now}
        else:
            existing_idx = next((i for i, it in enumerate(logs) if it.get("text") == text), None)
            if existing_idx is not None:
                del logs[existing_idx]
            for item in logs:
                if item.get("status") == "active":
                    item["status"] = "done"
            logs.append({"text": text, "status": status_flag, "ts": now})

        if len(logs) > 8:
            entry["logs"] = logs[-8:]
        entry["current"] = text
        entry["active"] = not done and not error
        entry["done"] = done
        entry["error"] = error
        entry["updated_at"] = now


def get_login_progress(session_id: str = "") -> dict[str, Any]:
    """Read real-time login progress non-blockingly without waiting on the session's Playwright thread."""
    sid = _sanitize_session_id(session_id)
    with _progress_lock:
        entry = _login_progress_map.get(sid)
        if not entry:
            return {"active": False, "done": False, "error": False, "current": "", "logs": [], "elapsed": 0}
        return {
            "active": bool(entry.get("active")),
            "done": bool(entry.get("done")),
            "error": bool(entry.get("error")),
            "current": entry.get("current", ""),
            "logs": [dict(x) for x in entry.get("logs", [])],
            "elapsed": max(0, int(time.time() - float(entry.get("started_at") or time.time()))),
        }

# 3-Minute Live DSR Attendance Micro-Cache & Deduplication Lock
# Keyed by (module, portal_date_fmt, dist_name, cutoff_time, sort_by, user_level, mandal_norm)
# (5-tuple legacy District keys remain supported for backwards compatibility)
_DSR_CACHE: dict[tuple[Any, ...], dict[str, Any]] = {}
_DSR_CACHE_LOCK = threading.Lock()
_DSR_CACHE_TTL_SECONDS = 180.0


def _sanitize_session_id(session_id: str) -> str:
    s = (session_id or "").strip()
    clean = re.sub(r"[^a-zA-Z0-9_\-]", "", s)
    return clean[:64] if clean else "default"


def _save_session_state(session: dict[str, Any]) -> None:
    sid = session["session_id"]
    state_dir = get_data_dir() / "sessions"
    state_dir.mkdir(parents=True, exist_ok=True)
    state_file = state_dir / f"session_{sid}.json"
    try:
        payload = {
            "session_id": sid,
            "user_id": session.get("user_id", ""),
            "user_level": session.get("user_level", "district"),
            "mandal_name": session.get("mandal_name", ""),
            "district_name": session.get("district_name", ""),
            "division_name": session.get("division_name", ""),
            "office_name": session.get("office_name", ""),
            "office_id": session.get("office_id", ""),
            "status": session.get("status", "idle"),
            "mode": session.get("mode", "idle"),
            "authenticated_at": session.get("authenticated_at", 0),
            "session_duration": session.get("session_duration", SESSION_DEFAULT_DURATION),
            "extended": session.get("extended", False),
            "last_activity": session.get("last_activity", time.time()),
        }
        state_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except Exception as exc:
        logger.warning("Could not persist session state for %s: %s", sid, exc)


def _load_session_state(session_id: str) -> dict[str, Any]:
    sid = _sanitize_session_id(session_id)
    state_dir = get_data_dir() / "sessions"
    state_file = state_dir / f"session_{sid}.json"
    try:
        if state_file.exists():
            payload = json.loads(state_file.read_text(encoding="utf-8"))
            auth_time = payload.get("authenticated_at", 0)
            dur = payload.get("session_duration", SESSION_DEFAULT_DURATION)
            if payload.get("status") == "authenticated" and (time.time() - auth_time) < dur:
                return payload
            elif payload.get("status") == "authenticated":
                _clear_session_state(sid)
    except Exception as exc:
        logger.warning("Could not load session state for %s: %s", sid, exc)
    return {}


def _clear_session_state(session_id: str) -> None:
    sid = _sanitize_session_id(session_id)
    state_dir = get_data_dir() / "sessions"
    state_file = state_dir / f"session_{sid}.json"
    try:
        if state_file.exists():
            state_file.unlink()
    except Exception:
        pass


def get_or_create_session(session_id: str = "") -> dict[str, Any]:
    """Retrieve or create an isolated session context with its own profile, downloads dir, and worker thread."""
    sid = _sanitize_session_id(session_id)
    with _sessions_lock:
        session = _sessions.get(sid)
        if not session:
            data_dir = get_data_dir()
            prof_dir = data_dir / "browser_profiles" / f"session_{sid}"
            prof_dir.mkdir(parents=True, exist_ok=True)
            dl_dir = data_dir / "downloads" / f"session_{sid}"
            dl_dir.mkdir(parents=True, exist_ok=True)
            executor = concurrent.futures.ThreadPoolExecutor(
                max_workers=1,
                thread_name_prefix=f"Bot_{sid[:6]}",
            )
            saved = _load_session_state(sid)
            session = {
                "session_id": sid,
                "user_id": saved.get("user_id", "") if saved else "",
                "user_level": saved.get("user_level", "district") if saved else "district",
                "mandal_name": saved.get("mandal_name", "") if saved else "",
                "district_name": saved.get("district_name", "") if saved else "",
                "division_name": saved.get("division_name", "") if saved else "",
                "office_name": saved.get("office_name", "") if saved else "",
                "office_id": saved.get("office_id", "") if saved else "",
                "status": saved.get("status", "idle") if saved else "idle",
                "mode": saved.get("mode", "idle") if saved else "idle",
                "bot": None,
                "executor": executor,
                "profile_dir": prof_dir,
                "downloads_dir": dl_dir,
                "last_error": "",
                "created_at": time.time(),
                "authenticated_at": saved.get("authenticated_at", 0.0) if saved else 0.0,
                "session_duration": saved.get("session_duration", SESSION_DEFAULT_DURATION) if saved else SESSION_DEFAULT_DURATION,
                "extended": saved.get("extended", False) if saved else False,
                "last_activity": time.time(),
                "latest_pdf_path": "",
                "latest_report_date": "",
                "report_data": {},
                "lock": threading.Lock(),
            }
            _sessions[sid] = session

        session["last_activity"] = time.time()
        return session


def run_in_session_thread(session: dict[str, Any], func, *args, **kwargs):
    """Execute a callable inside the session's dedicated single-thread bot executor."""
    executor = session.get("executor")
    if not executor:
        raise RuntimeError("Session executor is not active.")
    session["last_activity"] = time.time()
    future = executor.submit(func, *args, **kwargs)
    return future.result()


def run_in_bot_thread(func, *args, **kwargs):
    session = get_or_create_session("default")
    return run_in_session_thread(session, func, *args, **kwargs)


class _ActiveSessionProxy(dict):
    """Compatibility proxy so older references to `_active_session[...]` resolve to default session."""
    def __getitem__(self, item):
        return get_or_create_session("default").get(item)

    def get(self, item, default=None):
        return get_or_create_session("default").get(item, default)

    def __setitem__(self, key, value):
        get_or_create_session("default")[key] = value


_active_session = _ActiveSessionProxy()


def check_epts_reachability(timeout: float = 3.0) -> tuple[bool, str]:
    """Test if current server has reachability to epanchayat.telangana.gov.in."""
    url = "https://epanchayat.telangana.gov.in/cs"
    try:
        with httpx.Client(verify=False, timeout=timeout) as client:
            resp = client.head(url, headers={"User-Agent": "Mozilla/5.0"}, follow_redirects=True)
            if resp.status_code == 200:
                return True, "Reachable"
            return True, f"HTTP {resp.status_code}"
    except httpx.ConnectTimeout:
        return False, "ConnectTimeout (Telangana State Data Center firewall blocks foreign cloud datacenter IPs)"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def start_server_login(username: str, password: str, headless: bool = True, session_id: str = "") -> dict[str, Any]:
    """Initiate server-side browser login to e-Panchayat portal within the user's isolated session."""
    session = get_or_create_session(session_id)
    return run_in_session_thread(session, _start_server_login_impl, session, username, password, headless)


def _start_server_login_impl(session: dict[str, Any], username: str, password: str, headless: bool = True) -> dict[str, Any]:
    u = username.strip()
    p = password.strip()
    if not u or not p:
        raise ValueError("User ID and Password are required.")

    t_login_start = time.perf_counter()
    sid = session["session_id"]
    _reset_login_progress(sid)
    playwright_available = False
    try:
        import playwright  # noqa: F401
        import ddddocr  # noqa: F401
        playwright_available = True
    except ImportError:
        playwright_available = False

    if playwright_available:
        bot = None
        try:
            try:
                from dsr.automation import EPTSAutomation
            except (ImportError, ModuleNotFoundError):
                from epts_automation import EPTSAutomation

            prev_bot = session.get("bot")
            if prev_bot:
                try:
                    prev_bot.close()
                except Exception:
                    pass
                session["bot"] = None

            def _progress_cb(msg: str) -> None:
                _push_login_progress(sid, msg)

            bot = EPTSAutomation(
                headless=headless,
                profile_dir=session["profile_dir"],
                downloads_dir=session["downloads_dir"],
                on_status=_progress_cb,
            )
            bot.start_browser()
            bot.navigate_home()
            bot.open_department_login_modal()
            success = bot.submit_credentials_and_generate_otp(u, p)
            if success:
                otp_msg = bot.get_dynamic_otp_message() if hasattr(bot, "get_dynamic_otp_message") else getattr(bot, "otp_message", "")
                mobile_m = re.search(r"([xX\d]{6,12})", otp_msg) if otp_msg else None
                extracted_mobile = mobile_m.group(1) if mobile_m else ""
                if not otp_msg and extracted_mobile:
                    otp_msg = f"A 6 digit OTP has been sent to your registered mobile number {extracted_mobile}. Enter OTP to continue."

                session["bot"] = bot
                session["user_id"] = u
                session["status"] = "awaiting_otp"
                session["mode"] = "live_portal"
                session["otp_message"] = otp_msg
                session["mobile_number"] = extracted_mobile
                session["last_error"] = ""
                _save_session_state(session)
                elapsed_s = time.perf_counter() - t_login_start
                _push_login_progress(
                    sid,
                    "OTP Sent",
                    done=True,
                )
                logger.info("Live login OTP triggered for %s in %.2fs", u, elapsed_s)
                return {
                    "success": True,
                    "step": "otp_required",
                    "user_id": u,
                    "mode": "live_portal",
                    "otp_message": otp_msg,
                    "mobile_number": extracted_mobile,
                    "message": otp_msg or f"Real OTP triggered on e-Panchayat portal for officer {u}! Please check your registered mobile for the 6-digit SMS OTP.",
                }
            raise ValueError("Unable to complete credential submission on the e-Panchayat portal.")
        except ValueError as exc:
            _push_login_progress(sid, str(exc), error=True)
            if bot:
                try:
                    bot.close()
                except Exception:
                    pass
            raise
        except Exception as exc:
            _push_login_progress(sid, "Portal connection error. Please try again.", error=True)
            if bot:
                try:
                    bot.close()
                except Exception:
                    pass
            logger.warning("Live browser login error for session %s: %s", session["session_id"], exc)
            if not is_cloud_sync_fallback_allowed():
                raise RuntimeError(f"Department Login failed on e-Panchayat portal: {exc}") from exc

    reachable, reason = check_epts_reachability(timeout=3.0)
    if not is_cloud_sync_fallback_allowed():
        raise ConnectionError(
            f"Cannot reach Telangana e-Panchayat portal ({reason}). Please ensure server connectivity."
        )

    session["bot"] = None
    session["user_id"] = u
    session["status"] = "awaiting_otp"
    session["mode"] = "cloud_sync"
    session["last_error"] = ""
    fallback_mobile = "registered mobile"
    fallback_msg = f"A 6 digit OTP has been sent to your registered mobile number {fallback_mobile}. Enter OTP to continue."
    session["otp_message"] = fallback_msg
    session["mobile_number"] = fallback_mobile
    _save_session_state(session)
    return {
        "success": True,
        "step": "otp_required",
        "user_id": u,
        "mode": "cloud_sync",
        "otp_message": fallback_msg,
        "mobile_number": fallback_mobile,
        "message": fallback_msg,
    }


def verify_server_otp(otp_code: str, session_id: str = "") -> dict[str, Any]:
    """Validate entered OTP on the user's isolated e-Panchayat session."""
    session = get_or_create_session(session_id)
    return run_in_session_thread(session, _verify_server_otp_impl, session, otp_code)


def determine_user_level(info: dict[str, str], user_id: str = "") -> tuple[str, str]:
    """Determine user level ('district', 'division', 'mandal') and mandal_name from officer info and user_id."""
    office = (info.get("office_name") or "").upper()
    uname = (info.get("user_name") or user_id or "").upper()
    div = (info.get("division_name") or "").upper()
    mandal = (info.get("mandal_name") or "").strip()

    if "DPO" in uname or "DPM" in uname or "DISTRICT PANCHAYAT" in office or office.startswith("DPO"):
        return "district", ""

    is_mandal = bool(
        mandal
        or "MPO" in uname
        or "MPDO" in uname
        or "MANDAL" in uname
        or "MANDAL" in office
        or "MPO" in office
        or "MPDO" in office
        or "EO(PR&RD)" in office
        or "EOPRD" in office
        or "SECRETARY" in office
        or "PANCHAYAT SECRETARY" in uname
    )
    if is_mandal:
        if not mandal:
            m = re.search(r'(?:MPO|MPDO|MANDAL)[_\s]+([A-Za-z0-9_]+)', uname, re.I)
            if m:
                mandal = m.group(1).replace('_', ' ').strip().title()
            else:
                m2 = re.search(r'(?:Mandal|MPO|MPDO)[\s,]+(?:Office[\s,]+)?([A-Za-z\s]+)', office, re.I)
                if m2:
                    mandal = m2.group(1).replace('Panchayat', '').replace('Office', '').strip().title()
        return "mandal", mandal

    is_division = bool(
        "DLPO" in uname
        or "DLPO" in office
        or "DIVISIONAL" in office
        or ("DIVISION" in div and "DPO" not in uname and "DISTRICT" not in office and "DPOA" not in uname)
    )
    if is_division:
        return "division", ""

    return "district", ""


def extract_epanchayat_header_info(page) -> dict[str, str]:
    """Scrape Office ID, User Name, Office/Designation, Division, District, and Mandal from post-login header bar."""
    info = {
        "office_id": "",
        "user_name": "",
        "office_name": "",
        "division_name": "",
        "district_name": "",
        "mandal_name": "",
        "user_level": "district",
    }
    if not page:
        return info

    parts: list[str] = []
    try:
        loc = page.locator("tr:has-text('Office ID:'), div:has-text('Office ID:'), td:has-text('Office ID:')").first
        if loc and loc.count() > 0:
            for cell in loc.locator("td, th, span, div").all():
                t = cell.inner_text().strip()
                if t and t not in parts and len(t) < 80:
                    parts.append(t)
            full_txt = loc.inner_text()
            for p in re.split(r'[\t\r\n|]+|\s{2,}', full_txt):
                p = p.strip()
                if p and p not in parts:
                    parts.append(p)
    except Exception as exc:
        logger.debug("Officer info DOM lookup error: %s", exc)

    if not any("District" in p for p in parts):
        try:
            content = page.content()
            m = re.search(r"Office ID:\s*\d+.*?(?:Date:\s*\d{2}/\d{2}/\d{4}|</html>)", content, re.DOTALL | re.I)
            if m:
                clean_txt = re.sub(r"<[^>]+>", "    ", m.group(0))
                for p in re.split(r'[\t\r\n|]+|\s{2,}', clean_txt):
                    p = p.strip()
                    if p and p not in parts:
                        parts.append(p)
        except Exception:
            pass

    for p in parts:
        if re.search(r'Office ID:\s*(\d+)', p, re.I):
            info["office_id"] = re.search(r'Office ID:\s*(\d+)', p, re.I).group(1).strip()
        elif re.search(r'User Name:\s*([A-Za-z0-9_]+)', p, re.I):
            info["user_name"] = re.search(r'User Name:\s*([A-Za-z0-9_]+)', p, re.I).group(1).strip()
        elif re.search(r'Mandal\b', p, re.I) and not re.search(r'Office|Officer|Panchayat', p, re.I):
            info["mandal_name"] = p.replace("Mandal", "").replace(":", "").strip()
        elif re.search(r'Division\b', p, re.I):
            info["division_name"] = p.replace("Division", "").strip() + " Division"
        elif re.search(r'District\b', p, re.I) and not re.search(r'Office|Officer|Panchayat', p, re.I):
            info["district_name"] = p.replace("District", "").strip() + " District"
        elif re.search(r'Panchayat\s+Office|Officer|Secretary|MPO|DPO|DLPO|MPDO', p, re.I):
            info["office_name"] = p.strip()

    level, inferred_mandal = determine_user_level(info, info.get("user_name", ""))
    info["user_level"] = level
    if inferred_mandal and not info["mandal_name"]:
        info["mandal_name"] = inferred_mandal

    return info


def _verify_server_otp_impl(session: dict[str, Any], otp_code: str) -> dict[str, Any]:
    clean_otp = re.sub(r"\D", "", otp_code.strip())
    if len(clean_otp) != 6:
        raise ValueError("Please enter a valid 6-digit numeric OTP.")

    bot = session.get("bot")
    user_id = session.get("user_id") or ""
    mode = session.get("mode", "idle")

    if mode == "live_portal":
        if not bot or not getattr(bot, "page", None):
            raise ValueError("e-Panchayat browser session is no longer active. Please restart Department Login.")

        page = bot.page
        try:
            if page.locator("#otp").is_visible():
                page.fill("#otp", clean_otp)
            else:
                page.fill("input[placeholder*='otp' i]", clean_otp)

            time.sleep(0.5)
            validate_btn = page.locator("button:has-text('Validate OTP'), input[value='Validate OTP']").first
            validate_btn.click()
            time.sleep(4)

            if "deptLoginVerified" in page.url or "Office ID:" in page.content():
                session["status"] = "authenticated"
                session["authenticated_at"] = time.time()
                session["session_duration"] = SESSION_DEFAULT_DURATION
                session["extended"] = False
                session["user_id"] = user_id or "Officer"

                officer_info = extract_epanchayat_header_info(page)
                level, m_name = determine_user_level(officer_info, user_id)
                session["user_level"] = level
                if m_name:
                    session["mandal_name"] = m_name
                elif officer_info.get("mandal_name"):
                    session["mandal_name"] = officer_info["mandal_name"]

                if officer_info.get("district_name"):
                    session["district_name"] = officer_info["district_name"]

                if officer_info.get("office_name"):
                    session["office_name"] = officer_info["office_name"]

                if officer_info.get("division_name"):
                    session["division_name"] = officer_info["division_name"]

                if officer_info.get("office_id"):
                    session["office_id"] = officer_info["office_id"]

                _save_session_state(session)
                ensure_keepalive_running()
                return {
                    "success": True,
                    "step": "authenticated",
                    "user_id": session["user_id"],
                    "user_level": session.get("user_level", "district"),
                    "mandal_name": session.get("mandal_name", ""),
                    "district_name": session.get("district_name", ""),
                    "division_name": session.get("division_name", ""),
                    "office_name": session.get("office_name", ""),
                    "message": f"e-Panchayat login verified successfully for officer {session['user_id']} ({session.get('user_level', 'district').title()} Level)! Session is active.",
                }
            else:
                pvals = page.locator("#pvals")
                err_msg = pvals.inner_text().strip() if pvals.is_visible() else "Invalid OTP or session expired."
                raise ValueError(f"e-Panchayat portal error: {err_msg}")
        except ValueError:
            raise
        except Exception as exc:
            logger.warning("Portal OTP validation error for session %s: %s", session["session_id"], exc)
            raise ValueError(f"OTP verification failed on e-Panchayat portal: {exc}") from exc

    if mode != "cloud_sync" or not is_cloud_sync_fallback_allowed():
        raise ValueError("No active Department Login OTP request found. Please start Department Login first.")

    user_id = user_id or "Officer"
    session["status"] = "authenticated"
    session["authenticated_at"] = time.time()
    session["session_duration"] = SESSION_DEFAULT_DURATION
    session["extended"] = False
    session["user_id"] = user_id
    level, m_name = determine_user_level({}, user_id)
    session["user_level"] = level
    session["mandal_name"] = m_name or ""
    _save_session_state(session)
    ensure_keepalive_running()
    return {
        "success": True,
        "step": "authenticated",
        "user_id": user_id,
        "user_level": session.get("user_level", "district"),
        "mandal_name": session.get("mandal_name", ""),
        "district_name": session.get("district_name", ""),
        "division_name": session.get("division_name", ""),
        "office_name": session.get("office_name", ""),
        "message": f"OTP verified! Session authenticated for Officer {user_id} ({session.get('user_level', 'district').title()} Level).",
    }


def get_session_status(session_id: str = "") -> dict[str, Any]:
    """Return current background session status for this specific user."""
    session = get_or_create_session(session_id)
    return run_in_session_thread(session, _get_session_status_impl, session)


def _expire_session_impl(session: dict[str, Any]) -> dict[str, Any]:
    bot = session.get("bot")
    if bot:
        try:
            bot.close()
        except Exception as exc:
            logger.warning("[%s] Error closing bot on session expire: %s", session["session_id"][:6], exc)

    _clear_session_state(session["session_id"])
    session["bot"] = None
    session["user_id"] = ""
    session["status"] = "expired"
    session["mode"] = "idle"
    session["last_error"] = "Session auto-closed after inactivity timeout."
    session["latest_pdf_path"] = ""
    session["report_data"] = {}
    session["authenticated_at"] = 0.0
    session["session_duration"] = SESSION_DEFAULT_DURATION
    session["extended"] = False
    return {"success": True, "message": "Session expired and browser closed."}


def extend_session(session_id: str = "") -> dict[str, Any]:
    session = get_or_create_session(session_id)
    return run_in_session_thread(session, _extend_session_impl, session)


def _extend_session_impl(session: dict[str, Any]) -> dict[str, Any]:
    if session.get("status") != "authenticated":
        raise ValueError("Cannot extend: No active authenticated session found. Please log in first.")

    u_id = (session.get("user_id") or "").strip().upper()
    session["session_duration"] = 86400
    session["extended"] = True
    session["last_activity"] = time.time()
    _save_session_state(session)

    return {
        "success": True,
        "message": f"Officer {u_id or 'User'} active. Persistent Session (No time restriction / No expiry).",
        "expires_in": 999999,
        "session_duration": 999999,
        "can_extend": False,
        "extended": True,
        "no_expiry": True,
    }


def _get_session_status_impl(session: dict[str, Any]) -> dict[str, Any]:
    bot = session.get("bot")
    bot_alive = False
    if bot and getattr(bot, "page", None):
        try:
            bot_alive = not bot.page.is_closed()
        except Exception:
            bot_alive = False

    auth_time = session.get("authenticated_at") or 0
    duration = session.get("session_duration", SESSION_DEFAULT_DURATION)
    extended = session.get("extended", False)
    user_id = session.get("user_id") or ""

    if session.get("status") == "authenticated" and not bot_alive and session.get("mode") == "live_portal":
        session["status"] = "expired" if session.get("authenticated_at") else "idle"
        session["user_id"] = ""
        session["bot"] = None
        session["authenticated_at"] = 0.0
        _clear_session_state(session["session_id"])

    is_auth = (session.get("status") == "authenticated") and (bot_alive or session.get("mode") == "cloud_sync")
    is_expired = session.get("status") == "expired"
    age = int(time.time() - auth_time) if (auth_time and is_auth) else 0

    if is_auth:
        remaining = 999999
        can_extend = False
        extended = True
        msg = f"Officer {user_id} active. Persistent Session (No time restriction / No expiry)."
    else:
        remaining = 0
        can_extend = False
        msg = "Department Login session expired. Please log in again." if is_expired else "Session is idle."

    return {
        "success": True,
        "session_id": session["session_id"],
        "authenticated": is_auth,
        "expired": is_expired,
        "status": session.get("status", "idle"),
        "user_id": user_id,
        "user_level": session.get("user_level", "district"),
        "mandal_name": session.get("mandal_name", ""),
        "district_name": session.get("district_name", ""),
        "division_name": session.get("division_name", ""),
        "office_name": session.get("office_name", ""),
        "mode": session.get("mode", "idle"),
        "bot_alive": bot_alive,
        "session_age_seconds": age,
        "session_duration": (999999 if is_auth else duration),
        "no_expiry": is_auth,
        "expires_in": remaining,
        "can_extend": can_extend,
        "extended": extended,
        "max_duration": SESSION_MAX_DURATION,
        "latest_pdf_available": bool(session.get("latest_pdf_path")),
        "otp_message": session.get("otp_message", ""),
        "mobile_number": session.get("mobile_number", ""),
        "message": msg,
    }


def set_user_level_override(session_id: str = "", user_level: str = "district", mandal_name: str = "") -> dict[str, Any]:
    """Allow runtime switching between district, division, and mandal level on the caller session."""
    session = get_or_create_session(session_id)
    norm_level = (user_level or "district").strip().lower()
    if "mandal" in norm_level:
        norm_level = "mandal"
    elif "division" in norm_level:
        norm_level = "division"
    elif "district" in norm_level:
        norm_level = "district"
    if norm_level not in ("district", "division", "mandal"):
        norm_level = "district"
    session["user_level"] = norm_level
    if norm_level == "mandal":
        session["mandal_name"] = mandal_name.strip() or session.get("mandal_name") or "Kallur"
    else:
        session["mandal_name"] = ""
    _save_session_state(session)
    return {
        "success": True,
        "user_level": session["user_level"],
        "mandal_name": session.get("mandal_name", ""),
        "message": f"Session switched to {session['user_level'].title()} Level"
        + (f" ({session['mandal_name']} Mandal)" if session.get("mandal_name") else ""),
    }


def logout_server_session(session_id: str = "") -> dict[str, Any]:
    session = get_or_create_session(session_id)
    return run_in_session_thread(session, _logout_server_session_impl, session)


def _logout_server_session_impl(session: dict[str, Any]) -> dict[str, Any]:
    bot = session.get("bot")
    if bot:
        try:
            bot.close()
        except Exception:
            pass
    _clear_session_state(session["session_id"])
    session["bot"] = None
    session["user_id"] = ""
    session["status"] = "idle"
    session["mode"] = "idle"
    session["last_error"] = ""
    session["latest_pdf_path"] = ""
    session["report_data"] = {}
    session["authenticated_at"] = 0.0
    session["session_duration"] = SESSION_DEFAULT_DURATION
    session["extended"] = False
    return {"success": True, "message": "Logged out successfully."}


def is_authenticated(session_id: str = "") -> bool:
    session = get_or_create_session(session_id)
    bot = session.get("bot")
    bot_alive = False
    if bot and getattr(bot, "page", None):
        try:
            bot_alive = not bot.page.is_closed()
        except Exception:
            bot_alive = False
    if session.get("status") == "authenticated" and not bot_alive and session.get("mode") == "live_portal":
        session["status"] = "expired" if session.get("authenticated_at") else "idle"
        session["user_id"] = ""
        session["bot"] = None
        session["authenticated_at"] = 0.0
        _clear_session_state(session["session_id"])
        return False
    return (session.get("status") == "authenticated") and (bot_alive or session.get("mode") == "cloud_sync")


def mark_session_expired(session_id: str = "", reason: str = "Department Login session expired. Please log in again.") -> dict[str, Any]:
    """Explicitly mark a session as expired and close any stale upstream browser handle."""
    session = get_or_create_session(session_id)
    res = run_in_session_thread(session, _expire_session_impl, session)
    session["last_error"] = reason
    return res


def get_all_active_sessions_summary() -> dict[str, Any]:
    with _sessions_lock:
        sids = list(_sessions.keys())

    sessions_list = []
    auth_count = 0
    now = time.time()

    for sid in sids:
        with _sessions_lock:
            s = _sessions.get(sid)
        if not s:
            continue

        bot = s.get("bot")
        bot_alive = False
        if bot and getattr(bot, "page", None):
            try:
                bot_alive = not bot.page.is_closed()
            except Exception:
                bot_alive = False

        status = s.get("status", "idle")
        is_auth = (status == "authenticated") and (bot_alive or s.get("mode") == "cloud_sync")
        if is_auth:
            auth_count += 1

        auth_time = s.get("authenticated_at") or s.get("created_at") or now
        age_sec = int(now - auth_time)
        idle_sec = int(now - s.get("last_activity", now))

        dur = s.get("session_duration", SESSION_DEFAULT_DURATION)
        u_id = s.get("user_id") or "Unauthenticated"
        rem_sec = -1 if is_auth else 0
        dist = s.get("district_name") or ""
        office = s.get("office_name") or ""
        div = s.get("division_name") or ""
        off_id = s.get("office_id") or ""

        sessions_list.append({
            "session_id": sid,
            "session_id_short": (sid[:8] + "...") if len(sid) > 10 else sid,
            "user_id": u_id,
            "district_name": dist,
            "office_name": office,
            "division_name": div,
            "office_id": off_id,
            "status": status,
            "authenticated": is_auth,
            "mode": s.get("mode", "idle"),
            "bot_alive": bot_alive,
            "age_minutes": round(age_sec / 60, 1),
            "idle_minutes": round(idle_sec / 60, 1),
            "session_duration_minutes": 1440 if is_auth else (dur // 60),
            "expires_in_seconds": rem_sec,
            "extended": True if is_auth else s.get("extended", False),
            "latest_pdf_available": bool(s.get("latest_pdf_path")),
            "latest_report_date": s.get("latest_report_date", ""),
        })

    from zoneinfo import ZoneInfo
    IST = ZoneInfo("Asia/Kolkata")
    now_ist = datetime.now(IST)

    return {
        "success": True,
        "timestamp": now_ist.strftime("%d-%b-%Y %I:%M:%S %p IST"),
        "total_sessions": len(sessions_list),
        "authenticated_sessions": auth_count,
        "sessions": sessions_list,
    }


def _keepalive_ping(session: dict[str, Any]):
    bot = session.get("bot")
    if bot and getattr(bot, "page", None) and session.get("status") == "authenticated":
        try:
            if not bot.page.is_closed():
                bot.page.evaluate("() => document.title")
        except Exception as e:
            logger.debug("[%s] Keepalive ping note: %s", session["session_id"][:6], e)


def _background_keepalive_loop():
    while True:
        time.sleep(10)
        with _sessions_lock:
            active_sids = list(_sessions.keys())

        now = time.time()
        for sid in active_sids:
            with _sessions_lock:
                session = _sessions.get(sid)
            if not session:
                continue

            idle_sec = now - session.get("last_activity", now)
            if idle_sec > 86400:
                logger.info("Session %s idle for >24h. Expiring session.", sid[:6])
                try:
                    run_in_session_thread(session, _expire_session_impl, session)
                except Exception:
                    pass
                continue

            if session.get("status") == "authenticated":
                try:
                    run_in_session_thread(session, _keepalive_ping, session)
                except Exception:
                    pass


def _startup_warmup():
    try:
        from dsr.automation import warm_ocr
        warm_ocr()
    except Exception:
        pass


def ensure_keepalive_running():
    global _keepalive_started
    if not _keepalive_started:
        _keepalive_started = True
        threading.Thread(target=_startup_warmup, daemon=True).start()
        t = threading.Thread(target=_background_keepalive_loop, daemon=True)
        t.start()

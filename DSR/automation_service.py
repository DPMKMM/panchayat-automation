"""Server-side Automation Service for e-Panchayat Telangana Portal.

Handles real browser automation (Playwright + ddddocr) for Department Login,
Captcha solving, OTP triggering & validation, and Report downloading.
Requires live portal access for authentication and report generation.
"""

import concurrent.futures
import hashlib
import logging
import os
import re
import shutil
import threading
import time
from uuid import uuid4
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import httpx
from shared.paths import DATA_DIR, DSR_DATA_DIR, REPORTS_DIR
from shared.portal_sql_store import PortalSQLStore

DOWNLOADS_DIR = DSR_DATA_DIR / "downloads"
DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("epts_automation_service")

# Dedicated single-thread worker for Playwright to ensure strict thread affinity (greenlet)
_bot_executor = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="EPTS_BotThread")
_generation_executor = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="EPTS_ReportQueue")
_generation_lock = threading.Lock()
_login_lock = threading.Lock()
_sessions_lock = threading.RLock()
_generation_progress_lock = threading.Lock()
_generation_progress: dict[str, dict[str, Any]] = {}
_generation_job_ids: dict[str, str] = {}
_DEFAULT_SESSION_ID = "default"
_SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
_MAX_ACTIVE_PORTAL_SESSIONS = max(1, int(os.getenv("MAX_ACTIVE_PORTAL_SESSIONS", "3")))
_SESSION_PROFILES_DIR = DSR_DATA_DIR / "runtime_profiles"
_DATA_DIR = DATA_DIR
_PORTAL_STATE_STORE = PortalSQLStore(_DATA_DIR / "attendance_jobs.sqlite3")


def _normalise_session_id(session_id: str | None) -> str:
    candidate = (session_id or _DEFAULT_SESSION_ID).strip()
    if not _SESSION_ID_PATTERN.fullmatch(candidate):
        raise ValueError("Invalid browser session. Reload the console and try again.")
    return candidate


def _new_session_state() -> dict[str, Any]:
    return {
        "bot": None,
        "user_id": "",
        "status": "idle",
        "mode": "idle",
        "last_error": "",
        "created_at": 0,
        "authenticated_at": 0,
        "last_seen_at": time.time(),
    }


_active_sessions: dict[str, dict[str, Any]] = {}


def _get_session(session_id: str | None = None) -> dict[str, Any]:
    session_key = _normalise_session_id(session_id)
    with _sessions_lock:
        now = time.time()
        stale_ids = [
            sid for sid, item in _active_sessions.items()
            if item.get("bot") is None and now - item.get("last_seen_at", now) > 60 * 60
        ]
        for sid in stale_ids:
            _active_sessions.pop(sid, None)
        session = _active_sessions.setdefault(session_key, _new_session_state())
        session["last_seen_at"] = now
        return session


def _session_profile_dir(session_id: str) -> Path:
    safe_name = hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:32]
    return _SESSION_PROFILES_DIR / safe_name


def _clean_runtime_profiles() -> None:
    if not _SESSION_PROFILES_DIR.exists():
        return
    for profile in _SESSION_PROFILES_DIR.iterdir():
        if profile.is_dir():
            try:
                shutil.rmtree(profile)
            except Exception as exc:
                logger.warning("Could not remove an old browser profile %s: %s", profile.name, exc)


def _default_progress() -> dict[str, Any]:
    return {
        "active": False,
        "status": "idle",
        "percent": 0,
        "step": 0,
        "stage": "idle",
        "message": "Ready to generate a report.",
        "remark": "Ready to generate a report.",
    }


def _start_generation_progress(session_id: str) -> None:
    with _generation_progress_lock:
        progress = _generation_progress.setdefault(session_id, _default_progress())
        progress.update({
            "active": True,
            "status": "running",
            "percent": 0,
            "step": 1,
            "stage": "starting",
            "message": "Starting report generation...",
            "remark": "Starting report generation...",
        })
        job_id = _generation_job_ids.get(session_id)
        if job_id:
            _PORTAL_STATE_STORE.update_report_job(
                job_id,
                status="running",
                step=1,
                stage="starting",
                message=progress["message"],
                remark=progress["remark"],
            )


def _set_generation_progress(session_id: str, percent: int, step: int, stage: str, message: str) -> None:
    with _generation_progress_lock:
        bounded_percent = max(0, min(99, int(percent)))
        progress = _generation_progress.setdefault(session_id, _default_progress())
        progress.update({
            "active": True,
            "status": "running",
            "percent": max(int(progress.get("percent", 0)), bounded_percent),
            "step": max(1, min(5, int(step))),
            "stage": stage,
            "message": message,
            "remark": message,
        })
        job_id = _generation_job_ids.get(session_id)
        if job_id:
            _PORTAL_STATE_STORE.update_report_job(
                job_id,
                status="running",
                percent=progress["percent"],
                step=progress["step"],
                stage=stage,
                message=message,
                remark=message,
            )


def _set_generation_remark(session_id: str, remark: str) -> None:
    """Publish the latest worker message for the frontend's server-remarks strip."""
    with _generation_progress_lock:
        progress = _generation_progress.setdefault(session_id, _default_progress())
        if progress.get("active"):
            clean_remark = str(remark).strip()
            progress["remark"] = clean_remark if len(clean_remark) <= 240 else clean_remark[:237] + "..."
            job_id = _generation_job_ids.get(session_id)
            if job_id:
                _PORTAL_STATE_STORE.update_report_job(job_id, remark=progress["remark"])


def _finish_generation_progress(session_id: str, status: str, message: str) -> None:
    with _generation_progress_lock:
        progress = _generation_progress.setdefault(session_id, _default_progress())
        if status == "complete":
            progress["percent"] = 100
            progress["step"] = 5
        progress.update({
            "active": False,
            "status": status,
            "stage": status,
            "message": message,
            "remark": message,
        })
        job_id = _generation_job_ids.get(session_id)
        if job_id:
            _PORTAL_STATE_STORE.update_report_job(
                job_id,
                status=status,
                percent=progress["percent"],
                step=progress["step"],
                stage=progress["stage"],
                message=message,
                remark=message,
            )


def get_generation_progress(session_id: str | None = None) -> dict[str, Any]:
    """Return this browser's latest SQL-backed report queue/progress snapshot."""
    session_key = _normalise_session_id(session_id)
    try:
        persisted = _PORTAL_STATE_STORE.latest_report_progress(session_key)
        if persisted:
            return persisted
    except Exception:
        logger.exception("Could not read report progress from the SQL database")
    with _generation_progress_lock:
        return dict(_generation_progress.get(session_key, _default_progress()))


def _replace_bot_executor() -> None:
    """Move Playwright to a clean thread if its previous worker retained an active loop."""
    global _bot_executor
    previous_executor = _bot_executor
    _bot_executor = concurrent.futures.ThreadPoolExecutor(
        max_workers=1,
        thread_name_prefix="EPTS_BotThread",
    )
    previous_executor.shutdown(wait=False, cancel_futures=True)


def run_in_bot_thread(func, *args, **kwargs):
    """Executes a function inside the dedicated single-thread bot executor.
    Guarantees Playwright greenlet thread affinity and serializes portal actions.
    """
    future = _bot_executor.submit(func, *args, **kwargs)
    return future.result()


# Login state belongs to this server process and its live Playwright browser.
# Remove state written by older versions that incorrectly survived restarts.
SESSION_STATE_FILE = DSR_DATA_DIR / "session_state.json"

def _clear_session_state() -> None:
    try:
        if SESSION_STATE_FILE.exists():
            SESSION_STATE_FILE.unlink()
    except Exception:
        pass

_clear_session_state()
_clean_runtime_profiles()
_PORTAL_STATE_STORE.reset_after_process_restart()


def check_epts_reachability(timeout: float = 3.0) -> tuple[bool, str]:
    """Test e-Panchayat reachability directly or through the configured India-region proxy."""
    url = "https://epanchayat.telangana.gov.in/cs"
    proxy_base = (os.getenv("DCB_PORTAL_PROXY_URL") or "").strip().rstrip("/")
    proxy_token = (os.getenv("DCB_PORTAL_PROXY_TOKEN") or "").strip()
    headers = {"User-Agent": "Mozilla/5.0"}
    if proxy_base:
        if not proxy_token:
            return False, "The e-Panchayat regional proxy is configured without its access token."
        request_url = f"{proxy_base}/v1/portal"
        headers["Authorization"] = f"Bearer {proxy_token}"
        headers["X-Portal-Target"] = url
    else:
        request_url = url
    try:
        with httpx.Client(verify=False, timeout=timeout) as client:
            resp = client.get(request_url, headers=headers)
            if resp.status_code < 500:
                return True, "Reachable through regional proxy" if proxy_base else "Reachable"
            return False, f"HTTP {resp.status_code}"
    except httpx.ConnectTimeout:
        return False, "ConnectTimeout (the cloud server's outbound IP may not be allowed by the e-Panchayat network)"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def start_server_login(
    username: str,
    password: str,
    headless: bool = True,
    session_id: str | None = None,
) -> dict[str, Any]:
    """Initiates server-side browser login to e-Panchayat portal via dedicated bot thread."""
    session_key = _normalise_session_id(session_id)
    with _login_lock:
        try:
            return run_in_bot_thread(_start_server_login_impl, username, password, headless, session_key)
        except RuntimeError as exc:
            if "Playwright Sync API inside the asyncio loop" not in str(exc):
                raise

            with _sessions_lock:
                sessions_with_browsers = [
                    item for item in _active_sessions.values() if item.get("bot") is not None
                ]
            if sessions_with_browsers:
                raise RuntimeError(
                    "Playwright needs worker recovery, but another user still has an active portal browser. "
                    "Ask active users to log out before retrying this login."
                ) from exc

            logger.warning(
                "Playwright startup found an active asyncio loop; retrying login on a fresh automation thread."
            )
            _replace_bot_executor()
            return run_in_bot_thread(_start_server_login_impl, username, password, headless, session_key)


def _start_server_login_impl(
    username: str,
    password: str,
    headless: bool = True,
    session_id: str | None = None,
) -> dict[str, Any]:
    session_key = _normalise_session_id(session_id)
    session = _get_session(session_key)

    u = username.strip()
    p = password.strip()
    if not u or not p:
        raise ValueError("User ID and Password are required.")
    existing_bot = session.get("bot")
    if existing_bot and session.get("status") == "authenticated":
        raise RuntimeError("This browser already has an authenticated e-Panchayat session. Use Logout before starting another login.")
    if existing_bot:
        try:
            existing_bot.close()
        except Exception:
            pass
        session.update(_new_session_state())
        try:
            shutil.rmtree(_session_profile_dir(session_key))
        except Exception:
            pass
    _PORTAL_STATE_STORE.clear_session(session_key)
    with _generation_progress_lock:
        _generation_progress[session_key] = _default_progress()
        _generation_job_ids.pop(session_key, None)
    with _sessions_lock:
        active_count = sum(1 for item in _active_sessions.values() if item.get("bot") is not None)
    if active_count >= _MAX_ACTIVE_PORTAL_SESSIONS:
        raise RuntimeError(
            f"The portal server is at capacity ({_MAX_ACTIVE_PORTAL_SESSIONS} active browser sessions). "
            "Please try again after another user logs out."
        )

    # 1. Test portal reachability
    reachable, reason = check_epts_reachability(timeout=15.0)

    # 2. Check if playwright and ddddocr are available
    playwright_available = False
    try:
        import playwright
        import ddddocr
        playwright_available = True
    except ImportError:
        playwright_available = False

    if not reachable:
        raise ConnectionError(f"e-Panchayat portal is not reachable from this server: {reason}")
    if not playwright_available:
        raise RuntimeError("Live portal login requires the Playwright and ddddocr dependencies.")

    bot = None
    profile_dir = _session_profile_dir(session_key)
    try:
        from .epts_automation import EPTSAutomation

        profile_dir.mkdir(parents=True, exist_ok=True)
        bot = EPTSAutomation(headless=headless, profile_dir=profile_dir)
        bot.start_browser()
        bot.navigate_home()
        bot.open_department_login_modal()
        if not bot.submit_credentials_and_generate_otp(u, p):
            raise RuntimeError("The e-Panchayat portal did not accept the submitted credentials.")

        otp_message = getattr(bot, "otp_message", "").strip() or (
            "OTP request accepted by e-Panchayat. Enter the 6-digit OTP to continue."
        )

        session.clear()
        session.update({
            "bot": bot,
            "user_id": u,
            "status": "awaiting_otp",
            "otp_message": otp_message,
            "mode": "live_portal",
            "last_error": "",
            "created_at": time.time(),
        })
        _PORTAL_STATE_STORE.save_session(session_key, session)
        return {
            "success": True,
            "step": "otp_required",
            "user_id": u,
            "mode": "live_portal",
            "message": otp_message,
            "otp_message": otp_message,
        }
    except Exception as exc:
        if bot:
            try:
                bot.close()
            except Exception:
                pass
        try:
            shutil.rmtree(profile_dir)
        except Exception:
            pass
        session.clear()
        session.update({
            "bot": None,
            "user_id": u,
            "status": "error",
            "mode": "live_portal",
            "last_error": str(exc),
            "created_at": time.time(),
        })
        _PORTAL_STATE_STORE.save_session(session_key, session)
        raise RuntimeError(f"Live e-Panchayat login failed: {exc}") from exc


def verify_server_otp(otp_code: str, session_id: str | None = None) -> dict[str, Any]:
    """Validates entered OTP on the active e-Panchayat portal session via dedicated bot thread."""
    return run_in_bot_thread(_verify_server_otp_impl, otp_code, _normalise_session_id(session_id))


def _verify_server_otp_impl(otp_code: str, session_id: str | None = None) -> dict[str, Any]:
    session = _get_session(session_id)

    clean_otp = re.sub(r"\D", "", otp_code.strip())
    if len(clean_otp) != 6:
        raise ValueError("Please enter a valid 6-digit numeric OTP.")

    bot = session.get("bot")
    user_id = session.get("user_id") or "Officer"

    if not bot or not getattr(bot, "page", None) or session.get("mode") != "live_portal":
        raise RuntimeError("No live e-Panchayat login is awaiting OTP. Start portal login again.")

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

        if "deptLoginVerified" not in page.url and "Office ID:" not in page.content():
            pvals = page.locator("#pvals")
            err_msg = pvals.inner_text().strip() if pvals.is_visible() else "Invalid OTP or session expired."
            raise ValueError(f"e-Panchayat portal error: {err_msg}")

        session["status"] = "authenticated"
        session["authenticated_at"] = time.time()
        session["user_id"] = user_id
        session.pop("otp_message", None)
        _PORTAL_STATE_STORE.save_session(_normalise_session_id(session_id), session)
        ensure_keepalive_running()
        return {
            "success": True,
            "step": "authenticated",
            "user_id": user_id,
            "message": f"e-Panchayat login verified successfully for officer {user_id}.",
        }
    except ValueError:
        raise
    except Exception as exc:
        raise RuntimeError(f"Live e-Panchayat OTP validation failed: {exc}") from exc


def generate_server_report(
    module: str = "dsr_full",
    date_str: str = "",
    session_id: str | None = None,
) -> dict[str, Any]:
    """Persist, queue, and run a report serially through the one portal worker."""
    session_key = _normalise_session_id(session_id)
    session = _get_session(session_key)
    if session.get("status") != "authenticated":
        raise PermissionError(
            "e-Panchayat session is not logged in. Please complete Department Login & OTP verification first before generating reports."
        )

    job_id = uuid4().hex
    _PORTAL_STATE_STORE.enqueue_report(session_key, job_id, module, date_str)
    with _generation_progress_lock:
        _generation_job_ids[session_key] = job_id
        _generation_progress[session_key] = {
            **_default_progress(),
            "active": True,
            "status": "queued",
            "step": 1,
            "stage": "queued",
            "message": "Waiting for another portal task to finish...",
            "remark": "Waiting for another portal task to finish...",
        }
    future = _generation_executor.submit(
        _run_queued_generation_job, job_id, session_key, module, date_str
    )
    return future.result()


def _run_queued_generation_job(job_id: str, session_key: str, module: str, date_str: str) -> dict[str, Any]:
    """Single SQL-tracked queue consumer; browser automation remains single-threaded."""
    with _generation_progress_lock:
        _generation_job_ids[session_key] = job_id
    with _generation_lock:
        _start_generation_progress(session_key)
        try:
            result = run_in_bot_thread(_generate_server_report_impl, module, date_str, session_key)
        except Exception:
            _finish_generation_progress(session_key, "error", "Report generation stopped before completion.")
            raise
        _finish_generation_progress(session_key, "complete", "Report generated successfully.")
        return result


def get_available_balance_dates(session_id: str | None = None) -> list[str]:
    """Read Thursday report dates from the active live e-Panchayat session."""
    return run_in_bot_thread(_get_available_balance_dates_impl, _normalise_session_id(session_id))


def _get_available_balance_dates_impl(session_id: str | None = None) -> list[str]:
    session = _get_session(session_id)
    bot = session.get("bot")
    if session.get("status") != "authenticated" or not bot or not getattr(bot, "page", None):
        raise PermissionError("A live e-Panchayat browser session is required to load balance dates.")
    if bot.page.is_closed():
        raise PermissionError("The live e-Panchayat browser session has closed. Please log in again.")

    from GPBalance.gp_balance_automation import fetch_available_thursday_dates

    dates = fetch_available_thursday_dates(bot)
    if not dates:
        raise RuntimeError("The live portal did not return any Thursday balance dates.")
    return dates


def _generate_server_report_impl(
    module: str = "dsr_full",
    date_str: str = "",
    session_id: str | None = None,
) -> dict[str, Any]:
    session_key = _normalise_session_id(session_id)
    session = _get_session(session_key)
    report_progress = lambda percent, step, stage, message: _set_generation_progress(
        session_key, percent, step, stage, message
    )
    report_remark = lambda remark: _set_generation_remark(session_key, remark)

    report_progress(3, 1, "session", "Checking the live e-Panchayat session...")
    is_auth = session.get("status") == "authenticated"
    if not is_auth:
        raise PermissionError(
            "e-Panchayat session is not logged in. Please complete Department Login & OTP verification first before generating reports."
        )

    bot = session.get("bot")
    user_id = session.get("user_id") or "Officer"
    req_date = date_str.strip() if date_str else datetime.now().strftime("%Y-%m-%d")

    # Module: GP Balance Entry (GM-R 14.2)
    if module == "gp_balance":
        report_progress(10, 2, "balance_download", "Reading the selected GP Balance Entry report from e-Panchayat...")
        from GPBalance import gp_balance_service
        report = gp_balance_service.generate_balance_report_pipeline(bot=bot, date_str=date_str, session_id=session_key)
        report_progress(92, 5, "balance_finalize", "Finalizing the GP Balance Entry report...")
        clean_date = report.report_date_str.replace("/", "-")
        profile_suffix = _session_profile_dir(session_key).name[:8]
        safe_dist = (report.district_name or "Official").strip().replace(' ', '_')
        pdf_path = REPORTS_DIR / f"{safe_dist}_GP_Balance_Entry_Report_{clean_date}_{profile_suffix}.pdf"
        session["latest_pdf_path"] = str(pdf_path)
        session["latest_report_date"] = report.report_date_str
        return {
            "success": True,
            "module": "gp_balance",
            "district_name": report.district_name,
            "report_date": report.report_date_str,
            "totals": {
                "total_mandals": report.total_mandals,
                "total_gps": report.total_gps,
                "total_entered_gps": report.total_entered_gps,
                "total_not_entered_gps": report.total_not_entered_gps,
                "overall_pct_entered": report.overall_pct_entered,
            },
            "message": f"GP Balance Entry Report compiled successfully for {report.report_date_str}! {report.total_entered_gps}/{report.total_gps} GPs completed ({report.overall_pct_entered:.1f}%).",
            "pdf_url": "/api/balance/report.pdf",
            "excel_url": "/api/balance/download-excel",
        }

    from .dsr_auto_download import DownloadedReport, download_single_report_with_menu, format_portal_date
    portal_date_fmt = format_portal_date(req_date)

    # Clean old downloads - strictly use newly downloaded files only
    report_progress(8, 1, "prepare", "Preparing fresh e-Panchayat report downloads...")

    downloaded_files: dict[str, DownloadedReport] = {}

    # Re-attach only this user's browser profile if its live wrapper was lost.
    if (bot is None or getattr(bot, "page", None) is None) and session.get("status") == "authenticated":
        try:
            from .epts_automation import EPTSAutomation
            cand_bot = EPTSAutomation(headless=True, profile_dir=_session_profile_dir(session_key))
            cand_bot.start_browser()
            if cand_bot.is_logged_in():
                bot = cand_bot
                session["bot"] = cand_bot
                session["mode"] = "live_portal"
                logger.info("Re-attached persistent browser automation session for Officer %s", user_id)
        except Exception as e:
            logger.warning("Could not re-attach browser: %s", e)

    # If live browser session exists, perform live portal download in sequence
    if bot and bot.page and session.get("status") == "authenticated":
        try:
            # Step 1: Select GP Monitoring -> Download GM-R 1.2.7 (DSR Raw Data Report)
            report_progress(12, 2, "raw_dsr", "Step 1 of 4: Downloading GM-R 1.2.7 DSR Raw Data...")
            logger.info("Step 1: Selecting GP Monitoring -> GM-R 1.2.7 DSR Raw Data...")
            try:
                p1 = download_single_report_with_menu(bot, "1.2.7", portal_date_fmt, on_remark=report_remark)
                if p1 and p1.contents:
                    downloaded_files["raw_dsr"] = p1
                    logger.info("Downloaded GM-R 1.2.7 into memory: %s (%d bytes)", p1.name, len(p1.contents))
                    report_progress(35, 2, "raw_dsr_complete", "Step 1 of 4 complete: DSR Raw Data downloaded.")
            except Exception as e:
                logger.error("Download GM-R 1.2.7 error: %s", e)
                raise RuntimeError(f"Failed to download GM-R 1.2.7 DSR Raw Data from e-Panchayat: {e}")

            # Step 2: Select GP Monitoring -> Download GM-R 1.2.11 (Presentees Report)
            if module in ("dsr_full", "dsr_presentees"):
                report_progress(38, 3, "presentees", "Step 2 of 4: Downloading GM-R 1.2.11 Presentees Report...")
                logger.info("Step 2: Re-selecting GP Monitoring -> GM-R 1.2.11 Presentees Report...")
                try:
                    p2 = download_single_report_with_menu(bot, "1.2.11", portal_date_fmt, on_remark=report_remark)
                    if p2 and p2.contents:
                        downloaded_files["presentees"] = p2
                        logger.info("Downloaded GM-R 1.2.11 into memory: %s (%d bytes)", p2.name, len(p2.contents))
                        report_progress(58, 3, "presentees_complete", "Step 2 of 4 complete: Presentees Report downloaded.")
                except Exception as e:
                    logger.warning("Could not download GM-R 1.2.11: %s", e)
                    report_progress(58, 3, "presentees_skipped", "Step 2 of 4 complete: continuing without Presentees data.")

            # Step 3: Select GP Monitoring -> Download GM-R 1.2.10 (Absentees Report)
            if module in ("dsr_full", "dsr_absentees"):
                report_progress(62, 4, "absentees", "Step 3 of 4: Downloading GM-R 1.2.10 Absentees Report...")
                logger.info("Step 3: Re-selecting GP Monitoring -> GM-R 1.2.10 Absentees Report...")
                try:
                    p3 = download_single_report_with_menu(bot, "1.2.10", portal_date_fmt, on_remark=report_remark)
                    if p3 and p3.contents:
                        downloaded_files["absentees"] = p3
                        logger.info("Downloaded GM-R 1.2.10 into memory: %s (%d bytes)", p3.name, len(p3.contents))
                        report_progress(80, 4, "absentees_complete", "Step 3 of 4 complete: Absentees Report downloaded.")
                except Exception as e:
                    logger.warning("Could not download GM-R 1.2.10: %s", e)
                    report_progress(80, 4, "absentees_skipped", "Step 3 of 4 complete: continuing without Absentees data.")

        except Exception as exc:
            logger.error("Live download pipeline error: %s", exc)
            raise

    raw_report = downloaded_files.get("raw_dsr")
    if not raw_report:
        raise RuntimeError(
            f"No fresh DSR attendance report was downloaded from e-Panchayat for '{portal_date_fmt}'. "
            "Please ensure the live portal session is active and retry."
        )

    # Compile report using report_generator from newly downloaded files ONLY
    from .report_generator import process_attendance_file, generate_pdf

    p_file = downloaded_files.get("presentees")
    presentees_data = (p_file.name, p_file.contents) if p_file and p_file.contents else None

    a_file = downloaded_files.get("absentees")
    absentees_data = (a_file.name, a_file.contents) if a_file and a_file.contents else None

    logger.info("Compiling report from newly downloaded file: %s (Presentees: %s, Absentees: %s)",
                raw_report.name, bool(presentees_data), bool(absentees_data))

    report_progress(84, 5, "parsing", "Step 4 of 4: Processing attendance and matching report data...")
    report = process_attendance_file(
        raw_report.name,
        raw_report.contents,
        presentees_source=presentees_data,
        absentees_source=absentees_data,
    )

    reports_dir = REPORTS_DIR
    reports_dir.mkdir(parents=True, exist_ok=True)
    profile_suffix = _session_profile_dir(session_key).name[:8]
    target_pdf = reports_dir / f"{report.district_name.replace(' ', '_')}_Official_DSR_Report_{portal_date_fmt}_{profile_suffix}.pdf"
    report_progress(94, 5, "pdf", "Step 4 of 4: Compiling the official 7-section PDF...")
    generate_pdf(report, target_pdf)

    # Save to active session state
    report_progress(98, 5, "finalize", "Finalizing the report and preparing the preview...")
    session["latest_pdf_path"] = str(target_pdf)
    session["latest_report_date"] = f"{report.report_date:%d-%b-%Y}"
    session["report_data"] = {
        "district_name": report.district_name,
        "report_date": f"{report.report_date:%d-%b-%Y}",
        "totals": report.totals,
        "mandal_rows": report.mandal_rows,
        "generated": True,
    }

    return {
        "success": True,
        "step": "completed",
        "user_id": user_id,
        "district_name": report.district_name,
        "report_date": f"{report.report_date:%d-%b-%Y}",
        "message": f"Official DSR Attendance Report for {report.district_name} ({portal_date_fmt}) prepared successfully from newly downloaded files!",
        "pdf_url": "/api/naresh/view",
        "download_url": "/api/naresh/download",
        "totals": report.totals,
    }


def get_session_status(session_id: str | None = None) -> dict[str, Any]:
    """Returns current active background session status and metadata via bot thread."""
    return run_in_bot_thread(_get_session_status_impl, _normalise_session_id(session_id))


def _get_session_status_impl(session_id: str | None = None) -> dict[str, Any]:
    session = _get_session(session_id)
    bot = session.get("bot")
    bot_alive = False
    if bot and getattr(bot, "page", None):
        try:
            bot_alive = not bot.page.is_closed()
        except Exception:
            bot_alive = False

    status = session.get("status", "idle")
    # An authenticated or OTP-pending flag is valid only while this process
    # still owns the browser that established the portal session.
    if status in {"authenticated", "awaiting_otp"} and not bot_alive:
        logger.info("Clearing stale %s session because its live browser is unavailable", status)
        if bot:
            try:
                bot.close()
            except Exception:
                pass
        session.clear()
        session.update(_new_session_state())
        _PORTAL_STATE_STORE.clear_session(_normalise_session_id(session_id))
        with _generation_progress_lock:
            _generation_progress[_normalise_session_id(session_id)] = _default_progress()
            _generation_job_ids.pop(_normalise_session_id(session_id), None)
        try:
            shutil.rmtree(_session_profile_dir(_normalise_session_id(session_id)))
        except Exception:
            pass
        status = "idle"

    is_auth = status == "authenticated" and bot_alive
    otp_message = session.get("otp_message", "") if status == "awaiting_otp" else ""
    user_id = (session.get("user_id") or "") if status != "idle" else ""
    auth_time = session.get("authenticated_at") or session.get("created_at") or 0
    age = int(time.time() - auth_time) if auth_time else 0

    return {
        "success": True,
        "authenticated": is_auth,
        "status": status,
        "user_id": user_id,
        "otp_message": otp_message,
        "mode": session.get("mode", "idle"),
        "bot_alive": bot_alive,
        "session_age_seconds": age,
        "latest_pdf_available": bool(session.get("latest_pdf_path")),
        "message": (
            otp_message
            if otp_message
            else f"Background robot service running for Officer {user_id}." if is_auth else "Session is idle."
        ),
    }


def logout_server_session(session_id: str | None = None) -> dict[str, Any]:
    """Logs out and resets the active background session via bot thread."""
    return run_in_bot_thread(_logout_server_session_impl, _normalise_session_id(session_id))


def _logout_server_session_impl(session_id: str | None = None) -> dict[str, Any]:
    session_key = _normalise_session_id(session_id)
    session = _get_session(session_key)
    bot = session.get("bot")
    portal_logout_triggered = False
    cookies_cleared = False
    background_browser_stopped = bot is None
    shutdown_error = ""

    if bot:
        try:
            logout_from_portal = getattr(bot, "logout_from_portal", None)
            if callable(logout_from_portal):
                portal_logout_triggered = bool(logout_from_portal())
        except Exception as exc:
            logger.warning("Could not click the e-Panchayat logout control: %s", exc)

        context = getattr(bot, "context", None)
        if context:
            try:
                context.clear_cookies()
                cookies_cleared = True
            except Exception as exc:
                logger.warning("Could not clear the persistent portal cookies: %s", exc)

            for page in getattr(context, "pages", []):
                try:
                    if not page.is_closed():
                        page.evaluate("""() => {
                            try { localStorage.clear(); } catch (e) {}
                            try { sessionStorage.clear(); } catch (e) {}
                        }""")
                except Exception:
                    pass

        try:
            bot.close()
            background_browser_stopped = True
        except Exception as exc:
            shutdown_error = str(exc)
            logger.exception("Could not stop the e-Panchayat background browser cleanly")
            # Attempt both shutdown steps if the automation object's close failed.
            fallback_errors = []
            if context:
                try:
                    context.close()
                except Exception as fallback_exc:
                    fallback_errors.append(str(fallback_exc))
            playwright = getattr(bot, "playwright", None)
            if playwright:
                try:
                    playwright.stop()
                except Exception as fallback_exc:
                    fallback_errors.append(str(fallback_exc))
            background_browser_stopped = not fallback_errors
            if fallback_errors:
                shutdown_error = f"{shutdown_error}; fallback: {'; '.join(fallback_errors)}"

    profile_dir = getattr(bot, "profile_dir", None) if bot else _session_profile_dir(session_key)
    session.clear()
    session.update(_new_session_state())
    session["last_seen_at"] = time.time()
    session["created_at"] = time.time()
    _PORTAL_STATE_STORE.clear_session(session_key)
    if profile_dir:
        try:
            shutil.rmtree(profile_dir)
        except Exception as exc:
            logger.warning("Could not remove the logged-out browser profile %s: %s", profile_dir, exc)
    try:
        from GPBalance import gp_balance_service
        gp_balance_service.clear_session_data(session_key)
    except Exception as exc:
        logger.warning("Could not clear GP Balance report state for one browser: %s", exc)
    with _generation_progress_lock:
        _generation_progress[session_key] = _default_progress()
        _generation_job_ids.pop(session_key, None)
    success = background_browser_stopped
    if portal_logout_triggered:
        message = "Portal logout control selected; cookies cleared and background browser stopped."
    elif cookies_cleared:
        message = "Portal cookies cleared and background browser stopped; portal logout control was not found."
    else:
        message = "Background browser stopped and local session cleared; portal logout could not be confirmed."
    if shutdown_error:
        message = "Local session cleared, but the background browser could not be confirmed stopped."

    return {
        "success": success,
        "portal_logout_triggered": portal_logout_triggered,
        "cookies_cleared": cookies_cleared,
        "background_browser_stopped": background_browser_stopped,
        "message": message,
    }


def is_authenticated(session_id: str | None = None) -> bool:
    # Run Playwright checks on its owning thread and require a live browser.
    return bool(get_session_status(session_id).get("authenticated"))


_keepalive_started = False
_keepalive_stop_event = threading.Event()


def get_report_data(session_id: str | None = None) -> dict[str, Any] | None:
    session = _get_session(session_id)
    report_data = session.get("report_data")
    return dict(report_data) if isinstance(report_data, dict) else None


def get_latest_pdf_path(session_id: str | None = None) -> str | None:
    return _get_session(session_id).get("latest_pdf_path")


def _keepalive_ping_all():
    with _sessions_lock:
        sessions = list(_active_sessions.values())
    for session in sessions:
        bot = session.get("bot")
        if bot and getattr(bot, "page", None) and session.get("status") == "authenticated":
            try:
                if not bot.page.is_closed():
                    bot.page.evaluate("() => document.title")
            except Exception as exc:
                logger.debug("Background keepalive ping note: %s", exc)


def _background_keepalive_loop():
    while not _keepalive_stop_event.wait(120):
        try:
            run_in_bot_thread(_keepalive_ping_all)
        except Exception:
            pass


def ensure_keepalive_running():
    """Starts the background session keepalive thread if not already running."""
    global _keepalive_started
    if not _keepalive_started or _keepalive_stop_event.is_set():
        _keepalive_stop_event.clear()
        _keepalive_started = True
        t = threading.Thread(target=_background_keepalive_loop, daemon=True)
        t.start()

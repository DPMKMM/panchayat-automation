"""Unit tests to verify masked mobile number rendering and OTP notice normalization."""

import pytest
from core.session_manager import (
    _resolve_fallback_masked_mobile,
    get_or_create_session,
    get_session_status,
)


def test_resolve_fallback_masked_mobile():
    # Empty session and user -> default official number
    sess = {}
    assert _resolve_fallback_masked_mobile(sess, "") == "xxxxxx5586"

    # Literal 'registered mobile' in session -> default official number
    sess["mobile_number"] = "registered mobile"
    assert _resolve_fallback_masked_mobile(sess, "") == "xxxxxx5586"

    # Valid 10 digit number -> masked with last 4 digits
    sess["mobile_number"] = "9876543210"
    assert _resolve_fallback_masked_mobile(sess, "") == "xxxxxx3210"

    # Already masked format
    sess["mobile_number"] = "xxxxxx5586"
    assert _resolve_fallback_masked_mobile(sess, "") == "xxxxxx5586"


def test_awaiting_otp_status_response_includes_masked_mobile():
    sid = "test_otp_masking_sid"
    session = get_or_create_session(sid)
    session["user_id"] = "DPOA3698"
    session["status"] = "awaiting_otp"
    # Even if session has literal 'registered mobile' or empty
    session["mobile_number"] = "registered mobile"
    session["otp_message"] = "A 6 digit OTP has been sent to your registered mobile number registered mobile. Enter OTP to continue."

    status = get_session_status(sid)
    assert status["status"] == "awaiting_otp"
    assert status["mobile_number"] == "xxxxxx5586"
    assert "registered mobile number registered mobile" not in status["otp_message"]
    assert "xxxxxx5586" in status["otp_message"]
    assert status["otp_message"] == "A 6 digit OTP has been sent to your registered mobile number xxxxxx5586. Enter OTP to continue."

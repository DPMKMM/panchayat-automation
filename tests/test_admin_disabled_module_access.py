"""Unit tests verifying that disabled or hidden modules remain accessible and visible to administrators for testing purposes."""

import pytest
from core.access_policy import (
    can_user_access_automated_reports,
    get_access_policy,
    is_module_enabled,
    is_module_visible,
    update_access_policy,
)


@pytest.fixture(autouse=True)
def restore_policy():
    """Ensure access policy is reset before and after tests."""
    from core.access_policy import DEFAULT_POLICY, update_access_policy
    update_access_policy(DEFAULT_POLICY)
    yield
    update_access_policy(DEFAULT_POLICY)


def test_disabled_module_accessible_to_admin():
    # Disable module_dsr_excel
    update_access_policy({"module_dsr_excel": False})

    # Standard user or anonymous: disabled
    standard_user = {"user_id": "usr_standard", "is_admin": False, "role": "officer"}
    assert is_module_enabled("module_dsr_excel", user=None) is False
    assert is_module_enabled("module_dsr_excel", user=standard_user) is False

    # Admin user: remains accessible for testing
    admin_user = {"user_id": "usr_admin", "is_admin": True, "role": "admin"}
    assert is_module_enabled("module_dsr_excel", user=admin_user) is True


def test_hidden_module_visible_to_admin():
    # Hide module_state_format
    update_access_policy({"visible_module_state_format": False})

    # Standard user or anonymous: not visible
    standard_user = {"user_id": "usr_standard", "is_admin": False, "role": "officer"}
    assert is_module_visible("module_state_format", user=None) is False
    assert is_module_visible("module_state_format", user=standard_user) is False

    # Admin user: remains visible for testing
    admin_user = {"user_id": "usr_admin", "is_admin": True, "role": "admin"}
    assert is_module_visible("module_state_format", user=admin_user) is True


def test_admin_access_to_console_when_disabled():
    update_access_policy({"console_enabled": False, "automated_subscription_required": True})

    standard_user = {"user_id": "usr_standard", "is_admin": False, "has_automated_subscription": False}
    assert can_user_access_automated_reports(standard_user) is False

    admin_user = {"user_id": "usr_admin", "is_admin": True, "has_automated_subscription": False}
    assert can_user_access_automated_reports(admin_user) is True

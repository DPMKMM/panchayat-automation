"""Unit and integration tests for email registration, password login, and user profile management."""

import pytest
from fastapi.testclient import TestClient

from app import app
from core.firebase_store import (
    authenticate_email_password_user,
    get_user_by_gmail,
    hash_password,
    register_email_password_user,
    reset_inmemory_firestore,
    update_user_profile_details,
    verify_password,
)


@pytest.fixture(autouse=True)
def setup_test_db():
    reset_inmemory_firestore()
    yield
    reset_inmemory_firestore()


def test_password_hashing_and_verification():
    pwd = "SecretPassword123!"
    hashed, salt = hash_password(pwd)
    assert hashed and salt
    assert len(salt) >= 16
    assert verify_password(pwd, hashed, salt) is True
    assert verify_password("WrongPassword", hashed, salt) is False
    assert verify_password("", hashed, salt) is False


def test_register_email_user_and_citizen_designation():
    user = register_email_password_user(
        email="citizen.rajesh@example.com",
        password="ValidPassword123",
        surname="Kandula",
        name="Rajesh",
        display_name="Rajesh K",
        gender="Male",
        mobile_number="9876543210",
        state="Telangana",
        district="Khammam",
        mandal="Nelakondapalli",
        village_gp="Nelakondapalli",
        designation="CITIZEN",
    )
    assert user["email"] == "citizen.rajesh@example.com"
    assert user["name"] == "Rajesh"
    assert user["surname"] == "Kandula"
    assert user["display_name"] == "Rajesh K"
    assert user["gender"] == "Male"
    assert user["mobile_number"] == "9876543210"
    assert user["district"] == "Khammam"
    assert user["designation"] == "CITIZEN"
    assert user["role"] == "Citizen"
    assert user["auth_provider"] == "email"
    assert user["password_hash"] != ""


def test_register_duplicate_email_raises_error():
    register_email_password_user(
        email="unique.officer@example.com",
        password="ValidPassword123",
        name="Officer One",
        mobile_number="9876543210",
        designation="PS",
    )
    with pytest.raises(ValueError, match="already exists"):
        register_email_password_user(
            email="unique.officer@example.com",
            password="AnotherPassword",
            name="Officer Two",
            mobile_number="9876543211",
            designation="MPO",
        )


def test_register_other_designation_requires_custom_text():
    with pytest.raises(ValueError, match="specify your designation"):
        register_email_password_user(
            email="other.officer@example.com",
            password="ValidPassword123",
            name="Special Auditor",
            mobile_number="9876543210",
            designation="OTHER",
            designation_other="",
        )

    user = register_email_password_user(
        email="other.officer@example.com",
        password="ValidPassword123",
        name="Special Auditor",
        mobile_number="9876543210",
        designation="OTHER",
        designation_other="Audit Officer",
    )
    assert user["designation"] == "OTHER"
    assert user["designation_other"] == "Audit Officer"


def test_authenticate_email_password_user():
    register_email_password_user(
        email="secretary.suresh@example.com",
        password="MySecretPassword123",
        name="Suresh Kumar",
        mobile_number="9848012345",
        designation="PS",
    )

    # Success
    auth_user = authenticate_email_password_user(
        email="secretary.suresh@example.com",
        password="MySecretPassword123",
    )
    assert auth_user["email"] == "secretary.suresh@example.com"
    assert auth_user["name"] == "Suresh Kumar"

    # Bad password
    with pytest.raises(ValueError, match="Incorrect password"):
        authenticate_email_password_user(
            email="secretary.suresh@example.com",
            password="WrongPassword",
        )

    # Unknown email
    with pytest.raises(ValueError, match="No account found"):
        authenticate_email_password_user(
            email="nonexistent@example.com",
            password="SomePassword",
        )


def test_update_user_profile_details():
    user = register_email_password_user(
        email="edit.profile@example.com",
        password="Password123",
        name="Initial Name",
        mobile_number="9876543210",
        designation="CITIZEN",
    )
    uid = user["user_id"]

    updated = update_user_profile_details(
        user_id=uid,
        surname="Goud",
        name="Updated Name",
        display_name="Goud Updated",
        gender="Male",
        mobile_number="9848099999",
        state="Telangana",
        district="Warangal",
        mandal="Narsampet",
        village_gp="Maheshwaram",
        designation="PS",
    )
    assert updated["surname"] == "Goud"
    assert updated["name"] == "Updated Name"
    assert updated["display_name"] == "Goud Updated"
    assert updated["mobile_number"] == "9848099999"
    assert updated["district"] == "Warangal"
    assert updated["mandal"] == "Narsampet"
    assert updated["village_gp"] == "Maheshwaram"
    assert updated["designation"] == "PS"
    assert updated["role"] == "Mandal Level"


def test_api_auth_register_and_login_flow():
    client = TestClient(app)

    # 1. Register API
    reg_resp = client.post(
        "/api/auth/register",
        json={
            "surname": "Babu",
            "name": "Naresh",
            "display_name": "Naresh Babu",
            "gender": "Male",
            "mobile_number": "9876543210",
            "state": "Telangana",
            "district": "Khammam",
            "mandal": "Khammam Urban",
            "village_gp": "Khammam",
            "designation": "DPM",
            "email": "naresh.dpm@example.com",
            "password": "StrongPassword99",
        },
    )
    assert reg_resp.status_code == 200
    reg_data = reg_resp.json()
    assert reg_data["success"] is True
    assert reg_data["user"]["designation"] == "DPM"
    assert reg_data["user"]["district"] == "Khammam"
    assert reg_data["user"]["display_name"] == "Naresh Babu"

    # 2. Login API
    login_resp = client.post(
        "/api/auth/email-login",
        json={
            "email": "naresh.dpm@example.com",
            "password": "StrongPassword99",
        },
    )
    assert login_resp.status_code == 200
    login_data = login_resp.json()
    assert login_data["success"] is True
    assert login_data["token"] != ""
    token = login_data["token"]

    # 3. Update Profile API
    update_resp = client.post(
        "/api/auth/update-profile",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "surname": "Babu",
            "name": "Naresh Parala",
            "display_name": "Naresh Parala",
            "gender": "Male",
            "mobile_number": "9876543210",
            "state": "Telangana",
            "district": "Khammam",
            "mandal": "Khammam Rural",
            "village_gp": "Mallepally",
            "designation": "OTHER",
            "designation_other": "Project Director",
        },
    )
    assert update_resp.status_code == 200
    upd_data = update_resp.json()
    assert upd_data["success"] is True
    assert upd_data["user"]["name"] == "Naresh Parala"
    assert upd_data["user"]["designation"] == "OTHER"
    assert upd_data["user"]["designation_other"] == "Project Director"
    assert upd_data["user"]["effective_designation"] == "Project Director"

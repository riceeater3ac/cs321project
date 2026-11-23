"""Tests for the email-code login flow, /main, and logout."""
import re

import pytest

from app import mail
from conftest import GMU_EMAIL, flashed, session_value


# ---------- Public pages ----------

def test_home_page_loads(client):
    assert client.get("/").status_code == 200


def test_login_page_loads(client):
    assert client.get("/login").status_code == 200


# ---------- Step 1: submitting an email ----------

@pytest.mark.parametrize("email", [
    "someone@gmail.com",
    "someone@gmu.edu.evil.com",
    "someone@mail.gmu.edu",
    "gmu.edu",
    "",
])
def test_non_gmu_email_is_rejected(client, email):
    with mail.record_messages() as outbox:
        response = client.post("/login", data={"user": email})

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
    assert outbox == []                                   # nothing was emailed
    assert session_value(client, "pending_email") is None
    assert ("error", "Only GMU emails accepted.") in flashed(client)


def test_gmu_email_sends_code_and_goes_to_validate(client):
    with mail.record_messages() as outbox:
        response = client.post("/login", data={"user": GMU_EMAIL})

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/validate")
    assert len(outbox) == 1
    assert outbox[0].recipients == [GMU_EMAIL]
    assert re.search(r"\b\d{4}\b", outbox[0].body)
    assert session_value(client, "pending_email") == GMU_EMAIL


def test_email_check_ignores_case_and_whitespace(client):
    with mail.record_messages() as outbox:
        response = client.post("/login", data={"user": "  Student@GMU.EDU  "})

    assert response.headers["Location"].endswith("/validate")
    assert outbox[0].recipients == ["Student@GMU.EDU"]


def test_code_is_always_four_digits(get_code):
    for _ in range(25):
        code = get_code()
        assert len(code) == 4 and 1000 <= int(code) <= 9999


def test_email_failure_is_handled(client, monkeypatch):
    def boom(message):
        raise RuntimeError("SMTP is down")
    monkeypatch.setattr(mail, "send", boom)

    response = client.post("/login", data={"user": GMU_EMAIL})

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
    assert ("error", "Failed to send email.") in flashed(client)


# ---------- Step 2: entering the code ----------

def test_validate_without_pending_email_redirects_to_login(client):
    response = client.get("/validate")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_validate_page_loads_after_email_step(client, get_code):
    get_code()
    assert client.get("/validate").status_code == 200


def test_wrong_code_is_rejected(client, get_code):
    code = get_code()
    wrong = "1234" if code != "1234" else "4321"

    response = client.post("/validate", data={"code": wrong})

    assert response.headers["Location"].endswith("/validate")
    assert ("error", "Incorrect code.") in flashed(client)
    assert session_value(client, "user") is None


def test_correct_code_logs_user_in(client, get_code):
    code = get_code()

    response = client.post("/validate", data={"code": f" {code} "})  # spaces ok

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/main")
    assert session_value(client, "user") == GMU_EMAIL
    # the one-time code and pending state are cleared after use
    assert session_value(client, "login_code") is None
    assert session_value(client, "pending_email") is None


def test_new_login_attempt_invalidates_old_code(client, get_code):
    old_code = get_code()
    new_code = get_code()
    if old_code == new_code:
        pytest.skip("random codes happened to match")

    client.post("/validate", data={"code": old_code})

    assert session_value(client, "user") is None


# ---------- /main ----------

def test_main_requires_login(client):
    response = client.get("/main")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_main_sends_unverified_user_to_validate(client, get_code):
    get_code()  # email entered, code not yet submitted

    response = client.get("/main")

    assert response.headers["Location"].endswith("/validate")


def test_main_loads_when_logged_in(client, log_in, templates):
    log_in()

    response = client.get("/main")

    assert response.status_code == 200
    name, context = templates[-1]
    assert name == "main.html"
    assert context["user"] == GMU_EMAIL


def test_login_page_redirects_if_already_logged_in(client, log_in):
    log_in()

    response = client.get("/login")

    assert response.headers["Location"].endswith("/main")


# ---------- Logout ----------

def test_logout_clears_session(client, log_in):
    log_in()

    response = client.get("/logout")

    assert response.headers["Location"].endswith("/login")
    assert session_value(client, "user") is None
    assert client.get("/main").headers["Location"].endswith("/login")


def test_logout_when_not_logged_in_is_harmless(client):
    response = client.get("/logout")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")

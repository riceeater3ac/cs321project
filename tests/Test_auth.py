"""Tests for login (currently just an email), /main, and logout."""
import pytest

from conftest import USER_EMAIL, flashed, redirect_path, session_value


# ---------- Login page ----------

def test_login_page_loads(client, templates):
    response = client.get("/")

    assert response.status_code == 200
    assert templates[-1][0] == "home.html"


def test_valid_email_logs_in(client):
    response = client.post("/", data={"user": f"  {USER_EMAIL}  "})  # spaces trimmed

    assert response.status_code == 302
    assert redirect_path(response) == "/main"
    assert session_value(client, "user") == USER_EMAIL


@pytest.mark.parametrize("email", ["", "   "])
def test_blank_email_is_rejected(client, email):
    response = client.post("/", data={"user": email})

    assert redirect_path(response) == "/"
    assert ("error", "Please enter your email.") in flashed(client)
    assert session_value(client, "user") is None


def test_missing_email_field_is_a_bad_request(client):
    assert client.post("/", data={}).status_code == 400


def test_logged_in_user_is_sent_to_main(client, log_in):
    log_in()

    response = client.get("/")

    assert redirect_path(response) == "/main"


def test_logging_in_again_replaces_the_previous_user(client, log_in):
    log_in("first@gmu.edu")
    client.post("/", data={"user": "second@gmu.edu"})

    assert session_value(client, "user") == "second@gmu.edu"


# ---------- /main ----------

def test_main_requires_login(client):
    response = client.get("/main")

    assert redirect_path(response) == "/"
    assert ("error", "Please enter email.") in flashed(client)


def test_main_loads_when_logged_in(client, log_in, templates):
    log_in()

    response = client.get("/main")

    assert response.status_code == 200
    name, context = templates[-1]
    assert name == "main.html"
    assert context["user"] == USER_EMAIL


# ---------- Logout ----------

def test_logout_clears_the_session(client, log_in):
    log_in()

    response = client.get("/logout")

    assert redirect_path(response) == "/"
    assert session_value(client, "user") is None
    assert ("info", "You have been logged out.") in flashed(client)
    assert redirect_path(client.get("/main")) == "/"


def test_logout_when_not_logged_in_is_harmless(client):
    response = client.get("/logout")

    assert redirect_path(response) == "/"
    assert flashed(client) == []


# ---------- Known gaps (see the note at the bottom of test_reports.py) ----------
# These describe the behavior the login code is meant to have eventually. They
# are marked xfail because login() currently skips these checks on purpose
# ("temporarily disabled" / "TEMPORARY" in app.py). When you turn the checks
# back on, they start passing, and strict=True makes the run fail so you
# remember to delete the markers.

@pytest.mark.xfail(strict=True, reason="GMU email restriction is temporarily disabled in login()")
@pytest.mark.parametrize("email", [
    "someone@gmail.com",
    "someone@gmu.edu.evil.com",
    "someone@mail.gmu.edu",
])
def test_non_gmu_email_is_rejected(client, email):
    client.post("/", data={"user": email})

    assert session_value(client, "user") is None
    assert ("error", "Only GMU emails accepted.") in flashed(client)


@pytest.mark.xfail(strict=True, reason="email verification is skipped for MVP testing")
def test_email_alone_does_not_log_in(client):
    client.post("/", data={"user": USER_EMAIL})

    assert session_value(client, "user") is None

"""Shared fixtures for the MasonFind tests."""
import os
import re
import sqlite3
import tempfile

# app.py creates the database and upload folder when it is imported, so point
# them at a throwaway location before importing it. This keeps the tests away
# from real masonfind.db and static/uploads.
_IMPORT_DIR = tempfile.mkdtemp(prefix="masonfind-import-")
os.environ["DATABASE"] = os.path.join(_IMPORT_DIR, "import.db")
os.environ["UPLOAD_FOLDER"] = os.path.join(_IMPORT_DIR, "uploads")
os.environ["FLASK_SECRET_KEY"] = "test-secret-key"
# Flask-Mail needs a sender address even when nothing is really sent. Setting
# these here also stops a developer's real .env credentials from being used.
os.environ["MAIL_USERNAME"] = "masonfind-tests@example.com"
os.environ["MAIL_PASSWORD"] = "not-a-real-password"

import pytest
from flask import template_rendered

from app import app as flask_app, mail, init_db

GMU_EMAIL = "student@gmu.edu"


@pytest.fixture
def app(tmp_path):
    """The Flask app, using a fresh database and upload folder per test."""
    flask_app.config.update(
        TESTING=True,
        DATABASE=str(tmp_path / "test.db"),
        UPLOAD_FOLDER=str(tmp_path / "uploads"),
    )
    # Flask-Mail decides whether to really send mail when it is created
    # (not when TESTING is set later), so switch sending off explicitly.
    flask_app.extensions["mail"].suppress = True
    init_db()
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def query(app):
    """Run a SELECT against the test database and return the rows."""
    def run(sql, params=()):
        conn = sqlite3.connect(app.config["DATABASE"])
        conn.row_factory = sqlite3.Row
        try:
            return conn.execute(sql, params).fetchall()
        finally:
            conn.close()
    return run


@pytest.fixture
def get_code(client):
    """Submit the login form and return the 4-digit code that was 'emailed'."""
    def run(email=GMU_EMAIL):
        with mail.record_messages() as outbox:
            client.post("/login", data={"user": email})
        assert len(outbox) == 1, "expected exactly one login email"
        return re.search(r"\d{4}", outbox[0].body).group()
    return run


@pytest.fixture
def log_in(client, get_code):
    """Complete the whole email-code login for the given address."""
    def run(email=GMU_EMAIL):
        code = get_code(email)
        client.post("/validate", data={"code": code})
        return client
    return run


@pytest.fixture
def templates(app):
    """Record which templates were rendered and the data passed to them."""
    rendered = []

    def record(sender, template, context, **extra):
        rendered.append((template.name, context))

    template_rendered.connect(record, app)
    yield rendered
    template_rendered.disconnect(record, app)


def session_value(client, key, default=None):
    with client.session_transaction() as sess:
        return sess.get(key, default)


def flashed(client):
    """Return the flash messages waiting in the session as [(category, text)]."""
    with client.session_transaction() as sess:
        return list(sess.get("_flashes", []))

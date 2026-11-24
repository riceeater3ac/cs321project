"""Shared fixtures for the MasonFind tests."""
import os
import sqlite3
import tempfile
from urllib.parse import urlparse

# app.py creates the database and upload folder when it is imported, so point
# them at a throwaway location BEFORE importing it. This keeps the tests away
# from your real masonfind.db and static/uploads.
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

from app import app as flask_app, init_db

USER_EMAIL = "student@gmu.edu"


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
def log_in(client):
    """Log the test client in as a user (login is just an email right now)."""
    def run(email=USER_EMAIL):
        response = client.post("/", data={"user": email})
        assert session_value(client, "user") == email.strip(), "login helper failed"
        return response
    return run


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
def add_item(app):
    """Insert an item straight into the database and return its id."""
    def run(table="lost_items", **overrides):
        date_column = "date_lost" if table == "lost_items" else "date_found"
        row = {
            "item_name": "Keys",
            "category": "Keys",
            "description": "Silver ring with two keys",
            "location": "Johnson Center",
            date_column: "2026-11-20",
            "image": None,
            "status": "Open",
        }
        row.update(overrides)
        columns = ", ".join(row)
        marks = ", ".join("?" * len(row))
        conn = sqlite3.connect(app.config["DATABASE"])
        try:
            cursor = conn.execute(
                f"INSERT INTO {table} ({columns}) VALUES ({marks})", tuple(row.values()))
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()
    return run


@pytest.fixture
def templates(app):
    """Record (template name, context) for every template that gets rendered."""
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


def redirect_path(response):
    """The path a redirect response points to (ignores host / query string)."""
    return urlparse(response.headers["Location"]).path


def flashed(client):
    """Return the flash messages waiting in the session as [(category, text)]."""
    with client.session_transaction() as sess:
        return list(sess.get("_flashes", []))

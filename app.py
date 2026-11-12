from flask import Flask, render_template, url_for, request, redirect, session, flash
from flask_mail import Mail, Message
import sqlite3
import os
import random

# New imports for image uploads
from pathlib import Path
from uuid import uuid4
from PIL import Image, UnidentifiedImageError

from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)

# Application configuration
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "development-only-secret")

# Email configuration
app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 465
app.config["MAIL_USERNAME"] = os.environ.get("MAIL_USERNAME")
app.config["MAIL_PASSWORD"] = os.environ.get("MAIL_PASSWORD")
app.config["MAIL_USE_TLS"] = False
app.config["MAIL_USE_SSL"] = True

mail = Mail(app)

# Image upload configuration
UPLOAD_FOLDER = Path(app.root_path) / "static" / "uploads"
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

def save_image(file):
    if not file or not file.filename:
        return None

    extension = file.filename.rsplit(".", 1)[-1].lower()

    if extension not in {"jpg", "jpeg", "png", "webp"}:
        raise ValueError("Only JPG, PNG, and WEBP images are allowed.")

    try:
        with Image.open(file.stream) as img:
            img.verify()

        file.stream.seek(0)

        with Image.open(file.stream) as img:
            if img.width * img.height > 20_000_000:
                raise ValueError("Image is too large.")

            filename = f"{uuid4().hex}.jpg"
            img.convert("RGB").save(
                UPLOAD_FOLDER / filename, "JPEG"
            )

        return filename

    except (UnidentifiedImageError, OSError):
        raise ValueError("Invalid image file.")


# ======================================
# DATABASE
# ======================================
def init_db():
    with sqlite3.connect("masonfind.db") as conn:

        conn.execute("""
            CREATE TABLE IF NOT EXISTS lost_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_name TEXT NOT NULL,
                category TEXT NOT NULL,
                description TEXT NOT NULL,
                location TEXT NOT NULL,
                date_lost TEXT NOT NULL,
                image TEXT,
                status TEXT NOT NULL DEFAULT 'Open'
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS found_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_name TEXT NOT NULL,
                category TEXT NOT NULL,
                description TEXT NOT NULL,
                location TEXT NOT NULL,
                date_found TEXT NOT NULL,
                image TEXT,
                status TEXT NOT NULL DEFAULT 'Open'
            )
        """)

        # Add new columns to existing tables
        for table in ("lost_items", "found_items"):
            columns = {
                row[1] for row in conn.execute(
                    f"PRAGMA table_info({table})"
                )
            }

            if "image" not in columns:
                conn.execute(
                    f"ALTER TABLE {table} ADD COLUMN image TEXT"
                )

            if "status" not in columns:
                conn.execute(
                    f"ALTER TABLE {table} "
                    "ADD COLUMN status TEXT NOT NULL DEFAULT 'Open'"
                )


# ======================================
# LOGIN / HOME PAGE
# ======================================
@app.route("/", methods=["GET", "POST"])
def login():

    try:
        if request.method == "POST":
            email = request.form["user"].strip()

            #ensure the user's address is a gmu address
            if not email.lower().endswith("@gmu.edu"):
                flash("Only GMU emails accepted.", "error")
                return redirect(url_for("login"))

            session.clear()
            session["pending_email"] = email

            #generate a random 4-digit login code on each login attempt.
            #there are more secure ways to do this, but this should be fine for demonstration purposes.
            session["login_code"] = random.randint(1000, 9999)

            title = "Your MasonFind Login Code"
            body = "Your MasonFind login code is " + str(session["login_code"])
            send_email(title, body, email)

            return redirect(url_for("validate"))

        if session.get("user"):
            return redirect(url_for("mainpage"))

        return render_template("home.html")

    except Exception:
        app.logger.exception("Failed to send email.")
        flash("Failed to send email.", "error")
        return redirect(url_for("login"))


# ======================================
# EMAIL VERIFICATION
# ======================================
@app.route("/validate", methods=["GET", "POST"])
def validate():
    if "pending_email" not in session:
        flash("Please enter email.", "error")
        return redirect(url_for("login"))

    if request.method == "POST":
        code = request.form["code"].strip()

        if code == str(session.get("login_code", "")):
            email = session["pending_email"]
            session.clear()
            session["user"] = email
            return redirect(url_for("mainpage"))

        flash("Incorrect code.", "error")
        return redirect(url_for("validate"))

    return render_template("validate.html")

# ======================================
# MAIN PAGE
# ======================================
@app.route("/main")
def mainpage():
    if "user" not in session:
        if "pending_email" in session:
            flash("Please enter verification code.", "error")
            return redirect(url_for("validate"))
        flash("Please enter email.", "error")
        return redirect(url_for("login"))

    return render_template("main.html", user=session["user"])


# ======================================
# LOGOUT
# ======================================
@app.route("/logout")
def logout():
    if "user" in session:
        session.clear()
        flash("You have been logged out.", "info")

    return redirect(url_for("login"))


# ======================================
# REPORT LOST ITEM
# ======================================
@app.route("/report-lost", methods=["GET", "POST"])
def report_lost():
    if request.method == "POST":
        item_name = request.form["item_name"].strip()
        category = request.form["category"]
        description = request.form["description"].strip()
        location = request.form["location"].strip()
        date_lost = request.form["date_lost"]

        if not all([item_name, category, description, location, date_lost]):
            return "Please complete all fields.", 400

        # Save uploaded photo
        try:
            image = save_image(request.files.get("image"))
        except ValueError as error:
            return str(error), 400

        # Save item details and image in database
        with sqlite3.connect("masonfind.db") as conn:
            conn.execute("""
                INSERT INTO lost_items
                (item_name, category, description,
                 location, date_lost, image, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                item_name,
                category,
                description,
                location,
                date_lost,
                image,
                "Open"
            ))

        return redirect(url_for("lost_items"))

    return render_template("report_lost.html")

# ======================================
# VIEW LOST ITEMS
# ======================================
@app.route("/lost-items")
def lost_items():
    with sqlite3.connect("masonfind.db") as conn:
        conn.row_factory = sqlite3.Row

        items = conn.execute(
            "SELECT * FROM lost_items ORDER BY id DESC"
        ).fetchall()

    return render_template("lost_items.html", items=items)


# ======================================
# MOVE TO FOUND ITEMS
# ======================================
@app.route("/lost-items/<int:item_id>/mark-found", methods=["POST"])
def mark_found(item_id):
    # Save item details and image in database
    with sqlite3.connect("masonfind.db") as conn:
        conn.row_factory = sqlite3.Row

        item = conn.execute(
            "SELECT * FROM lost_items WHERE id = ?",
            (item_id, )
        ).fetchone()

        conn.execute("""
            INSERT INTO found_items
            (item_name, category, description,
             location, date_found, image, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            item["item_name"],
            item["category"],
            item["description"],
            item["location"],
            item["date_lost"],
            item["image"],
            "Closed"
        ))

        title = "An item has been found!"
        body = f"Your item: {item["item_name"]} has been found."
        send_email(title, body, session["user"])

        conn.execute(
            f"DELETE FROM lost_items WHERE id = ?",
            (item_id, )
        )

    return redirect(url_for("found_items"))

# ======================================
# VIEW FOUND ITEMS
# ======================================
@app.route("/found-items")
def found_items():
    with sqlite3.connect("masonfind.db") as conn:
        conn.row_factory = sqlite3.Row

        items = conn.execute(
            "SELECT * FROM found_items ORDER BY id DESC"
        ).fetchall()

    return render_template("found_items.html", items=items)

# ======================================
# SEND EMAIL
# ======================================
def send_email(title, body, recipient):
    msg = Message(
        title,
        sender=app.config["MAIL_USERNAME"],
        recipients=[recipient]
        )
    msg.body = body
    mail.send(msg)

# ======================================
# REMOVE ITEM
# ======================================
@app.route("/<item_type>-items/<int:item_id>/delete", methods=["POST"])
def delete_item(item_type, item_id):
    with sqlite3.connect("masonfind.db") as conn:
        conn.execute(
            f"DELETE FROM {item_type}_items WHERE id = ?",
            (item_id, )
        )

    return redirect(request.referrer)

# ======================================
# START APPLICATION
# ======================================
init_db()

if __name__ == "__main__":
    app.run(debug=True)
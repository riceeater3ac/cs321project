
from flask import Flask, render_template, url_for, request, redirect, session, flash
from flask_mail import Mail, Message
import sqlite3
import os

app = Flask(__name__)

# Application configuration
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "development-only-secret")

# Email configuration
app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 465
app.config["MAIL_USERNAME"] = "cs321lostandfound@gmail.com"
app.config["MAIL_PASSWORD"] = os.environ.get("MAIL_PASSWORD")
app.config["MAIL_USE_TLS"] = False
app.config["MAIL_USE_SSL"] = True

mail = Mail(app)


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
                date_lost TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS found_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_name TEXT NOT NULL,
                category TEXT NOT NULL,
                description TEXT NOT NULL,
                location TEXT NOT NULL,
                date_found TEXT NOT NULL
            )
        """)


# ======================================
# HOME PAGE
# ======================================

@app.route("/")
def home():
    return render_template("home.html")


# ======================================
# LOGIN
# ======================================

@app.route("/login", methods=["GET", "POST"])
def login():
    try:
        if request.method == "POST":
            user = request.form["user"].strip()

            session["user"] = user

            msg = Message(
                "email code",
                sender=app.config["MAIL_USERNAME"],
                recipients=[user]
            )

            msg.body = "code is 1234"
            mail.send(msg)

            return redirect(url_for("validate"))

        if "user" in session:
            return redirect(url_for("mainpage"))

        return render_template("login.html")

    except Exception:
        app.logger.exception("Failed to send email.")
        flash("Failed to send email.", "error")
        return redirect(url_for("login"))


# ======================================
# EMAIL VERIFICATION
# ======================================

@app.route("/validate", methods=["GET", "POST"])
def validate():
    if request.method == "POST":
        code = request.form["code"].strip()

        if code == "1234":
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

        with sqlite3.connect("masonfind.db") as conn:
            conn.execute("""
                INSERT INTO lost_items
                (item_name, category, description, location, date_lost)
                VALUES (?, ?, ?, ?, ?)
            """, (
                item_name,
                category,
                description,
                location,
                date_lost
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
# REPORT FOUND ITEM
# ======================================

@app.route("/report-found", methods=["GET", "POST"])
def report_found():
    if request.method == "POST":
        item_name = request.form["item_name"].strip()
        category = request.form["category"]
        description = request.form["description"].strip()
        location = request.form["location"].strip()
        date_found = request.form["date_found"]

        if not all([item_name, category, description, location, date_found]):
            return "Please complete all fields.", 400

        with sqlite3.connect("masonfind.db") as conn:
            conn.execute("""
                INSERT INTO found_items
                (item_name, category, description, location, date_found)
                VALUES (?, ?, ?, ?, ?)
            """, (
                item_name,
                category,
                description,
                location,
                date_found
            ))

        return redirect(url_for("found_items"))

    return render_template("report_found.html")


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
# START APPLICATION
# ======================================

init_db()

if __name__ == "__main__":
    app.run(debug=True)

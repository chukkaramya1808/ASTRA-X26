from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import sqlite3
from pathlib import Path
from functools import wraps
from datetime import datetime
import hashlib
import base64
import hmac
import secrets

BASE_DIR = Path(__file__).resolve().parent
DATABASE = BASE_DIR / "database.db"

app = Flask(__name__)
app.config["SECRET_KEY"] = "CHANGE-THIS-TO-A-LONG-RANDOM-SECRET-BEFORE-PUBLIC-DEPLOYMENT"

COMPETITIONS = [
    ("BOT - ARENA", "Build / present an AI chatbot solution for a real-world problem."),
    ("AI CINEVERSE", "AI-supported short film using creativity, story, and video production."),
    ("NEURA QUEST", "AI and general knowledge quiz with multiple competitive rounds."),
    ("VISION-X", "Generate a PPT on a given topic based on AI and robotics."),
    ("AI CROSSFIRE", "Structured debate on AI-related topics."),
    ("PROMPT WARS", "Create the most effective prompt for a given task."),
]

# Secure PBKDF2 hash. The plaintext admin password is NOT stored in the database.
ADMIN_PASSWORD_HASH = 'pbkdf2_sha256$600000$wjSwPjsk5K2y4l_6SIALAg==$M7JyTur3X-cHwN_3oWms1YXGe3G3b3W-5jDWV-Rb5OM='
ADMIN_USERS = ("ramya", "varshu")


def password_hash(password):
    salt = secrets.token_bytes(16)
    iterations = 600_000
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return f"pbkdf2_sha256${iterations}${base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(digest).decode()}"


def check_password(password, stored):
    try:
        algorithm, iterations, salt_b64, digest_b64 = stored.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        salt = base64.urlsafe_b64decode(salt_b64.encode())
        expected = base64.urlsafe_b64decode(digest_b64.encode())
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), salt, int(iterations)
        )
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_name TEXT NOT NULL,
            course TEXT NOT NULL,
            year TEXT NOT NULL,
            suc_code TEXT NOT NULL UNIQUE,
            competition TEXT NOT NULL,
            registered_at TEXT NOT NULL
        )
    """)

    for username in ADMIN_USERS:
        conn.execute("""
            INSERT INTO admins (username, password_hash)
            VALUES (?, ?)
            ON CONFLICT(username) DO UPDATE SET password_hash = excluded.password_hash
        """, (username, ADMIN_PASSWORD_HASH))

    placeholders = ",".join("?" for _ in ADMIN_USERS)
    conn.execute(
        f"DELETE FROM admins WHERE username NOT IN ({placeholders})",
        ADMIN_USERS
    )

    conn.commit()
    conn.close()


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin_user"):
            return redirect(url_for("admin_login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


@app.context_processor
def inject_competitions():
    return {"competitions": COMPETITIONS}


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")

    student_name = request.form.get("student_name", "").strip()
    course = request.form.get("course", "").strip()
    year = request.form.get("year", "").strip()
    suc_code = request.form.get("suc_code", "").strip()
    competition = request.form.get("competition", "").strip()

    errors = []

    if not student_name:
        errors.append("Student name is required.")
    if not course:
        errors.append("Course is required.")
    if not year:
        errors.append("Year is required.")
    if not suc_code.isdigit() or len(suc_code) != 10:
        errors.append("SUC Code must contain exactly 10 digits.")
    if competition not in [name for name, _ in COMPETITIONS]:
        errors.append("Please select a valid competition.")

    if errors:
        for error in errors:
            flash(error, "error")
        return render_template(
            "register.html",
            form=request.form,
            selected_competition=competition
        ), 400

    conn = get_db()
    try:
        conn.execute("""
            INSERT INTO registrations
            (student_name, course, year, suc_code, competition, registered_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            student_name,
            course,
            year,
            suc_code,
            competition,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.rollback()
        flash("This student has already registered for a competition.", "error")
        return render_template(
            "register.html",
            form=request.form,
            selected_competition=competition
        ), 409
    finally:
        conn.close()

    return render_template(
        "register.html",
        success=True,
        registered_name=student_name,
        selected_competition=competition
    )


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if session.get("admin_user"):
        return redirect(url_for("admin_dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")

        conn = get_db()
        admin = conn.execute(
            "SELECT username, password_hash FROM admins WHERE username = ?",
            (username,)
        ).fetchone()
        conn.close()

        if admin and check_password(password, admin["password_hash"]):
            session.clear()
            session["admin_user"] = admin["username"]
            session.permanent = True
            return redirect(url_for("admin_dashboard"))

        flash("Invalid username or password.", "error")

    return render_template("login.html")


@app.route("/admin")
@admin_required
def admin_dashboard():
    conn = get_db()
    registrations = conn.execute("""
        SELECT id, student_name, course, year, suc_code, competition, registered_at
        FROM registrations
        ORDER BY id DESC
    """).fetchall()
    conn.close()

    counts = {name: 0 for name, _ in COMPETITIONS}
    for row in registrations:
        if row["competition"] in counts:
            counts[row["competition"]] += 1

    return render_template(
        "admin.html",
        registrations=registrations,
        counts=counts,
        admin_user=session.get("admin_user")
    )


@app.route("/admin/delete/<int:registration_id>", methods=["POST"])
@admin_required
def delete_registration(registration_id):
    conn = get_db()
    conn.execute("DELETE FROM registrations WHERE id = ?", (registration_id,))
    conn.commit()
    conn.close()
    flash("Registration deleted successfully.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/health")
def health():
    return jsonify({"status": "ok"})

init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)


from flask import Blueprint, render_template, request, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
from db import get_db_connection

# Blueprint for authentication
auth_bp = Blueprint("auth", __name__)


# ---------------- Register ----------------
@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Check if username or email already exists
        cursor.execute(
            "SELECT * FROM users WHERE username=%s OR email=%s", (username, email)
        )
        existing_user = cursor.fetchone()

        if existing_user:
            flash("User already exists!", "error")
            cursor.close()
            conn.close()
            return redirect(url_for("auth.register"))

        # Hash the password before saving
        hashed_password = generate_password_hash(password)

        cursor.execute(
            "INSERT INTO users (username, email, password) VALUES (%s, %s, %s)",
            (username, email, hashed_password),
        )
        conn.commit()
        cursor.close()
        conn.close()

        flash("Registration successful! Please login.", "success")
        return redirect(url_for("auth.login"))  # 🔑 Go directly to login

    return render_template("register.html")


# ---------------- Login ----------------
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        login_id = request.form["login_id"]  # username or email
        password = request.form["password"]

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            "SELECT * FROM users WHERE username=%s OR email=%s", (login_id, login_id)
        )
        user = cursor.fetchone()

        cursor.close()
        conn.close()

        if user and check_password_hash(user["password"], password):
            flash("Login successful!", "success")
            return redirect(url_for("auth.dashboard"))
        else:
            flash("Entered username/email or password is wrong!", "error")
            return redirect(url_for("auth.login"))

    return render_template("login.html")


# ---------------- Dashboard ----------------
@auth_bp.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")

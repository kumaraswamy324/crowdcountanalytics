from flask import Blueprint, render_template, request, redirect, url_for, flash, make_response
from werkzeug.security import generate_password_hash, check_password_hash
from db import get_db_connection
import jwt
import datetime
from functools import wraps

auth_bp = Blueprint("auth", __name__)
SECRET_KEY = "your_jwt_secret_here"  # change this to a secure, random key


# ---------------- JWT Token Decorator ----------------
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.cookies.get("token")
        if not token:
            flash("Please login first.", "error")
            return redirect(url_for("auth.login"))

        try:
            data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            current_user = data.get("username")  # fetch username from token
        except jwt.ExpiredSignatureError:
            flash("Session expired. Please login again.", "error")
            return redirect(url_for("auth.login"))
        except jwt.InvalidTokenError:
            flash("Invalid token. Please login again.", "error")
            return redirect(url_for("auth.login"))

        return f(current_user, *args, **kwargs)

    return decorated


# ---------------- Register ----------------
@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        first_name = request.form["first_name"]
        last_name = request.form["last_name"]
        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]
        place = request.form["place"]
        dob = request.form["dob"]

        # Password confirmation check
        if password != confirm_password:
            flash("Passwords do not match!", "error")
            return redirect(url_for("auth.register"))

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Check if user exists
        cursor.execute(
            "SELECT * FROM users WHERE username=%s OR email=%s", (username, email)
        )
        existing_user = cursor.fetchone()

        if existing_user:
            flash("User already exists!", "error")
            cursor.close()
            conn.close()
            return redirect(url_for("auth.register"))

        # Hash password and insert
        hashed_password = generate_password_hash(password)
        cursor.execute(
            """
            INSERT INTO users (first_name, last_name, username, email, password, place, dob)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (first_name, last_name, username, email, hashed_password, place, dob),
        )
        conn.commit()
        cursor.close()
        conn.close()

        flash("Registration successful! Please login.", "success")
        return redirect(url_for("auth.login"))

    return render_template("register.html")



# ---------------- Login ----------------
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        login_id = request.form["login_id"]
        password = request.form["password"]

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            "SELECT * FROM users WHERE username=%s OR email=%s", (login_id, login_id)
        )
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if not user or not check_password_hash(user["password"], password):
            flash("Invalid username/email or password!", "error")
            return redirect(url_for("auth.login"))

        # Create JWT including username
        token = jwt.encode(
            {
                "username": user["username"],
                "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1),
            },
            SECRET_KEY,
            algorithm="HS256",
        )

        resp = make_response(redirect(url_for("auth.dashboard")))
        resp.set_cookie("token", token, httponly=True, samesite="Lax")

        flash("Login successful!", "success")
        return resp

    return render_template("login.html")


# ---------------- Dashboard ----------------
@auth_bp.route("/dashboard")
@token_required
def dashboard(current_user):
    return render_template("dashboard.html", username=current_user)


# ---------------- Logout ----------------
@auth_bp.route("/logout")
def logout():
    resp = make_response(redirect(url_for("auth.login")))
    resp.delete_cookie("token")
    flash("Logged out successfully.", "success")
    return resp

# ---------------- User Data Page ----------------
@auth_bp.route("/userdata")
@token_required
def userdata(current_user):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT first_name, last_name, username, email, place, dob FROM users WHERE username=%s", (current_user,))
    user = cursor.fetchone()

    cursor.close()
    conn.close()

    if not user:
        flash("User not found!", "error")
        return redirect(url_for("auth.dashboard"))

    return render_template("userdata.html", user=user)

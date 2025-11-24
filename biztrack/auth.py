# biztrack/auth.py
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from biztrack.biztrack_db import execute_query
import hashlib, os

auth_bp = Blueprint("auth", __name__, template_folder="templates")

#Insert default admin user if not exists
from biztrack.biztrack_db import execute_query
import os, hashlib

username = "admin"
password = "admin123"
salt = os.urandom(8).hex()
passhash = hashlib.sha256((salt + password).encode()).hexdigest()

execute_query(
    "INSERT OR IGNORE INTO Admins (username, salt, passhash) VALUES (?, ?, ?);",
    (username, salt, passhash), commit=True
)


# ---------------- Helper ---------------- #
def hash_password(password: str, salt: str) -> str:
    return hashlib.sha256((salt + password).encode()).hexdigest()

def login_required(func):
    from functools import wraps
    @wraps(func)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.login"))
        return func(*args, **kwargs)
    return wrapper

# ---------------- Routes ---------------- #
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        user = execute_query(
            "SELECT id, salt, passhash FROM Admins WHERE username=?;",
            (username,), fetchone=True
        )
        if user:
            user_id, salt, passhash = user
            if hash_password(password, salt) == passhash:
                session["user_id"] = user_id
                session["username"] = username
                flash("Login successful!", "success")
                return redirect(url_for("main.dashboard"))

        flash("Invalid username or password", "danger")
        return redirect(url_for("auth.login"))

    return render_template("login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    session.clear()
    flash("Logged out successfully", "info")
    return redirect(url_for("auth.login"))

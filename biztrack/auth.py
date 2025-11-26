
# ========================================
# FIX 3: auth.py - Add current_year to login template
# ========================================

from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from biztrack.biztrack_db import execute_query, get_user_by_username
import os
import logging
from functools import wraps
from datetime import datetime
from .forms import LoginForm

auth_bp = Blueprint("auth", __name__, template_folder="templates")

def setup_admin_if_needed():
    """Create default admin user on first run from environment variables"""
    existing = execute_query("SELECT COUNT(*) FROM users;", fetchone=True)

    if existing and existing[0] == 0:
        username = os.environ.get('ADMIN_USER', 'admin')
        password = os.environ.get('ADMIN_PASS', 'admin123')

        if password == 'admin123':
            logging.warning("⚠️ Using default admin password! Set ADMIN_PASS environment variable!")

        passhash = generate_password_hash(password, method='pbkdf2:sha256')

        execute_query(
            "INSERT INTO users (username, password, role) VALUES (?, ?, ?);",
            (username, passhash, "admin"),
            commit=True
        )
        logging.info("Default admin user created")

# Initialize admin on import
setup_admin_if_needed()

def login_required(func):
    """Decorator to require login for routes"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to access this page", "warning")
            return redirect(url_for("auth.login"))
        return func(*args, **kwargs)
    return wrapper

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data.strip()
        password = form.password.data

        user = get_user_by_username(username)
        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["username"] = username  # Store username in session
            flash("Login successful!", "success")
            return redirect(url_for("main.dashboard"))
        else:
            flash("Invalid username or password", "danger")

    # Add current_year for footer
    return render_template("login.html", form=form, current_year=datetime.now().year)

@auth_bp.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))
# ========================================
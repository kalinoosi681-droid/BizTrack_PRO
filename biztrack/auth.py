
# ========================================
# auth.py (SECURE VERSION)
# ========================================
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from biztrack.biztrack_db import execute_query
import os

auth_bp = Blueprint("auth", __name__, template_folder="templates")

def setup_admin_if_needed():
    """Create admin user on first run from environment variables"""
    existing = execute_query(
        "SELECT COUNT(*) FROM admins;",
        fetchone=True
    )
    
    if existing and existing[0] == 0:
        username = os.environ.get('ADMIN_USER', 'admin')
        password = os.environ.get('ADMIN_PASS', 'admin123')
        
        # Warn if using default password
        if password == 'admin123':
            import logging
            logging.warning("⚠️  Using default admin password! Set ADMIN_PASS environment variable!")
        
        passhash = generate_password_hash(password, method='pbkdf2:sha256')
        
        execute_query(
            "INSERT INTO admins (username, salt, passhash) VALUES (?, ?, ?);",
            (username, '', passhash),  # salt is handled by werkzeug
            commit=True
        )

# Initialize admin on import
setup_admin_if_needed()

def login_required(func):
    """Decorator to require login for routes"""
    from functools import wraps
    @wraps(func)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to access this page", "warning")
            return redirect(url_for("auth.login"))
        return func(*args, **kwargs)
    return wrapper

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    # Rate limiting applied via @limiter.limit in __init__.py
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        
        # Input validation
        if not username or not password:
            flash("Username and password are required", "danger")
            return redirect(url_for("auth.login"))
        
        if len(username) > 50:
            flash("Invalid username", "danger")
            return redirect(url_for("auth.login"))
        
        user = execute_query(
            "SELECT id, username, passhash FROM admins WHERE username=?;",
            (username,),
            fetchone=True
        )
        
        if user and check_password_hash(user[2], password):
            session["user_id"] = user[0]
            session["username"] = user[1]
            session.permanent = True  # Use configured session lifetime
            flash("Login successful!", "success")
            return redirect(url_for("main.dashboard"))
        
        # Generic error message to prevent username enumeration
        flash("Invalid credentials", "danger")
        return redirect(url_for("auth.login"))
    
    return render_template("login.html")

@auth_bp.route("/logout")
@login_required
def logout():
    session.clear()
    flash("Logged out successfully", "info")
    return redirect(url_for("auth.login"))

# ========================================
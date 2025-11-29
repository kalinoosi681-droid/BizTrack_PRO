
# ========================================
# auth.py
# ========================================

from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from biztrack.biztrack_db import execute_query, get_user_by_username, get_user_by_token
import os
import logging
import secrets
from functools import wraps
from datetime import datetime, timedelta
from .forms import LoginForm, RegisterForm, ForgotPasswordForm, ResetPasswordForm

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

# The initialization is now handled by the test fixtures or run.py
# setup_admin_if_needed()

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
        remember = form.remember.data

        user = get_user_by_username(username)

        # Check if account is locked
        if user and user.get("locked_until") and datetime.now() < datetime.fromisoformat(user["locked_until"]):
            flash(f"Account is temporarily locked. Please try again later.", "danger")
            return render_template("login.html", form=form)

        if user and check_password_hash(user["password"], password):
            # Reset failed attempts on successful login
            execute_query("UPDATE users SET failed_attempts = 0, locked_until = NULL WHERE id = ?;", (user["id"],), commit=True)

            # Mitigate session fixation by clearing the old session and creating a new one.
            session.clear()

            # Populate the new session
            session["user_id"] = user["id"]
            session["username"] = username  # Store username in session
            session.permanent = remember  # Set session lifetime based on "Remember Me"
            flash("Login successful!", "success")
            return redirect(url_for("main.dashboard"))
        else:
            # Handle failed login attempt
            if user:
                new_attempts = user.get("failed_attempts", 0) + 1
                lock_until = None
                
                # Lock account after 5 failed attempts for 15 minutes
                if new_attempts >= 5:
                    lock_until_time = datetime.now() + timedelta(minutes=15)
                    lock_until = lock_until_time.isoformat()
                    # Don't flash the lock message here to prevent user enumeration.
                    # The lock will be enforced on the next attempt.
                else:
                    execute_query(
                        "UPDATE users SET failed_attempts = ?, locked_until = ? WHERE id = ?;",
                        (new_attempts, lock_until, user["id"]),
                        commit=True
                    )

            flash("Invalid username or password", "danger")

    return render_template("login.html", form=form)

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        username = form.username.data.strip()
        password = form.password.data
        
        if get_user_by_username(username):
            flash("Username already exists.", "danger")
        else:
            passhash = generate_password_hash(password, method='pbkdf2:sha256')
            execute_query(
                "INSERT INTO users (username, password, role) VALUES (?, ?, ?);",
                (username, passhash, "user"), # Default role is 'user'
                commit=True
            )
            flash("Account created successfully! Please log in.", "success")
            return redirect(url_for("auth.login"))
            
    return render_template("register.html", form=form)

@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        user = get_user_by_username(form.username.data.strip())
        if user:
            token = secrets.token_urlsafe(32)
            expires = datetime.now() + timedelta(hours=1)
            
            execute_query(
                "UPDATE users SET reset_token = ?, reset_token_expiration = ? WHERE id = ?;",
                (token, expires.isoformat(), user["id"]),
                commit=True
            )
            
            # In a real app, you would email this link
            _reset_url = url_for('auth.reset_password', token=token, _external=True)
            flash(f"Password reset link generated. In a real app, this would be emailed. Link: {_reset_url}", "info")
        else:
            flash("Username not found.", "danger")
        return redirect(url_for('auth.login'))
        
    return render_template("forgot_password.html", form=form)

@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    user = get_user_by_token(token)
    
    if not user:
        flash("Invalid or expired password reset token.", "danger")
        return redirect(url_for('auth.login'))
        
    # Check for token expiration
    if datetime.now() > datetime.fromisoformat(user["reset_token_expiration"]):
        flash("Password reset token has expired.", "danger")
        return redirect(url_for('auth.forgot_password'))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        new_password = form.password.data
        passhash = generate_password_hash(new_password, method='pbkdf2:sha256')
        
        # Update password and clear token
        execute_query(
            "UPDATE users SET password = ?, reset_token = NULL, reset_token_expiration = NULL, failed_attempts = 0 WHERE id = ?;",
            (passhash, user["id"]),
            commit=True
        )
        flash("Your password has been reset successfully. Please log in.", "success")
        return redirect(url_for('auth.login'))
        
    return render_template("reset_password.html", form=form, token=token)

@auth_bp.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))
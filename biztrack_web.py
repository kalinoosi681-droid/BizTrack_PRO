from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from shutil import copy2
from typing import Optional

from biztrack_db import execute_query, get_connection


def generate_pdf_receipt(invoice_id: int) -> str:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.pdfgen import canvas
    except Exception as exc:
        raise RuntimeError("reportlab is required to generate PDFs. Install with `pip install reportlab`.") from exc

    inv = execute_query("SELECT invoice_number, customer_id, total, date FROM invoices WHERE id = ?;", (invoice_id,), fetchone=True)
    if not inv:
        raise RuntimeError("Invoice not found")
    invoice_number, customer_id, total, date = inv
    cust = execute_query("SELECT name, phone, email FROM customers WHERE id = ?;", (customer_id,), fetchone=True) or ("Unknown", "", "")
    lines = execute_query("SELECT p.name, s.qty, s.total_price, p.price FROM sales s JOIN products p ON s.product_id = p.id WHERE s.invoice_id = ?;", (invoice_id,), fetch=True) or []

    RECEIPTS_DIR = Path("receipts")
    RECEIPTS_DIR.mkdir(exist_ok=True)
    filename = RECEIPTS_DIR / f"invoice_{invoice_number}.pdf"

    c = canvas.Canvas(str(filename), pagesize=A4)
    width, height = A4
    margin = 20 * mm
    x = margin
    y = height - margin

    c.setFont("Helvetica-Bold", 14)
    c.drawString(x, y, "BIZTRACK - Invoice")
    c.setFont("Helvetica", 10)
    y -= 12
    c.drawString(x, y, f"Invoice #: {invoice_number}")
    y -= 12
    c.drawString(x, y, f"Date: {date}")
    y -= 18
    c.drawString(x, y, f"Customer: {cust[0]}  Phone: {cust[1] if len(cust)>1 else ''}")
    y -= 18
    c.drawString(x, y, "-" * 80)
    y -= 18
    c.drawString(x, y, f"{'Item':40} {'Qty':>5} {'Unit':>8} {'Line Total':>12}")
    y -= 12
    c.drawString(x, y, "-" * 80)
    y -= 12

    for (pname, qty, line_total, unit_price) in lines:
        if y < 80:
            c.showPage()
            y = height - margin
        c.drawString(x, y, f"{pname:40} {qty:>5} {unit_price:>8.2f} {line_total:>12.2f}")
        y -= 14

    y -= 10
    c.drawString(x, y, "-" * 80)
    y -= 18
    c.setFont("Helvetica-Bold", 12)
    c.drawString(x, y, f"TOTAL: {total:.2f}")
    y -= 30
    c.setFont("Helvetica", 9)
    c.drawString(x, y, "Thank you for your business!")
    c.save()
    STATIC_RECEIPTS = Path("static/receipts")
    STATIC_RECEIPTS.mkdir(parents=True, exist_ok=True)
    copy2(filename, STATIC_RECEIPTS / filename.name)
    return str(filename)


def create_flask_app(static_folder: str = "static"):
    # Lazy import Flask and helpers to avoid import-time errors in non-web runs
    try:
        from flask import Flask, jsonify, request, render_template_string, redirect, url_for, session, send_file, send_from_directory
    except Exception as exc:
        raise RuntimeError("Flask is not installed. Install with `pip install flask`.") from exc

    from functools import wraps
    import secrets as _secrets

    app = Flask("BizTrackWeb", static_folder=static_folder)
    app.secret_key = os.environ.get("BIZTRACK_SECRET", _secrets.token_hex(32))

    def login_required(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not session.get("logged_in"):
                return jsonify({"error": "unauthorized"}), 401 if request.is_json else redirect(url_for("login_web"))
            return fn(*args, **kwargs)
        return wrapper

    # For brevity, import the routes from the original file by reusing the same route strings.
    # We'll implement only the endpoints used by tests / basic flows here.

    @app.route("/login", methods=["GET", "POST"])
    def login_web():
        error = None
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            pw = request.form.get("password", "")
            row = execute_query("SELECT salt, passhash FROM Admins WHERE username = ?;", (username,), fetchone=True)
            if not row:
                error = "Unknown username"
            else:
                salt, ph = row
                # verify locally to avoid circular import of auth module
                from biztrack_auth import verify_password
                if verify_password(pw, salt, ph):
                    session["logged_in"] = True
                    session["username"] = username
                    return redirect(url_for("index"))
                error = "Invalid credentials"
        # Minimal HTML
        return "Login Page" if not error else f"Login Page - {error}"

    @app.route('/')
    @login_required
    def index():
        prod_count = execute_query("SELECT IFNULL(COUNT(*),0) FROM products;", fetchone=True) or (0,)
        return f"Products: {prod_count[0]}"

    @app.route('/invoice/<int:invoice_id>/pdf')
    @login_required
    def invoice_pdf(invoice_id):
        inv = execute_query("SELECT invoice_number FROM invoices WHERE id = ?;", (invoice_id,), fetchone=True)
        if not inv:
            return "Invoice not found", 404
        invoice_number = inv[0]
        pdf_file = Path("receipts") / f"invoice_{invoice_number}.pdf"
        if not pdf_file.exists():
            try:
                create_pdf = generate_pdf_receipt(invoice_id)
            except Exception as e:
                return f"PDF generation failed: {e}", 500
        return send_file(str(pdf_file), as_attachment=True)

    return app

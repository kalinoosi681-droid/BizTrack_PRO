from __future__ import annotations

#!/usr/bin/env python3
"""
biztrack.py

Single-file professional BizTrack:
- CLI (default)
- Flask web app + REST API (--web)
- Simple Tkinter GUI (--gui)

Features:
- Products / Customers / Sales / Payroll
- Admin authentication (PBKDF2)
- Tabulated console output (tabulate)
- Colored UI (colorama)
- CSV export/import, textual receipts
- DB backups, duplicate cleanup
"""
# Global persistent connection for in-memory DB
_MEMORY_CONN = None

import argparse
import csv
import getpass
import hashlib
import os
import secrets
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from shutil import copy2
from typing import Optional, Sequence, Tuple
# ReportLab is optional — import lazily where PDFs are generated

# Optional GUI / web imports
try:
    from flask import Flask, jsonify, request, render_template_string, redirect, url_for, session
    FLASK_AVAILABLE = True
    from flask import send_file
except Exception:
    FLASK_AVAILABLE = False

try:
    import tkinter as tk
    from tkinter import simpledialog, messagebox
    TK_AVAILABLE = True
except Exception:
    TK_AVAILABLE = False

try:
    from colorama import Fore, Style, init as colorama_init
    colorama_init(autoreset=True)
except Exception:
    class _DummyANSI:
        def __getattr__(self, name):
            return ""
    Fore = Style = _DummyANSI()
    def colorama_init(*a, **k):
        return None

try:
    from tabulate import tabulate
except Exception:
    def tabulate(rows, headers=None, tablefmt=None, floatfmt=None):
        # very small fallback for environments without tabulate
        hdr = (" | ".join(headers) + "\n") if headers else ""
        body = "\n".join(" | ".join(str(c) for c in r) for r in (rows or []))
        return hdr + body

# ---------------------------
# Config
# ---------------------------
DB_FILE = os.environ.get("BIZTRACK_DB", "biztrack.db")
BACKUP_DIR = Path("backups")
RECEIPTS_DIR = Path("receipts")
RECEIPTS_DIR.mkdir(exist_ok=True)
BACKUP_DIR.mkdir(exist_ok=True)

HASH_NAME = "sha256"
ITERATIONS = 400_000
SALT_BYTES = 16
KEY_LEN = 32

# Twilio optional SMS integration
TWILIO_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_FROM = os.environ.get("TWILIO_FROM")
MANAGER_PHONE = os.environ.get("BIZTRACK_MANAGER_PHONE")  # single manager fallback

def send_low_stock_sms(message: str, phone: Optional[str] = None) -> bool:
    target = phone or MANAGER_PHONE
    if not (TWILIO_SID and TWILIO_TOKEN and TWILIO_FROM and target):
        # not configured; silently skip but log
        print(Fore.YELLOW + "Twilio not configured; skipping SMS.")
        return False
    try:
        from twilio.rest import Client
        client = Client(TWILIO_SID, TWILIO_TOKEN)
        client.messages.create(body=message, from_=TWILIO_FROM, to=target)
        print(Fore.GREEN + f"SMS sent to {target}")
        return True
    except Exception as exc:
        print(Fore.RED + f"Twilio error: {exc}")
        return False

# ---------------------------
# DB helpers (single-access)
# ---------------------------
def set_db_file(path: str) -> None:
    global DB_FILE
    DB_FILE = path

def get_connection(db_file: Optional[str] = None) -> sqlite3.Connection:
    global _MEMORY_CONN

    path = db_file or DB_FILE

    # Special handling for in-memory DB
    if path == ":memory:":
        if _MEMORY_CONN is None:
            _MEMORY_CONN = sqlite3.connect(":memory:")
            _MEMORY_CONN.execute("PRAGMA foreign_keys = ON;")
        return _MEMORY_CONN

    # Normal file-based DB
    dirpath = os.path.dirname(os.path.abspath(path))
    if dirpath and not os.path.exists(dirpath):
        os.makedirs(dirpath, exist_ok=True)

    conn = sqlite3.connect(path, timeout=10)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def execute_query(query: str, params: Sequence = (), fetch: bool = False, fetchone: bool = False, commit: bool = False):
    """
    Execute SQL. Returns:
      - If fetchone=True -> single row tuple or None
      - If fetch=True -> list of rows (possibly empty)
      - Otherwise -> last cursor (or True on commit) but typically None
    On DB exception: returns None for fetchone, [] for fetch, and False otherwise.
    """
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            result = None
            if fetchone:
                result = cur.fetchone()
            elif fetch:
                result = cur.fetchall()
            if commit:
                conn.commit()
            cur.close()
            # Normalize to safe defaults so callers don't blow up with TypeError
            if fetch:
                return result if result is not None else []
            if fetchone:
                return result  # might be None
            return result
    except Exception as exc:
        # print more detail in debug logs but do not crash the app
        import logging
        logger = logging.getLogger("biztrack")
        logging.basicConfig(level=logging.INFO)
        logger.error("DB ERROR: %s | Params: %s", query, params)
        if fetch:
            return []
        if fetchone:
            return None
        return None

def generate_invoice_number() -> str:
    return "INV" + datetime.now().strftime("%Y%m%d%H%M%S")

def create_invoice_and_insert_sales(customer_id: int, items: list, sale_time: Optional[str] = None) -> Optional[int]:
    """
    items: list of dicts {pid, qty, price, line_total}
    Creates invoice row and multiple sales rows linked to invoice_id.
    Returns invoice_id or None on error.
    """
    if not sale_time:
        sale_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    invoice_number = generate_invoice_number()
    total = sum(i["line_total"] for i in items)
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("BEGIN;")
            cur.execute("INSERT INTO invoices (invoice_number, customer_id, total, date) VALUES (?, ?, ?, ?);",
                        (invoice_number, customer_id, total, sale_time))
            invoice_id = cur.lastrowid
            # insert each line into sales with invoice_id
            for it in items:
                cur.execute("INSERT INTO sales (customer_id, product_id, qty, total_price, date, invoice_id) VALUES (?, ?, ?, ?, ?, ?);",
                            (customer_id, it["pid"], it["qty"], it["line_total"], sale_time, invoice_id))
                # decrement stock (ensure not negative)
                cur.execute("UPDATE products SET qty = MAX(qty - ?, 0) WHERE id = ?;", (it["qty"], it["pid"]))
            conn.commit()
            cur.close()
        return invoice_id
    except Exception as exc:
        print(Fore.RED + f"[Invoice Error] {exc}")
        return None

#--------------------------

# CENTRALIZED VALIDATORS

#--------------------------
def validate_product(name: str, qty: int, price: float):
    if not name or not name.strip():
        raise ValueError("Product name cannot be empty")
    if qty < 0:
        raise ValueError("Quantity cannot be negative")
    if price < 0:
        raise ValueError("Price cannot be negative")

def validate_customer(name, phone):
    if not name.strip():
        raise ValueError("Customer name required")
    if phone and len(phone) < 8:
        raise ValueError("Phone number invalid")

def validate_sale_item(item):
    if item['qty'] <= 0:
        raise ValueError("Sale quantity must be positive")
    if item['price'] < 0:
        raise ValueError("Price cannot be negative")

# ---------------------------
# Password/hash utils
# ---------------------------
def hash_password(password: str, salt: Optional[bytes] = None) -> Tuple[str, str]:
    if salt is None:
        salt = secrets.token_bytes(SALT_BYTES)
    key = hashlib.pbkdf2_hmac(HASH_NAME, password.encode("utf-8"), salt, ITERATIONS, dklen=KEY_LEN)
    return salt.hex(), key.hex()

def verify_password(password: str, salt_hex: str, key_hex: str) -> bool:
    salt = bytes.fromhex(salt_hex)
    expected = bytes.fromhex(key_hex)
    key = hashlib.pbkdf2_hmac(HASH_NAME, password.encode("utf-8"), salt, ITERATIONS, dklen=len(expected))
    return secrets.compare_digest(key, expected)

# ---------------------------
# Initialization + seed
# ---------------------------
def init_db() -> None:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT,
                qty INTEGER NOT NULL DEFAULT 0,
                price REAL NOT NULL DEFAULT 0.0,
                UNIQUE(name, category)
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT,
                email TEXT,
                UNIQUE(name, phone)
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER,
                product_id INTEGER,
                qty INTEGER,
                total_price REAL,
                date TEXT,
                FOREIGN KEY (customer_id) REFERENCES customers(id),
                FOREIGN KEY (product_id) REFERENCES products(id)
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS payrolls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_name TEXT,
                salary REAL,
                date TEXT,
                UNIQUE(employee_name, date)
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS Admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                salt TEXT NOT NULL,
                passhash TEXT NOT NULL
            );
        """)
        conn.commit()
        cur.close()

def seed_default_data() -> None:
    # seed products if table empty
    res = execute_query("SELECT COUNT(*) FROM products;", fetchone=True)
    if res is None:
        return
    count = res[0]
    if count == 0:
        products = [
            ("Espresso Beans 1kg", "Beverages", 12, 8.5),
            ("Black Tea 200g", "Beverages", 30, 3.0),
            ("Blue Apron Towel", "Home", 5, 12.0),
            ("Notebook A5", "Stationery", 50, 1.5),
            ("Hand Sanitizer 500ml", "Health", 20, 4.5),
        ]
        try:
            with get_connection() as conn:
                cur = conn.cursor()
                cur.executemany("INSERT OR IGNORE INTO products (name, category, qty, price) VALUES (?, ?, ?, ?);", products)
                conn.commit()
                cur.close()
            print(Fore.GREEN + "Default product data added successfully.")
        except Exception as exc:
            print(Fore.RED + f"[Seed Error] {exc}")
    else:
        print(Fore.BLUE + "Product data exists, skipping seed.")

# Ensure invoices table exists and sales has invoice_id column
def ensure_invoice_schema():
    # create invoices table if not exists
    execute_query("""
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_number TEXT UNIQUE NOT NULL,
            customer_id INTEGER,
            total REAL,
            date TEXT,
            FOREIGN KEY(customer_id) REFERENCES customers(id)
        );
    """, commit=True)

    # add invoice_id column to sales if missing
    # SQLite doesn't support IF NOT EXISTS for ALTER COLUMN; check pragma
    cols = execute_query("PRAGMA table_info(sales);", fetch=True) or []
    col_names = [c[1] for c in cols]
    if "invoice_id" not in col_names:
        try:
            execute_query("ALTER TABLE sales ADD COLUMN invoice_id INTEGER;", commit=True)
            # Note: existing rows will have NULL invoice_id
        except Exception:
            pass

def backup_db() -> Optional[str]:
    try:
        src = Path(DB_FILE)
        if not src.exists():
            return None
        dest = BACKUP_DIR / f"{src.stem}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}{src.suffix}"
        copy2(src, dest)
        return str(dest)
    except Exception as exc:
        print(Fore.RED + f"[Backup Error] {exc}")
        return None

def remove_duplicates() -> None:
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                DELETE FROM products
                WHERE id NOT IN (
                    SELECT MIN(id) FROM products GROUP BY name, category
                );
            """)
            cur.execute("""
                DELETE FROM customers
                WHERE id NOT IN (
                    SELECT MIN(id) FROM customers GROUP BY name, phone
                );
            """)
            cur.execute("""
                DELETE FROM sales
                WHERE id NOT IN (
                    SELECT MIN(id) FROM sales GROUP BY customer_id, product_id, qty, date
                );
            """)
            cur.execute("""
                DELETE FROM payrolls
                WHERE id NOT IN (
                    SELECT MIN(id) FROM payrolls GROUP BY employee_name, salary, date
                );
            """)
            conn.commit()
            cur.close()
        print(Fore.GREEN + "Duplicate records removed (if any).")
    except Exception as exc:
        print(Fore.RED + f"[Cleanup Error] {exc}")

# ---------------------------
# Admin functions
# ---------------------------
def admin_exists() -> bool:
    r = execute_query("SELECT COUNT(*) FROM Admins;", fetchone=True)
    return bool(r and r[0] > 0)

def set_admin_password_interactive() -> None:
    print(Fore.CYAN + "=== Set Admin Password ===")
    username = input("Admin username (default 'admin'): ").strip() or "admin"
    while True:
        pw = getpass.getpass("Enter new password: ")
        pw2 = getpass.getpass("Confirm password: ")
        if pw != pw2:
            print(Fore.RED + "Passwords do not match — try again.")
            continue
        if len(pw) < 6:
            print(Fore.RED + "Password too short — minimum 6 characters.")
            continue
        salt_hex, key_hex = hash_password(pw)
        try:
            execute_query("""
                INSERT INTO Admins (username, salt, passhash)
                VALUES (?, ?, ?)
                ON CONFLICT(username) DO UPDATE SET salt=excluded.salt, passhash=excluded.passhash;
            """, (username, salt_hex, key_hex), commit=True)
            print(Fore.GREEN + "Admin password set.")
            break
        except Exception as exc:
            print(Fore.RED + f"[Admin Save Error] {exc}")
            break

def login() -> bool:
    from hmac import compare_digest
    print(Fore.CYAN + Style.BRIGHT + "\n=== Admin Login ===")
    username = input("Admin username: ").strip()
    pw = getpass.getpass("Password: ")
    try:
        row = execute_query("SELECT salt, passhash FROM Admins WHERE username=?;", (username,), fetchone=True)
        if not row:
            print(Fore.RED + "Unknown admin username.")
            return False
        salt_hex, key_hex = row
        if verify_password(pw, salt_hex, key_hex):
            print(Fore.GREEN + "\n--- Welcome back Admin! ---")
            return True
        print(Fore.RED + "\n⚠️ Wrong Credentials!")
        return False
    except Exception as exc:
        print(Fore.RED + f"[Login Error] {exc}")
        return False

def reset_admin_password_cli():
    print(Fore.CYAN + "=== Reset Admin Password (requires current password) ===")
    username = input("Admin username: ").strip()
    if not username:
        print(Fore.RED + "Username required.")
        return
    current = getpass.getpass("Current password: ")
    row = execute_query("SELECT salt, passhash FROM Admins WHERE username = ?;", (username,), fetchone=True)
    if not row:
        print(Fore.RED + "Admin user not found.")
        return
    salt, ph = row
    if not verify_password(current, salt, ph):
        print(Fore.RED + "Current password incorrect.")
        return
    while True:
        newpw = getpass.getpass("New password: ")
        newpw2 = getpass.getpass("Confirm new password: ")
        if newpw != newpw2:
            print(Fore.RED + "Passwords do not match.")
            continue
        if len(newpw) < 6:
            print(Fore.RED + "Password too short; min 6 chars.")
            continue
        s_hex, k_hex = hash_password(newpw)
        execute_query("UPDATE Admins SET salt=?, passhash=? WHERE username=?;", (s_hex, k_hex, username), commit=True)
        print(Fore.GREEN + "Password updated.")
        break

# ---------------------------
# CRUD & utilities
# ---------------------------
def add_product():
    name = input("Enter product name: ").strip()
    if not name:
        print(Fore.RED + "Product name required.")
        return
    category = input("Enter category: ").strip()
    qty_s = input("Enter quantity (integer): ").strip()
    ok, qty = (qty_s.isdigit(), int(qty_s)) if qty_s.isdigit() else (False, None)
    if not ok:
        print(Fore.RED + "Invalid quantity. Use a non-negative integer.")
        return
    try:
        price_s = input("Enter price (e.g. 12.50): ").strip()
        price = float(price_s)
        if price < 0:
            raise ValueError()
    except Exception:
        print(Fore.RED + "Invalid price. Use a non-negative number.")
        return
    execute_query("INSERT OR IGNORE INTO products (name, category, qty, price) VALUES (?, ?, ?, ?);",
                  (name, category, qty, price), commit=True)
    print(Fore.GREEN + "Product added (or already existed).")

def view_products():
    rows = execute_query("SELECT id, name, category, qty, price FROM products ORDER BY id;", fetch=True) or []
    if rows:
        print(tabulate(rows, headers=['ID', 'Name', 'Category', 'Qty', 'Price'], tablefmt='psql'))
    else:
        print(Fore.YELLOW + "No products found.")

def search_products():
    print("\nSearch by: 1.Name 2.Category 3.Price range")
    choice = input("Choose: ").strip()
    if choice == "1":
        term = input("Enter name term: ").strip()
        rows = execute_query("SELECT id, name, category, qty, price FROM products WHERE name LIKE ?;", (f"%{term}%",), fetch=True) or []
    elif choice == "2":
        term = input("Enter category: ").strip()
        rows = execute_query("SELECT id, name, category, qty, price FROM products WHERE category LIKE ?;", (f"%{term}%",), fetch=True) or []
    elif choice == "3":
        try:
            low = float(input("Min price: ").strip())
            high = float(input("Max price: ").strip())
        except ValueError:
            print(Fore.RED + "Invalid price.")
            return
        rows = execute_query("SELECT id, name, category, qty, price FROM products WHERE price BETWEEN ? AND ?;", (low, high), fetch=True) or []
    else:
        print(Fore.RED + "Invalid choice.")
        return

    if rows:
        print(tabulate(rows, headers=['ID', 'Name', 'Category', 'Qty', 'Price'], tablefmt='psql'))
    else:
        print(Fore.YELLOW + "No products found matching criteria.")

def view_customers():
    rows = execute_query("SELECT id, name, phone, email FROM customers ORDER BY id;", fetch=True) or []
    if rows:
        print(tabulate(rows, headers=['ID', 'Name', 'Phone', 'Email'], tablefmt='psql'))
    else:
        print(Fore.YELLOW + "No customers found.")

def add_customer():
    name = input("Enter customer name: ").strip()
    if not name:
        print(Fore.RED + "Customer name required.")
        return
    phone = input("Enter phone (optional): ").strip()
    email = input("Enter email (optional): ").strip()
    # basic email validation
    if email and "@" not in email:
        print(Fore.RED + "Invalid email format.")
        return
    execute_query("INSERT OR IGNORE INTO customers (name, phone, email) VALUES (?, ?, ?);", (name, phone, email), commit=True)
    print(Fore.GREEN + "Customer added (or already existed).")

def view_sales():
    rows = execute_query("""
        SELECT s.id, c.name, p.name, s.qty, s.total_price, s.date
        FROM sales s
        LEFT JOIN customers c ON s.customer_id = c.id
        LEFT JOIN products p ON s.product_id = p.id
        ORDER BY s.date DESC;
    """, fetch=True) or []
    if rows:
        print(tabulate(rows, headers=['Sale ID', 'Customer', 'Product', 'Qty', 'Total', 'Date'], tablefmt='psql'))
    else:
        print(Fore.YELLOW + "No sales found.")

def customer_history():
    cid_s = input("Enter customer ID: ").strip()
    if not cid_s.isdigit():
        print(Fore.RED + "Invalid ID.")
        return
    cid = int(cid_s)
    rows = execute_query("""
        SELECT i.invoice_number, i.date, p.name, s.qty, s.total_price
        FROM invoices i
        JOIN sales s ON s.invoice_id = i.id
        JOIN products p ON s.product_id = p.id
        WHERE i.customer_id = ?
        ORDER BY i.date DESC, i.invoice_number DESC;
    """, (cid,), fetch=True) or []
    if rows:
        print(tabulate(rows, headers=["Invoice", "Date", "Product", "Qty", "Line Total"], tablefmt="psql"))
    else:
        print(Fore.YELLOW + "No purchase history found.")

def generate_receipt(customer_id, product_id, qty, total_price):
    cust = execute_query("SELECT name, phone FROM customers WHERE id = ?;", (customer_id,), fetchone=True)
    prod = execute_query("SELECT name, price FROM products WHERE id = ?;", (product_id,), fetchone=True)
    customer_name = cust[0] if cust else "Unknown"
    customer_phone = cust[1] if cust and len(cust) > 1 else ""
    product_name = prod[0] if prod else "Unknown"
    unit_price = prod[1] if prod and len(prod) > 1 else 0.0

    lines = []
    lines.append("BIZTRACK RECEIPT")
    lines.append("=" * 40)
    lines.append(f"Customer: {customer_name}")
    lines.append(f"Phone: {customer_phone}")
    lines.append("")
    lines.append(f"Product: {product_name}")
    lines.append(f"Quantity: {qty}")
    lines.append(f"Unit price: {unit_price}")
    lines.append("-" * 40)
    lines.append(f"TOTAL: {total_price:.2f}")
    lines.append("")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("=" * 40)

    filename = RECEIPTS_DIR / f"receipt_{customer_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    filename.write_text("\n".join(lines), encoding="utf-8")
    print(Fore.GREEN + f"Receipt saved: {filename}")
    return str(filename)

def record_sale():
    # select or add customer
    view_customers()
    cid_s = input("Enter customer ID (or 0 to add new): ").strip()
    if not cid_s.isdigit():
        print(Fore.RED + "Invalid ID.")
        return
    cid = int(cid_s)
    if cid == 0:
        add_customer()
        res = execute_query("SELECT id FROM customers ORDER BY id DESC LIMIT 1;", fetchone=True)
        if not res:
            print(Fore.RED + "Failed to create customer.")
            return
        cid = res[0]

    items = []
    total_sale_amount = 0

    print(Fore.CYAN + "\nAdd products to this sale (press ENTER with no input to finish)\n")

    while True:
        view_products()
        pid_s = input("Enter product ID (or press ENTER to finish): ").strip()
        if pid_s == "":
            break
        if not pid_s.isdigit():
            print(Fore.RED + "Invalid product ID.")
            continue

        pid = int(pid_s)
        qty_s = input("Enter quantity: ").strip()
        if not qty_s.isdigit():
            print(Fore.RED + "Invalid quantity.")
            continue
        qty = int(qty_s)

        row = execute_query("SELECT qty, price, name FROM products WHERE id = ?;", (pid,), fetchone=True)
        if not row:
            print(Fore.RED + "Product not found.")
            continue

        stock, price, pname = row
        if stock < qty:
            print(Fore.RED + f"Not enough stock (available: {stock}).")
            continue

        line_total = qty * price
        total_sale_amount += line_total

        items.append({
            "pid": pid,
            "name": pname,
            "qty": qty,
            "price": price,
            "line_total": line_total
        })

    if not items:
        print(Fore.YELLOW + "No items added. Sale cancelled.")
        return

    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("BEGIN;")
            sale_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            for item in items:
                cur.execute("""
                    INSERT INTO sales (customer_id, product_id, qty, total_price, date)
                    VALUES (?, ?, ?, ?, ?);
                """, (cid, item["pid"], item["qty"], item["line_total"], sale_time))

                cur.execute("UPDATE products SET qty = qty - ? WHERE id = ?;",
                            (item["qty"], item["pid"]))

            conn.commit()
            cur.close()

        print(Fore.GREEN + f"Sale recorded. Total: {total_sale_amount:.2f}")
        generate_multi_receipt(cid, items, total_sale_amount, sale_time)

    except Exception as exc:
        print(Fore.RED + f"[Sale Error] {exc}")

def generate_multi_receipt(customer_id, items, total, timestamp):
    print(Fore.CYAN + "\n=== RECEIPT ===")
    row = execute_query("SELECT name FROM customers WHERE id = ?;", (customer_id,), fetchone=True)
    cname = row[0] if row else "Unknown"

    print(f"Customer: {cname}")
    print(f"Date: {timestamp}")
    print("\nItems:")
    print("----------------------------------------")
    for item in items:
        print(f"{item['name']}  x{item['qty']}  @ {item['price']}  = {item['line_total']:.2f}")
    print("----------------------------------------")
    print(f"TOTAL: {total:.2f}")
    print("Thank you for your purchase!\n")


def generate_pdf_receipt(invoice_id: int) -> str:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.pdfgen import canvas
    except Exception as exc:
        raise RuntimeError("reportlab is required to generate PDFs. Install with `pip install reportlab`.") from exc
    # fetch invoice + customer + sales lines
    inv = execute_query("SELECT invoice_number, customer_id, total, date FROM invoices WHERE id = ?;", (invoice_id,), fetchone=True)
    if not inv:
        raise RuntimeError("Invoice not found")
    invoice_number, customer_id, total, date = inv
    cust = execute_query("SELECT name, phone, email FROM customers WHERE id = ?;", (customer_id,), fetchone=True) or ("Unknown", "", "")
    lines = execute_query("SELECT p.name, s.qty, s.total_price, p.price FROM sales s JOIN products p ON s.product_id = p.id WHERE s.invoice_id = ?;", (invoice_id,), fetch=True) or []

    # create receipts dir if not exists
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

def top_sellers(limit: int = 10):
    rows = execute_query("""
        SELECT p.id, p.name, SUM(s.qty) AS total_qty, SUM(s.total_price) AS revenue
        FROM sales s JOIN products p ON s.product_id = p.id
        GROUP BY p.id, p.name
        ORDER BY total_qty DESC, revenue DESC
        LIMIT ?;
    """, (limit,), fetch=True) or []
    if rows:
        print(tabulate(rows, headers=["Product ID", "Name", "Total Sold", "Revenue"], tablefmt="psql"))
    else:
        print(Fore.YELLOW + "No sales data.")

# ====================== PAYROLL CRUD ======================
def add_payroll():
    print(Fore.CYAN + "\n=== Add Payroll Entry ===")
    employee_name = input("Employee name: ").strip()
    if not employee_name:
        print(Fore.RED + "Name cannot be empty.")
        return
    try:
        salary = float(input("Salary amount: ").strip())
        if salary < 0:
            raise ValueError
    except ValueError:
        print(Fore.RED + "Invalid salary amount.")
        return
    date_input = input(f"Date (YYYY-MM-DD) or press Enter for today [{datetime.now():%Y-%m-%d}]: ").strip()
    date = date_input if date_input else datetime.now().strftime("%Y-%m-%d")
    execute_query(
        "INSERT OR IGNORE INTO payrolls (employee_name, salary, date) VALUES (?, ?, ?);",
        (employee_name, salary, date), commit=True
    )
    print(Fore.GREEN + f"Payroll entry added for {employee_name} → {salary:.2f} on {date}")

def view_payrolls():
    rows = execute_query("""
        SELECT id, employee_name, salary, date FROM payrolls
        ORDER BY date DESC, id DESC;
    """, fetch=True) or []
    if rows:
        print(tabulate(rows, headers=['ID', 'Employee', 'Salary', 'Date'], tablefmt='psql', floatfmt=".2f"))
    else:
        print(Fore.YELLOW + "No payroll entries found.")

def update_payroll():
    view_payrolls()
    try:
        pid = int(input("\nEnter Payroll ID to update: ").strip())
    except ValueError:
        print(Fore.RED + "Invalid ID.")
        return
    row = execute_query("SELECT employee_name, salary, date FROM payrolls WHERE id = ?;", (pid,), fetchone=True)
    if not row:
        print(Fore.RED + "Payroll entry not found.")
        return
    name, old_salary, old_date = row
    print(Fore.CYAN + f"Current → {name} | {old_salary:.2f} | {old_date}") 
    new_name = input(f"New name (Enter to keep '{name}'): ").strip() or name
    try:
        new_salary = input(f"New salary (Enter to keep {old_salary:.2f}): ").strip()
        new_salary = float(new_salary) if new_salary else old_salary
    except ValueError:
        print(Fore.RED + "Invalid salary.")
        return
    new_date = input(f"New date (Enter to keep {old_date}): ").strip() or old_date
    execute_query("""
        UPDATE payrolls SET employee_name=?, salary=?, date=?
        WHERE id=?;
    """, (new_name, new_salary, new_date, pid), commit=True)
    print(Fore.GREEN + "Payroll updated successfully.")

def delete_payroll():
    view_payrolls()
    try:
        pid = int(input("\nEnter Payroll ID to delete: ").strip())
    except ValueError:
        print(Fore.RED + "Invalid ID.")
        return
    confirm = input(Fore.RED + "Type 'DELETE' to confirm: ").strip()
    if confirm == "DELETE":
        execute_query("DELETE FROM payrolls WHERE id = ?;", (pid,), commit=True)
        print(Fore.GREEN + "Payroll entry deleted.")
    else:
        print(Fore.YELLOW + "Deletion cancelled.")

# ====================== PRODUCT UPDATE/DELETE ======================
def update_product():
    view_products()
    try:
        pid = int(input("\nEnter Product ID to update: ").strip())
    except ValueError:
        return
    row = execute_query("SELECT name, category, qty, price FROM products WHERE id = ?;", (pid,), fetchone=True)
    if not row:
        print(Fore.RED + "Product not found.")
        return
    name, cat, qty, price = row
    print(Fore.CYAN + f"Current → {name} | {cat} | Qty: {qty} | Price: {price}")

    new_name = input(f"New name (Enter = keep): ").strip() or name
    new_cat = input(f"New category (Enter = keep): ").strip() or cat
    new_qty = input(f"New quantity (Enter = keep {qty}): ").strip()
    new_qty = int(new_qty) if new_qty.isdigit() else qty
    new_price = input(f"New price (Enter = keep {price}): ").strip()
    new_price = float(new_price) if new_price.replace('.', '').isdigit() else price

    execute_query("""
        UPDATE products SET name=?, category=?, qty=?, price=? WHERE id=?
    """, (new_name, new_cat, new_qty, new_price, pid), commit=True)
    print(Fore.GREEN + "Product updated.")

def delete_product():
    view_products()
    try:
        pid = int(input("\nEnter Product ID to delete: ").strip())
    except ValueError:
        return
    confirm = input(Fore.RED + "Type 'DELETE' to confirm: ").strip()
    if confirm == "DELETE":
        execute_query("DELETE FROM products WHERE id = ?;", (pid,), commit=True)
        print(Fore.GREEN + "Product deleted.")
    else:
        print(Fore.YELLOW + "Cancelled.")

# ====================== CUSTOMER UPDATE/DELETE ======================
def update_customer():
    view_customers()
    try:
        cid = int(input("\nEnter Customer ID to update: ").strip())
    except ValueError:
        return
    row = execute_query("SELECT name, phone, email FROM customers WHERE id = ?;", (cid,), fetchone=True)
    if not row:
        print(Fore.RED + "Customer not found.")
        return
    name, phone, email = row
    new_name = input(f"New name (Enter = keep '{name}'): ").strip() or name
    new_phone = input(f"New phone (Enter = keep '{phone}'): ").strip() or phone
    new_email = input(f"New email (Enter = keep '{email or 'None'}'): ").strip()
    new_email = new_email or email or None

    execute_query("""
        UPDATE customers SET name=?, phone=?, email=? WHERE id=?
    """, (new_name, new_phone, new_email, cid), commit=True)
    print(Fore.GREEN + "Customer updated.")

def delete_customer():
    view_customers()
    try:
        cid = int(input("\nEnter Customer ID to delete: ").strip())
    except ValueError:
        return
    confirm = input(Fore.RED + "Type 'DELETE' to confirm: ").strip()
    if confirm == "DELETE":
        execute_query("DELETE FROM customers WHERE id = ?;", (cid,), commit=True)
        print(Fore.GREEN + "Customer deleted.")
    else:
        print(Fore.YELLOW + "Cancelled.")

def export_sales_csv(filename: Optional[str] = None):
    filename = filename or f"sales_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    rows = execute_query("SELECT id, customer_id, product_id, qty, total_price, date FROM sales ORDER BY id;", fetch=True) or []
    if not rows:
        print(Fore.YELLOW + "No sales to export.")
        return
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "customer_id", "product_id", "qty", "total_price", "date"])
        writer.writerows(rows)
    print(Fore.GREEN + f"Exported {len(rows)} rows to {filename}")

def import_sales_csv(filename: str = "sales.csv"):
    path = Path(filename)
    if not path.exists():
        print(Fore.RED + f"File not found: {filename}")
        return
    created = 0
    skipped = 0
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required = {"customer_id", "product_id", "qty", "total_price", "date"}
        if not required.issubset(set(reader.fieldnames or [])):
            print(Fore.RED + f"CSV missing required columns. Required: {sorted(required)}")
            return
        with get_connection() as conn:
            cur = conn.cursor()
            for row in reader:
                try:
                    cid = int(row["customer_id"])
                    pid = int(row["product_id"])
                    qty = int(row["qty"])
                    total = float(row["total_price"])
                    date = row.get("date") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    # check existence of product & customer
                    if not execute_query("SELECT 1 FROM customers WHERE id=?;", (cid,), fetchone=True):
                        skipped += 1
                        continue
                    prow = execute_query("SELECT qty FROM products WHERE id=?;", (pid,), fetchone=True)
                    if not prow:
                        skipped += 1
                        continue
                    # insert in transaction
                    cur.execute("BEGIN;")
                    cur.execute("INSERT INTO sales (customer_id, product_id, qty, total_price, date) VALUES (?, ?, ?, ?, ?);",
                                (cid, pid, qty, total, date))
                    # reduce stock but don't allow negatives
                    cur.execute("UPDATE products SET qty = MAX(qty - ?, 0) WHERE id = ?;", (qty, pid))
                    conn.commit()
                    created += 1
                except Exception as e:
                    conn.rollback()
                    skipped += 1
                    continue
            cur.close()
    print(Fore.GREEN + f"Imported {created} rows, skipped {skipped} invalid rows.")

# ---------------------------
# CLI menu
# ---------------------------
def interactive_menu():
    while True:
        print(Fore.CYAN + Style.BRIGHT + "\n=== BIZTRACK PRO MENU ===")
        print("1. Add Product          | 8. Customer History      | 16. Import CSV File")
        print("2. View Products         | 9. Update Product       | 17. Export CSV File")
        print("3. Search Products       | 10. Delete Product      | 18. Top sellers")
        print("4. Add Customer          | 11. Update Customer")
        print("5. View Customers        | 12. Delete Customer")
        print("6. Record Sale           | 13. Payroll → Add | View | Update | Delete")
        print("7. View Sales            | 14. Backup DB | 15. Remove Duplicates")
        print("0. Exit")
        choice = input(Style.BRIGHT + "Choose: " + Style.NORMAL).strip()

        if choice == '1': add_product()
        elif choice == '2': view_products()
        elif choice == '3': search_products()
        elif choice == '4': add_customer()
        elif choice == '5': view_customers()
        elif choice == '6': record_sale()
        elif choice == '7': view_sales()
        elif choice == '8': customer_history()
        elif choice == '9': update_product()
        elif choice == '10': delete_product()
        elif choice == '11': update_customer()
        elif choice == '12': delete_customer()
        elif choice == '13':
            print("\nPayroll submenu: 1.Add  2.View  3.Update  4.Delete")
            sub = input("Choose: ").strip()
            if sub == '1': add_payroll()
            elif sub == '2': view_payrolls()
            elif sub == '3': update_payroll()
            elif sub == '4': delete_payroll()
            else: print(Fore.RED + "Invalid.")
        elif choice == '14':
            b = backup_db()
            print(Fore.GREEN + f"Backup: {b}" if b else Fore.RED + "Backup failed")
        elif choice == '15': remove_duplicates()
        elif choice == '17': export_sales_csv()
        elif choice == '18': top_sellers()
        elif choice == '0':
            print(Fore.MAGENTA + Style.BRIGHT + "\nThank you for using BizTrack PRO! 🚀")
            break
        else:
            print(Fore.RED + "Invalid choice!")

# ---------------------------
# Flask web app
# ---------------------------
def create_flask_app(static_folder: str = "static"):
    """
    Drop-in improved Flask app for BizTrack.

    Requirements:
      - This function expects the following helpers/vars in the same module:
         execute_query, get_connection, generate_invoice_number (optional),
         create_invoice_and_insert_sales, generate_pdf_receipt,
         verify_password, RECEIPTS_DIR, BACKUP_DIR, DB_FILE
      - Uses lazy imports to avoid import-time failures.
    """

    # Lazy imports
    try:
        from flask import Flask, jsonify, request, render_template_string, redirect, url_for, session, send_file, send_from_directory
    except Exception as exc:
        raise RuntimeError("Flask is not installed. Install with `pip install flask`.") from exc

    from functools import wraps
    import json
    import secrets as _secrets
    from datetime import datetime
    from pathlib import Path

    # App setup
    app = Flask("BizTrackWeb", static_folder=static_folder)
    # Use env var for secret in production & fallback for dev
    app.secret_key = os.environ.get("BIZTRACK_SECRET", _secrets.token_hex(32))

    # A minimal safe login_required decorator
    def login_required(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not session.get("logged_in"):
                return jsonify({"error": "unauthorized"}), 401 if request.is_json else redirect(url_for("login_web"))
            return fn(*args, **kwargs)
        return wrapper

    # Inlined CSS + JS for a single-file approach (modern black theme + subtle animations)
    # Uses Chart.js for top-sellers chart (client-side) and Fetch API for AJAX.
    BASE_HTML = r"""
    <!doctype html>
    <html lang="en" data-theme="dark">
    <head>
      <meta charset="utf-8" />
      <meta name="viewport" content="width=device-width,initial-scale=1" />
      <title>BizTrack PRO — {{ title }}</title>

      <!-- Lightweight modern fonts and icons (CDN) -->
      <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap" rel="stylesheet">

      <style>
        :root{
          --bg: #0b0b0b;
          --panel: rgba(255,255,255,0.03);
          --muted: #9aa3b2;
          --accent: #0d6efd;
          --glass: rgba(255,255,255,0.04);
          --success: #16a34a;
        }
        html,body{height:100%;margin:0;font-family:Inter,system-ui,-apple-system,Segoe UI,Roboto,"Helvetica Neue",Arial;}
        body{background: radial-gradient(circle at 10% 10%, rgba(13,110,253,0.06), transparent 6%),
                        linear-gradient(180deg, rgba(255,255,255,0.01), transparent 50%), var(--bg);
              color: #e8eef6; -webkit-font-smoothing:antialiased;}
        .container{max-width:1150px;margin:28px auto;padding:20px;}
        header{display:flex;align-items:center;justify-content:space-between;margin-bottom:20px;}
        .brand{display:flex;gap:12px;align-items:center}
        .logo{width:48px;height:48px;border-radius:10px;background:linear-gradient(135deg,var(--accent),#6610f2);box-shadow:0 8px 30px rgba(2,6,23,0.6);display:flex;align-items:center;justify-content:center;font-weight:700}
        .brand h1{font-size:1.05rem;margin:0}
        nav .btn{background:transparent;border:1px solid transparent;color:var(--muted);padding:8px 12px;border-radius:10px}
        .card{background:var(--panel);border-radius:14px;padding:16px;margin-bottom:18px;box-shadow:0 6px 30px rgba(2,6,23,0.6);border:1px solid rgba(255,255,255,0.03)}
        .metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:16px}
        .metric{padding:16px;border-radius:12px;background:linear-gradient(180deg, rgba(255,255,255,0.02), transparent);display:flex;flex-direction:column;align-items:flex-start;gap:8px;transition:transform 0.18s ease}
        .metric:hover{transform:translateY(-6px)}
        .metric .value{font-size:1.6rem;font-weight:700;color:var(--accent)}
        .grid{display:grid;grid-template-columns:2fr 1fr;gap:16px;align-items:start}
        table{width:100%;border-collapse:collapse;color:#cfe7ff}
        table th, table td{padding:8px 10px;text-align:left;border-bottom:1px solid rgba(255,255,255,0.02);font-size:0.95rem}
        .muted{color:var(--muted);font-size:0.9rem}
        .actions{display:flex;gap:8px;flex-wrap:wrap}
        input,select,button,textarea{background:transparent;border:1px solid rgba(255,255,255,0.06);padding:8px 10px;border-radius:8px;color:inherit}
        .btn-primary{background:linear-gradient(90deg,var(--accent),#0b58d1);border:none;color:white;padding:8px 12px;border-radius:10px}
        .small{font-size:0.85rem}
        .muted-2{color:#8b94a0}
        footer{margin-top:28px;text-align:center;color:var(--muted);font-size:0.9rem}
        /* subtle floating circles */
        .bg-circles{position:fixed;inset:0;pointer-events:none;z-index:0;mix-blend-mode:screen}
        .circle{position:absolute;border-radius:50%;filter:blur(60px);opacity:0.12;animation:float 10s infinite alternate}
        .c1{width:420px;height:420px;background:#0d6efd;left:-120px;top:-60px}
        .c2{width:300px;height:300px;background:#6610f2;right:-80px;bottom:-40px}
        @keyframes float{from{transform:translateY(-8px) scale(1)} to{transform:translateY(8px) scale(1.03)}}
        /* responsive */
        @media (max-width:900px){.metrics{grid-template-columns:repeat(2,1fr)} .grid{grid-template-columns:1fr}}
        .toast{position:fixed;right:18px;bottom:18px;background:rgba(10,10,10,0.75);padding:10px 14px;border-radius:10px;border:1px solid rgba(255,255,255,0.04)}
      </style>

      <!-- Chart.js CDN for charts -->
      <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    </head>
    <body>
      <div class="bg-circles" aria-hidden="true"><div class="circle c1"></div><div class="circle c2"></div></div>

      <div class="container">
        <header>
          <div class="brand">
            <div class="logo">BT</div>
            <div>
              <h1>BizTrack <span class="muted">PRO</span></h1>
              <div class="muted-2 small">Inventory & Sales — Dashboard</div>
            </div>
          </div>
          <div class="actions">
            <button class="btn" onclick="location.href='/products'">Products</button>
            <button class="btn" onclick="location.href='/customers'">Customers</button>
            <button class="btn" onclick="location.href='/sales'">Sales</button>
            <button class="btn" onclick="location.href='/top-sellers'">Top sellers</button>
            <button class="btn" onclick="location.href='/invoice/new'">New Invoice</button>
          </div>
        </header>

        <main id="app-content">
          <!-- content injected by server -->
          {{ body|safe }}
        </main>

        <footer>
          © {{ year }} BizTrack PRO — Designed for creative businesses
        </footer>
      </div>

      <div id="toast" class="toast" style="display:none"></div>

    </body>
    </html>
    """

    # ------------------------------------------------------------------
    # LOGIN page (GET/POST)
    # ------------------------------------------------------------------
    LOGIN_HTML = """
      <div class="card" style="max-width:420px;margin:40px auto;">
        <h2 style="margin:0 0 8px 0">Admin Login</h2>
        {% if error %}<div style="color:#ffb4b4;margin-bottom:8px">{{ error }}</div>{% endif %}
        <form method="post" action="/login">
          <label class="small">Username</label><br/>
          <input name="username" required /><br/><br/>
          <label class="small">Password</label><br/>
          <input name="password" type="password" required /><br/><br/>
          <button class="btn-primary">Sign in</button>
        </form>
      </div>
    """

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
                if verify_password(pw, salt, ph):
                    session["logged_in"] = True
                    session["username"] = username
                    return redirect(url_for("index"))
                error = "Invalid credentials"
        return render_template_string(BASE_HTML, title="Login", body=LOGIN_HTML if not error else (LOGIN_HTML.replace("{{ error }}", error)), year=datetime.now().year)

    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login_web"))

    # ------------------------------------------------------------------
    # DASHBOARD (home)
    # ------------------------------------------------------------------
    @app.route("/")
    @login_required
    def index():
        # counts
        prod_count = execute_query("SELECT IFNULL(COUNT(*),0) FROM products;", fetchone=True) or (0,)
        cust_count = execute_query("SELECT IFNULL(COUNT(*),0) FROM customers;", fetchone=True) or (0,)
        sales_count = execute_query("SELECT IFNULL(COUNT(*),0) FROM sales;", fetchone=True) or (0,)
        revenue = execute_query("SELECT IFNULL(SUM(total_price),0) FROM sales;", fetchone=True) or (0.0,)

        # recent sales (limit 10)
        recent = execute_query(
            "SELECT s.id, IFNULL(c.name,'Unknown'), IFNULL(p.name,'Unknown'), s.qty, s.total_price, s.date FROM sales s LEFT JOIN customers c ON s.customer_id=c.id LEFT JOIN products p ON p.id=s.product_id ORDER BY s.date DESC LIMIT 10;",
            fetch=True
        ) or []

        # Small inline dashboard body
        body = f'''
        <div class="metrics">
          <div class="metric card"><div class="value">{prod_count[0]}</div><div class="muted">Products</div></div>
          <div class="metric card"><div class="value">{cust_count[0]}</div><div class="muted">Customers</div></div>
          <div class="metric card"><div class="value">{sales_count[0]}</div><div class="muted">Sales</div></div>
          <div class="metric card"><div class="value">${float(revenue[0]):.2f}</div><div class="muted">Total revenue</div></div>
        </div>

        <div class="grid">
          <div class="card">
            <h3 style="margin-top:0">Recent sales</h3>
            <table>
              <thead><tr><th>ID</th><th>Customer</th><th>Product</th><th>Qty</th><th>Total</th><th>Date</th></tr></thead>
              <tbody>
                {''.join('<tr>' + ''.join(f'<td>{c}</td>' for c in row) + '</tr>' for row in recent)}
              </tbody>
            </table>
          </div>

          <div class="card">
            <h3 style="margin-top:0">Top sellers (live)</h3>
            <canvas id="topChart" style="width:100%;max-height:260px"></canvas>
            <div style="margin-top:10px"><button onclick="loadTopSellers()" class="btn-primary small">Refresh</button></div>
          </div>
        </div>

        '''

        return render_template_string(BASE_HTML, title="Dashboard", body=body, year=datetime.now().year)

    # ------------------------------------------------------------------
    # PRODUCTS CRUD - pages + JSON endpoints (AJAX)
    # ------------------------------------------------------------------
    @app.route("/products")
    @login_required
    def products_page():
        rows = execute_query("SELECT id, name, category, qty, price FROM products ORDER BY id DESC;", fetch=True) or []
        table_html = "<div class='card'><h3>Products</h3>"
        table_html += "<div style='margin-bottom:8px'><button onclick=\"showAddProduct()\" class='btn-primary small'>Add product</button> <button onclick=\"exportCSV()\" class='btn small'>Export CSV</button></div>"
        table_html += "<table><thead><tr><th>ID</th><th>Name</th><th>Category</th><th>Qty</th><th>Price</th><th>Actions</th></tr></thead><tbody>"
        for r in rows:
            table_html += f"<tr><td>{r[0]}</td><td>{r[1]}</td><td>{r[2]}</td><td>{r[3]}</td><td>{r[4]:.2f}</td>"
            table_html += f"<td><button onclick='editProduct({r[0]})' class='btn small'>Edit</button> <button onclick='deleteProduct({r[0]})' class='btn small'>Delete</button></td></tr>"
        table_html += "</tbody></table></div>"

        # Add modal & scripts for AJAX product add/update/delete
        table_html += r"""
        <div id="addProductForm" style="display:none" class="card">
          <h4>Add / Edit Product</h4>
          <form id="pform" onsubmit="return saveProduct(event)">
            <input name="id" type="hidden" />
            <label>Name</label><br/><input name="name" required /><br/>
            <label>Category</label><br/><input name="category" /><br/>
            <label>Qty</label><br/><input name="qty" type="number" min="0" value="0" /><br/>
            <label>Price</label><br/><input name="price" type="number" step="0.01" min="0" value="0.00" /><br/><br/>
            <button class="btn-primary">Save</button> <button type="button" onclick="hideAdd()">Cancel</button>
          </form>
        </div>

        """

        return render_template_string(BASE_HTML, title="Products", body=table_html, year=datetime.now().year)

    # JSON endpoints for product CRUD
    @app.route("/api/product", methods=["POST"])
    @login_required
    def api_add_product():
        data = request.get_json(force=True)
        # basic validation
        name = (data.get("name") or "").strip()
        if not name:
            return jsonify({"error":"name required"}), 400
        try:
            qty = int(data.get("qty", 0))
            price = float(data.get("price", 0.0))
        except Exception:
            return jsonify({"error":"invalid qty/price"}), 400
        category = (data.get("category") or "").strip()
        # insert
        try:
            execute_query("INSERT INTO products (name, category, qty, price) VALUES (?, ?, ?, ?);", (name, category, qty, price), commit=True)
            return jsonify({"status":"ok"})
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    @app.route("/api/product/<int:pid>", methods=["GET","PUT","DELETE"])
    @login_required
    def api_product_detail(pid):
        if request.method == "GET":
            row = execute_query("SELECT id,name,category,qty,price FROM products WHERE id = ?;", (pid,), fetchone=True)
            if not row: return jsonify({"error":"not found"}), 404
            return jsonify({"id":row[0],"name":row[1],"category":row[2],"qty":row[3],"price":row[4]})
        if request.method == "PUT":
            data = request.get_json(force=True)
            name = (data.get("name") or "").strip()
            try:
                qty = int(data.get("qty", 0))
                price = float(data.get("price", 0.0))
            except Exception:
                return jsonify({"error":"invalid qty/price"}), 400
            category = (data.get("category") or "").strip()
            execute_query("UPDATE products SET name=?, category=?, qty=?, price=? WHERE id=?;", (name, category, qty, price, pid), commit=True)
            return jsonify({"status":"ok"})
        if request.method == "DELETE":
            execute_query("DELETE FROM products WHERE id = ?;", (pid,), commit=True)
            return jsonify({"status":"deleted"})

    # ------------------------------------------------------------------
    # CUSTOMERS page + JSON endpoints
    # ------------------------------------------------------------------
    @app.route("/customers")
    @login_required
    def customers_page():
        rows = execute_query("SELECT id, name, phone, email FROM customers ORDER BY id DESC;", fetch=True) or []
        html = "<div class='card'><h3>Customers</h3><div style='margin-bottom:8px'><button onclick=\"showAddCust()\" class='btn-primary small'>Add customer</button></div>"
        html += "<table><thead><tr><th>ID</th><th>Name</th><th>Phone</th><th>Email</th><th>Actions</th></tr></thead><tbody>"
        for r in rows:
            html += f"<tr><td>{r[0]}</td><td>{r[1]}</td><td>{r[2] or ''}</td><td>{r[3] or ''}</td>"
            html += f"<td><button onclick='editCust({r[0]})' class='btn small'>Edit</button> <button onclick='deleteCust({r[0]})' class='btn small'>Delete</button></td></tr>"
        html += "</tbody></table></div>"
        html += r"""
        <div id="addCustForm" style="display:none" class="card">
          <h4>Add / Edit Customer</h4>
          <form id="cform" onsubmit="return saveCust(event)">
            <input name="id" type="hidden" />
            <label>Name</label><br/><input name="name" required /><br/>
            <label>Phone</label><br/><input name="phone" /><br/>
            <label>Email</label><br/><input name="email" type="email" /><br/><br/>
            <button class="btn-primary">Save</button> <button type="button" onclick="hideCust()">Cancel</button>
          </form>
        </div>
        """
        return render_template_string(BASE_HTML, title="Customers", body=html, year=datetime.now().year)

    @app.route("/api/customer", methods=["POST"])
    @login_required
    def api_add_customer():
        data = request.get_json(force=True)
        name = (data.get("name") or "").strip()
        if not name: return jsonify({"error":"name required"}), 400
        phone = (data.get("phone") or "").strip()
        email = (data.get("email") or "").strip()
        execute_query("INSERT INTO customers (name, phone, email) VALUES (?, ?, ?);", (name, phone or None, email or None), commit=True)
        return jsonify({"status":"ok"})

    @app.route("/api/customer/<int:cid>", methods=["GET","PUT","DELETE"])
    @login_required
    def api_customer_detail(cid):
        if request.method == "GET":
            row = execute_query("SELECT id,name,phone,email FROM customers WHERE id=?;", (cid,), fetchone=True)
            if not row: return jsonify({"error":"not found"}), 404
            return jsonify({"id":row[0],"name":row[1],"phone":row[2],"email":row[3]})
        if request.method == "PUT":
            data = request.get_json(force=True)
            name = (data.get("name") or "").strip(); phone = (data.get("phone") or "").strip(); email = (data.get("email") or "").strip()
            execute_query("UPDATE customers SET name=?, phone=?, email=? WHERE id=?;", (name, phone or None, email or None, cid), commit=True)
            return jsonify({"status":"ok"})
        if request.method == "DELETE":
            execute_query("DELETE FROM customers WHERE id=?;", (cid,), commit=True)
            return jsonify({"status":"deleted"})

    # ------------------------------------------------------------------
    # SALES page + API (record sale)
    # ------------------------------------------------------------------
    @app.route("/sales")
    @login_required
    def sales_page():
        rows = execute_query("SELECT s.id, IFNULL(c.name,'Unknown'), IFNULL(p.name,'Unknown'), s.qty, s.total_price, s.date FROM sales s LEFT JOIN customers c ON c.id=s.customer_id LEFT JOIN products p ON p.id=s.product_id ORDER BY s.date DESC LIMIT 200;", fetch=True) or []
        html = "<div class='card'><h3>Sales</h3>"
        html += "<div style='margin-bottom:8px'><button onclick=\"location.href='/invoice/new'\" class='btn-primary small'>Create Invoice</button></div>"
        html += "<table><thead><tr><th>ID</th><th>Customer</th><th>Product</th><th>Qty</th><th>Total</th><th>Date</th></tr></thead><tbody>"
        for r in rows:
            html += f"<tr><td>{r[0]}</td><td>{r[1]}</td><td>{r[2]}</td><td>{r[3]}</td><td>{r[4]:.2f}</td><td>{r[5]}</td></tr>"
        html += "</tbody></table></div>"
        return render_template_string(BASE_HTML, title="Sales", body=html, year=datetime.now().year)

    @app.route("/api/sale", methods=["POST"])
    @login_required
    def api_create_sale():
        payload = request.get_json(force=True)
        try:
            cid = int(payload.get("customer_id"))
            pid = int(payload.get("product_id"))
            qty = int(payload.get("qty"))
        except Exception:
            return jsonify({"error":"invalid payload"}), 400
        row = execute_query("SELECT qty,price FROM products WHERE id=?;", (pid,), fetchone=True)
        if not row: return jsonify({"error":"product not found"}), 404
        stock, price = row
        if stock < qty: return jsonify({"error":"not enough stock", "available":stock}), 400
        total_price = qty * price
        try:
            with get_connection() as conn:
                cur = conn.cursor()
                cur.execute("BEGIN;")
                cur.execute("INSERT INTO sales (customer_id,product_id,qty,total_price,date) VALUES (?,?,?,?,?);",
                            (cid,pid,qty,total_price,datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                cur.execute("UPDATE products SET qty = qty - ? WHERE id = ?;", (qty,pid))
                conn.commit()
                cur.close()
            # optionally return a generated textual receipt or PDF link
            generate_receipt(cid,pid,qty,total_price)
            return jsonify({"status":"ok","total":total_price}), 201
        except Exception as exc:
            return jsonify({"error":str(exc)}), 500

    # ------------------------------------------------------------------
    # INVOICE creation page + PDF download
    # ------------------------------------------------------------------
    @app.route("/invoice/new", methods=["GET","POST"])
    @login_required
    def invoice_new():
        if request.method == "GET":
            form = """
            <div class="card"><h3>Create Invoice</h3>
            <form method="post">
              <label>Customer ID</label><br/><input name="customer_id" required /><br/>
              <label>Items (pid:qty, comma separated)</label><br/><input name="items" style="width:100%" required /><br/><br/>
              <button class="btn-primary">Create Invoice</button>
            </form></div>
            """
            return render_template_string(BASE_HTML, title="Create Invoice", body=form, year=datetime.now().year)

        # POST: parse & validate items
        cid = int(request.form.get("customer_id") or 0)
        items_raw = request.form.get("items","")
        parsed = []
        for part in items_raw.split(","):
            part = part.strip()
            if not part: continue
            try:
                pid_s, qty_s = part.split(":")
                pid = int(pid_s.strip()); qty = int(qty_s.strip())
            except Exception:
                return "Invalid items format. Use product_id:qty pairs separated by commas.", 400
            prow = execute_query("SELECT qty, price, name FROM products WHERE id = ?;", (pid,), fetchone=True)
            if not prow: return f"Product id {pid} not found.", 400
            stock, price, pname = prow
            if stock < qty: return f"Not enough stock for {pname} (id {pid}). Available {stock}", 400
            parsed.append({"pid": pid, "qty": qty, "price": price, "line_total": qty*price, "name":pname})

        inv_id = create_invoice_and_insert_sales(cid, parsed)
        if not inv_id: return "Failed to create invoice", 500
        # generate PDF and redirect to download
        try:
            pdf_path = generate_pdf_receipt(inv_id)
        except Exception as exc:
            # continue but tell the user
            return f"Invoice {inv_id} created, but PDF failed: {exc}", 200
        return redirect(url_for("invoice_pdf", invoice_id=inv_id))

    @app.route("/invoice/<int:invoice_id>/pdf")
    @login_required
    def invoice_pdf(invoice_id):
        inv = execute_query("SELECT invoice_number FROM invoices WHERE id = ?;", (invoice_id,), fetchone=True)
        if not inv: return "Invoice not found", 404
        invoice_number = inv[0]
        pdf_file = RECEIPTS_DIR / f"invoice_{invoice_number}.pdf"
        if not pdf_file.exists():
            try:
                generate_pdf_receipt(invoice_id)
            except Exception as e:
                return f"PDF generation failed: {e}", 500
        return send_file(str(pdf_file), as_attachment=True)

    # ------------------------------------------------------------------
    # TOP SELLERS API
    # ------------------------------------------------------------------
    @app.route("/api/top_sellers")
    @login_required
    def api_top_sellers():
        limit = int(request.args.get("limit", "10"))
        rows = execute_query("""
            SELECT p.id, p.name, IFNULL(SUM(s.qty),0) AS total_qty, IFNULL(SUM(s.total_price),0) AS revenue
            FROM products p LEFT JOIN sales s ON s.product_id = p.id
            GROUP BY p.id, p.name
            ORDER BY total_qty DESC, revenue DESC
            LIMIT ?;
        """, (limit,), fetch=True) or []
        data = [{"id":r[0],"name":r[1],"total_sold":r[2],"revenue":r[3]} for r in rows]
        return jsonify(data)

    # ------------------------------------------------------------------
    # Export CSV & Backup endpoints
    # ------------------------------------------------------------------
    @app.route("/export_sales")
    @login_required
    def export_sales():
        filename = f"sales_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        rows = execute_query("SELECT id, customer_id, product_id, qty, total_price, date FROM sales ORDER BY id;", fetch=True) or []
        import csv, io
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["id","customer_id","product_id","qty","total_price","date"])
        w.writerows(rows)
        buf.seek(0)
        return app.response_class(buf.getvalue(), mimetype="text/csv",
                                  headers={"Content-Disposition":f"attachment;filename={filename}"})

    @app.route("/backup")
    @login_required
    def backup():
        # attempt DB copy
        src = Path(DB_FILE)
        if not src.exists(): return "DB file not found", 404
        dest = Path(BACKUP_DIR) / f"{src.stem}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}{src.suffix}"
        copy2(str(src), str(dest))
        return send_file(str(dest), as_attachment=True)

    # ------------------------------------------------------------------
    # Static receipts serving (safe)
    # ------------------------------------------------------------------
    @app.route("/static/receipts/<path:filename>")
    @login_required
    def static_receipts(filename):
        safe_dir = str(Path(RECEIPTS_DIR).resolve())
        return send_from_directory(safe_dir, filename, as_attachment=False)

    # End of app function
    return app


# ---------------------------
# Simple Tk GUI (minimal)
# ---------------------------
def run_tk_gui():
    if not TK_AVAILABLE:
        print(Fore.RED + "Tkinter not available on this environment.")
        return

    root = tk.Tk()
    root.title("BizTrack GUI")

    def refresh_products():
        rows = execute_query("SELECT id, name, category, qty, price FROM products ORDER BY id;", fetch=True) or []
        txt.delete("1.0", tk.END)
        txt.insert(tk.END, tabulate(rows, headers=['ID','Name','Category','Qty','Price'], tablefmt='psql'))

    def add_product_gui():
        name = simpledialog.askstring("Product name", "Name:", parent=root)
        if not name:
            return
        category = simpledialog.askstring("Category", "Category:", parent=root) or ""
        qty = simpledialog.askinteger("Quantity", "Quantity:", parent=root, minvalue=0)
        price = simpledialog.askfloat("Price", "Price:", parent=root, minvalue=0.0)
        execute_query("INSERT OR IGNORE INTO products (name, category, qty, price) VALUES (?, ?, ?, ?);",
                      (name, category, qty or 0, price or 0.0), commit=True)
        refresh_products()

    def record_sale_gui():
        cid = simpledialog.askinteger("Customer ID", "Customer ID (0 to add):", parent=root, minvalue=0)
        if cid == 0:
            cname = simpledialog.askstring("Customer Name", "Name:", parent=root)
            cphone = simpledialog.askstring("Phone", "Phone:", parent=root)
            execute_query("INSERT OR IGNORE INTO customers (name, phone) VALUES (?, ?);", (cname, cphone), commit=True)
            cid = execute_query("SELECT id FROM customers ORDER BY id DESC LIMIT 1;", fetchone=True)[0]
        pid = simpledialog.askinteger("Product ID", "Product ID:", parent=root, minvalue=1)
        qty = simpledialog.askinteger("Quantity", "Quantity:", parent=root, minvalue=1)
        # reuse record_sale logic (simple)
        row = execute_query("SELECT qty,price FROM products WHERE id = ?;", (pid,), fetchone=True)
        if not row:
            messagebox.showerror("Error", "Product not found.")
            return
        stock, price = row
        if stock < qty:
            messagebox.showerror("Error", f"Not enough stock ({stock}).")
            return
        total_price = qty * price
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("BEGIN;")
            cur.execute("INSERT INTO sales (customer_id,product_id,qty,total_price,date) VALUES (?,?,?,?,?);",
                        (cid,pid,qty,total_price,datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            cur.execute("UPDATE products SET qty = qty - ? WHERE id = ?;", (qty,pid))
            conn.commit()
            cur.close()
        generate_receipt(cid, pid, qty, total_price)
        messagebox.showinfo("Sale", f"Sale recorded: {total_price:.2f}")
        refresh_products()

    frm = tk.Frame(root)
    frm.pack(padx=8, pady=8, fill=tk.BOTH, expand=True)
    btn_frame = tk.Frame(frm)
    btn_frame.pack(side=tk.TOP, fill=tk.X)
    tk.Button(btn_frame, text="Refresh Products", command=refresh_products).pack(side=tk.LEFT, padx=4)
    tk.Button(btn_frame, text="Add Product", command=add_product_gui).pack(side=tk.LEFT, padx=4)
    tk.Button(btn_frame, text="Record Sale", command=record_sale_gui).pack(side=tk.LEFT, padx=4)
    txt = tk.Text(frm, width=100, height=30)
    txt.pack(fill=tk.BOTH, expand=True)
    refresh_products()
    root.mainloop()

# ---------------------------
# Entrypoint CLI wrapper
# ---------------------------
def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="BizTrack — All-in-one tool")
    parser.add_argument("--db", help="Path to DB file", default=None)
    parser.add_argument("--no-seed", action="store_true", help="Don't seed sample data")
    parser.add_argument("--web", action="store_true", help="Run Flask web app")
    parser.add_argument("--gui", action="store_true", help="Run Tkinter GUI (if available)")
    parser.add_argument("--port", type=int, default=5000, help="Port for web server (default: 5000)")
    parser.add_argument("--export", nargs="?", const="auto_export.csv", help="Export sales CSV and exit")
    args = parser.parse_args(argv)

    if args.db:
        set_db_file(args.db)

    init_db()
    if not args.no_seed:
        seed_default_data()
    remove_duplicates()
    ensure_invoice_schema()

    if args.export:
        export_sales_csv(args.export)
        return

    if args.web:
        if not FLASK_AVAILABLE:
            print(Fore.RED + "Flask not installed. Install `flask` to use web mode.")
            return
        print(Fore.CYAN + f"Starting Flask app at http://127.0.0.1:{args.port}")
        app = create_flask_app()
        app.run(host="0.0.0.0", port=args.port, debug=False)
        return

    if args.gui:
        run_tk_gui()
        return

    # CLI admin and menu
    if not admin_exists():
        print(Fore.YELLOW + "No admin account found — create one now.")
        set_admin_password_interactive()

    if not login():
        print(Fore.RED + "Exiting (failed login).")
        sys.exit(1)

    interactive_menu()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n" + Fore.YELLOW + "Interrupted. Exiting.")
        sys.exit(0)


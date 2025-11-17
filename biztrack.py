from __future__ import annotations

#!/usr/bin/env python3
"""
biztrack_full.py

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

# Optional GUI / web imports
try:
    from flask import Flask, jsonify, request, render_template_string, redirect, url_for
    FLASK_AVAILABLE = True
except Exception:
    FLASK_AVAILABLE = False

try:
    import tkinter as tk
    from tkinter import simpledialog, messagebox
    TK_AVAILABLE = True
except Exception:
    TK_AVAILABLE = False

from colorama import Fore, Style, init as colorama_init
from tabulate import tabulate

colorama_init(autoreset=True)

# ---------------------------
# Config
# ---------------------------
DB_FILE = os.environ.get("BIZTRACK_DB", "biztrack.db")
BACKUP_DIR = Path("backups")
RECEIPTS_DIR = Path("receipts")
RECEIPTS_DIR.mkdir(exist_ok=True)
BACKUP_DIR.mkdir(exist_ok=True)

HASH_NAME = "sha256"
ITERATIONS = 150_000
SALT_BYTES = 16
KEY_LEN = 32

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
            return result
    except Exception as exc:
        print(Fore.RED + f"[DB ERROR] {exc}")
        return None

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

# ---------------------------
# CRUD & utilities
# ---------------------------
def add_product():
    name = input("Enter product name: ").strip()
    category = input("Enter category: ").strip()
    qty_s = input("Enter quantity (integer): ").strip()
    if not qty_s.isdigit():
        print(Fore.RED + "Invalid quantity.")
        return
    qty = int(qty_s)
    try:
        price = float(input("Enter price (e.g. 12.50): ").strip())
    except ValueError:
        print(Fore.RED + "Invalid price.")
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
    phone = input("Enter phone: ").strip()
    email = input("Enter email (optional): ").strip()
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
        SELECT s.id, p.name, s.qty, s.total_price, s.date
        FROM sales s JOIN products p ON s.product_id = p.id
        WHERE s.customer_id = ?
        ORDER BY s.date DESC;
    """, (cid,), fetch=True) or []
    if rows:
        print(tabulate(rows, headers=['Sale ID', 'Product', 'Qty', 'Total', 'Date'], tablefmt='psql'))
    else:
        print(Fore.YELLOW + "No purchase history found for this customer.")

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
    # Offer to choose customer or add
    view_customers()
    cid_s = input("Enter customer ID (or 0 to add new): ").strip()
    if not cid_s.isdigit():
        print(Fore.RED + "Invalid ID.")
        return
    cid = int(cid_s)
    if cid == 0:
        add_customer()
        last = execute_query("SELECT id FROM customers ORDER BY id DESC LIMIT 1;", fetchone=True)
        if not last:
            print(Fore.RED + "Failed to create customer.")
            return
        cid = last[0]

    view_products()
    pid_s = input("Enter product ID: ").strip()
    if not pid_s.isdigit():
        print(Fore.RED + "Invalid product ID.")
        return
    pid = int(pid_s)
    qty_s = input("Enter quantity to sell: ").strip()
    if not qty_s.isdigit():
        print(Fore.RED + "Invalid quantity.")
        return
    qty = int(qty_s)

    row = execute_query("SELECT qty, price FROM products WHERE id = ?;", (pid,), fetchone=True)
    if not row:
        print(Fore.RED + "Product not found.")
        return
    stock, price = row
    if stock < qty:
        print(Fore.RED + f"Not enough stock (available: {stock}).")
        return
    total_price = qty * price
    # transaction
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("BEGIN;")
            cur.execute("INSERT INTO sales (customer_id, product_id, qty, total_price, date) VALUES (?, ?, ?, ?, ?);",
                        (cid, pid, qty, total_price, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            cur.execute("UPDATE products SET qty = qty - ? WHERE id = ?;", (qty, pid))
            conn.commit()
            cur.close()
        print(Fore.GREEN + f"Sale recorded: {total_price:.2f}")
        generate_receipt(cid, pid, qty, total_price)
        new_stock = execute_query("SELECT qty FROM products WHERE id = ?;", (pid,), fetchone=True)[0]
        if new_stock <= 5:
            print(Fore.YELLOW + f"⚠️ Low stock for product ID {pid}: {new_stock} left.")
    except Exception as exc:
        print(Fore.RED + f"[Sale Error] {exc}")

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
    if not Path(filename).exists():
        print(Fore.RED + f"File not found: {filename}")
        return
    with open(filename, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        created = 0
        with get_connection() as conn:
            cur = conn.cursor()
            for r in reader:
                try:
                    cur.execute("INSERT INTO sales (customer_id, product_id, qty, total_price, date) VALUES (?, ?, ?, ?, ?);",
                                (int(r["customer_id"]), int(r["product_id"]), int(r["qty"]), float(r["total_price"]), r["date"]))
                    created += 1
                except Exception:
                    continue
            conn.commit()
            cur.close()
    print(Fore.GREEN + f"Imported {created} rows from {filename}")

# ---------------------------
# CLI menu
# ---------------------------
def interactive_menu():
    while True:
        print(Fore.CYAN + Style.BRIGHT + "\n=== BIZTRACK PRO MENU ===")
        print("1. Add Product          | 8. Customer History")
        print("2. View Products         | 9. Update Product")
        print("3. Search Products       | 10. Delete Product")
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
        elif choice == '0':
            print(Fore.MAGENTA + Style.BRIGHT + "\nThank you for using BizTrack PRO! 🚀")
            break
        else:
            print(Fore.RED + "Invalid choice!")

# ---------------------------
# Flask web app (simple)
# ---------------------------
def create_flask_app():
    if not FLASK_AVAILABLE:
        raise RuntimeError("Flask is not installed. Install with `pip install flask`")

    app = Flask("BizTrackWeb")
    #Simple HTML templates inline for quick demo
    INDEX_HTML = """
    <html>
    <head><title>BizTrack</title></head>
    <body>
      <h1>BizTrack — Inventory & Sales</h1>
      <p><a href="/products">Products</a> | <a href="/customers">Customers</a> | <a href="/sales">Sales</a></p>
    </body>
    </html>
    """

    TABLE_HTML = """
    <html>
    <head><title>{{title}}</title></head>
    <body>
      <h2>{{title}}</h2>
      <pre>{{table}}</pre>
      <p><a href="/">Back</a></p>
    </body>
    </html>
    """
    app.route("/")
    def index():
        return render_template_string(INDEX_HTML)

    @app.route("/api/products")
    def api_products():
        rows = execute_query("SELECT id,name,category,qty,price FROM products ORDER BY id;", fetch=True) or []
        data = [{"id": r[0], "name": r[1], "category": r[2], "qty": r[3], "price": r[4]} for r in rows]
        return jsonify(data)

    @app.route("/api/customers")
    def api_customers():
        rows = execute_query("SELECT id,name,phone,email FROM customers ORDER BY id;", fetch=True) or []
        data = [{"id": r[0], "name": r[1], "phone": r[2], "email": r[3]} for r in rows]
        return jsonify(data)

    @app.route("/api/sales")
    def api_sales():
        rows = execute_query("""
            SELECT s.id, c.name, p.name, s.qty, s.total_price, s.date
            FROM sales s
            LEFT JOIN customers c ON s.customer_id=c.id
            LEFT JOIN products p ON s.product_id=p.id
            ORDER BY s.date DESC;
        """, fetch=True) or []
        data = [{"id": r[0], "customer": r[1], "product": r[2], "qty": r[3], "total": r[4], "date": r[5]} for r in rows]
        return jsonify(data)

    @app.route("/products")
    def products_page():
        rows = execute_query("SELECT id,name,category,qty,price FROM products ORDER BY id;", fetch=True) or []
        table = tabulate(rows, headers=['ID','Name','Category','Qty','Price'], tablefmt='psql')
        return render_template_string(TABLE_HTML, title="Products", table=table)

    @app.route("/customers")
    def customers_page():
        rows = execute_query("SELECT id,name,phone,email FROM customers ORDER BY id;", fetch=True) or []
        table = tabulate(rows, headers=['ID','Name','Phone','Email'], tablefmt='psql')
        return render_template_string(TABLE_HTML, title="Customers", table=table)

    @app.route("/sales")
    def sales_page():
        rows = execute_query("""
            SELECT s.id, c.name, p.name, s.qty, s.total_price, s.date
            FROM sales s
            LEFT JOIN customers c ON s.customer_id=c.id
            LEFT JOIN products p ON s.product_id=p.id
            ORDER BY s.date DESC;
        """, fetch=True) or []
        table = tabulate(rows, headers=['Sale ID','Customer','Product','Qty','Total','Date'], tablefmt='psql')
        return render_template_string(TABLE_HTML, title="Sales", table=table)

    # Simple API to record sale (POST JSON)
    @app.route("/api/sale", methods=["POST"])
    def api_create_sale():
        payload = request.get_json(force=True)
        try:
            cid = int(payload.get("customer_id"))
            pid = int(payload.get("product_id"))
            qty = int(payload.get("qty"))
        except Exception:
            return jsonify({"error":"invalid payload"}), 400
        row = execute_query("SELECT qty,price FROM products WHERE id=?;", (pid,), fetchone=True)
        if not row:
            return jsonify({"error":"product not found"}), 404
        stock, price = row
        if stock < qty:
            return jsonify({"error":"not enough stock", "available":stock}), 400
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
            generate_receipt(cid,pid,qty,total_price)
            return jsonify({"status":"ok","total":total_price}), 201
        except Exception as exc:
            return jsonify({"error":str(exc)}), 500

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
    parser.add_argument("--export", nargs="?", const="auto_export.csv", help="Export sales CSV and exit")
    args = parser.parse_args(argv)

    if args.db:
        set_db_file(args.db)

    init_db()
    if not args.no_seed:
        seed_default_data()
    remove_duplicates()

    if args.export:
        export_sales_csv(args.export)
        return

    if args.web:
        if not FLASK_AVAILABLE:
            print(Fore.RED + "Flask not installed. Install `flask` to use web mode.")
            return
        app = create_flask_app()
        print(Fore.CYAN + "Starting Flask app at http://127.0.0.1:5000")
        app.run(debug=False)
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


from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from shutil import copy2
from datetime import datetime
from typing import Optional, Sequence

try:
    from colorama import Fore
except Exception:
    class _D:
        def __getattr__(self, name):
            return ""
    Fore = _D()

# DB file path (module-local)
DB_FILE = os.environ.get("BIZTRACK_DB", "biztrack.db")

# In-memory connection (persist for :memory: usage)
_MEMORY_CONN = None

def set_db_file(path: str) -> None:
    global DB_FILE
    DB_FILE = path

def get_connection(db_file: Optional[str] = None) -> sqlite3.Connection:
    global _MEMORY_CONN
    path = db_file or DB_FILE
    if path == ":memory:":
        if _MEMORY_CONN is None:
            _MEMORY_CONN = sqlite3.connect(":memory:")
            _MEMORY_CONN.execute("PRAGMA foreign_keys = ON;")
        return _MEMORY_CONN
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
            if fetch:
                return result if result is not None else []
            if fetchone:
                return result
            return result
    except Exception as exc:
        import logging
        logger = logging.getLogger("biztrack.db")
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
            for it in items:
                cur.execute("INSERT INTO sales (customer_id, product_id, qty, total_price, date, invoice_id) VALUES (?, ?, ?, ?, ?, ?);",
                            (customer_id, it["pid"], it["qty"], it["line_total"], sale_time, invoice_id))
                cur.execute("UPDATE products SET qty = MAX(qty - ?, 0) WHERE id = ?;", (it["qty"], it["pid"]))
            conn.commit()
            cur.close()
        return invoice_id
    except Exception as exc:
        try:
            print(Fore.RED + f"[Invoice Error] {exc}")
        except Exception:
            print(f"[Invoice Error] {exc}")
        return None

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
            try:
                print(Fore.GREEN + "Default product data added successfully.")
            except Exception:
                print("Default product data added successfully.")
        except Exception as exc:
            try:
                print(Fore.RED + f"[Seed Error] {exc}")
            except Exception:
                print(f"[Seed Error] {exc}")
    else:
        try:
            print(Fore.BLUE + "Product data exists, skipping seed.")
        except Exception:
            print("Product data exists, skipping seed.")

def ensure_invoice_schema():
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
    cols = execute_query("PRAGMA table_info(sales);", fetch=True) or []
    col_names = [c[1] for c in cols]
    if "invoice_id" not in col_names:
        try:
            execute_query("ALTER TABLE sales ADD COLUMN invoice_id INTEGER;", commit=True)
        except Exception:
            pass

def backup_db() -> Optional[str]:
    try:
        src = Path(DB_FILE)
        if not src.exists():
            return None
        dest = Path("backups") / f"{src.stem}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}{src.suffix}"
        copy2(src, dest)
        return str(dest)
    except Exception as exc:
        try:
            print(Fore.RED + f"[Backup Error] {exc}")
        except Exception:
            print(f"[Backup Error] {exc}")
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
        try:
            print(Fore.GREEN + "Duplicate records removed (if any).")
        except Exception:
            print("Duplicate records removed (if any).")
    except Exception as exc:
        try:
            print(Fore.RED + f"[Cleanup Error] {exc}")
        except Exception:
            print(f"[Cleanup Error] {exc}")

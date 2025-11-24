# biztrack_db.py
from __future__ import annotations
import os
import sqlite3
from pathlib import Path
from shutil import copy2
from datetime import datetime
from typing import Optional, Sequence, List, Dict
import logging

# Configure logging
logger = logging.getLogger("biztrack_db")
logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

# DB file path
DB_FILE = os.environ.get("BIZTRACK_DB", "biztrack.db")
_MEMORY_CONN: Optional[sqlite3.Connection] = None

def set_db_file(path: str) -> None:
    global DB_FILE
    DB_FILE = path
    logger.info(f"DB file set to {DB_FILE}")

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
                return result or []
            if fetchone:
                return result
            return result
    except Exception as exc:
        logger.error("DB ERROR: %s | Params: %s", query, params)
        logger.exception(exc)
        if fetch or fetchone:
            return None if fetchone else []
        return None

def generate_invoice_number() -> str:
    return "INV" + datetime.now().strftime("%Y%m%d%H%M%S")

def create_invoice_and_insert_sales(customer_id: int, items: List[Dict], sale_time: Optional[str] = None) -> Optional[int]:
    """
    Inserts an invoice and its sales items into the database, updating product stock.
    Validates stock quantities before committing.
    """
    if not sale_time:
        sale_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Validate stock before starting transaction
    for it in items:
        pid = it["pid"]
        qty = it["qty"]
        stock = execute_query("SELECT qty FROM products WHERE id = ?;", (pid,), fetchone=True)
        if stock is None:
            logger.error(f"Product ID {pid} not found")
            return None
        if qty > stock[0]:
            logger.error(f"Insufficient stock for Product ID {pid}: requested {qty}, available {stock[0]}")
            return None
        it["line_total"] = round(qty * float(it["price"]), 2)

    invoice_number = generate_invoice_number()
    total = sum(it["line_total"] for it in items)

    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("BEGIN;")
            cur.execute(
                "INSERT INTO invoices (invoice_number, customer_id, total, date) VALUES (?, ?, ?, ?);",
                (invoice_number, customer_id, total, sale_time)
            )
            invoice_id = cur.lastrowid
            for it in items:
                cur.execute(
                    "INSERT INTO sales (customer_id, product_id, qty, total_price, date, invoice_id) VALUES (?, ?, ?, ?, ?, ?);",
                    (customer_id, it["pid"], it["qty"], it["line_total"], sale_time, invoice_id)
                )
                cur.execute(
                    "UPDATE products SET qty = qty - ? WHERE id = ?;",
                    (it["qty"], it["pid"])
                )
            conn.commit()
            cur.close()
        logger.info(f"Invoice {invoice_number} created successfully with ID {invoice_id}")
        return invoice_id
    except Exception as exc:
        logger.exception(f"Failed to create invoice {invoice_number}")
        return None

# Compatibility wrapper
def insert_invoice_and_sales(customer_id: int, items: List[Dict], sale_time: Optional[str] = None):
    return create_invoice_and_insert_sales(customer_id, items, sale_time)

def init_db() -> None:
    with get_connection() as conn:
        cur = conn.cursor()
        # Products table
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
        # Customers
        cur.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT,
                email TEXT,
                UNIQUE(name, phone)
            );
        """)
        # Sales
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER,
                product_id INTEGER,
                qty INTEGER,
                total_price REAL,
                date TEXT,
                invoice_id INTEGER,
                FOREIGN KEY(customer_id) REFERENCES customers(id) ON DELETE CASCADE,
                FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE,
                FOREIGN KEY(invoice_id) REFERENCES invoices(id) ON DELETE CASCADE
            );
        """)
        # Payrolls
        cur.execute("""
            CREATE TABLE IF NOT EXISTS payrolls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_name TEXT,
                salary REAL,
                date TEXT,
                UNIQUE(employee_name, date)
            );
        """)
        # Admins
        cur.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                salt TEXT NOT NULL,
                passhash TEXT NOT NULL
            );
        """)
        # Invoices
        cur.execute("""
            CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_number TEXT UNIQUE NOT NULL,
                customer_id INTEGER,
                total REAL,
                date TEXT,
                FOREIGN KEY(customer_id) REFERENCES customers(id) ON DELETE CASCADE
            );
        """)
        conn.commit()
        cur.close()
    logger.info("Database initialized successfully")

def remove_duplicates() -> None:
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                DELETE FROM products
                WHERE id NOT IN (SELECT MIN(id) FROM products GROUP BY name, category);
            """)
            cur.execute("""
                DELETE FROM customers
                WHERE id NOT IN (SELECT MIN(id) FROM customers GROUP BY name, phone);
            """)
            cur.execute("""
                DELETE FROM sales
                WHERE id NOT IN (SELECT MIN(id) FROM sales GROUP BY customer_id, product_id, qty, date);
            """)
            cur.execute("""
                DELETE FROM payrolls
                WHERE id NOT IN (SELECT MIN(id) FROM payrolls GROUP BY employee_name, salary, date);
            """)
            conn.commit()
            cur.close()
        logger.info("Duplicate records removed successfully")
    except Exception as exc:
        logger.exception("Failed to remove duplicates")

def backup_db() -> Optional[str]:
    try:
        src = Path(DB_FILE)
        if not src.exists():
            logger.warning("DB file does not exist for backup")
            return None
        dest_dir = Path("backups")
        dest_dir.mkdir(exist_ok=True)
        dest = dest_dir / f"{src.stem}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}{src.suffix}"
        copy2(src, dest)
        logger.info(f"Backup created at {dest}")
        return str(dest)
    except Exception as exc:
        logger.exception("Failed to backup DB")
        return None

def seed_default_data() -> None:
    try:
        count_res = execute_query("SELECT COUNT(*) FROM products;", fetchone=True)
        if count_res is None or count_res[0] > 0:
            logger.info("Product data exists, skipping seed")
            return
        products = [
            ("Espresso Beans 1kg", "Beverages", 12, 8.5),
            ("Black Tea 200g", "Beverages", 30, 3.0),
            ("Blue Apron Towel", "Home", 5, 12.0),
            ("Notebook A5", "Stationery", 50, 1.5),
            ("Hand Sanitizer 500ml", "Health", 20, 4.5),
        ]
        with get_connection() as conn:
            cur = conn.cursor()
            cur.executemany(
                "INSERT OR IGNORE INTO products (name, category, qty, price) VALUES (?, ?, ?, ?);",
                products
            )
            conn.commit()
            cur.close()
        logger.info("Default product data added successfully")
    except Exception as exc:
        logger.exception("Failed to seed default product data")


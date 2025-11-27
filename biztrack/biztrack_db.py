# biztrack_db.py
from __future__ import annotations
import os
import sqlite3
from pathlib import Path
from shutil import copy2
from datetime import datetime
from typing import Optional, Sequence, List, Dict, Tuple
import logging
import uuid
from werkzeug.security import generate_password_hash

# Configure logging
logger = logging.getLogger("biztrack_db")
logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

# DB file path
DB_FILE = os.environ.get("BIZTRACK_DB", "biztrack.db")
_MEMORY_CONN: Optional[sqlite3.Connection] = None

# ============================
# Connection & Query Helpers
# ============================
def set_db_file(path: str) -> None:
    global DB_FILE
    DB_FILE = path
    logger.info(f"DB file set to {DB_FILE}")

def get_connection(db_file: Optional[str] = None) -> sqlite3.Connection:
    """
    Returns a SQLite connection with foreign keys enabled.
    Uses a shared in-memory connection for ':memory:'.
    """
    global _MEMORY_CONN
    path = db_file or DB_FILE
    if path == ":memory:":
        if _MEMORY_CONN is None:
            _MEMORY_CONN = sqlite3.connect(":memory:", check_same_thread=False)
            _MEMORY_CONN.execute("PRAGMA foreign_keys = ON;")
        return _MEMORY_CONN
    dirpath = os.path.dirname(os.path.abspath(path))
    if dirpath and not os.path.exists(dirpath):
        os.makedirs(dirpath, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def execute_query(
    query: str,
    params: Sequence = (),
    fetch: bool = False,
    fetchone: bool = False,
    commit: bool = False
):
    """
    Executes a SQL query safely and returns fetched results if requested.
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

# ============================
# Schema Initialization
# ============================
def generate_invoice_number() -> str:
    """
    Generates a collision-resistant invoice number combining timestamp and UUID suffix.
    """
    return "INV" + datetime.now().strftime("%Y%m%d%H%M%S") + "-" + uuid.uuid4().hex[:6]

def init_db() -> None:
    """
    Initializes tables and indexes if they do not exist.
    """
    with get_connection() as conn:
        cur = conn.cursor()

        # Products table with threshold column
        cur.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT,
                qty INTEGER NOT NULL DEFAULT 0,
                price REAL NOT NULL DEFAULT 0.0,
                low_stock_threshold INTEGER DEFAULT 10,
                UNIQUE(name, category)
            );
        """)

        # Customers table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT,
                email TEXT,
                UNIQUE(name, phone)
            );
        """)

        # Invoices table
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

        # Sales table
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

        # Payrolls table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS payrolls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_name TEXT,
                salary REAL,
                date TEXT,
                UNIQUE(employee_name, date)
            );
        """)

        # Users table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Indexes for performance
        cur.execute("CREATE INDEX IF NOT EXISTS idx_sales_customer ON sales(customer_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_sales_product ON sales(product_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_sales_invoice ON sales(invoice_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_payrolls_employee ON payrolls(employee_name);")

        conn.commit()
        cur.close()

    logger.info("Database initialized successfully")
    
# ============================
# Schema Migration Helpers
# ============================
def migrate_schema() -> None:
    """
    Ensures all expected columns exist in tables.
    Adds low_stock_threshold to products if missing.
    """
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            # Check columns in products
            cur.execute("PRAGMA table_info(products)")
            cols = [c[1] for c in cur.fetchall()]
            if "low_stock_threshold" not in cols:
                cur.execute("ALTER TABLE products ADD COLUMN low_stock_threshold INTEGER DEFAULT 10;")
                conn.commit()
                logger.info("Added missing column 'low_stock_threshold' to products table")
            cur.close()
    except Exception as e:
        logger.warning(f"Schema migration failed: {e}")

# ============================
# Maintenance Utilities
# ============================
def remove_duplicates() -> None:
    """
    Removes duplicate records, keeping the lowest id per uniqueness group.
    """
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""DELETE FROM products
                           WHERE id NOT IN (SELECT MIN(id) FROM products GROUP BY name, category);""")
            cur.execute("""DELETE FROM customers
                           WHERE id NOT IN (SELECT MIN(id) FROM customers GROUP BY name, phone);""")
            cur.execute("""DELETE FROM sales
                           WHERE id NOT IN (SELECT MIN(id) FROM sales GROUP BY customer_id, product_id, qty, date);""")
            cur.execute("""DELETE FROM payrolls
                           WHERE id NOT IN (SELECT MIN(id) FROM payrolls GROUP BY employee_name, salary, date);""")
            conn.commit()
            cur.close()
        logger.info("Duplicate records removed successfully")
    except Exception as exc:
        logger.exception("Failed to remove duplicates")

def backup_db() -> Optional[str]:
    """
    Creates a timestamped copy of the database file in a configurable backups directory.
    """
    try:
        src = Path(DB_FILE)
        if not src.exists():
            logger.warning("DB file does not exist for backup")
            return None
        dest_dir = Path(os.getenv("BIZTRACK_BACKUP_DIR", "backups"))
        dest_dir.mkdir(exist_ok=True)
        dest = dest_dir / f"{src.stem}_backup_{datetime.now().strftime('%Y%m%d%H%M%S')}{src.suffix}"
        copy2(src, dest)
        logger.info(f"Backup created at {dest}")
        return str(dest)
    except Exception as exc:
        logger.exception("Failed to backup DB")
        return None
    
# ============================
# CSV Import / Export
# ============================
import csv

def export_table_to_csv(table: str, filepath: str) -> bool:
    """Export any table to CSV file."""
    try:
        rows = execute_query(f"SELECT * FROM {table};", fetch=True)
        columns = _get_columns(table)
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(columns)
            writer.writerows(rows)
        logger.info(f"Exported {table} to {filepath}")
        return True
    except Exception as e:
        logger.error(f"Failed to export {table}: {e}")
        return False

def import_table_from_csv(table: str, filepath: str) -> bool:
    """Import data into a table from CSV file."""
    try:
        columns = _get_columns(table)
        with open(filepath, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            with get_connection() as conn:
                cur = conn.cursor()
                for row in reader:
                    values = [row[col] for col in columns if col in row]
                    placeholders = ",".join("?" for _ in values)
                    cur.execute(
                        f"INSERT OR IGNORE INTO {table} ({','.join(columns)}) VALUES ({placeholders});",
                        values
                    )
                conn.commit()
                cur.close()
        logger.info(f"Imported {table} from {filepath}")
        return True
    except Exception as e:
        logger.error(f"Failed to import {table}: {e}")
        return False

def seed_default_data() -> None:
    """
    Seeds minimal default data for development: products and admin user.
    """
    try:
        # Seed products
        count_res = execute_query("SELECT COUNT(*) FROM products;", fetchone=True)
        if count_res is None or count_res[0] == 0:
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

        # Seed default admin user
        user_res = execute_query("SELECT COUNT(*) FROM users;", fetchone=True)
        if user_res is None or user_res[0] == 0:
            with get_connection() as conn:
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO users (username, password, role) VALUES (?, ?, ?);",
                    ("admin", generate_password_hash("admin123"), "admin")
                )
                conn.commit()
                cur.close()
            logger.info("Default admin user added successfully")

    except Exception as exc:
        logger.exception("Failed to seed default data")

# ============================
# User Helpers
# ============================
_USER_COLUMNS: Optional[List[str]] = None

def get_user_by_username(username: str) -> Optional[dict]:
    """
    Returns a user dict by username or None.
    """
    global _USER_COLUMNS
    if _USER_COLUMNS is None:
        cursor = get_connection().cursor()
        cursor.execute("PRAGMA table_info(users)")
        _USER_COLUMNS = [col[1] for col in cursor.fetchall()]
    row = execute_query("SELECT * FROM users WHERE username=?;", (username,), fetchone=True)
    return dict(zip(_USER_COLUMNS, row)) if row else None

# ============================
# Product CRUD & Thresholds
# ============================
def _get_columns(table: str) -> List[str]:
    """
    Helper to fetch column names for a table.
    """
    cursor = get_connection().cursor()
    cursor.execute(f"PRAGMA table_info({table})")
    return [col[1] for col in cursor.fetchall()]

def get_products() -> list[dict]:
    rows = execute_query("SELECT * FROM products;", fetch=True)
    columns = _get_columns("products")
    return [dict(zip(columns, row)) for row in rows]

def add_product(name: str, category: str, qty: int, price: float) -> bool:
    try:
        execute_query(
            "INSERT INTO products (name, category, qty, price) VALUES (?, ?, ?, ?);",
            (name, category, qty, price),
            commit=True
        )
        return True
    except Exception as e:
        logger.error(f"Failed to add product: {e}")
        return False

def update_product(pid: int, name: str, category: str, qty: int, price: float) -> bool:
    try:
        execute_query(
            "UPDATE products SET name=?, category=?, qty=?, price=? WHERE id=?;",
            (name, category, qty, price, pid),
            commit=True
        )
        return True
    except Exception as e:
        logger.error(f"Failed to update product: {e}")
        return False

def delete_product(pid: int) -> bool:
    try:
        execute_query(
            "DELETE FROM products WHERE id=?;",
            (pid,),
            commit=True
        )
        return True
    except Exception as e:
        logger.error(f"Failed to delete product: {e}")
        return False

def update_product_threshold(pid: int, threshold: Optional[int]) -> bool:
    try:
        execute_query(
            "UPDATE products SET low_stock_threshold=? WHERE id=?;",
            (threshold, pid),
            commit=True
        )
        return True
    except Exception as e:
        logger.error(f"Failed to update product threshold: {e}")
        return False

def get_low_stock_products() -> List[Tuple[int, str, int, int]]:
    """
    Returns tuples of (id, name, qty, threshold) for low-stock products.
    """
    return execute_query("""
        SELECT id, name, qty, COALESCE(low_stock_threshold, 10) AS threshold
        FROM products
        WHERE qty < COALESCE(low_stock_threshold, 10)
        ORDER BY qty ASC;
    """, fetch=True) or []

# ============================
# Customer CRUD
# ============================
def get_customers() -> list[dict]:
    """Returns all customers as list of dicts"""
    rows = execute_query("SELECT * FROM customers;", fetch=True)
    cursor = get_connection().cursor()
    cursor.execute("PRAGMA table_info(customers)")
    columns = [col[1] for col in cursor.fetchall()]
    cursor.close()
    return [dict(zip(columns, row)) for row in rows]

def add_customer(name: str, phone: str, email: str) -> bool:
    try:
        execute_query(
            "INSERT INTO customers (name, phone, email) VALUES (?, ?, ?);",
            (name, phone, email),
            commit=True
        )
        return True
    except Exception as e:
        logger.error(f"Failed to add customer: {e}")
        return False

def update_customer(cid: int, name: str, phone: str, email: str) -> bool:
    try:
        execute_query(
            "UPDATE customers SET name=?, phone=?, email=? WHERE id=?;",
            (name, phone, email, cid),
            commit=True
        )
        return True
    except Exception as e:
        logger.error(f"Failed to update customer: {e}")
        return False

def delete_customer(cid: int) -> bool:
    try:
        execute_query(
            "DELETE FROM customers WHERE id=?;",
            (cid,),
            commit=True
        )
        return True
    except Exception as e:
        logger.error(f"Failed to delete customer: {e}")
        return False
    
# ============================
# Payroll CRUD
# ============================
def get_payrolls() -> list[dict]:
    rows = execute_query("SELECT * FROM payrolls;", fetch=True)
    columns = _get_columns("payrolls")
    return [dict(zip(columns, row)) for row in rows]

def add_payroll(employee_name: str, salary: float, date: str) -> bool:
    try:
        execute_query(
            "INSERT INTO payrolls (employee_name, salary, date) VALUES (?, ?, ?);",
            (employee_name, salary, date),
            commit=True
        )
        return True
    except Exception as e:
        logger.error(f"Failed to add payroll: {e}")
        return False

def update_payroll(pid: int, salary: float) -> bool:
    try:
        execute_query(
            "UPDATE payrolls SET salary=? WHERE id=?;",
            (salary, pid),
            commit=True
        )
        return True
    except Exception as e:
        logger.error(f"Failed to update payroll: {e}")
        return False

def delete_payroll(pid: int) -> bool:
    try:
        execute_query("DELETE FROM payrolls WHERE id=?;", (pid,), commit=True)
        return True
    except Exception as e:
        logger.error(f"Failed to delete payroll: {e}")
        return False

# ============================
# Invoices & Sales
# ============================
def get_invoices() -> list[dict]:
    rows = execute_query("SELECT * FROM invoices;", fetch=True)
    columns = _get_columns("invoices")
    return [dict(zip(columns, row)) for row in rows]

def get_sales() -> list[dict]:
    rows = execute_query("SELECT * FROM sales;", fetch=True)
    columns = _get_columns("sales")
    return [dict(zip(columns, row)) for row in rows]

def get_sale_details(invoice_id: int) -> list[dict]:
    """
    Returns sales records for a given invoice_id as dicts.
    """
    rows = execute_query(
        "SELECT * FROM sales WHERE invoice_id=?;",
        (invoice_id,),
        fetch=True
    )
    columns = _get_columns("sales")
    return [dict(zip(columns, row)) for row in rows]

def create_invoice_and_insert_sales(
    customer_id: int,
    items: List[Dict],
    sale_time: Optional[str] = None
) -> Optional[int]:
    """
    Inserts an invoice and its line items into the database, updating product stock.
    Validates stock quantities before committing. Returns invoice_id or None.
    items: [{pid: int, qty: int, price: float}, ...]
    """
    if not sale_time:
        sale_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Validate stock and compute line_total
    for it in items:
        pid = it["pid"]
        qty = it["qty"]
        price = float(it["price"])
        stock = execute_query("SELECT qty FROM products WHERE id = ?;", (pid,), fetchone=True)
        if stock is None:
            logger.error(f"Product ID {pid} not found")
            return None
        if qty > stock[0]:
            logger.error(f"Insufficient stock for Product ID {pid}: requested {qty}, available {stock[0]}")
            return None
        it["line_total"] = round(qty * price, 2)

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

# ============================
# SMS Utility
# ============================
def send_sms(phone: str, message: str) -> bool:
    """Generic SMS sender using utils_sms."""
    try:
        from biztrack.utils_sms import send_message  # type: ignore
        send_message(phone, message)
        logger.info(f"SMS sent to {phone}: {message}")
        return True
    except Exception as e:
        logger.warning(f"SMS failed: {e}")
        return False

def record_sale(customer_id: int, items: List[Dict]) -> Optional[int]:
    """
    Creates invoice and sales lines; triggers low-stock SMS alerts if configured.
    items: [{pid: int, qty: int, price: float}, ...]
    """
    invoice_id = create_invoice_and_insert_sales(customer_id, items)
    if not invoice_id:
        return None

    # Optional SMS alert hook (safe import)
    try:
        low_stock = get_low_stock_products()
        alert_phone = os.getenv("ALERT_PHONE")
        if low_stock and alert_phone:
            try:
                # Late import to keep this file self-contained
                from biztrack.utils_sms import send_low_stock_alerts  # type: ignore
            except Exception:
                send_low_stock_alerts = None  # type: ignore
            if send_low_stock_alerts:
                try:
                    send_low_stock_alerts(low_stock, alert_phone)  # type: ignore
                    logger.info(f"Sent low-stock alerts for {len(low_stock)} product(s)")
                except Exception as e:
                    logger.warning(f"SMS alert failed: {e}")
    except Exception as e:
        logger.warning(f"Low-stock check failed: {e}")

    return invoice_id

def delete_sale(sale_id: int) -> bool:
    try:
        execute_query(
            "DELETE FROM sales WHERE id=?;",
            (sale_id,),
            commit=True
        )
        return True
    except Exception as e:
        logger.error(f"Failed to delete sale: {e}")
        return False

# ============================
# Reporting & Utilities
# ============================
def get_top_sellers(limit: int = 5) -> list[dict]:
    """
    Returns top-selling products by revenue using sales.total_price.
    """
    query = """
        SELECT p.id, p.name, SUM(s.total_price) AS revenue
        FROM sales s
        JOIN products p ON s.product_id = p.id
        GROUP BY p.id, p.name
        ORDER BY revenue DESC
        LIMIT ?;
    """
    rows = execute_query(query, (limit,), fetch=True)
    return [{"id": row[0], "name": row[1], "revenue": row[2]} for row in rows]

def get_utilities() -> list[dict]:
    """
    Placeholder for admin UI utilities.
    """
    return [{"name": "Backup Database"}, {"name": "Remove Duplicates"}]

# ============================
# Admin Commands (Strict)
# ============================
def execute_command(command: str, admin_user_id: int = None) -> dict:
    """
    Executes a whitelisted admin command.
    Returns: {"success": bool, "output": str, "error": str|None}
    """
    if not admin_user_id:
        return {
            "success": False,
            "output": "",
            "error": "Unauthorized: Admin access required"
        }

    # Optional role check if you route via UI:
    # role = execute_query("SELECT role FROM users WHERE id=?;", (admin_user_id,), fetchone=True)
    # if not role or role[0] != "admin":
    #     return {"success": False, "output": "", "error": "Forbidden: Admin role required"}

    try:
        if not command.strip():
            return {"success": False, "output": "", "error": "No command provided"}

        parts = command.strip().split(maxsplit=1)
        cmd = parts[0].lower()

        # Whitelist
        allowed_commands = {'backup', 'dedupe', 'stats', 'health'}
        allowed_commands = {'backup', 'dedupe', 'stats', 'health', 'export', 'import', 'payroll'}

        if cmd not in allowed_commands:
            return {
                "success": False,
                "output": "",
                "error": f"Command '{cmd}' not allowed. Allowed: {', '.join(allowed_commands)}"
            }

        if cmd == "backup":
            path = backup_db()
            return {
                "success": bool(path),
                "output": f"Backup created: {path}" if path else "",
                "error": None if path else "Backup failed"
            }

        elif cmd == "dedupe":
            remove_duplicates()
            return {"success": True, "output": "Duplicates removed", "error": None}

        elif cmd == "stats":
            product_count = execute_query("SELECT COUNT(*) FROM products;", fetchone=True)[0]
            customer_count = execute_query("SELECT COUNT(*) FROM customers;", fetchone=True)[0]
            invoice_count = execute_query("SELECT COUNT(*) FROM invoices;", fetchone=True)[0]
            payroll_count = execute_query("SELECT COUNT(*) FROM payrolls;", fetchone=True)[0]
            return {
                "success": True,
                "output": (
                    f"Products: {product_count}, Customers: {customer_count}, "
                    f"Invoices: {invoice_count}, Payrolls: {payroll_count}"
                ),
                "error": None
            }

        elif cmd == "health":
            try:
                execute_query("SELECT 1;", fetchone=True)
                return {"success": True, "output": "Database: OK", "error": None}
            except Exception as e:
                return {"success": False, "output": "", "error": f"Database error: {e}"}
            
        elif cmd == "export":
            filepath = parts[1] if len(parts) > 1 else "export.csv"
            success = export_table_to_csv("products", filepath)
            return {"success": success, "output": f"Exported to {filepath}", "error": None if success else "Export failed"}

        elif cmd == "import":
            filepath = parts[1] if len(parts) > 1 else "import.csv"
            success = import_table_from_csv("products", filepath)
            return {"success": success, "output": f"Imported from {filepath}", "error": None if success else "Import failed"}

        elif cmd == "payroll":
            payrolls = get_payrolls()
            return {"success": True, "output": str(payrolls), "error": None}

    except Exception as e:
        logger.exception("Command execution error")
        return {"success": False, "output": "", "error": str(e)}

def run_admin_command(cmd: str, admin_user_id: int = None) -> str:
    """
    Convenience wrapper for admin command execution returning a plain string.
    """
    result = execute_command(cmd, admin_user_id)
    if result["success"]:
        return result["output"]
    else:
        return f"Error: {result['error']}"
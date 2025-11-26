# biztrack_db.py
from __future__ import annotations
import os
import sqlite3
from pathlib import Path
from shutil import copy2
from datetime import datetime
from typing import Optional, Sequence, List, Dict
import logging
from werkzeug.security import generate_password_hash

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

        # ✅ Users table (replaces admins)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
        else:
            logger.info("Product data exists, skipping seed")

        # ✅ Seed default admin user
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
        else:
            logger.info("User data exists, skipping seed")

    except Exception as exc:
        logger.exception("Failed to seed default data")
# ----------------------------
# User helper functions
def get_user_by_username(username: str) -> Optional[dict]:
    row = execute_query("SELECT * FROM users WHERE username=?;", (username,), fetchone=True)
    if row:
        # Get column names properly
        cursor = get_connection().cursor()
        cursor.execute("PRAGMA table_info(users)")
        columns = [col[1] for col in cursor.fetchall()]  # <-- use col[1], not col[0]
        return dict(zip(columns, row))
    return None
# ----------------------------
# Web route helper functions
# -------------------------
def get_products() -> list[dict]:
    rows = execute_query("SELECT * FROM products;", fetch=True)
    cursor = get_connection().cursor()
    cursor.execute("PRAGMA table_info(products)")
    columns = [col[1] for col in cursor.fetchall()]  # use column names
    return [dict(zip(columns, row)) for row in rows]

def get_customers() -> list[dict]:
    rows = execute_query("SELECT * FROM customers;", fetch=True)
    cursor = get_connection().cursor()
    cursor.execute("PRAGMA table_info(customers)")
    columns = [col[1] for col in cursor.fetchall()]
    return [dict(zip(columns, row)) for row in rows]

def get_invoices() -> list[dict]:
    rows = execute_query("SELECT * FROM invoices;", fetch=True)
    cursor = get_connection().cursor()
    cursor.execute("PRAGMA table_info(invoices)")
    columns = [col[1] for col in cursor.fetchall()]
    return [dict(zip(columns, row)) for row in rows]

def get_sale_details() -> list[dict]:
    rows = execute_query("SELECT * FROM sale_details;", fetch=True)
    cursor = get_connection().cursor()
    cursor.execute("PRAGMA table_info(sale_details)")
    columns = [col[1] for col in cursor.fetchall()]
    return [dict(zip(columns, row)) for row in rows]

def get_top_sellers(limit: int = 5) -> list[dict]:
    """
    Return top-selling products by revenue.
    Joins sale_details with products to calculate total revenue.
    """
    query = """
        SELECT p.id, p.name, SUM(sd.qty * sd.price) AS revenue
        FROM sale_details sd
        JOIN products p ON sd.product_id = p.id
        GROUP BY p.id, p.name
        ORDER BY revenue DESC
        LIMIT ?;
    """
    rows = execute_query(query, (limit,), fetch=True)
    cursor = get_connection().cursor()
    cursor.execute("PRAGMA table_info(products)")
    product_columns = [col[1] for col in cursor.fetchall()]
    # We only care about id, name, and revenue here
    return [{"id": row[0], "name": row[1], "revenue": row[2]} for row in rows]

def get_utilities() -> list[dict]:
    # Example placeholder: returns backups and duplicates info
    return [{"name": "Backup Database"}, {"name": "Remove Duplicates"}]

# ----------------------------
# Product CRUD
# ----------------------------
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


# ----------------------------
# Customer CRUD
# ----------------------------
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
# -----------------------

# ----------------------------
# Sales / Invoices
# ----------------------------
def record_sale(customer_id: int, items: List[Dict]) -> Optional[int]:
    """
    items: List of dicts [{pid: int, qty: int, price: float}, ...]
    Returns invoice_id or None if failed
    """
    return create_invoice_and_insert_sales(customer_id, items)

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

def get_sale_details(invoice_id: int) -> list[dict]:
    rows = execute_query(
        "SELECT * FROM sales WHERE invoice_id=?;",
        (invoice_id,),
        fetch=True
    )
    columns = [column[0] for column in get_connection().cursor().execute("PRAGMA table_info(sales)")]
    return [dict(zip(columns, row)) for row in rows]
# -----------------------
# -----------------------
# Command Execution
# Make it admin-only with strict whitelisting
def execute_command(command: str, admin_user_id: int = None) -> dict:
    """
    DANGEROUS: Only use with strict validation
    Returns: {"success": bool, "output": str, "error": str|None}
    """
    if not admin_user_id:
        return {
            "success": False,
            "output": "",
            "error": "Unauthorized: Admin access required"
        }
    
    try:
        if not command.strip():
            return {"success": False, "output": "", "error": "No command provided"}
        
        parts = command.strip().split(maxsplit=1)
        cmd = parts[0].lower()
        
        # STRICT WHITELIST - only these exact commands allowed
        allowed_commands = {'backup', 'dedupe', 'stats', 'health'}
        
        if cmd not in allowed_commands:
            return {
                "success": False,
                "output": "",
                "error": f"Command '{cmd}' not allowed. Allowed: {', '.join(allowed_commands)}"
            }
        
        # Execute whitelisted commands
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
            
            return {
                "success": True,
                "output": f"Products: {product_count}, Customers: {customer_count}, Invoices: {invoice_count}",
                "error": None
            }
        
        elif cmd == "health":
            try:
                execute_query("SELECT 1;", fetchone=True)
                return {"success": True, "output": "Database: OK", "error": None}
            except Exception as e:
                return {"success": False, "output": "", "error": f"Database error: {e}"}
        
    except Exception as e:
        logger.exception("Command execution error")
        return {"success": False, "output": "", "error": str(e)}
    
def run_admin_command(cmd: str, admin_user_id: int = None) -> str:
    result = execute_command(cmd, admin_user_id)
    if result["success"]:
        return result["output"]
    else:
        return f"Error: {result['error']}"

# -----------------------
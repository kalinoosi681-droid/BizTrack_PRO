from __future__ import annotations
import os
from flask import current_app
import sqlite3
from flask import g
from pathlib import Path
from shutil import copy2
from datetime import datetime
from typing import Optional, Sequence, List, Dict, Tuple
import logging
import uuid
import csv

# Configure logging
logger = logging.getLogger("biztrack_db")
logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

DB_FILE = os.environ.get("BIZTRACK_DB", "biztrack.db")
_COLUMN_CACHE: Dict[str, List[str]] = {}

# ============================
# Connection & Query Helpers
# ============================
def set_db_file(path: str) -> None:
    global DB_FILE
    DB_FILE = path
    logger.info(f"DB file set to {DB_FILE}")

def get_connection(db_file: Optional[str] = None) -> sqlite3.Connection:
    """Get a database connection for the current application context."""
    # For testing with an in-memory database, we need a single, persistent connection
    # for the life of the app. We attach it to the app object itself.
    if current_app.config.get('TESTING') and DB_FILE == ':memory:':
        if not hasattr(current_app, 'sqlite_db_conn'):
            current_app.sqlite_db_conn = sqlite3.connect(":memory:", check_same_thread=False)
            current_app.sqlite_db_conn.execute("PRAGMA foreign_keys = ON;")
        return current_app.sqlite_db_conn

    if 'db_conn' not in g:
        path = db_file or DB_FILE
        conn = sqlite3.connect(path, timeout=10, check_same_thread=False)
        conn.execute("PRAGMA foreign_keys = ON;")
        g.db_conn = conn

    return g.db_conn

def close_connection(e=None) -> None:
    """Close the database connection at the end of the request."""
    conn = g.pop('db_conn', None)
    if conn is not None:
        # To check if it's an in-memory DB, we check the database file path.
        # We don't close the persistent in-memory connection for tests.
        conn.close()

def execute_query(query: str, params: Sequence = (), fetch: bool = False,
                  fetchone: bool = False, commit: bool = False):
    try:
        conn = get_connection()
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
    return "INV" + datetime.now().strftime("%Y%m%d%H%M%S") + "-" + uuid.uuid4().hex[:6]


def init_db() -> None:
    conn = get_connection()
    cur = conn.cursor()
    try:
        # Products
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

        # Users
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                failed_attempts INTEGER DEFAULT 0,
                locked_until TIMESTAMP,
                reset_token TEXT,
                reset_token_expiration TIMESTAMP
            );
        """)

        # Metrics tables
        cur.execute("""
            CREATE TABLE IF NOT EXISTS product_metrics_daily (
                product_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                sales_qty INTEGER DEFAULT 0,
                ema3 REAL DEFAULT 0,
                ema7 REAL DEFAULT 0,
                momentum_up INTEGER DEFAULT 0,
                PRIMARY KEY (product_id, date),
                FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS store_metrics_daily (
                date TEXT PRIMARY KEY,
                revenue REAL DEFAULT 0,
                margin_pct REAL DEFAULT 0,
                invoices_count INTEGER DEFAULT 0
            );
        """)

        # Indexes
        cur.execute("CREATE INDEX IF NOT EXISTS idx_sales_customer ON sales(customer_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_sales_product ON sales(product_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_sales_invoice ON sales(invoice_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_sales_date ON sales(date);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_products_name_lower ON products(LOWER(name));")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_products_category_lower ON products(LOWER(category));")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_customers_name_lower ON customers(LOWER(name));")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_payrolls_employee ON payrolls(employee_name);")

        # Advanced Upgrade: Full-Text Search (FTS5)
        cur.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS products_fts USING fts5(
                name, category, content='products', content_rowid='id'
            );
        """)
        cur.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS customers_fts USING fts5(
                name, phone, email, content='customers', content_rowid='id'
            );
        """)
        # Triggers to keep FTS tables in sync
        cur.execute("CREATE TRIGGER IF NOT EXISTS products_after_insert AFTER INSERT ON products BEGIN INSERT INTO products_fts(rowid, name, category) VALUES (new.id, new.name, new.category); END;")
        cur.execute("CREATE TRIGGER IF NOT EXISTS products_after_delete AFTER DELETE ON products BEGIN INSERT INTO products_fts(products_fts, rowid, name, category) VALUES ('delete', old.id, old.name, old.category); END;")
        cur.execute("CREATE TRIGGER IF NOT EXISTS products_after_update AFTER UPDATE ON products BEGIN INSERT INTO products_fts(products_fts, rowid, name, category) VALUES ('delete', old.id, old.name, old.category); INSERT INTO products_fts(rowid, name, category) VALUES (new.id, new.name, new.category); END;")
        conn.commit()
    finally:
        cur.close()

    logger.info("Database initialized successfully")    
    
# ============================

def migrate_schema() -> None:
    """
    Safely migrate existing database schema to add missing columns.
    This function checks for missing columns and adds them without data loss.
    """
    try:
        conn = get_connection()
        cur = conn.cursor()
        try:
            # Check and add low_stock_threshold to products if missing
            cur.execute("PRAGMA table_info(products);")
            products_cols = [col[1] for col in cur.fetchall()]
            
            if 'low_stock_threshold' not in products_cols:
                logger.info("Adding low_stock_threshold column to products table")
                cur.execute("""
                    ALTER TABLE products 
                    ADD COLUMN low_stock_threshold INTEGER DEFAULT 10;
                """)
                logger.info("✅ Added low_stock_threshold to products")
            
            # Check if metrics tables exist, create if missing
            cur.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='product_metrics_daily';
            """)
            
            if not cur.fetchone():
                logger.info("Creating product_metrics_daily table")
                cur.execute("""
                    CREATE TABLE product_metrics_daily (
                        product_id INTEGER NOT NULL,
                        date TEXT NOT NULL,
                        sales_qty INTEGER DEFAULT 0,
                        ema3 REAL DEFAULT 0,
                        ema7 REAL DEFAULT 0,
                        momentum_up INTEGER DEFAULT 0,
                        PRIMARY KEY (product_id, date),
                        FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE
                    );
                """)
                logger.info("✅ Created product_metrics_daily table")
            
            cur.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='store_metrics_daily';
            """)
            
            if not cur.fetchone():
                logger.info("Creating store_metrics_daily table")
                cur.execute("""
                    CREATE TABLE store_metrics_daily (
                        date TEXT PRIMARY KEY,
                        revenue REAL DEFAULT 0,
                        margin_pct REAL DEFAULT 0,
                        invoices_count INTEGER DEFAULT 0
                    );
                """)
                logger.info("✅ Created store_metrics_daily table")
            
            # Verify invoice_id column exists in sales table
            cur.execute("PRAGMA table_info(sales);")
            sales_cols = [col[1] for col in cur.fetchall()]
            
            if 'invoice_id' not in sales_cols:
                logger.info("Adding invoice_id column to sales table")
                cur.execute("""
                    ALTER TABLE sales 
                    ADD COLUMN invoice_id INTEGER 
                    REFERENCES invoices(id) ON DELETE CASCADE;
                """)
                logger.info("✅ Added invoice_id to sales")
            
            # Check and add security columns to users table
            cur.execute("PRAGMA table_info(users);")
            users_cols = {col[1] for col in cur.fetchall()}
            security_cols = {
                "failed_attempts": "INTEGER DEFAULT 0",
                "locked_until": "TIMESTAMP",
                "reset_token": "TEXT",
                "reset_token_expiration": "TIMESTAMP"
            }

            for col, col_type in security_cols.items():
                if col not in users_cols:
                    logger.info(f"Adding '{col}' column to users table")
                    cur.execute(f"ALTER TABLE users ADD COLUMN {col} {col_type};")
                    logger.info(f"✅ Added '{col}' to users")

            conn.commit()
        finally:
            cur.close()
        logger.info("✅ Database schema migration completed successfully")    
        
    except Exception as exc:
        logger.exception("Failed to migrate schema")
        # Optionally re-raise if migration failure is critical

def compute_daily_store_metrics() -> None:
    agg = execute_query("""
        SELECT COALESCE(SUM(total),0), COUNT(*)
        FROM invoices
        WHERE date(date) = date('now');
    """, fetchone=True)
    revenue = float(agg[0] or 0)
    invoices_count = int(agg[1] or 0)

    # Heuristic margin until cost is tracked; adjust as needed
    margin_pct = 30.0

    execute_query("""
        INSERT INTO store_metrics_daily(date, revenue, margin_pct, invoices_count)
        VALUES (date('now'), ?, ?, ?)
        ON CONFLICT(date) DO UPDATE SET
          revenue=excluded.revenue,
          margin_pct=excluded.margin_pct,
          invoices_count=excluded.invoices_count;
    """, (revenue, margin_pct, invoices_count), commit=True)

def compute_daily_product_metrics() -> None:
    products = execute_query("SELECT id FROM products;", fetch=True) or []
    for (pid,) in products:
        series = execute_query("""
            SELECT date, COALESCE(SUM(qty),0) AS qty
            FROM sales
            WHERE product_id = ? AND date >= date('now','-30 day')
            GROUP BY date ORDER BY date;
        """, (pid,), fetch=True) or []
        vals = [q for _, q in series]
        def ema(v, n):
            a = 2/(n+1); out=[]; prev=None
            for x in v:
                prev = x if prev is None else a*x + (1-a)*prev
                out.append(prev)
            return out
        ema3, ema7 = ema(vals, 3), ema(vals, 7)
        momentum_up = int(bool(ema3 and ema7 and (ema3[-1] > ema7[-1])))

        today_qty = execute_query("""
            SELECT COALESCE(SUM(qty),0)
            FROM sales
            WHERE product_id = ? AND date = date('now');
        """, (pid,), fetchone=True)[0] or 0

        execute_query("""
            INSERT INTO product_metrics_daily(product_id, date, sales_qty, ema3, ema7, momentum_up)
            VALUES (?, date('now'), ?, ?, ?, ?)
            ON CONFLICT(product_id, date) DO UPDATE SET
              sales_qty=excluded.sales_qty,
              ema3=excluded.ema3,
              ema7=excluded.ema7,
              momentum_up=excluded.momentum_up;
        """, (pid, int(today_qty), float(ema3[-1] if ema3 else 0), float(ema7[-1] if ema7 else 0), momentum_up), commit=True)


# ============================
# Maintenance Utilities
# ============================
def remove_duplicates() -> None:
    try:
        conn = get_connection()
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

def optimize_db() -> None:
    try:
        conn = get_connection()
        conn.execute("ANALYZE;")
        conn.execute("VACUUM;")
        logger.info("Database optimized")
    except Exception as exc:
        logger.exception("Failed to optimize DB")

# ============================
# CSV Import / Export
# ============================
def export_table_to_csv(table: str, filepath: str) -> bool:
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
    if not os.path.isfile(filepath):
        logger.error(f"CSV file not found: {filepath}")
        return False

    try:
        table_cols = _get_columns(table)
        with open(filepath, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            csv_cols = [c for c in reader.fieldnames or [] if c in table_cols]
            if not csv_cols:
                logger.error("CSV columns do not match table schema")
                return False
            
            conn = get_connection()
            cur = conn.cursor()
            placeholders = ",".join("?" for _ in csv_cols)
            for row in reader:
                values = [row.get(c) for c in csv_cols]
                try:
                    cur.execute(
                        f"INSERT OR IGNORE INTO {table} ({','.join(csv_cols)}) VALUES ({placeholders});",
                        values
                    )
                except Exception as row_exc:
                    logger.warning(f"Row insert failed: {row_exc} | Row: {row}")
            conn.commit()
        logger.info(f"Imported {table} from {filepath}")
        return True

    except Exception as e:
        logger.exception(f"Failed to import {table} from {filepath}")
        return False

def seed_default_data() -> None:
    """    
    Seeds minimal default data for development: products and admin user.
    """
    try:
        from werkzeug.security import generate_password_hash
        products = [
            ("Espresso Beans 1kg", "Beverages", 12, 8.5),
            ("Black Tea 200g", "Beverages", 30, 3.0),
            ("Blue Apron Towel", "Home", 5, 12.0),
            ("Notebook A5", "Stationery", 50, 1.5),
            ("Hand Sanitizer 500ml", "Health", 20, 4.5),
        ]
        conn = get_connection()
        cur = conn.cursor()
        cur.executemany(
            "INSERT OR IGNORE INTO products (name, category, qty, price) VALUES (?, ?, ?, ?);",
            products
        )
        conn.commit()

        # Seed default admin user
        admin_exists = execute_query("SELECT 1 FROM users WHERE username = 'admin';", fetchone=True)
        if not admin_exists:
            execute_query(
                "INSERT INTO users (username, password, role) VALUES (?, ?, ?);",
                ("admin", generate_password_hash("admin123"), "admin"),
                commit=True
            )
            logger.info("Default admin user added successfully")
        cur.close()

    except Exception as exc:
        logger.exception("Failed to seed default data")

# ============================
# User Helpers
# ============================
def get_user_by_username(username: str) -> Optional[dict]:
    """
    Returns a user dict by username or None.
    """
    columns = _get_columns("users")
    row = execute_query("SELECT * FROM users WHERE username=?;", (username,), fetchone=True)
    return dict(zip(columns, row)) if row else None

def get_user_by_token(token: str) -> Optional[dict]:
    """Returns a user dict by reset token or None."""
    columns = _get_columns("users")
    row = execute_query("SELECT * FROM users WHERE reset_token=?;", (token,), fetchone=True)
    return dict(zip(columns, row)) if row else None

def get_user_by_id(user_id: int) -> Optional[dict]:
    """
    Returns a user dict by user ID or None.
    Used by Flask-Login's user_loader.
    """
    columns = _get_columns("users")
    row = execute_query("SELECT * FROM users WHERE id=?;", (user_id,), fetchone=True)
    return dict(zip(columns, row)) if row else None

# ============================
# Product CRUD & Thresholds
# ============================
def _get_columns(table: str) -> List[str]:
    """Helper to fetch column names for a table, with caching."""
    global _COLUMN_CACHE
    if table in _COLUMN_CACHE:
        return _COLUMN_CACHE[table]
    
    cursor = get_connection().cursor()
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [col[1] for col in cursor.fetchall()]
    _COLUMN_CACHE[table] = columns
    return columns

def get_products() -> list[dict]:
    """Returns all products as a list of dicts."""
    rows = execute_query("SELECT * FROM products;", fetch=True)
    columns = _get_columns("products")
    return [dict(zip(columns, row)) for row in rows]

def get_customers(with_insights: bool = False) -> list[dict]:
    """
    Returns all customers. If with_insights is True, joins and calculates
    total spend and last purchase date in a single efficient query.
    """
    if not with_insights:
        rows = execute_query("SELECT * FROM customers;", fetch=True)
        columns = _get_columns("customers")
        return [dict(zip(columns, row)) for row in rows]

    # Optimized query to fetch customers with insights
    query = """
        SELECT 
            c.id, 
            c.name, 
            c.phone, 
            c.email,
            COALESCE(SUM(i.total), 0) as total_spend,
            MAX(i.date) as last_purchase
        FROM customers c
        LEFT JOIN invoices i ON c.id = i.customer_id
        GROUP BY c.id, c.name, c.phone, c.email
        ORDER BY c.name;
    """
    rows = execute_query(query, fetch=True)
    return [
        {
            "id": row[0], "name": row[1], "phone": row[2], "email": row[3],
            "total_spend": float(row[4]), "last_purchase": row[5]
        }
        for row in rows
    ]

def get_invoices() -> list[dict]:
    """Returns all invoices joined with customer names for readability."""
    query = """
        SELECT i.id, i.invoice_number, i.customer_id, c.name as customer_name, i.total, i.date
        FROM invoices i
        LEFT JOIN customers c ON i.customer_id = c.id
        ORDER BY i.date DESC;
    """
    rows = execute_query(query, fetch=True)
    # Manually define columns as we have a custom query
    columns = ["id", "invoice_number", "customer_id", "customer_name", "total", "date"]
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

def update_product_stock(pid: int, new_qty: int) -> bool:
    """Updates the stock quantity for a single product."""
    try:
        # First, check if the product exists to provide better feedback
        exists = execute_query("SELECT 1 FROM products WHERE id=?;", (pid,), fetchone=True)
        if not exists:
            logger.warning(f"Attempted to update stock for non-existent product ID: {pid}")
            return False

        execute_query("UPDATE products SET qty = ? WHERE id = ?;", (new_qty, pid), commit=True)
        logger.info(f"Stock for product ID {pid} updated to {new_qty}")
        return True
    except Exception as e:
        logger.error(f"Failed to update product stock for ID {pid}: {e}")
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
    
def get_store_avg_7d_qty() -> float:
    row = execute_query("""
        SELECT COALESCE(AVG(sq), 0) FROM (
            SELECT COALESCE(SUM(qty),0) AS sq
            FROM sales
            WHERE date >= date('now','-7 day')
            GROUP BY product_id
        );
    """, fetchone=True)
    return float(row[0] or 0)

def get_product_7d_qty(product_id: int) -> int:
    row = execute_query("""
        SELECT COALESCE(SUM(qty),0)
        FROM sales
        WHERE product_id = ? AND date >= date('now','-7 day');
    """, (product_id,), fetchone=True)
    return int(row[0] or 0)

def compute_perf_percent(product_id: int) -> float:
    avg_store = get_store_avg_7d_qty()
    p7 = get_product_7d_qty(product_id)
    return round(100.0 * (p7 / avg_store), 1) if avg_store > 0 else 100.0

def get_customer_insights(cid: int) -> dict:
    """
    Advanced function to get comprehensive customer insights in a single, optimized query.
    Calculates total spend, average spend, last purchase date, and days since last purchase.
    """
    insights = execute_query("""
        SELECT 
            COALESCE(SUM(total), 0) as total_spend,
            COALESCE(AVG(total), 0) as avg_spend,
            MAX(date) as last_purchase,
            CAST(JULIANDAY('now') - JULIANDAY(MAX(date)) AS INTEGER) as days_since_purchase
        FROM invoices WHERE customer_id=?;
    """, (cid,), fetchone=True)
    
    return {
        "total_spend": float(insights[0] or 0),
        "avg_spend": float(insights[1] or 0),
        "last_purchase": insights[2],
        "days_since_purchase": insights[3]
    }
    
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

def update_payroll(pid: int, employee_name: str, salary: float, date: str) -> bool:
    try:
        execute_query(
            "UPDATE payrolls SET employee_name=?, salary=?, date=? WHERE id=?;",
            (employee_name, salary, date, pid),
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
def get_sales() -> list[dict]:
    rows = execute_query("SELECT * FROM sales;", fetch=True)
    columns = _get_columns("sales")
    return [dict(zip(columns, row)) for row in rows]

def get_sale_details(invoice_id: int) -> list[dict]:
    """Returns enriched line items for a given invoice_id."""
    # This query now joins with products to get the name and calculates
    # the historical unit price from the sales record.
    query = """
        SELECT 
            s.product_id,
            p.name as product_name,
            s.qty,
            s.total_price,
            (s.total_price / s.qty) as price -- Calculate historical unit price
        FROM sales s
        JOIN products p ON s.product_id = p.id
        WHERE s.invoice_id = ?;
    """
    rows = execute_query(query, (invoice_id,), fetch=True)
    return [
        {"product_id": r[0], "product_name": r[1], "qty": r[2], "total_price": r[3], "price": r[4]}
        for r in rows
    ]

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
        if qty > stock[0]: # Check if stock is sufficient
            logger.error(f"Invoice creation failed: Insufficient stock for Product ID {pid}. Requested: {qty}, Available: {stock[0]}")
            return None
        it["line_total"] = round(qty * price, 2)

    invoice_number = generate_invoice_number() # Generate a unique invoice number
    total = sum(it["line_total"] for it in items)

    conn = get_connection()
    cur = conn.cursor()
    try:
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
        logger.info(f"Invoice {invoice_number} created successfully with ID {invoice_id}")
        return invoice_id
    except Exception as exc:
        logger.exception(f"Failed to create invoice {invoice_number}")
        if conn:
            conn.rollback()
        return None
    finally:
        if cur:
            cur.close()

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
    # CRITICAL SECURITY FIX: Verify the user has the 'admin' role.
    role_result = execute_query("SELECT role FROM users WHERE id=?;", (admin_user_id,), fetchone=True)
    if not role_result or role_result[0] != "admin":
        return {"success": False, "output": "", "error": "Forbidden: Admin role required"}

    # This check is now redundant due to the one above, but kept for defense-in-depth.
    if not admin_user_id:
        return {"success": False, "output": "", "error": "Unauthorized: Admin access required"}

    try:
        if not command.strip():
            return {"success": False, "output": "", "error": "No command provided"}

        parts = command.strip().split(maxsplit=1)
        cmd = parts[0].lower()

        # Whitelist
        allowed_commands = {'backup', 'dedupe', 'stats', 'health'}

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
    

def get_stock_performance() -> dict:
    """
    Returns comprehensive stock performance analysis
    Fast-moving: >10 units sold in 30 days
    Slow-moving: <3 units sold in 30 days
    """
    fast_moving = execute_query("""
        SELECT p.id, p.name, p.category, SUM(s.qty) as total_sold
        FROM products p
        JOIN sales s ON p.id = s.product_id
        WHERE s.date >= date('now', '-30 days')
        GROUP BY p.id
        HAVING total_sold > 10
        ORDER BY total_sold DESC;
    """, fetch=True)
    
    slow_moving = execute_query("""
        SELECT p.id, p.name, p.category, p.qty,
               COALESCE(SUM(s.qty), 0) as total_sold,
               JULIANDAY('now') - JULIANDAY(MAX(s.date)) as days_since_last_sale
        FROM products p
        LEFT JOIN sales s ON p.id = s.product_id 
            AND s.date >= date('now', '-30 days')
        WHERE p.qty > 0
        GROUP BY p.id
        HAVING total_sold < 3
        ORDER BY days_since_last_sale DESC;
    """, fetch=True)
    
    return {
        "fast_moving": fast_moving or [],
        "slow_moving": slow_moving or []
    }

def get_sales_stats_in_range(start_date: str, end_date: str) -> dict:
    """
    Calculates sales statistics for a given date range.
    Dates should be in 'YYYY-MM-DD' format.
    """
    query = """
        SELECT COUNT(*), COALESCE(SUM(total), 0)
        FROM invoices
        WHERE date(date) BETWEEN ? AND ?;
    """
    stats = execute_query(query, (start_date, end_date), fetchone=True)
    return {"invoice_count": stats[0], "total_revenue": stats[1]} if stats else {"invoice_count": 0, "total_revenue": 0}


# ============================
# Customer Intelligence Queries
# ============================

def get_top_customers(limit: int = 5) -> list[dict]:
    """Returns top customers by total spending."""
    query = """
        SELECT c.id, c.name, SUM(i.total) as total_spent
        FROM customers c
        JOIN invoices i ON c.id = i.customer_id
        GROUP BY c.id, c.name
        ORDER BY total_spent DESC
        LIMIT ?;
    """
    rows = execute_query(query, (limit,), fetch=True)
    return [{"id": row[0], "name": row[1], "total_spent": row[2]} for row in rows]

def search_customers_by_name(name_query: str, limit: int = 5) -> list[dict]:
    """Searches for customers by a partial name match."""
    # Upgraded to use FTS5 for performance and relevance
    rows = execute_query("""
        SELECT c.id, c.name, c.phone, c.email
        FROM customers_fts f
        JOIN customers c ON f.rowid = c.id
        WHERE f.customers_fts MATCH ?
        ORDER BY rank
        LIMIT ?;
    """, (f'"{name_query}"*', limit), fetch=True)
    return [{"id": row[0], "name": row[1], "phone": row[2], "email": row[3]} for row in rows]

def get_inactive_customers(days: int = 90, limit: int = 5) -> list[dict]:
    """Finds customers who have not made a purchase in a given number of days."""
    query = """
        SELECT c.id, c.name, MAX(i.date) as last_purchase_date,
               CAST(JULIANDAY('now') - JULIANDAY(MAX(i.date)) AS INTEGER) as days_since_purchase
        FROM customers c
        LEFT JOIN invoices i ON c.id = i.customer_id
        GROUP BY c.id, c.name
        HAVING last_purchase_date IS NOT NULL AND days_since_purchase > ?
        ORDER BY days_since_purchase DESC
        LIMIT ?;
    """
    rows = execute_query(query, (days, limit), fetch=True)
    return [{"id": row[0], "name": row[1], "last_purchase_date": row[2], "days_since_purchase": row[3]} for row in rows]

def get_customer_last_purchase(customer_id: int) -> list[dict]:
    """Gets the items from a customer's most recent invoice."""
    last_invoice_id = execute_query("""
        SELECT id FROM invoices WHERE customer_id = ? ORDER BY date DESC LIMIT 1;
    """, (customer_id,), fetchone=True)

    if not last_invoice_id:
        return []

    query = """
        SELECT p.name, s.qty, s.total_price
        FROM sales s
        JOIN products p ON s.product_id = p.id
        WHERE s.invoice_id = ?;
    """
    rows = execute_query(query, (last_invoice_id[0],), fetch=True)
    return [{"product_name": row[0], "qty": row[1], "total_price": row[2]} for row in rows]



def get_product_sale_history(product_id: int, days: int = 30) -> list[dict]:
    """Get sale history for a specific product"""
    rows = execute_query("""
        SELECT date, qty, total_price
        FROM sales
        WHERE product_id = ? AND date >= date('now', ? || ' days')
        ORDER BY date DESC;
    """, (product_id, -days), fetch=True)
    
    return [
        {"date": row[0], "qty": row[1], "total": row[2]}
        for row in rows
    ]

def get_reorder_alerts(lead_time_days: int = 7, safety_stock_days: int = 3) -> list[dict]:
    """
    Generates reorder alerts based on sales velocity.
    - lead_time_days: How many days it takes for new stock to arrive.
    - safety_stock_days: Extra buffer of stock.
    """
    query = """
        WITH product_sales_velocity AS (
            SELECT
                p.id,
                p.name,
                p.qty,
                p.low_stock_threshold,
                COALESCE(SUM(s.qty) / 30.0, 0.0) AS daily_avg_sale
            FROM products p
            LEFT JOIN sales s ON p.id = s.product_id AND s.date >= date('now', '-30 days')
            GROUP BY p.id, p.name, p.qty, p.low_stock_threshold
        )
        SELECT
            id,
            name,
            qty,
            daily_avg_sale,
            (daily_avg_sale * (? + ?)) AS reorder_point -- lead_time + safety_stock
        FROM product_sales_velocity
        WHERE qty < (daily_avg_sale * (? + ?)) AND daily_avg_sale > 0;
    """
    params = (lead_time_days, safety_stock_days, lead_time_days, safety_stock_days)
    rows = execute_query(query, params, fetch=True)

    alerts = []
    for row in rows:
        product_id, name, current_stock, daily_avg, reorder_point = row
        days_of_stock_left = current_stock / daily_avg if daily_avg > 0 else 999
        
        urgency = "low"
        if days_of_stock_left <= safety_stock_days:
            urgency = "critical"
        elif days_of_stock_left <= lead_time_days:
            urgency = "high"

        alerts.append({
            "product_id": product_id, "product_name": name, "current_stock": current_stock,
            "reorder_qty": max(10, round(reorder_point * 1.5)), # Suggest reordering 1.5x the reorder point
            "urgency": urgency, "recommendation": f"Stock may run out in ~{int(days_of_stock_left)} days."
        })
    return sorted(alerts, key=lambda x: (x['urgency'] != 'critical', x['urgency'] != 'high'))

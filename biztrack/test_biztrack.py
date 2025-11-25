import pytest
from biztrack.biztrack_db import set_db_file, init_db, execute_query

# Use in-memory DB — super fast, no file left behind
set_db_file(":memory:")

# This fixture runs BEFORE every test and creates all tables + seed data
@pytest.fixture(autouse=True)
def setup_database():
    init_db()   # ← This creates ALL tables (products, customers, payrolls, etc.)
    # Optional: seed minimal data if you want
    execute_query(
        "INSERT INTO customers (name, phone) VALUES (?, ?);",
        ("Test Customer", "000-000-000"), commit=True
    )
    execute_query(
        "INSERT INTO products (name, category, qty, price) VALUES (?, ?, ?, ?);",
        ("Premium Coffee", "Drinks", 200, 12.99), commit=True
    )

def test_add_and_view_product():
    execute_query(
        "INSERT INTO products (name, category, qty, price) VALUES (?, ?, ?, ?);",
        ("Latte", "Drinks", 100, 4.5), commit=True
    )
    row = execute_query(
        "SELECT name, price FROM products WHERE name = ?;", ("Latte",), fetchone=True
    )
    assert row is not None
    assert row[0] == "Latte"
    assert row[1] == 4.5

def test_record_sale_reduces_stock():
    # Get IDs of seeded data
    cid = execute_query("SELECT id FROM customers WHERE name = 'Test Customer';", fetchone=True)[0]
    pid = execute_query("SELECT id FROM products WHERE name = 'Premium Coffee';", fetchone=True)[0]

    old_qty = execute_query("SELECT qty FROM products WHERE id = ?;", (pid,), fetchone=True)[0]

    # Record a sale
    execute_query(
        "INSERT INTO sales (customer_id, product_id, qty, total_price, date) VALUES (?, ?, ?, ?, datetime('now'));",
        (cid, pid, 15, 194.85), commit=True
    )
    execute_query("UPDATE products SET qty = qty - 15 WHERE id = ?;", (pid,), commit=True)

    new_qty = execute_query("SELECT qty FROM products WHERE id = ?;", (pid,), fetchone=True)[0]
    assert new_qty == old_qty - 15

def test_payroll_crud():
    execute_query(
        "INSERT INTO payrolls (employee_name, salary, date) VALUES (?, ?, ?);",
        ("Alice Johnson", 3500.0, "2025-11-01"), commit=True
    )
    row = execute_query(
        "SELECT salary FROM payrolls WHERE employee_name = 'Alice Johnson';", fetchone=True
    )
    assert row is not None
    assert row[0] == 3500.0

    # Test update
    execute_query(
        "UPDATE payrolls SET salary = 4000.0 WHERE employee_name = 'Alice Johnson';", commit=True
    )
    updated = execute_query(
        "SELECT salary FROM payrolls WHERE employee_name = 'Alice Johnson';", fetchone=True
    )
    assert updated[0] == 4000.0

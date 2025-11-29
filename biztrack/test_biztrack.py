import pytest
from biztrack import create_app, auth
from biztrack.biztrack_db import (
    init_db, execute_query, create_invoice_and_insert_sales, 
    get_customers, get_low_stock_products, get_sales_stats_in_range, seed_default_data
)
from biztrack.ai_engine import predict_category, _parse_date_range_from_query, parse_ai_query
from datetime import datetime, timedelta
import os
import uuid


@pytest.fixture
def app():
    """Create and configure a new app instance for each test."""
    # Use an in-memory database for testing
    os.environ['BIZTRACK_DB'] = ':memory:'
    app = create_app('testing')

    yield app

    # Teardown: close the in-memory database connection
    with app.app_context():
        # The connection is now managed on the app object for tests
        if hasattr(app, 'sqlite_db_conn'):
            conn = app.sqlite_db_conn
            conn.close()

@pytest.fixture
def client(app):
    """A test client for the app."""
    with app.app_context():
        init_db()
        seed_default_data()
        auth.setup_admin_if_needed()
    return app.test_client()

def login(client, username, password):
    """Helper function to log in a user."""
    return client.post('/login', data=dict(
        username=username,
        password=password
    ), follow_redirects=True)

def test_add_and_view_product(client):
    with client.application.app_context():
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

def test_record_sale_reduces_stock(client):
    with client.application.app_context():
        # Get IDs of seeded data
        cid = execute_query("SELECT id FROM customers WHERE name = 'Test Customer';", fetchone=True)[0]
        pid = execute_query("SELECT id FROM products WHERE name = 'Premium Coffee';", fetchone=True)[0]

        old_qty = execute_query("SELECT qty FROM products WHERE id = ?;", (pid,), fetchone=True)[0]
        
        items = [{"pid": pid, "qty": 15, "price": 12.99}]

        # Record a sale
        invoice_id = create_invoice_and_insert_sales(cid, items)
        
        assert invoice_id is not None

        new_qty = execute_query("SELECT qty FROM products WHERE id = ?;", (pid,), fetchone=True)[0]
        assert new_qty == old_qty - 15

import uuid

def test_payroll_crud(client):
    with client.application.app_context():
        employee_name = f"Alice Johnson {uuid.uuid4()}"
        execute_query(
            "INSERT INTO payrolls (employee_name, salary, date) VALUES (?, ?, ?);",
            (employee_name, 3500.0, "2025-11-01"), commit=True
        )
        row = execute_query(
            "SELECT salary FROM payrolls WHERE employee_name = ?;", (employee_name,), fetchone=True
        )
        assert row is not None
        assert row[0] == 3500.0

        # Test update
        execute_query(
            "UPDATE payrolls SET salary = 4000.0 WHERE employee_name = ?;", (employee_name,), commit=True
        )
        updated = execute_query(
            "SELECT salary FROM payrolls WHERE employee_name = ?;", (employee_name,), fetchone=True
        )
        assert updated[0] == 4000.0

# ========================================
# NEW TESTS FOR DATABASE LOGIC
# ========================================

def test_get_customers_with_insights(client):
    """Test the N+1 optimization for fetching customers with their sales data."""
    with client.application.app_context():
        # Create a unique customer for this test
        customer_name = f"Test Customer {uuid.uuid4()}"
        execute_query(
            "INSERT INTO customers (name, phone) VALUES (?, ?);",
            (customer_name, "111-111-111"), commit=True
        )
        cid = execute_query("SELECT id FROM customers WHERE name = ?;", (customer_name,), fetchone=True)[0]
        pid = execute_query("SELECT id FROM products WHERE name = 'Premium Coffee';", fetchone=True)[0]

        # Create two invoices for the customer
        create_invoice_and_insert_sales(cid, [{"pid": pid, "qty": 1, "price": 10.0}])
        create_invoice_and_insert_sales(cid, [{"pid": pid, "qty": 1, "price": 20.0}])

        # Fetch customers with insights
        customers = get_customers(with_insights=True)
        test_customer = next((c for c in customers if c['id'] == cid), None)

        assert test_customer is not None
        assert test_customer['total_spend'] == 30.0
        assert test_customer['last_purchase'] is not None

def test_insufficient_stock_fails_invoice(client):
    """Ensure an invoice cannot be created if stock is too low."""
    with client.application.app_context():
        cid = execute_query("SELECT id FROM customers WHERE name = 'Test Customer';", fetchone=True)[0]
        pid = execute_query("SELECT id FROM products WHERE name = 'Low Stock Tea';", fetchone=True)[0]
        
        # Current stock is 5. Try to sell 6.
        items = [{"pid": pid, "qty": 6, "price": 3.99}]
        invoice_id = create_invoice_and_insert_sales(cid, items)

        assert invoice_id is None, "Invoice should not be created with insufficient stock"

        # Verify stock was not changed
        stock_after = execute_query("SELECT qty FROM products WHERE id = ?;", (pid,), fetchone=True)[0]
        assert stock_after == 5

def test_get_low_stock_products(client):
    """Test that only products below their threshold are returned."""
    with client.application.app_context():
        # Create a unique product that is low on stock
        product_name = f"Low Stock Product {uuid.uuid4()}"
        execute_query(
            "INSERT INTO products (name, category, qty, price, low_stock_threshold) VALUES (?, ?, ?, ?, ?);",
            (product_name, "Test", 5, 10.0, 10), commit=True
        )
        # Create a unique product that is not low on stock
        product_name_ok = f"OK Stock Product {uuid.uuid4()}"
        execute_query(
            "INSERT INTO products (name, category, qty, price, low_stock_threshold) VALUES (?, ?, ?, ?, ?);",
            (product_name_ok, "Test", 20, 10.0, 10), commit=True
        )

        low_stock_items = get_low_stock_products()

        # Filter out other low stock items from the initial setup
        low_stock_items = [item for item in low_stock_items if item[1] == product_name]
        
        assert len(low_stock_items) == 1
        assert low_stock_items[0][1] == product_name # Check name
        assert low_stock_items[0][2] == 5 # Check qty

def test_get_sales_stats_in_range(client):
    """Test sales reporting for a specific date range."""
    with client.application.app_context():
        # Create a unique customer and product for this test
        customer_name = f"Test Customer {uuid.uuid4()}"
        product_name = f"Test Product {uuid.uuid4()}"
        execute_query(
            "INSERT INTO customers (name, phone) VALUES (?, ?);",
            (customer_name, "222-222-222"), commit=True
        )
        cid = execute_query("SELECT id FROM customers WHERE name = ?;", (customer_name,), fetchone=True)[0]
        execute_query(
            "INSERT INTO products (name, category, qty, price) VALUES (?, ?, ?, ?);",
            (product_name, "Test", 100, 10.0), commit=True
        )
        pid = execute_query("SELECT id FROM products WHERE name = ?;", (product_name,), fetchone=True)[0]

        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
        
        # Create an invoice for yesterday
        create_invoice_and_insert_sales(cid, [{"pid": pid, "qty": 1, "price": 50.0}], sale_time=yesterday)

        # Check stats for yesterday
        start_date = end_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        stats = get_sales_stats_in_range(start_date, end_date)

        assert stats["invoice_count"] == 1
        assert stats["total_revenue"] == 50.0

        # Check stats for today (should be 0)
        today_str = datetime.now().strftime("%Y-%m-%d")
        stats_today = get_sales_stats_in_range(today_str, today_str)
        assert stats_today["invoice_count"] == 0
        assert stats_today["total_revenue"] == 0

# ========================================
# NEW TESTS FOR AI ENGINE
# ========================================

def test_predict_category(client):
    """Test the AI category prediction."""
    with client.application.app_context():
        assert predict_category("1kg Premium Coffee Beans")[0] == "Beverages"
        assert predict_category("A5 Hardcover Notebook")[0] == "Stationery"
        assert predict_category("Disinfectant Cleaner Spray")[0] == "Cleaning"
        assert predict_category("Wireless USB Mouse")[0] == "Electronics"
        assert predict_category("Some Unknown Gadget")[0] == "Uncategorized"

def test_parse_date_range_from_query(client):
    """Test natural language date parsing."""
    with client.application.app_context():
        today_str = datetime.now().strftime("%Y-%m-%d")
        yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

        assert _parse_date_range_from_query("today") == (today_str, today_str)
        assert _parse_date_range_from_query("yesterday") == (yesterday_str, yesterday_str)

def test_ai_query_parser(client):
    """Test the main AI query parsing brain."""
    login(client, 'admin', 'admin123')
    with client.application.app_context():
        # Ensure there is a low-stock product
        execute_query(
            "INSERT INTO products (name, category, qty, price, low_stock_threshold) VALUES (?, ?, ?, ?, ?);",
            ("AI Low Stock Tea", "Drinks", 5, 3.99, 10), commit=True
        )
    response = client.post('/api/ai/chat', json={'query': 'show low stock'})
    assert response.status_code == 200
    json_data = response.get_json()
    assert "Reorder Alerts" in json_data['response']

    response = client.post('/api/ai/chat', json={'query': "add product 'New Test Item' stock 50 price 19.99"})
    assert response.status_code == 200
    json_data = response.get_json()
    assert "✅ Done!" in json_data['response']

    with client.application.app_context():
        new_item = execute_query("SELECT name FROM products WHERE name='New Test Item'", fetchone=True)
        assert new_item is not None
        assert new_item[0] == "New Test Item"

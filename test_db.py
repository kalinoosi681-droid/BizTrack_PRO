from biztrack import set_db_file, init_db
from biztrack_db import execute_query, get_connection


def test_db_basic_crud():
    # use in-memory DB for fast tests
    set_db_file(":memory:")
    init_db()

    # insert a product
    execute_query("INSERT INTO products (name, category, qty, price) VALUES (?, ?, ?, ?);",
                  ("Test Item", "Test", 10, 2.5), commit=True)

    row = execute_query("SELECT name, category, qty, price FROM products WHERE name = ?;", ("Test Item",), fetchone=True)
    assert row is not None
    assert row[0] == "Test Item"
    assert row[2] == 10

    # update qty
    execute_query("UPDATE products SET qty = qty - 3 WHERE name = ?;", ("Test Item",), commit=True)
    row2 = execute_query("SELECT qty FROM products WHERE name = ?;", ("Test Item",), fetchone=True)
    assert row2[0] == 7

import json
from biztrack import set_db_file, init_db, hash_password
from biztrack_db import execute_query


def create_test_admin(username: str = "admin", password: str = "pw"):
    salt_hex, key_hex = hash_password(password)
    execute_query("INSERT INTO Admins (username, salt, passhash) VALUES (?, ?, ?);", (username, salt_hex, key_hex), commit=True)


def test_login_and_top_sellers_route(tmp_path):
    # in-memory DB
    set_db_file(":memory:")
    init_db()
    # create admin
    create_test_admin("tester", "secretpw")

    # import app factory lazily
    from biztrack import create_flask_app

    app = create_flask_app()
    client = app.test_client()

    # GET login page
    rv = client.get("/login")
    assert rv.status_code == 200

    # POST login
    rv2 = client.post("/login", data={"username": "tester", "password": "secretpw"}, follow_redirects=True)
    assert rv2.status_code in (200, 302)

    # After login, access top sellers API (should return JSON list)
    rv3 = client.get("/api/top_sellers")
    assert rv3.status_code == 200
    data = json.loads(rv3.get_data(as_text=True))
    assert isinstance(data, list)

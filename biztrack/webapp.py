# webapp.py
from flask import Flask, jsonify
from biztrack.biztrack_db import execute_query

def create_flask_app():
    app = Flask(__name__)

    @app.route("/")
    def home():
        return "✅ BizTrack PRO Web Server is running!"

    @app.route("/products")
    def list_products():
        rows = execute_query("SELECT id, name, category, qty, price FROM products;", fetch=True)
        products = [
            {"id": r[0], "name": r[1], "category": r[2], "qty": r[3], "price": r[4]}
            for r in rows or []
        ]
        return jsonify(products)

    @app.route("/customers")
    def list_customers():
        rows = execute_query("SELECT id, name, phone, email FROM customers;", fetch=True)
        customers = [
            {"id": r[0], "name": r[1], "phone": r[2], "email": r[3]}
            for r in rows or []
        ]
        return jsonify(customers)

    @app.route("/invoices")
    def list_invoices():
        rows = execute_query("SELECT id, invoice_number, customer_id, total, date FROM invoices;", fetch=True)
        invoices = [
            {"id": r[0], "invoice_number": r[1], "customer_id": r[2], "total": r[3], "date": r[4]}
            for r in rows or []
        ]
        return jsonify(invoices)

    return app

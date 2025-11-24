# biztrack/routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from biztrack.biztrack_db import execute_query, insert_invoice_and_sales
from functools import wraps

main_bp = Blueprint("main", __name__, template_folder="templates")

# ---------------- Login Required ---------------- #
def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.login"))
        return func(*args, **kwargs)
    return wrapper

# ---------------- Dashboard ---------------- #
@main_bp.route("/")
@login_required
def dashboard():
    products = execute_query("SELECT name, qty FROM products ORDER BY qty ASC LIMIT 5;", fetch=True)
    invoices = execute_query("SELECT invoice_number, total FROM invoices ORDER BY date DESC LIMIT 5;", fetch=True)
    return render_template("index.html", products=products, invoices=invoices)

# ---------------- Products ---------------- #
@main_bp.route("/products", methods=["GET", "POST"])
@login_required
def products():
    if request.method == "POST":
        name = request.form.get("name")
        category = request.form.get("category")
        qty = int(request.form.get("qty", 0))
        price = float(request.form.get("price", 0))
        execute_query(
            "INSERT INTO products(name, category, qty, price) VALUES (?, ?, ?, ?);",
            (name, category, qty, price),
            commit=True
        )
        flash(f"Product '{name}' added!", "success")
        return redirect(url_for("main.products"))

    rows = execute_query("SELECT id, name, category, qty, price FROM products;", fetch=True)
    return render_template("products.html", products=rows)

@main_bp.route("/products/delete/<int:pid>")
@login_required
def delete_product(pid):
    execute_query("DELETE FROM products WHERE id=?;", (pid,), commit=True)
    flash("Product deleted!", "info")
    return redirect(url_for("main.products"))

# ---------------- Customers ---------------- #
@main_bp.route("/customers", methods=["GET", "POST"])
@login_required
def customers():
    if request.method == "POST":
        name = request.form.get("name")
        phone = request.form.get("phone")
        email = request.form.get("email")
        execute_query(
            "INSERT INTO customers(name, phone, email) VALUES (?, ?, ?);",
            (name, phone, email),
            commit=True
        )
        flash(f"Customer '{name}' added!", "success")
        return redirect(url_for("main.customers"))

    rows = execute_query("SELECT id, name, phone, email FROM customers;", fetch=True)
    return render_template("customers.html", customers=rows)

# ---------------- Invoices ---------------- #
@main_bp.route("/invoices", methods=["GET", "POST"])
@login_required
def invoices():
    customers = execute_query("SELECT id, name FROM customers;", fetch=True)
    products = execute_query("SELECT id, name, price FROM products WHERE qty>0;", fetch=True)

    if request.method == "POST":
        customer_id = int(request.form.get("customer_id"))
        items = []
        for pid, qty, price in zip(
            request.form.getlist("product_id"),
            request.form.getlist("qty"),
            request.form.getlist("price")
        ):
            items.append({"pid": int(pid), "qty": int(qty), "price": float(price)})
        invoice_id = insert_invoice_and_sales(customer_id, items)
        if invoice_id:
            flash(f"Invoice #{invoice_id} created!", "success")
        else:
            flash("Failed to create invoice", "danger")
        return redirect(url_for("main.invoices"))

    invoices = execute_query(
        "SELECT i.invoice_number, c.name, i.total, i.date "
        "FROM invoices i LEFT JOIN customers c ON i.customer_id=c.id "
        "ORDER BY i.date DESC;", fetch=True
    )
    return render_template("invoices.html", invoices=invoices, customers=customers, products=products)

# ---------------- Top Sellers ---------------- #
@main_bp.route("/top-sellers")
@login_required
def top_sellers():
    rows = execute_query(
        "SELECT p.name, SUM(s.qty) as sold_qty "
        "FROM sales s JOIN products p ON s.product_id=p.id "
        "GROUP BY s.product_id ORDER BY sold_qty DESC LIMIT 10;", fetch=True
    )
    return render_template("top_sellers.html", top_sellers=rows)

# ---------------- Utilities ---------------- #
@main_bp.route("/utils", methods=["GET", "POST"])
@login_required
def utils():
    if request.method == "POST":
        action = request.form.get("action")
        if action == "dedupe":
            from biztrack.biztrack_db import remove_duplicates
            remove_duplicates()
            flash("Duplicates removed successfully!", "success")
        elif action == "backup":
            from biztrack.biztrack_db import backup_db
            path = backup_db()
            if path:
                flash(f"Backup created: {path}", "success")
            else:
                flash("Backup failed.", "danger")
    return render_template("utils.html")

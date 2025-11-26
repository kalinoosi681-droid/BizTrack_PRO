from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from .auth import login_required
from biztrack.forms import  (
    CustomerAddForm, CustomerDeleteForm,
    ProductAddForm, ProductDeleteForm,
    InvoiceAddForm, InvoiceDeleteForm
)
from .biztrack_db import get_top_sellers
from .biztrack_db import (
    init_db, seed_default_data,
    get_products, get_customers, get_invoices, get_top_sellers, get_utilities,
    add_product, update_product, delete_product,
    add_customer, update_customer, delete_customer,
    record_sale, delete_sale, get_sale_details,
    execute_command
)


# Blueprint
main = Blueprint("main", __name__)

# Initialize DB and seed defaults
init_db()
seed_default_data()

# -----------------------
# Dashboard
# -----------------------
@main.route("/")
@login_required
def dashboard():
    products = get_products()
    invoices = get_invoices()
    customers = get_customers()

    # KPI counts
    total_sales = 8200  # placeholder, replace with aggregation query
    customer_count = len(customers)
    product_count = len(products)
    invoice_count = len(invoices)

    return render_template(
        "index.html",
        products=products,
        invoices=invoices,
        customers=customers,
        total_sales=total_sales,
        customer_count=customer_count,
        product_count=product_count,
        invoice_count=invoice_count
    )

# -----------------------
# Dashboard API Endpoints
# -----------------------
@main.route("/api/dashboard/sales")
@login_required
def api_dashboard_sales():
    months = ["Jan", "Feb", "Mar", "Apr", "May"]
    sales = [1200, 1500, 1800, 1700, 2000]
    return jsonify({"months": months, "sales": sales})

@main.route("/api/dashboard/categories")
@login_required
def api_dashboard_categories():
    categories = ["Electronics", "Clothing", "Books", "Food"]
    counts = [40, 25, 15, 20]
    return jsonify({"categories": categories, "counts": counts})

# -----------------------
# Products
# -----------------------
@main.route("/products", methods=["GET", "POST"])
@login_required
def products():
    add_form = ProductAddForm()
    delete_form = ProductDeleteForm()

    if add_form.validate_on_submit() and getattr(add_form, "action", None) and add_form.action.data == "add":
        try:
            add_product(add_form.name.data, add_form.category.data,
                        add_form.qty.data, add_form.price.data)
            flash("Product added successfully", "success")
        except Exception as e:
            flash(f"Error: {str(e)}", "error")
        return redirect(url_for("main.products"))

    if delete_form.validate_on_submit() and getattr(delete_form, "action", None) and delete_form.action.data == "delete":
        try:
            delete_product(int(delete_form.id.data))
            flash("Product deleted successfully", "success")
        except Exception as e:
            flash(f"Error: {str(e)}", "error")
        return redirect(url_for("main.products"))

    products = get_products()
    return render_template("products.html", products=products,
                           add_form=add_form, delete_form=delete_form)

# -----------------------
# Customers
# -----------------------
@main.route("/customers", methods=["GET", "POST"])
@login_required
def customers():
    add_form = CustomerAddForm()
    delete_form = CustomerDeleteForm()

    if add_form.validate_on_submit() and add_form.action.data == "add":
        try:
            add_customer(add_form.name.data, add_form.phone.data, add_form.email.data)
            flash("Customer added successfully", "success")
        except Exception as e:
            flash(f"Error: {str(e)}", "error")
        return redirect(url_for("main.customers"))

    if delete_form.validate_on_submit() and delete_form.action.data == "delete":
        try:
            delete_customer(int(delete_form.id.data))
            flash("Customer deleted successfully", "success")
        except Exception as e:
            flash(f"Error: {str(e)}", "error")
        return redirect(url_for("main.customers"))

    customers = get_customers()
    return render_template("customers.html", customers=customers,
                           add_form=add_form, delete_form=delete_form)

# -----------------------
# Invoices
# -----------------------
@main.route("/invoices", methods=["GET", "POST"])
@login_required
def invoices():
    add_form = InvoiceAddForm()
    delete_form = InvoiceDeleteForm()

    if add_form.validate_on_submit():
        try:
            invoice_id = record_sale(add_form.customer_id.data, add_form.items.data)
            flash(f"Invoice {invoice_id} created successfully", "success")
        except Exception as e:
            flash(f"Error: {str(e)}", "error")
        return redirect(url_for("main.invoices"))

    if delete_form.validate_on_submit() and delete_form.action.data == "delete":
        try:
            delete_sale(int(delete_form.id.data))
            flash("Invoice deleted successfully", "success")
        except Exception as e:
            flash(f"Error: {str(e)}", "error")
        return redirect(url_for("main.invoices"))

    invoices = get_invoices()
    return render_template("invoices.html", invoices=invoices,
                           add_form=add_form, delete_form=delete_form)

# -----------------------
# Top Sellers
# -----------------------
@main.route("/top-sellers")
@login_required
def top_sellers():
    top = get_top_sellers()
    return render_template("top-sellers.html", top_sellers=top)

# -----------------------
# Utilities (CLI)
# -----------------------
@main.route("/utils")
@login_required
def utils():
    utilities = get_utilities()
    return render_template("utils.html", utilities=utilities)

@main.route("/run_command", methods=["POST"])
@login_required
def run_command():
    data = request.get_json()
    cmd = data.get("command", "")
    output = execute_command(cmd)
    return jsonify({"output": output})

# -----------------------
# Routes Reference
# -----------------------
@main.route("/routes")
@login_required
def routes_page():
    routes = [
        {"name": "dashboard", "description": "Main dashboard overview"},
        {"name": "customers", "description": "Manage customers"},
        {"name": "products", "description": "Manage products"},
        {"name": "invoices", "description": "View invoices"},
        {"name": "utils", "description": "Run CLI commands"},
        {"name": "top-sellers", "description": "View top selling products"},
    ]
    return render_template("routes.html", routes=routes)
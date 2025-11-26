from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from .auth import login_required
from biztrack.forms import  (
    CustomerAddForm, CustomerDeleteForm, CustomerUpdateForm,
    ProductAddForm, ProductDeleteForm, ProductUpdateForm,
    InvoiceAddForm, InvoiceDeleteForm, InvoiceUpdateForm,
    PayrollAddForm, PayrollDeleteForm
)
from .biztrack_db import (get_top_sellers, execute_query, create_invoice_and_insert_sales)
from .biztrack_db import (
    init_db, seed_default_data,
    get_products, get_customers, get_invoices, get_low_stock_products,
    get_top_sellers, get_utilities,
    export_table_to_csv, import_table_from_csv,
    add_product, update_product, delete_product,
    add_customer, update_customer, delete_customer,
    get_payrolls, add_payroll, update_payroll, delete_payroll,
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
    payroll_count = len(get_payrolls()) # New line to get payroll count
    return jsonify({"categories": categories, "counts": counts})

# -----------------------
# Products
# -----------------------
@main.route("/products", methods=["GET", "POST"])
@login_required
def products():
    add_form = ProductAddForm()
    delete_form = ProductDeleteForm()
    update_form = ProductUpdateForm()

    # Handle Add
    if add_form.validate_on_submit() and add_form.action.data == "add":
        try:
            execute_query(
                "INSERT INTO products (name, category, qty, price) VALUES (?, ?, ?, ?);",
                (add_form.name.data, add_form.category.data, add_form.qty.data, add_form.price.data),
                commit=True
            )
            flash("Product added successfully", "success")
        except Exception as e:
            flash(f"Error adding product: {e}", "danger")
        return redirect(url_for("main.products"))

    # Handle Delete
    if delete_form.validate_on_submit() and delete_form.action.data == "delete":
        try:
            execute_query("DELETE FROM products WHERE id=?;", (delete_form.id.data,), commit=True)
            flash("Product deleted successfully", "success")
        except Exception as e:
            flash(f"Error deleting product: {e}", "danger")
        return redirect(url_for("main.products"))

    # Handle Update
    if update_form.validate_on_submit() and update_form.action.data == "update":
        try:
            execute_query(
                "UPDATE products SET name=?, category=?, qty=?, price=? WHERE id=?;",
                (update_form.name.data, update_form.category.data, update_form.qty.data,
                 update_form.price.data, update_form.id.data),
                commit=True
            )
            flash("Product updated successfully", "success")
        except Exception as e:
            flash(f"Error updating product: {e}", "danger")
        return redirect(url_for("main.products"))

    products = get_products()
    return render_template("products.html", products=products,
                           add_form=add_form, delete_form=delete_form, update_form=update_form)

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
    
@main.route("/customers", methods=["GET", "POST"])
@login_required
def customers():
    add_form = CustomerAddForm()
    delete_form = CustomerDeleteForm()
    update_form = CustomerUpdateForm()

    if update_form.validate_on_submit() and update_form.action.data == "update":
        execute_query(
            "UPDATE customers SET name=?, phone=?, email=? WHERE id=?;",
            (update_form.name.data, update_form.phone.data, update_form.email.data, update_form.id.data),
            commit=True
        )
        flash("Customer updated successfully", "success")
        return redirect(url_for("main.customers"))

    customers = get_customers()
    return render_template("customers.html", customers=customers,
                           add_form=add_form, delete_form=delete_form, update_form=update_form)

# -----------------------
# Payrolls
#-----------------------
@main.route("/payrolls", methods=["GET", "POST"])
@login_required
def payrolls():
    # You’ll create PayrollAddForm and PayrollDeleteForm in forms.py
    add_form = PayrollAddForm()
    delete_form = PayrollDeleteForm()

    if add_form.validate_on_submit() and add_form.action.data == "add":
        try:
            add_payroll(add_form.employee_name.data, add_form.salary.data, add_form.date.data)
            flash("Payroll record added successfully", "success")
        except Exception as e:
            flash(f"Error: {str(e)}", "error")
        return redirect(url_for("main.payrolls"))

    if delete_form.validate_on_submit() and delete_form.action.data == "delete":
        try:
            delete_payroll(int(delete_form.id.data))
            flash("Payroll record deleted successfully", "success")
        except Exception as e:
            flash(f"Error: {str(e)}", "error")
        return redirect(url_for("main.payrolls"))

    payrolls = get_payrolls()
    return render_template("payrolls.html", payrolls=payrolls, add_form=add_form, delete_form=delete_form)

# -----------------------
# Invoices
# -----------------------
@main.route("/invoices", methods=["GET", "POST"])
@login_required
def invoices():
    add_form = InvoiceAddForm()
    delete_form = InvoiceDeleteForm()
    update_form = InvoiceUpdateForm()

    # Handle Add
    if add_form.validate_on_submit() and add_form.action.data == "add":
        try:
            items = []
            for item_form in add_form.items.entries:
                items.append({
                    "pid": item_form.form.pid.data,
                    "qty": item_form.form.qty.data,
                    "price": item_form.form.price.data
                })
            invoice_id = create_invoice_and_insert_sales(add_form.customer_id.data, items)
            if invoice_id:
                flash("Invoice created successfully", "success")
            else:
                flash("Failed to create invoice", "danger")
        except Exception as e:
            flash(f"Error creating invoice: {e}", "danger")
        return redirect(url_for("main.invoices"))

    # Handle Delete
    if delete_form.validate_on_submit() and delete_form.action.data == "delete":
        try:
            execute_query("DELETE FROM invoices WHERE id=?;", (delete_form.id.data,), commit=True)
            flash("Invoice deleted successfully", "success")
        except Exception as e:
            flash(f"Error deleting invoice: {e}", "danger")
        return redirect(url_for("main.invoices"))

    # Handle Update
    if update_form.validate_on_submit() and update_form.action.data == "update":
        try:
            execute_query(
                "UPDATE invoices SET customer_id=?, total=?, date=? WHERE id=?;",
                (update_form.customer_id.data, update_form.total.data,
                 update_form.date.data, update_form.id.data),
                commit=True
            )
            flash("Invoice updated successfully", "success")
        except Exception as e:
            flash(f"Error updating invoice: {e}", "danger")
        return redirect(url_for("main.invoices"))

    invoices = get_invoices()
    return render_template("invoices.html", invoices=invoices,
                           add_form=add_form, delete_form=delete_form, update_form=update_form)
# -----------------------
# Alerts

@main.route("/alerts/low-stock")
@login_required
def low_stock_alerts():
    low_stock = get_low_stock_products()
    return render_template("alerts.html", low_stock=low_stock)

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

@main.route("/export/<table>")
@login_required
def export_table(table):
    filepath = f"{table}.csv"
    success = export_table_to_csv(table, filepath)
    if success:
        flash(f"{table} exported to {filepath}", "success")
    else:
        flash(f"Failed to export {table}", "error")
    return redirect(url_for("main.utils"))

@main.route("/import/<table>", methods=["POST"])
@login_required
def import_table(table):
    file = request.files.get("file")
    if not file:
        flash("No file uploaded", "error")
        return redirect(url_for("main.utils"))
    filepath = f"uploads/{file.filename}"
    file.save(filepath)
    success = import_table_from_csv(table, filepath)
    if success:
        flash(f"{table} imported successfully", "success")
    else:
        flash(f"Failed to import {table}", "error")
    return redirect(url_for("main.utils"))

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
        {"name": "payrolls", "description": "Manage payroll records"},
        {"name": "alerts/low-stock", "description": "View low-stock alerts"},
        {"name": "utils", "description": "Run CLI commands"},
        {"name": "top-sellers", "description": "View top selling products"},
    ]
    return render_template("routes.html", routes=routes)
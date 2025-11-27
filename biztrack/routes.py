
# ========================================
# FIX 1: routes.py - Fix duplicate customers route & missing session
# ========================================

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session, send_file
from .auth import login_required
from biztrack.forms import (
    CustomerAddForm, CustomerDeleteForm, CustomerUpdateForm,
    ProductAddForm, ProductDeleteForm, ProductUpdateForm,
    InvoiceAddForm, InvoiceDeleteForm, InvoiceUpdateForm,
    PayrollAddForm, PayrollDeleteForm, PayrollUpdateForm
)
from .biztrack_db import (
    get_top_sellers, execute_query, create_invoice_and_insert_sales,
    init_db, seed_default_data,
    get_products, get_customers, get_invoices, get_low_stock_products,
    get_utilities, get_payrolls,
    export_table_to_csv, import_table_from_csv,
    add_product, update_product, delete_product,
    add_customer, update_customer, delete_customer,
    add_payroll, update_payroll, delete_payroll,
    record_sale, delete_sale, get_sale_details,
    execute_command
)
import os
from datetime import datetime

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
    payrolls = get_payrolls()
    low_stock = get_low_stock_products()

    # KPI counts - calculate real total sales
    total_sales_result = execute_query("SELECT SUM(total) FROM invoices;", fetchone=True)
    total_sales = round(total_sales_result[0], 2) if total_sales_result and total_sales_result[0] else 0
    
    customer_count = len(customers)
    product_count = len(products)
    invoice_count = len(invoices)
    payroll_count = len(payrolls)

    return render_template(
        "index.html",
        products=products,
        invoices=invoices,
        customers=customers,
        low_stock=low_stock,
        total_sales=total_sales,
        customer_count=customer_count,
        product_count=product_count,
        invoice_count=invoice_count,
        payroll_count=payroll_count
    )

# -----------------------
# Dashboard API Endpoints
# -----------------------
@main.route("/api/dashboard/sales")
@login_required
def api_dashboard_sales():
    # Get actual sales data by month
    query = """
        SELECT strftime('%m', date) as month, SUM(total) as total
        FROM invoices
        WHERE date >= date('now', '-6 months')
        GROUP BY strftime('%m', date)
        ORDER BY date;
    """
    rows = execute_query(query, fetch=True)
    
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]
    sales = [0, 0, 0, 0, 0, 0]
    
    for row in rows:
        month_num = int(row[0]) - 1
        if 0 <= month_num < 6:
            sales[month_num] = round(row[1], 2)
    
    return jsonify({"months": months, "sales": sales})

@main.route("/api/dashboard/categories")
@login_required
def api_dashboard_categories():
    # Get actual category counts
    query = """
        SELECT COALESCE(category, 'Uncategorized') as cat, COUNT(*) as cnt
        FROM products
        GROUP BY category
        LIMIT 5;
    """
    rows = execute_query(query, fetch=True)
    
    categories = [row[0] for row in rows] if rows else ["No Data"]
    counts = [row[1] for row in rows] if rows else [0]
    
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

    if request.method == "POST":
        action = request.form.get("action")
        
        # Handle Add
        if action == "add" and add_form.validate_on_submit():
            try:
                add_product(
                    add_form.name.data,
                    add_form.category.data or "",
                    add_form.qty.data,
                    add_form.price.data
                )
                flash("Product added successfully", "success")
            except Exception as e:
                flash(f"Error adding product: {e}", "danger")
            return redirect(url_for("main.products"))

        # Handle Delete
        elif action == "delete" and delete_form.validate_on_submit():
            try:
                delete_product(delete_form.id.data)
                flash("Product deleted successfully", "success")
            except Exception as e:
                flash(f"Error deleting product: {e}", "danger")
            return redirect(url_for("main.products"))

        # Handle Update
        elif action == "update" and update_form.validate_on_submit():
            try:
                update_product(
                    update_form.id.data,
                    update_form.name.data,
                    update_form.category.data or "",
                    update_form.qty.data,
                    update_form.price.data
                )
                flash("Product updated successfully", "success")
            except Exception as e:
                flash(f"Error updating product: {e}", "danger")
            return redirect(url_for("main.products"))

    products = get_products()
    return render_template("products.html", products=products,
                           add_form=add_form, delete_form=delete_form, update_form=update_form)

# -----------------------
# Customers (FIXED - removed duplicate)
# -----------------------
@main.route("/customers", methods=["GET", "POST"])
@login_required
def customers():
    add_form = CustomerAddForm()
    delete_form = CustomerDeleteForm()
    update_form = CustomerUpdateForm()

    if request.method == "POST":
        action = request.form.get("action")
        
        # Handle Add
        if action == "add" and add_form.validate_on_submit():
            try:
                add_customer(
                    add_form.name.data,
                    add_form.phone.data or "",
                    add_form.email.data or ""
                )
                flash("Customer added successfully", "success")
            except Exception as e:
                flash(f"Error: {str(e)}", "danger")
            return redirect(url_for("main.customers"))
        
        # Handle Delete
        elif action == "delete" and delete_form.validate_on_submit():
            try:
                delete_customer(int(delete_form.id.data))
                flash("Customer deleted successfully", "success")
            except Exception as e:
                flash(f"Error: {str(e)}", "danger")
            return redirect(url_for("main.customers"))
        
        # Handle Update
        elif action == "update" and update_form.validate_on_submit():
            try:
                update_customer(
                    int(update_form.id.data),
                    update_form.name.data,
                    update_form.phone.data or "",
                    update_form.email.data or ""
                )
                flash("Customer updated successfully", "success")
            except Exception as e:
                flash(f"Error: {str(e)}", "danger")
            return redirect(url_for("main.customers"))

    customers = get_customers()
    return render_template("customers.html", customers=customers,
                           add_form=add_form, delete_form=delete_form, update_form=update_form)

# -----------------------
# Payrolls
# -----------------------
@main.route("/payrolls", methods=["GET", "POST"])
@login_required
def payrolls():
    add_form = PayrollAddForm()
    delete_form = PayrollDeleteForm()
    update_form = PayrollUpdateForm()  # <-- ADD THIS

    if request.method == "POST":
        action = request.form.get("action")
        
        # Handle Add
        if action == "add" and add_form.validate_on_submit():
            try:
                date_str = add_form.date.data.strftime("%Y-%m-%d") if add_form.date.data else datetime.now().strftime("%Y-%m-%d")
                add_payroll(
                    add_form.employee_name.data,
                    add_form.salary.data,
                    date_str
                )
                flash("Payroll record added successfully", "success")
            except Exception as e:
                flash(f"Error: {str(e)}", "danger")
            return redirect(url_for("main.payrolls"))

        # Handle Update
        elif action == "update" and update_form.validate_on_submit():
            try:
                date_str = update_form.date.data.strftime("%Y-%m-%d") if update_form.date.data else datetime.now().strftime("%Y-%m-%d")
                # Update in database
                execute_query(
                    "UPDATE payrolls SET employee_name=?, salary=?, date=? WHERE id=?;",
                    (update_form.employee_name.data, update_form.salary.data, date_str, update_form.id.data),
                    commit=True
                )
                flash("Payroll record updated successfully", "success")
            except Exception as e:
                flash(f"Error: {str(e)}", "danger")
            return redirect(url_for("main.payrolls"))

        # Handle Delete
        elif action == "delete" and delete_form.validate_on_submit():
            try:
                delete_payroll(int(delete_form.id.data))
                flash("Payroll record deleted successfully", "success")
            except Exception as e:
                flash(f"Error: {str(e)}", "danger")
            return redirect(url_for("main.payrolls"))

    payrolls = get_payrolls()
    return render_template("payrolls.html", payrolls=payrolls, 
                           add_form=add_form, delete_form=delete_form, update_form=update_form)
# -----------------------
# Invoices
# -----------------------
@main.route("/invoices", methods=["GET", "POST"])
@login_required
def invoices():
    add_form = InvoiceAddForm()
    delete_form = InvoiceDeleteForm()
    update_form = InvoiceUpdateForm()

    if request.method == "POST":
        action = request.form.get("action")
        
        # Handle Add
        if action == "add" and add_form.validate_on_submit():
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
                    flash(f"Invoice #{invoice_id} created successfully", "success")
                else:
                    flash("Failed to create invoice. Check stock levels.", "danger")
            except Exception as e:
                flash(f"Error creating invoice: {e}", "danger")
            return redirect(url_for("main.invoices"))

        # Handle Update
        elif action == "update" and update_form.validate_on_submit():
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

        # Handle Delete
        elif action == "delete" and delete_form.validate_on_submit():
            try:
                execute_query("DELETE FROM invoices WHERE id=?;", (delete_form.id.data,), commit=True)
                flash("Invoice deleted successfully", "success")
            except Exception as e:
                flash(f"Error deleting invoice: {e}", "danger")
            return redirect(url_for("main.invoices"))

    invoices = get_invoices()
    return render_template("invoices.html", invoices=invoices,
                           add_form=add_form, delete_form=delete_form, update_form=update_form)

# -----------------------
# Low Stock Alerts
# -----------------------
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
# Utilities & CSV Import/Export
# -----------------------
@main.route("/utils")
@login_required
def utils():
    utilities = ["backup", "dedupe", "stats", "health"]
    return render_template("utils.html", utilities=utilities)

@main.route("/export/<table>")
@login_required
def export_table(table):
    """Export table to CSV and send as download"""
    # Validate table name to prevent SQL injection
    allowed_tables = ["products", "customers", "invoices", "sales", "payrolls"]
    if table not in allowed_tables:
        flash(f"Invalid table name: {table}", "danger")
        return redirect(url_for("main.utils"))
    
    try:
        # Create exports directory if it doesn't exist
        os.makedirs("exports", exist_ok=True)
        
        filepath = f"exports/{table}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        success = export_table_to_csv(table, filepath)
        
        if success:
            return send_file(filepath, as_attachment=True, download_name=f"{table}.csv")
        else:
            flash(f"Failed to export {table}", "danger")
            return redirect(url_for("main.utils"))
    except Exception as e:
        flash(f"Export error: {e}", "danger")
        return redirect(url_for("main.utils"))

@main.route("/import/<table>", methods=["POST"])
@login_required
def import_table(table):
    """Import CSV data into table"""
    # Validate table name
    allowed_tables = ["products", "customers", "invoices", "sales", "payrolls"]
    if table not in allowed_tables:
        flash(f"Invalid table name: {table}", "danger")
        return redirect(url_for("main.utils"))
    
    file = request.files.get("file")
    if not file:
        flash("No file uploaded", "danger")
        return redirect(url_for("main.utils"))
    
    if not file.filename.endswith('.csv'):
        flash("Please upload a CSV file", "danger")
        return redirect(url_for("main.utils"))
    
    try:
        # Create uploads directory if it doesn't exist
        os.makedirs("uploads", exist_ok=True)
        
        filepath = f"uploads/{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
        file.save(filepath)
        
        success = import_table_from_csv(table, filepath)
        
        if success:
            flash(f"{table} imported successfully", "success")
        else:
            flash(f"Failed to import {table}", "danger")
    except Exception as e:
        flash(f"Import error: {e}", "danger")
    
    return redirect(url_for("main.utils"))

@main.route("/run_command", methods=["POST"])
@login_required
def run_command():
    """Execute CLI command via web interface"""
    data = request.get_json()
    cmd = data.get("command", "").strip()
    
    if not cmd:
        return jsonify({"output": "Error: No command provided"})
    
    # Get user_id from session for admin verification
    user_id = session.get("user_id")
    
    # Execute the command
    result = execute_command(cmd, admin_user_id=user_id)
    
    if result["success"]:
        return jsonify({"output": result["output"]})
    else:
        return jsonify({"output": f"Error: {result['error']}"})

# -----------------------
# Routes Reference
# -----------------------
@main.route("/routes")
@login_required
def routes_page():
    routes = [
        {"name": "backup", "description": "Create database backup"},
        {"name": "dedupe", "description": "Remove duplicate records"},
        {"name": "stats", "description": "Show database statistics"},
        {"name": "health", "description": "Check database health"},
    ]
    return render_template("routes.html", routes=routes)
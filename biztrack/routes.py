from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from .biztrack_db import (
    init_db, seed_default_data,
    get_products, get_customers, get_invoices, get_top_sellers, get_utilities,
    add_product, update_product, delete_product,
    add_customer, update_customer, delete_customer,
    record_sale, delete_sale, get_sale_details,
    execute_command
)
from .auth import login_required

# Blueprint for main routes
main = Blueprint("main", __name__)
cli = Blueprint("cli", __name__)

# Initialize DB and seed default data
init_db()
seed_default_data()

# -----------------------
# Main pages
# -----------------------

@main.route("/")
@login_required
def dashboard():
    products = get_products()
    invoices = get_invoices()
    return render_template("index.html", products=products, invoices=invoices)

# ========================================
# Add input validation function
def validate_product_data(name, category, qty, price):
    """Validate product input data"""
    errors = []
    
    if not name or len(name.strip()) < 2:
        errors.append("Product name must be at least 2 characters")
    
    if len(name) > 200:
        errors.append("Product name too long (max 200 characters)")
    
    if category and len(category) > 100:
        errors.append("Category too long (max 100 characters)")
    
    try:
        qty = int(qty)
        if qty < 0:
            errors.append("Quantity cannot be negative")
    except (ValueError, TypeError):
        errors.append("Quantity must be a valid number")
    
    try:
        price = float(price)
        if price < 0:
            errors.append("Price cannot be negative")
        if price > 999999.99:
            errors.append("Price too large")
    except (ValueError, TypeError):
        errors.append("Price must be a valid number")
    
    return errors
# ========================================


# Update products route
@main.route("/products", methods=["GET", "POST"])
@login_required
def products():
    if request.method == "POST":
        action = request.form.get("action")
        pid = request.form.get("id")
        name = request.form.get("name", "").strip()
        category = request.form.get("category", "").strip()
        qty = request.form.get("qty")
        price = request.form.get("price")
        
        # Validate input
        errors = validate_product_data(name, category, qty, price)
        if errors:
            for error in errors:
                flash(error, "error")
            return redirect(url_for("main.products"))
        
        qty = int(qty)
        price = float(price)
        
        try:
            if action == "add":
                if add_product(name, category, qty, price):
                    flash("Product added successfully", "success")
                else:
                    flash("Failed to add product", "error")
            elif action == "update" and pid:
                if update_product(int(pid), name, category, qty, price):
                    flash("Product updated successfully", "success")
                else:
                    flash("Failed to update product", "error")
            elif action == "delete" and pid:
                if delete_product(int(pid)):
                    flash("Product deleted successfully", "success")
                else:
                    flash("Failed to delete product", "error")
        except Exception as e:
            flash(f"Error: {str(e)}", "error")
            
        return redirect(url_for("main.products"))
    
    products = get_products()
    return render_template("products.html", products=products)

@main.route("/customers", methods=["GET", "POST"])
@login_required
def customers():
    if request.method == "POST":
        action = request.form.get("action")
        cid = request.form.get("id")
        name = request.form.get("name")
        phone = request.form.get("phone")
        email = request.form.get("email")

        if action == "add":
            add_customer(name, phone, email)
            flash("Customer added successfully", "success")
        elif action == "update" and cid:
            update_customer(int(cid), name, phone, email)
            flash("Customer updated successfully", "success")
        elif action == "delete" and cid:
            delete_customer(int(cid))
            flash("Customer deleted successfully", "success")
        return redirect(url_for("main.customers"))

    customers = get_customers()
    return render_template("customers.html", customers=customers)

@main.route("/invoices", methods=["GET", "POST"])
@login_required
def invoices():
    if request.method == "POST":
        customer_id = request.form.get("customer_id")
        items = request.form.getlist("items[]")  # expects JSON objects or dictionaries
        # Example: items = [{"pid":1,"qty":2,"price":5.0}]
        invoice_id = record_sale(int(customer_id), items)
        flash(f"Invoice {invoice_id} created successfully", "success")
        return redirect(url_for("main.invoices"))

    invoices = get_invoices()
    return render_template("invoices.html", invoices=invoices)

@main.route("/top_sellers")
@login_required
def top_sellers():
    top = get_top_sellers()
    return render_template("top_sellers.html", top_sellers=top)

@main.route("/utils", methods=["GET", "POST"])
@login_required
def utils():
    utilities = get_utilities()
    if request.method == "POST":
        command = request.form.get("command", "")
        output = execute_command(command)
        flash(output)
        return redirect(url_for("main.utils"))
    return render_template("utils.html", utilities=utilities)

# -----------------------
# CLI AJAX route
# -----------------------

@cli.route("/run_command", methods=["POST"])
@login_required
def run_command():
    data = request.json
    cmd = data.get("command", "")
    output = execute_command(cmd)
    return jsonify({"output": output})
# -----------------------
@cli.route("/run-command")
def run_command():
    from .biztrack_db import execute_command
    data = request.get_json()
    cmd = data.get("command", "")
    output = execute_command(cmd)
    return jsonify({"output": output})
# -----------------------
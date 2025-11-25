from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from biztrack_db import (
    init_db, seed_default_data, get_products, get_customers,
    get_invoices, get_top_sellers, get_utilities, execute_command
)
from auth import login_required

# Blueprint for main routes
main = Blueprint("main", __name__)
cli = Blueprint("cli", __name__)

# Initialize DB and seed default data on startup
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

@main.route("/products")
@login_required
def products():
    products = get_products()
    return render_template("products.html", products=products)

@main.route("/customers")
@login_required
def customers():
    customers = get_customers()
    return render_template("customers.html", customers=customers)

@main.route("/invoices")
@login_required
def invoices():
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


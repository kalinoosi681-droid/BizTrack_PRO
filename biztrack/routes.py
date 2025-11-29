# ========================================
# ENHANCED routes.py - Real-Time Intelligence
# ========================================
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session, send_file
from .auth import login_required
from biztrack.forms import (
    CustomerAddForm, CustomerDeleteForm, CustomerUpdateForm, ProductBulkUpdateForm,
    ProductAddForm, ProductDeleteForm, ProductUpdateForm, ProductThresholdUpdateForm,
    InvoiceAddForm, InvoiceDeleteForm, InvoiceUpdateForm,
    PayrollAddForm, PayrollDeleteForm, PayrollUpdateForm
)
from .extensions import limiter, csrf
from .biztrack_db import (
    get_top_sellers, execute_query, create_invoice_and_insert_sales,
    init_db, seed_default_data, compute_daily_store_metrics, compute_daily_product_metrics, _get_columns,
    get_products, get_customers, get_invoices, get_low_stock_products,
    get_customer_insights, compute_perf_percent, update_product_threshold,
    get_utilities, get_payrolls, get_stock_performance, get_product_sale_history,
    export_table_to_csv, import_table_from_csv,
    add_product, update_product, delete_product,
    add_customer, update_customer, delete_customer,
    add_payroll, update_payroll, delete_payroll,
    record_sale, delete_sale, get_sale_details,
    execute_command, get_store_avg_7d_qty, get_product_7d_qty
)
import os
from datetime import datetime
import csv
from werkzeug.utils import secure_filename

main = Blueprint("main", __name__)

# ========================================
# DASHBOARD - REAL-TIME ANALYTICS
# ========================================

@main.route("/")
@login_required
def dashboard():
    """Enhanced dashboard with real-time intelligence"""
    # Advanced Upgrade: Use a single, optimized query to fetch all KPIs at once.
    # This is much more performant than running multiple full-table queries.
    kpi_query = """
        SELECT
            (SELECT COUNT(*) FROM products) as product_count,
            (SELECT COUNT(*) FROM customers) as customer_count,
            (SELECT COUNT(*) FROM invoices) as invoice_count,
            (SELECT COUNT(*) FROM payrolls) as payroll_count,
            (SELECT COALESCE(SUM(total), 0) FROM invoices) as total_sales;
    """
    kpis = execute_query(kpi_query, fetchone=True)

    # This data is now fetched dynamically by dashboard.js, so server-side calculation is redundant.
    # today_revenue and month_revenue are removed.

    low_stock = get_low_stock_products()

    return render_template(
        "index.html",
        low_stock=low_stock,
        product_count=kpis[0] if kpis else 0,
        customer_count=kpis[1] if kpis else 0,
        invoice_count=kpis[2] if kpis else 0,
        payroll_count=kpis[3] if kpis else 0,
        total_sales=float(kpis[4]) if kpis else 0.0
    )

@main.route("/api/dashboard/realtime")
@login_required
@csrf.exempt # This is a read-only GET endpoint for polling
def api_dashboard_realtime():
    """Real-time transaction updates (like trading board)"""
    # Last 10 transactions
    recent_transactions = execute_query("""
        SELECT i.id, i.invoice_number, i.total, i.date, c.name as customer_name
        FROM invoices i
        LEFT JOIN customers c ON i.customer_id = c.id
        ORDER BY i.date DESC
        LIMIT 10;
    """, fetch=True)
    
    # Today's metrics
    today_metrics = execute_query("""
        SELECT 
            COUNT(*) as transaction_count,
            COALESCE(SUM(total), 0) as today_revenue,
            COALESCE(AVG(total), 0) as avg_transaction
        FROM invoices
        WHERE date(date) = date('now');
    """, fetchone=True)
    
    # Hourly breakdown (last 24 hours)
    hourly_sales = execute_query("""
        SELECT 
            strftime('%H:00', date) as hour,
            COUNT(*) as transactions,
            COALESCE(SUM(total), 0) as revenue
        FROM invoices
        WHERE datetime(date) >= datetime('now', '-24 hours')
        GROUP BY strftime('%H', date)
        ORDER BY hour;
    """, fetch=True) or []

    # If no sales in the last 24h, create a default structure to avoid chart errors
    if not hourly_sales:
        from datetime import datetime, timedelta
        now = datetime.now()
        hourly_sales = [
            {
                "hour": (now - timedelta(hours=i)).strftime("%H:00"),
                "transactions": 0, "revenue": 0
            } for i in range(7, -1, -1) # Default to last 8 hours
        ]
    
    return jsonify({
        "recent_transactions": [{
            "id": t[0],
            "invoice_number": t[1],
            "total": float(t[2] or 0),
            "date": t[3],
            "customer": t[4] or "Walk-in"
        } for t in (recent_transactions or [])],
        "today": {
            "transactions": today_metrics[0] if today_metrics else 0,
            "revenue": round(float(today_metrics[1] or 0), 2) if today_metrics else 0,
            "avg_transaction": round(float(today_metrics[2] or 0), 2) if today_metrics else 0
        },
        "hourly": [{
            "hour": h[0],
            "transactions": h[1],
            "revenue": round(float(h[2] or 0), 2)
        } for h in (hourly_sales or [])]
    })
# ... (keep existing dashboard API endpoints)
@main.route("/api/dashboard/sales")
@login_required
def api_dashboard_sales():
    """Monthly sales chart data"""
    query = """
        SELECT strftime('%Y-%m', date) as month, SUM(total) as total
        FROM invoices
        WHERE date >= date('now', '-6 months')
        GROUP BY strftime('%Y-%m', date)
        ORDER BY month;
    """
    rows = execute_query(query, fetch=True)
    
    from datetime import datetime, timedelta
    months_list = []
    sales_list = []
    
    current_date = datetime.now()
    for i in range(5, -1, -1):
        month_date = current_date - timedelta(days=30*i)
        month_str = month_date.strftime('%Y-%m')
        month_name = month_date.strftime('%b')
        months_list.append(month_name)
        
        sales_value = 0
        for row in (rows or []):
            if row[0] == month_str:
                sales_value = round(float(row[1]), 2)
                break
        sales_list.append(sales_value)
    
    return jsonify({"months": months_list, "sales": sales_list})

@main.route("/api/dashboard/month-revenue")
@login_required
def api_month_revenue():
    """Get current month's revenue"""
    result = execute_query("""
        SELECT COALESCE(SUM(total), 0) 
        FROM invoices 
        WHERE strftime('%Y-%m', date) = strftime('%Y-%m', 'now');
    """, fetchone=True)
    return jsonify({"revenue": float(result[0]) if result else 0.0})

@main.route("/api/dashboard/categories")
@login_required
def api_dashboard_categories():
    """Category distribution"""
    query = """
        SELECT COALESCE(category, 'Uncategorized') as cat, COUNT(*) as cnt
        FROM products
        GROUP BY category
        ORDER BY cnt DESC
        LIMIT 5;
    """
    rows = execute_query(query, fetch=True)
    
    categories = [row[0] for row in rows] if rows else ["No Data"]
    counts = [row[1] for row in rows] if rows else [0]
    
    return jsonify({"categories": categories, "counts": counts})

@main.route("/api/dashboard/daily")
@login_required
def api_dashboard_daily():
    """Daily metrics"""
    rows = execute_query("""
        SELECT date, revenue, margin_pct, invoices_count
        FROM store_metrics_daily
        WHERE date >= date('now','-30 day')
        ORDER BY date;
    """, fetch=True) or []
    
    dates = [r[0] for r in rows]
    revenue = [float(r[1]) for r in rows]
    margin = [float(r[2]) for r in rows]
    invoices_count = [int(r[3]) for r in rows]
    
    return jsonify({
        "dates": dates, 
        "revenue": revenue, 
        "margin": margin, 
        "invoices_count": invoices_count
    })

@main.route("/api/search")
@login_required
def api_search():
    """Global search across products, customers, invoices"""
    q = (request.args.get("q","")).strip().lower()
    if not q:
        return jsonify({"products":[], "customers":[], "invoices":[]})

    # Advanced Upgrade: Use FTS5 for high-performance, relevance-ranked search
    fts_query = f'"{q}"*' # Prepare query for prefix matching

    products = execute_query("""
        SELECT p.id, p.name, p.category, p.price
        FROM products_fts f JOIN products p ON f.rowid = p.id
        WHERE f.products_fts MATCH ? ORDER BY rank LIMIT 5;
    """, (fts_query,), fetch=True)

    customers = execute_query("""
        SELECT c.id, c.name, c.phone
        FROM customers_fts f JOIN customers c ON f.rowid = c.id
        WHERE f.customers_fts MATCH ? ORDER BY rank LIMIT 5;
    """, (fts_query,), fetch=True)

    # Invoice search remains by ID/number as it's specific
    invoices = execute_query("""
        SELECT i.id, i.customer_id, i.total, i.date, c.name as customer_name
        FROM invoices i
        LEFT JOIN customers c ON i.customer_id = c.id
        WHERE i.invoice_number LIKE ? OR CAST(i.id AS TEXT) = ?
        ORDER BY date DESC
        LIMIT 5;
    """, (f"%{q}%", q), fetch=True)

    return jsonify({
        "products":[{
            "id":p[0], 
            "name":p[1], 
            "category":p[2], 
            "price":float(p[3]), 
            "url":url_for("main.product_detail", pid=p[0])
        } for p in products or []],
        "customers":[{
            "id":c[0], 
            "name":c[1], 
            "phone":c[2] or "", 
            "url":url_for("main.customer_detail", cid=c[0])
        } for c in customers or []],
        "invoices":[{
            "id":i[0], 
            "customer_id":i[1], 
            "total":float(i[2] or 0),
            "date":i[3], 
            "customer_name": i[4] or "Walk-in",
            "url":url_for("main.invoice_detail", iid=i[0])
        } for i in invoices or []]
    })

# ========================================
# PRODUCT ROUTES
# ========================================

@main.route("/products", methods=["GET", "POST"])
@login_required
def products():
    """Product management with full CRUD"""
    add_form = ProductAddForm()
    delete_form = ProductDeleteForm()
    update_form = ProductUpdateForm()
    bulk_update_form = ProductBulkUpdateForm() # Instantiate the bulk form

    if request.method == "POST":
        action = request.form.get("action")
        
        if action == "add" and add_form.validate_on_submit():
            try:
                add_product(
                    add_form.name.data,
                    add_form.category.data or "",
                    add_form.qty.data,
                    add_form.price.data
                )
                flash("✅ Product added successfully", "success")
            except Exception as e:
                flash(f"❌ Error adding product: {e}", "danger")
            return redirect(url_for("main.products"))

        elif action == "delete" and delete_form.validate_on_submit():
            try:
                delete_product(delete_form.id.data)
                flash("✅ Product deleted successfully", "success")
            except Exception as e:
                flash(f"❌ Error deleting product: {e}", "danger")
            return redirect(url_for("main.products"))

        elif action == "update" and update_form.validate_on_submit():
            try:
                update_product(
                    update_form.id.data,
                    update_form.name.data,
                    update_form.category.data or "",
                    update_form.qty.data,
                    update_form.price.data
                )
                flash("✅ Product updated successfully", "success")
            except Exception as e:
                flash(f"❌ Error updating product: {e}", "danger")
            return redirect(url_for("main.products"))

    # --- Performance Optimization: Fetch all product performance data in one query ---
    products_list = execute_query("""
        WITH sales_30d AS (
            SELECT product_id, SUM(qty) as total_sold
            FROM sales
            WHERE date >= date('now', '-30 days')
            GROUP BY product_id
        )
        SELECT p.*, COALESCE(s.total_sold, 0) as sold_30d
        FROM products p
        LEFT JOIN sales_30d s ON p.id = s.product_id
        ORDER BY p.name;
    """, fetch=True)

    columns = _get_columns("products") + ['sold_30d']
    products_with_perf = [dict(zip(columns, row)) for row in products_list]

    for p in products_with_perf:
        if p['sold_30d'] > 10:
            p['perf_flag'] = "🔥 Fast"
        elif p['sold_30d'] < 3:
            p['perf_flag'] = "🐢 Slow"
        else:
            p['perf_flag'] = "Normal"

    return render_template("products.html", products=products_with_perf,
                           add_form=add_form, delete_form=delete_form, update_form=update_form,
                           bulk_update_form=bulk_update_form) # Pass form to template

@main.route("/product/<int:pid>")
@login_required
def product_detail(pid):
    """Product detail page with sales history and threshold update."""
    threshold_form = ProductThresholdUpdateForm()

    # --- Performance Optimization: Fetch product details and performance in one query ---
    query = """
        WITH store_avg AS (
            SELECT COALESCE(AVG(sq), 0.0001) as avg_7d FROM (
                SELECT SUM(qty) as sq FROM sales WHERE date >= date('now','-7 day') GROUP BY product_id
            )
        ),
        product_sales AS (
            SELECT COALESCE(SUM(qty), 0) as sold_7d FROM sales WHERE product_id = ? AND date >= date('now','-7 day')
        )
        SELECT p.id, p.name, p.category, p.qty, p.price, p.low_stock_threshold,
               (SELECT sold_7d FROM product_sales) * 100.0 / (SELECT avg_7d FROM store_avg) as perf_percent
        FROM products p
        WHERE p.id = ?;
    """
    row = execute_query(query, (pid, pid), fetchone=True)
    
    if not row:
        flash("❌ Product not found", "danger")
        return redirect(url_for("main.products"))
    
    product = {
        "id": row[0], "name": row[1], "category": row[2] or "Uncategorized",
        "qty": row[3], "price": float(row[4]), "low_stock_threshold": row[5] or 10,
        "perf_percent": row[6]
    }
    
    # Get sale history
    sale_history = get_product_sale_history(pid, days=30)
    
    return render_template(
        "product_detail.html", 
        product=product, 
        sale_history=sale_history, 
        threshold_form=threshold_form)

@main.route("/product/<int:pid>/update-threshold", methods=["POST"])
@login_required
def update_product_threshold_route(pid):
    """Handles the form submission for updating a product's low-stock threshold."""
    threshold_form = ProductThresholdUpdateForm()
    if threshold_form.validate_on_submit():
        try:
            update_product_threshold(pid, threshold_form.low_stock_threshold.data)
            flash("✅ Low-stock threshold updated successfully", "success")
        except Exception as e:
            flash(f"❌ Error updating threshold: {e}", "danger")
    return redirect(url_for("main.product_detail", pid=pid))

@main.route("/products/bulk-update", methods=["POST"])
@login_required
def bulk_update_products():
    """Handles bulk updates for selected products."""
    # This route is now the target of the bulk update form.
    form = ProductBulkUpdateForm()
    product_ids = request.form.getlist('product_ids')

    if not product_ids:
        flash("❌ No products selected for bulk action.", "warning")
        return redirect(url_for('main.products'))

    if form.validate_on_submit():
        bulk_action = form.bulk_action.data
        try:
            if bulk_action == 'set_category':
                new_category = form.new_category.data
                if new_category:
                    placeholders = ','.join('?' for _ in product_ids)
                    execute_query(f"UPDATE products SET category = ? WHERE id IN ({placeholders})", [new_category] + product_ids, commit=True)
                    flash(f"✅ Updated category for {len(product_ids)} products to '{new_category}'.", "success")

            elif bulk_action == 'adjust_price':
                percentage = form.price_percentage.data
                if percentage is not None and percentage != 0:
                    placeholders = ','.join('?' for _ in product_ids)
                    execute_query(f"UPDATE products SET price = ROUND(price * (1 + ? / 100.0), 2) WHERE id IN ({placeholders})", [percentage] + product_ids, commit=True)
                    flash(f"✅ Adjusted price for {len(product_ids)} products by {percentage}%.", "success")

        except Exception as e:
            flash(f"❌ Bulk update failed: {e}", "danger")
    else:
        # If form validation fails, flash the errors
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"❌ Error in '{getattr(form, field).label.text}': {error}", "danger")

    return redirect(url_for('main.products'))


@main.route("/api/search/products")
@login_required
def api_search_products():
    """Search products with performance data"""
    q = (request.args.get("q","")).strip().lower()
    if not q:
        return jsonify([])

    # Optimized query to fetch products and their 30-day sales in one go
    rows = execute_query("""
        WITH sales_30d AS (
            SELECT product_id, SUM(qty) as total_sold
            FROM sales WHERE date >= date('now', '-30 days')
            GROUP BY product_id
        )
        SELECT p.id, p.name, p.category, p.price, p.qty, COALESCE(s.total_sold, 0)
        FROM products p
        LEFT JOIN sales_30d s ON p.id = s.product_id
        WHERE LOWER(p.name) LIKE ? OR CAST(p.id AS TEXT) LIKE ? OR LOWER(p.category) LIKE ?
        ORDER BY p.name ASC LIMIT 15;
    """, (f"%{q}%", f"%{q}%", f"%{q}%"), fetch=True)

    out = []
    for id_, name, category, price, qty, sold_30d in rows or []:
        if sold_30d > 10:
            flag = "fast"
        elif sold_30d < 3:
            flag = "slow"
        else:
            flag = "normal"
        out.append({
            "id": id_, 
            "name": name, 
            "category": category or "Uncategorized",
            "price": float(price), 
            "qty": int(qty),
            "flag": flag,
            "display": f"#{id_} • {name} ({category}) • ${price:.2f}",
            "url": url_for("main.product_detail", pid=id_)
        })
    return jsonify(out)

@main.route("/api/product/<int:pid>")
@login_required
def api_get_product(pid):
    """Get single product details by ID"""
    row = execute_query(
        "SELECT id, name, category, price, qty FROM products WHERE id = ?;",
        (pid,),
        fetchone=True
    )
    
    if not row:
        return jsonify({"error": "Product not found"}), 404
    
    return jsonify({
        "id": row[0],
        "name": row[1],
        "category": row[2],
        "price": float(row[3]),
        "qty": row[4]
    })
# ========================================
# CUSTOMER ROUTES
# ========================================

@main.route("/customers", methods=["GET", "POST"])
@login_required
def customers():
    """Customer management with full CRUD"""
    add_form = CustomerAddForm()
    delete_form = CustomerDeleteForm()
    update_form = CustomerUpdateForm()

    if request.method == "POST":
        action = request.form.get("action")
        
        if action == "add" and add_form.validate_on_submit():
            try:
                add_customer(
                    add_form.name.data,
                    add_form.phone.data or "",
                    add_form.email.data or ""
                )
                flash("✅ Customer added successfully", "success")
            except Exception as e:
                flash(f"❌ Error: {str(e)}", "danger")
            return redirect(url_for("main.customers"))
        
        elif action == "delete" and delete_form.validate_on_submit():
            try:
                delete_customer(int(delete_form.id.data))
                flash("✅ Customer deleted successfully", "success")
            except Exception as e:
                flash(f"❌ Error: {str(e)}", "danger")
            return redirect(url_for("main.customers"))
        
        elif action == "update" and update_form.validate_on_submit():
            try:
                update_customer(
                    int(update_form.id.data),
                    update_form.name.data,
                    update_form.phone.data or "",
                    update_form.email.data or ""
                )
                flash("✅ Customer updated successfully", "success")
            except Exception as e:
                flash(f"❌ Error: {str(e)}", "danger")
            return redirect(url_for("main.customers"))

    # Performance Optimization: Use the optimized query to fetch customers with insights
    customers_list = get_customers(with_insights=True)
    return render_template("customers.html", customers=customers_list,
                           add_form=add_form, delete_form=delete_form, update_form=update_form)

@main.route("/customer/<int:cid>")
@login_required
def customer_detail(cid):
    """Customer detail page with purchase history"""
    row = execute_query(
        "SELECT id, name, phone, email FROM customers WHERE id = ?;",
        (cid,),
        fetchone=True
    )
    
    if not row:
        flash("❌ Customer not found", "danger")
        return redirect(url_for("main.customers"))
    
    customer = {
        "id": row[0],
        "name": row[1],
        "phone": row[2] or "N/A",
        "email": row[3] or "N/A"
    }
    
    # Get insights
    insights = get_customer_insights(cid)
    customer.update(insights)
    
    # Get purchase history
    purchases = execute_query("""
        SELECT i.id, i.invoice_number, i.total, i.date
        FROM invoices i
        WHERE i.customer_id = ?
        ORDER BY i.date DESC
        LIMIT 10;
    """, (cid,), fetch=True)
    
    purchase_list = [{
        "id": p[0],
        "invoice_number": p[1],
        "total": float(p[2] or 0),
        "date": p[3]
    } for p in purchases or []]
    
    return render_template("customer_detail.html", customer=customer, purchases=purchase_list)

@main.route("/api/search/customers")
@login_required
def api_search_customers():
    """Search customers with insights"""
    q = (request.args.get("q","")).strip().lower()
    if not q:
        return jsonify([])

    # Optimized query to fetch customers and their insights in one go
    rows = execute_query("""
        SELECT 
            c.id, c.name, c.phone, c.email,
            MAX(i.date) as last_purchase,
            COALESCE(SUM(i.total), 0) as total_spend
        FROM customers c
        LEFT JOIN invoices i ON c.id = i.customer_id
        WHERE LOWER(c.name) LIKE ? OR CAST(c.id AS TEXT) LIKE ? OR c.phone LIKE ?
        GROUP BY c.id, c.name, c.phone, c.email
        ORDER BY c.name ASC LIMIT 15;
    """, (f"%{q}%", f"%{q}%", f"%{q}%"), fetch=True)

    out = []
    for id_, name, phone, email, last_purchase, total_spend in rows or []:
        out.append({
            "id": id_, 
            "name": name, 
            "phone": phone or "", 
            "email": email or "",
            "last_purchase": last_purchase, 
            "total_spend": total_spend,
            "display": f"#{id_} • {name} ({phone or 'No phone'})",
            "url": url_for("main.customer_detail", cid=id_)
        })
    return jsonify(out)

@main.route("/api/customer/<int:cid>")
@login_required
def api_get_customer(cid):
    """Get single customer details by ID"""
    row = execute_query(
        "SELECT id, name, phone, email FROM customers WHERE id = ?;",
        (cid,),
        fetchone=True
    )
    
    if not row:
        return jsonify({"error": "Customer not found"}), 404
    
    return jsonify({
        "id": row[0],
        "name": row[1],
        "phone": row[2] or "",
        "email": row[3] or ""
    })

# ========================================
# INVOICE ROUTES
# =
# ========================================
# INVOICE MANAGEMENT - MULTI-ITEM SUPPORT
# ========================================

@main.route("/invoices", methods=["GET", "POST"])
@login_required
def invoices():
    """Enhanced invoice management with dynamic items"""
    add_form = InvoiceAddForm()
    delete_form = InvoiceDeleteForm()
    update_form = InvoiceUpdateForm()

    if request.method == "POST":
        action = request.form.get("action")
        
        if action == "add":
            # Handle dynamic items from JavaScript
            try:
                customer_id = int(request.form.get("customer_id"))
                
                # Parse items dynamically
                items = []
                item_index = 0
                while True:
                    pid_key = f"items-{item_index}-pid"
                    qty_key = f"items-{item_index}-qty"
                    price_key = f"items-{item_index}-price"
                    
                    if pid_key not in request.form:
                        break
                    
                    pid = request.form.get(pid_key)
                    qty = request.form.get(qty_key)
                    price = request.form.get(price_key)
                    
                    if pid and qty and price:
                        items.append({
                            "pid": int(pid),
                            "qty": int(qty),
                            "price": float(price)
                        })
                    
                    item_index += 1
                
                if not items:
                    flash("❌ At least one item is required", "danger")
                    return redirect(url_for("main.invoices"))
                
                invoice_id = create_invoice_and_insert_sales(customer_id, items)
                
                if invoice_id:
                    flash(f"✅ Invoice #{invoice_id} created successfully", "success")
                else:
                    flash("❌ Failed to create invoice. Check stock levels.", "danger")
                    
            except Exception as e:
                flash(f"❌ Error creating invoice: {e}", "danger")
            
            return redirect(url_for("main.invoices"))

        elif action == "delete" and delete_form.validate_on_submit():
            try:
                execute_query("DELETE FROM invoices WHERE id=?;", (delete_form.id.data,), commit=True)
                flash("✅ Invoice deleted successfully", "success")
            except Exception as e:
                flash(f"❌ Error deleting invoice: {e}", "danger")
            return redirect(url_for("main.invoices"))

    invoices = get_invoices()
    return render_template("invoices.html", invoices=invoices,
                           add_form=add_form, delete_form=delete_form, update_form=update_form)

@main.route("/invoice/<int:iid>")
@login_required
def invoice_detail(iid):
    """Invoice detail with line items"""
    # --- Performance Optimization: Fetch invoice and customer name in one query ---
    row = execute_query(
        """
        SELECT i.id, i.invoice_number, i.customer_id, i.total, i.date, c.name as customer_name
        FROM invoices i
        LEFT JOIN customers c ON i.customer_id = c.id
        WHERE i.id = ?;
        """,
        (iid,),
        fetchone=True
    )
    
    if not row:
        flash("❌ Invoice not found", "danger")
        return redirect(url_for("main.invoices"))
    
    invoice = {
        "id": row[0], "invoice_number": row[1], "customer_id": row[2],
        "total": float(row[3] or 0), "date": row[4],
        "customer_name": row[5] or "Unknown Customer" # Handle deleted customers
    }
    
    items = get_sale_details(iid)
    
    return render_template("invoice_detail.html", invoice=invoice, items=items)


# ========================================
# PAYROLL ROUTES
# ========================================

@main.route("/payrolls", methods=["GET", "POST"])
@login_required
def payrolls():
    """Payroll management with full CRUD"""
    add_form = PayrollAddForm()
    delete_form = PayrollDeleteForm()
    update_form = PayrollUpdateForm()

    if request.method == "POST":
        action = request.form.get("action")
        
        if action == "add" and add_form.validate_on_submit():
            try:
                date_str = add_form.date.data.strftime("%Y-%m-%d") if add_form.date.data else datetime.now().strftime("%Y-%m-%d")
                add_payroll(
                    add_form.employee_name.data,
                    add_form.salary.data,
                    date_str
                )
                flash("✅ Payroll record added successfully", "success")
            except Exception as e:
                flash(f"❌ Error: {str(e)}", "danger")
            return redirect(url_for("main.payrolls"))

        elif action == "update" and update_form.validate_on_submit():
            try:
                date_str = update_form.date.data.strftime("%Y-%m-%d") if update_form.date.data else datetime.now().strftime("%Y-%m-%d")
                update_payroll(update_form.id.data, update_form.employee_name.data, update_form.salary.data, date_str)
                flash("✅ Payroll record updated successfully", "success")
            except Exception as e:
                flash(f"❌ Error: {str(e)}", "danger")
            return redirect(url_for("main.payrolls"))

        elif action == "delete" and delete_form.validate_on_submit():
            try:
                delete_payroll(int(delete_form.id.data))
                flash("✅ Payroll record deleted successfully", "success")
            except Exception as e:
                flash(f"❌ Error: {str(e)}", "danger")
            return redirect(url_for("main.payrolls"))

    # Performance Optimization: Calculate total payroll in the backend.
    total_payroll_disbursed_result = execute_query("SELECT COALESCE(SUM(salary), 0) FROM payrolls;", fetchone=True)
    total_payroll_disbursed = float(total_payroll_disbursed_result[0]) if total_payroll_disbursed_result else 0.0
    payrolls = get_payrolls()
    return render_template("payrolls.html", payrolls=payrolls,
                           total_payroll_disbursed=total_payroll_disbursed,
                           add_form=add_form, delete_form=delete_form, update_form=update_form)

@main.route("/api/payroll/monthly")
@login_required
def api_payroll_monthly():
    """API endpoint to get monthly payroll totals for the last 6 months."""
    query = """
        SELECT strftime('%Y-%m', date) as month, SUM(salary) as total_salary
        FROM payrolls
        WHERE date >= date('now', '-6 months')
        GROUP BY month
        ORDER BY month ASC;
    """
    rows = execute_query(query, fetch=True)
    data = {row[0]: row[1] for row in rows}

    return jsonify(data)


# ========================================
# ANALYTICS ROUTES
# ========================================

@main.route("/stock-performance")
@login_required
def stock_performance():
    """Stock performance analysis dashboard"""
    performance = get_stock_performance()
    return render_template("stock_performance.html", 
                         fast_moving=performance["fast_moving"],
                         slow_moving=performance["slow_moving"])

@main.route("/api/stock/performance")
@login_required
def api_stock_performance():
    """Get stock performance metrics"""
    performance = get_stock_performance()
    
    return jsonify({
        "fast_moving": [{
            "id": row[0],
            "name": row[1],
            "category": row[2],
            "total_sold": row[3],
            "status": "🔥 Fast Moving"
        } for row in performance["fast_moving"]],
        "slow_moving": [{
            "id": row[0],
            "name": row[1],
            "category": row[2],
            "qty": row[3],
            "total_sold": row[4],
            "days_since_last_sale": int(row[5]) if row[5] else None,
            "status": "🐌 Slow Moving"
        } for row in performance["slow_moving"]]
    })

@main.route("/alerts/low-stock")
@login_required
def low_stock_alerts():
    """Low stock alerts page"""
    low_stock_tuples = get_low_stock_products()
    # Convert tuples to a list of dictionaries for better template readability
    low_stock_list = [
        {"id": p[0], "name": p[1], "qty": p[2], "threshold": p[3]}
        for p in low_stock_tuples
    ]
    return render_template("alerts.html", low_stock=low_stock_list)

@main.route("/top-sellers")
@login_required
def top_sellers():
    """Top selling products page"""
    top = get_top_sellers()
    return render_template("top-sellers.html", top_sellers=top)

@main.route("/api/top-sellers")
@login_required
def api_top_sellers():
    """API endpoint to get top selling products by revenue."""
    try:
        limit = request.args.get('limit', 5, type=int)
        if not 1 <= limit <= 50:
            limit = 5 # Enforce a reasonable limit
        top_sellers_data = get_top_sellers(limit=limit)
        return jsonify(top_sellers_data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ========================================
# UTILITIES
# ========================================

@main.route("/utils")
@login_required
def utils():
    """Utilities dashboard"""
    utilities = ["backup", "dedupe", "stats", "health"]
    return render_template("utils.html", utilities=utilities)

@main.route("/export/<table>")
@login_required
def export_table(table):
    """Export table to CSV"""
    allowed_tables = ["products", "customers", "invoices", "sales", "payrolls"]
    if table not in allowed_tables:
        flash(f"❌ Invalid table name: {table}", "danger")
        return redirect(url_for("main.utils"))
    
    try:
        os.makedirs("exports", exist_ok=True)
        filepath = f"exports/{table}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        success = export_table_to_csv(table, filepath)
        
        if success:
            return send_file(filepath, as_attachment=True, download_name=f"{table}.csv")
        else:
            flash(f"❌ Failed to export {table}", "danger")
            return redirect(url_for("main.utils"))
    except Exception as e:
        flash(f"❌ Export error: {e}", "danger")
        return redirect(url_for("main.utils"))


@main.route("/import/<table>", methods=["POST"])
@login_required
def import_table(table):
    """FIXED: CSV Import with proper CSRF handling"""
    allowed_tables = ["products", "customers", "invoices", "sales", "payrolls"]
    
    if table not in allowed_tables:
        flash(f"❌ Invalid table name: {table}", "danger")
        return redirect(url_for("main.utils"))
    
    if 'file' not in request.files:
        flash("❌ No file uploaded", "danger")
        return redirect(url_for("main.utils"))
    
    file = request.files['file']
    
    if file.filename == '':
        flash("❌ No file selected", "danger")
        return redirect(url_for("main.utils"))
    
    if not file.filename.endswith('.csv'):
        flash("❌ Please upload a CSV file", "danger")
        return redirect(url_for("main.utils"))
    
    try:
        os.makedirs("uploads", exist_ok=True)
        filename = secure_filename(file.filename)
        filepath = os.path.join("uploads", f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}")
        file.save(filepath)
        
        success = import_table_from_csv(table, filepath)
        
        if success:
            flash(f"✅ {table} imported successfully from {filename}", "success")
        else:
            flash(f"❌ Failed to import {table}", "danger")
            
    except Exception as e:
        flash(f"❌ Import error: {e}", "danger")
    
    return redirect(url_for("main.utils"))

@main.route("/run_command", methods=["POST"])
@login_required
def run_command():
    """FIXED: Working CLI command execution"""
    data = request.get_json()
    cmd = data.get("command", "").strip()
    
    if not cmd:
        return jsonify({"output": "Error: No command provided"})
    
    user_id = session.get("user_id")
    result = execute_command(cmd, admin_user_id=user_id)
    
    if result["success"]:
        return jsonify({"output": result["output"]})
    else:
        return jsonify({"output": f"Error: {result['error']}"})
    
@main.route("/routes")
@login_required
def routes_page():
    """CLI routes reference"""
    routes = [
        {"name": "backup", "description": "Create database backup"},
        {"name": "dedupe", "description": "Remove duplicate records"},
        {"name": "stats", "description": "Show database statistics"},
        {"name": "health", "description": "Check database health"},
    ]
    return render_template("routes.html", routes=routes)

@main.route("/ai-insights")
@login_required
def ai_insights():
    """AI insights dashboard page"""
    return render_template("ai_insights.html")
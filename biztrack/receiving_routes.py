# ========================================
# biztrack/receiving_routes.py - NEW FILE
# Receiving System Routes & API
# ========================================
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_login import login_required, current_user
from datetime import datetime, timedelta
import csv
import os
import logging

from .extensions import limiter, csrf
from .biztrack_db import execute_query, get_connection
from .receiving_forms import ReceivingForm, ReceivingFilterForm, CategoryMarginForm

logger = logging.getLogger(__name__)

receiving_bp = Blueprint('receiving', __name__, url_prefix='/receiving')

# ========================================
# HELPER FUNCTIONS
# ========================================

def get_category_margin(category):
    """Get profit margin for a category"""
    try:
        result = execute_query(
            "SELECT profit_margin_percent FROM category_margins WHERE category_name = ?",
            (category,),
            fetchone=True
        )
        return float(result[0]) if result else 25.0  # Default 25%
    except Exception as e:
        logger.error(f"Error fetching category margin: {e}")
        return 25.0

def calculate_selling_price(cost_price, margin_percent):
    """Calculate selling price from cost price and margin"""
    return round(cost_price * (1 + margin_percent / 100), 2)

def update_product_receiving(product_id, quantity, cost_price, selling_price):
    """Update product with new stock and prices"""
    try:
        execute_query("""
            UPDATE products 
            SET qty = qty + ?,
                price = ?,
                last_cost_price = ?,
                last_received_date = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (quantity, selling_price, cost_price, product_id), commit=True)
        return True
    except Exception as e:
        logger.error(f"Error updating product: {e}")
        return False

# ========================================
# RECEIVING DASHBOARD
# ========================================

@receiving_bp.route('/')
@login_required
def index():
    """Receiving dashboard - shows recent transactions and quick receive form"""
    
    # Get recent receiving transactions
    recent_transactions = execute_query("""
        SELECT 
            rt.id,
            rt.received_date,
            p.name as product_name,
            rt.quantity_received,
            rt.cost_price,
            rt.selling_price,
            rt.total_cost,
            rt.supplier_name,
            u.username as received_by_name
        FROM receiving_transactions rt
        JOIN products p ON rt.product_id = p.id
        LEFT JOIN users u ON rt.received_by = u.id
        ORDER BY rt.received_date DESC
        LIMIT 20
    """, fetch=True)
    
    transactions = []
    for row in recent_transactions or []:
        transactions.append({
            'id': row[0],
            'received_date': row[1],
            'product_name': row[2],
            'quantity_received': row[3],
            'cost_price': row[4],
            'selling_price': row[5],
            'total_cost': row[6],
            'supplier_name': row[7] or 'N/A',
            'received_by_name': row[8]
        })
    
    # Get statistics
    stats = execute_query("""
        SELECT 
            COUNT(*) as total_transactions,
            SUM(quantity_received) as total_quantity,
            SUM(total_cost) as total_value,
            COUNT(DISTINCT product_id) as unique_products
        FROM receiving_transactions
        WHERE received_date >= date('now', '-30 days')
    """, fetchone=True)
    
    dashboard_stats = {
        'total_transactions': stats[0] if stats else 0,
        'total_quantity': stats[1] if stats else 0,
        'total_value': float(stats[2]) if stats and stats[2] else 0.0,
        'unique_products': stats[3] if stats else 0
    }
    
    # Get low stock alerts for quick access
    low_stock = execute_query("""
        SELECT id, name, qty, low_stock_threshold
        FROM products
        WHERE qty <= COALESCE(low_stock_threshold, 10)
        ORDER BY qty ASC
        LIMIT 10
    """, fetch=True)
    
    low_stock_products = [
        {'id': row[0], 'name': row[1], 'qty': row[2], 'threshold': row[3]}
        for row in low_stock or []
    ]
    
    return render_template(
        'receiving/index.html',
        transactions=transactions,
        stats=dashboard_stats,
        low_stock=low_stock_products
    )

# ========================================
# RECEIVE STOCK (SINGLE PRODUCT)
# ========================================

@receiving_bp.route('/receive', methods=['GET', 'POST'])
@login_required
@limiter.limit("30 per minute")
def receive_stock():
    """Receive stock for a single product"""
    form = ReceivingForm()
    
    if form.validate_on_submit():
        try:
            product_id = form.product_id.data
            quantity = form.quantity_received.data
            cost_price = form.cost_price.data
            selling_price = form.selling_price.data
            supplier_name = form.supplier_name.data or None
            supplier_phone = form.supplier_phone.data or None
            invoice_number = form.invoice_number.data or None
            notes = form.notes.data or None
            
            # Get product details
            product = execute_query(
                "SELECT name, category, price FROM products WHERE id = ?",
                (product_id,),
                fetchone=True
            )
            
            if not product:
                flash("❌ Product not found!", "danger")
                return redirect(url_for('receiving.receive_stock'))
            
            product_name, category, current_price = product
            
            # Calculate margin
            margin_percent = ((selling_price - cost_price) / cost_price * 100) if cost_price > 0 else 0
            total_cost = quantity * cost_price
            total_value = quantity * selling_price
            
            # Start transaction
            conn = get_connection()
            cursor = conn.cursor()
            
            try:
                cursor.execute("BEGIN")
                
                # Insert receiving transaction
                cursor.execute("""
                    INSERT INTO receiving_transactions (
                        product_id, quantity_received, cost_price, selling_price,
                        margin_percentage, total_cost, total_value,
                        supplier_name, supplier_phone, invoice_number, notes,
                        received_by
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    product_id, quantity, cost_price, selling_price,
                    margin_percent, total_cost, total_value,
                    supplier_name, supplier_phone, invoice_number, notes,
                    current_user.id
                ))
                
                # Update product
                cursor.execute("""
                    UPDATE products 
                    SET qty = qty + ?,
                        price = ?,
                        last_cost_price = ?,
                        last_received_date = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (quantity, selling_price, cost_price, product_id))
                
                # Update supplier if provided
                if supplier_name:
                    cursor.execute("""
                        INSERT INTO suppliers (name, phone, total_supplies, last_supply_date)
                        VALUES (?, ?, 1, CURRENT_TIMESTAMP)
                        ON CONFLICT(name) DO UPDATE SET
                            phone = excluded.phone,
                            total_supplies = total_supplies + 1,
                            last_supply_date = CURRENT_TIMESTAMP
                    """, (supplier_name, supplier_phone))
                
                conn.commit()
                
                flash(f"✅ Received {quantity} units of {product_name} successfully!", "success")
                flash(f"💰 Cost: M{total_cost:.2f} | Selling: M{total_value:.2f} | Margin: {margin_percent:.1f}%", "info")
                
                return redirect(url_for('receiving.index'))
                
            except Exception as e:
                conn.rollback()
                raise e
                
        except Exception as e:
            logger.error(f"Error receiving stock: {e}", exc_info=True)
            flash(f"❌ Error: {str(e)}", "danger")
    
    return render_template('receiving/receive.html', form=form)

# ========================================
# API: GET PRODUCT DETAILS
# ========================================

@receiving_bp.route('/api/product/<int:product_id>')
@login_required
@csrf.exempt
def api_get_product_details(product_id):
    """Get product details for receiving form"""
    try:
        product = execute_query("""
            SELECT 
                id, name, category, price, qty, 
                last_cost_price, last_received_date
            FROM products 
            WHERE id = ?
        """, (product_id,), fetchone=True)
        
        if not product:
            return jsonify({'error': 'Product not found'}), 404
        
        # Get category margin
        category = product[2] or 'Uncategorized'
        margin = get_category_margin(category)
        
        # Calculate suggested selling price if we have last cost
        last_cost = float(product[5]) if product[5] else None
        suggested_price = calculate_selling_price(last_cost, margin) if last_cost else float(product[3])
        
        return jsonify({
            'id': product[0],
            'name': product[1],
            'category': category,
            'current_price': float(product[3]),
            'current_qty': product[4],
            'last_cost_price': last_cost,
            'last_received_date': product[6],
            'category_margin': margin,
            'suggested_selling_price': suggested_price
        })
        
    except Exception as e:
        logger.error(f"API error: {e}")
        return jsonify({'error': str(e)}), 500

# ========================================
# API: CALCULATE SELLING PRICE
# ========================================

@receiving_bp.route('/api/calculate-price', methods=['POST'])
@login_required
@csrf.exempt
def api_calculate_price():
    """Calculate selling price from cost price and category"""
    try:
        data = request.get_json()
        cost_price = float(data.get('cost_price', 0))
        category = data.get('category', 'Uncategorized')
        
        margin = get_category_margin(category)
        selling_price = calculate_selling_price(cost_price, margin)
        
        return jsonify({
            'selling_price': selling_price,
            'margin_percent': margin,
            'markup_amount': round(selling_price - cost_price, 2)
        })
        
    except Exception as e:
        logger.error(f"Price calculation error: {e}")
        return jsonify({'error': str(e)}), 500

# ========================================
# RECEIVING HISTORY
# ========================================

@receiving_bp.route('/history')
@login_required
def history():
    """View receiving history with filters"""
    filter_form = ReceivingFilterForm(request.args)
    
    # Build query with filters
    query = """
        SELECT 
            rt.id,
            rt.received_date,
            p.name as product_name,
            p.category,
            rt.quantity_received,
            rt.cost_price,
            rt.selling_price,
            rt.margin_percentage,
            rt.total_cost,
            rt.total_value,
            rt.supplier_name,
            rt.invoice_number,
            rt.notes,
            u.username as received_by_name
        FROM receiving_transactions rt
        JOIN products p ON rt.product_id = p.id
        LEFT JOIN users u ON rt.received_by = u.id
        WHERE 1=1
    """
    params = []
    
    # Apply filters
    if filter_form.start_date.data:
        query += " AND date(rt.received_date) >= ?"
        params.append(filter_form.start_date.data.strftime('%Y-%m-%d'))
    
    if filter_form.end_date.data:
        query += " AND date(rt.received_date) <= ?"
        params.append(filter_form.end_date.data.strftime('%Y-%m-%d'))
    
    if filter_form.product_id.data:
        query += " AND rt.product_id = ?"
        params.append(filter_form.product_id.data)
    
    if filter_form.supplier_name.data:
        query += " AND rt.supplier_name LIKE ?"
        params.append(f"%{filter_form.supplier_name.data}%")
    
    query += " ORDER BY rt.received_date DESC LIMIT 500"
    
    results = execute_query(query, tuple(params), fetch=True)
    
    transactions = []
    for row in results or []:
        transactions.append({
            'id': row[0],
            'received_date': row[1],
            'product_name': row[2],
            'category': row[3],
            'quantity_received': row[4],
            'cost_price': row[5],
            'selling_price': row[6],
            'margin_percentage': row[7],
            'total_cost': row[8],
            'total_value': row[9],
            'supplier_name': row[10] or 'N/A',
            'invoice_number': row[11] or 'N/A',
            'notes': row[12] or '',
            'received_by_name': row[13]
        })
    
    return render_template(
        'receiving/history.html',
        transactions=transactions,
        filter_form=filter_form
    )

# ========================================
# EXPORT RECEIVING HISTORY
# ========================================

@receiving_bp.route('/export')
@login_required
def export_history():
    """Export receiving history to CSV"""
    try:
        # Get all transactions
        transactions = execute_query("""
            SELECT 
                rt.id,
                rt.received_date,
                p.name,
                p.category,
                rt.quantity_received,
                rt.cost_price,
                rt.selling_price,
                rt.margin_percentage,
                rt.total_cost,
                rt.total_value,
                rt.supplier_name,
                rt.supplier_phone,
                rt.invoice_number,
                rt.notes,
                u.username
            FROM receiving_transactions rt
            JOIN products p ON rt.product_id = p.id
            LEFT JOIN users u ON rt.received_by = u.id
            ORDER BY rt.received_date DESC
        """, fetch=True)
        
        # Create CSV
        filename = f"receiving_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        filepath = os.path.join('exports', filename)
        os.makedirs('exports', exist_ok=True)
        
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([
                'ID', 'Date', 'Product', 'Category', 'Quantity', 
                'Cost Price', 'Selling Price', 'Margin %', 
                'Total Cost', 'Total Value', 'Supplier', 'Supplier Phone',
                'Invoice #', 'Notes', 'Received By'
            ])
            
            for row in transactions or []:
                writer.writerow(row)
        
        return send_file(
            filepath,
            as_attachment=True,
            download_name=filename,
            mimetype='text/csv'
        )
        
    except Exception as e:
        logger.error(f"Export error: {e}")
        flash(f"❌ Export failed: {str(e)}", "danger")
        return redirect(url_for('receiving.history'))

# ========================================
# CATEGORY MARGIN MANAGEMENT
# ========================================

@receiving_bp.route('/margins')
@login_required
def manage_margins():
    """View and manage category profit margins"""
    margins = execute_query("""
        SELECT
            cm.id,
            category_name,
            profit_margin_percent,
            updated_at,
            u.username as updated_by_name
        FROM category_margins cm
        LEFT JOIN users u ON cm.updated_by = u.id
        ORDER BY category_name
    """, fetch=True)
    
    margin_list = []
    for row in margins or []:
        margin_list.append({
            'id': row[0],
            'category_name': row[1],
            'profit_margin_percent': row[2],
            'updated_at': row[3],
            'updated_by_name': row[4] or 'System'
        })
    
    return render_template('receiving/margins.html', margins=margin_list)

# ========================================
# UPDATE CATEGORY MARGIN
# ========================================

@receiving_bp.route('/margins/update', methods=['POST'])
@login_required
@limiter.limit("10 per minute")
def update_margin():
    """Update category profit margin"""
    form = CategoryMarginForm()
    
    if form.validate_on_submit():
        try:
            category = form.category_name.data
            margin = form.profit_margin_percent.data
            
            execute_query("""
                UPDATE category_margins
                SET profit_margin_percent = ?,
                    updated_at = CURRENT_TIMESTAMP,
                    updated_by = ?
                WHERE category_name = ?
            """, (margin, current_user.id, category), commit=True)
            
            flash(f"✅ Updated {category} margin to {margin}%", "success")
            
        except Exception as e:
            logger.error(f"Margin update error: {e}")
            flash(f"❌ Error: {str(e)}", "danger")
    
    return redirect(url_for('receiving.manage_margins'))

# ========================================
# SUPPLIER MANAGEMENT
# ========================================

@receiving_bp.route('/suppliers')
@login_required
def suppliers():
    """View supplier list"""
    supplier_list = execute_query("""
        SELECT 
            id,
            name,
            phone,
            email,
            address,
            total_supplies,
            last_supply_date
        FROM suppliers
        ORDER BY name
    """, fetch=True)
    
    suppliers = []
    for row in supplier_list or []:
        suppliers.append({
            'id': row[0],
            'name': row[1],
            'phone': row[2] or 'N/A',
            'email': row[3] or 'N/A',
            'address': row[4] or 'N/A',
            'total_supplies': row[5],
            'last_supply_date': row[6]
        })
    
    return render_template('receiving/suppliers.html', suppliers=suppliers)

logger.info("✅ Receiving routes loaded successfully")
# ========================================
# NEW FILE: biztrack/ai_routes.py
# ========================================
import logging
# Third-party Libraries
from flask import Blueprint, request, jsonify, Response
from werkzeug.exceptions import BadRequest

# Local Application Imports
from .auth import login_required
from .extensions import limiter
from .ai_engine import (
    parse_ai_query, 
    predict_category, 
    suggest_price_range, 
    recommend_initial_stock, 
    find_similar_products, 
    forecast_sales, 
)
from .biztrack_db import get_products, get_product_sale_history, execute_query, get_reorder_alerts

logger = logging.getLogger(__name__)

ai_bp = Blueprint("ai", __name__, url_prefix="/api/ai")

@ai_bp.route("/predict-product", methods=["POST"])
@login_required
@limiter.limit("30 per minute")
def ai_predict_product() -> Response:
    """AI-powered product prediction endpoint"""
    try:
        data = request.get_json()
        if not data:
            raise BadRequest("Missing JSON in request")

        product_name = data.get("product_name", "").strip()
        # Allow user to override category for more accurate suggestions
        user_category = data.get("category", "").strip()

        if not product_name:
            return jsonify({"error": "Product name is required"}), 400
        
        all_products = get_products()
        
        category, confidence = (user_category, 1.0) if user_category else predict_category(product_name)
        similar = find_similar_products(product_name, category, all_products)
        price_rec = suggest_price_range(product_name, category, similar)
        stock_rec = recommend_initial_stock(category, similar)
        
        return jsonify({
            "category": {"predicted": category, "confidence": round(confidence * 100, 1)},
            "price": price_rec,
            "stock": stock_rec,
            "similar_products": similar[:3]
        })
    except BadRequest as e:
        return jsonify({"error": f"Invalid request: {e.description}"}), 400
    except Exception as e:
        logger.error(f"AI product prediction failed: {e}", exc_info=True)
        return jsonify({"error": "An internal error occurred during prediction."}), 500

@ai_bp.route("/forecast/<int:product_id>")
@login_required
@limiter.limit("30 per minute")
def ai_forecast_product(product_id: int) -> Response:
    """Forecast future sales for product"""
    # Check if product exists first
    try:
        product_exists = execute_query("SELECT 1 FROM products WHERE id = ?;", (product_id,), fetchone=True)
        if not product_exists:
            return jsonify({"error": "Product not found"}), 404

        # Allow flexible forecast period via query param, e.g., ?days=30
        days_ahead = request.args.get('days', 7, type=int)
        if not 1 <= days_ahead <= 90: # Add reasonable limits
            return jsonify({"error": "Forecast period must be between 1 and 90 days."}), 400

        sales_history = get_product_sale_history(product_id, days=90) # Use more data for better accuracy
        forecast = forecast_sales(product_id, sales_history, days_ahead=days_ahead)
        return jsonify(forecast)
    except Exception as e:
        logger.error(f"AI forecast for product {product_id} failed: {e}", exc_info=True)
        return jsonify({"error": "An internal error occurred during forecast."}), 500

@ai_bp.route("/reorder-alerts")
@login_required
@limiter.limit("15 per minute")
def ai_reorder_alerts() -> Response:
    """Get products that need reordering based on sales velocity."""
    try:
        lead_time = request.args.get('lead_time', 7, type=int)
        safety_stock = request.args.get('safety_stock', 3, type=int)
        alerts = get_reorder_alerts(lead_time_days=lead_time, safety_stock_days=safety_stock)
        return jsonify({"alerts": alerts})
    except Exception as e:
        logger.error(f"AI reorder alert generation failed: {e}", exc_info=True)
        return jsonify({"error": "An internal error occurred while generating alerts."}), 500

@ai_bp.route("/chat", methods=["POST"])
@login_required
@limiter.limit("60 per minute")
def ai_chat_query() -> Response:
    """Handle natural language queries from the AI chat widget."""
    try:
        data = request.get_json()
        if not data or "query" not in data:
            raise BadRequest("Missing 'query' field in JSON request")

        query = data.get("query", "").strip()
        if not query:
            return jsonify({"response": "Please ask a question."})
        
        response_html = parse_ai_query(query)
        return jsonify({"response": response_html})
    except BadRequest as e:
        return jsonify({"error": f"Invalid request: {e.description}"}), 400
    except Exception as e:
        logger.error(f"AI chat query failed: {e}", exc_info=True)
        return jsonify({"error": "An internal error occurred processing your request."}), 500
# ========================================
# biztrack/ai_routes.py
# ========================================
import logging
from flask import Blueprint, request, jsonify, Response, stream_with_context
from werkzeug.exceptions import BadRequest
import json
from datetime import datetime, timedelta

from .auth import login_required
from .extensions import csrf, limiter
from .ai_engine_unified import get_ai_engine, get_ai_response, quick_insight
from .biztrack_db import execute_query, get_reorder_alerts

logger = logging.getLogger(__name__)

ai_bp = Blueprint("ai", __name__, url_prefix="/api/ai")

# ========================================
# AI CHAT
# ========================================
@ai_bp.route("/chat", methods=["POST"])
@login_required
@csrf.exempt  # CRITICAL: This must be here
@limiter.limit("60 per minute")
def ai_chat():
    """Main conversational AI endpoint - returns clean JSON responses"""
    try:
        data = request.get_json()
        if not data or "query" not in data:
            return jsonify({"error": "Missing 'query' field"}), 400

        user_message = data.get("query", "").strip()
        conversation_id = data.get("conversation_id")
        user_id = request.user_id if hasattr(request, 'user_id') else 1
        
        if not user_message:
            return jsonify({"response": "Please ask me something!"})
        
        logger.info(f"Processing AI query: {user_message[:50]}...")
        
        response_text = ""
        try:
            for token in get_ai_response(user_message, user_id, conversation_id):
                response_text += str(token)
            
            if not response_text:
                response_text = "I couldn't generate a response. Please try again."
                
            logger.info(f"Generated response: {response_text[:100]}...")
            return jsonify({"response": response_text, "success": True})
            
        except Exception as e:
            logger.error(f"AI generation error: {e}", exc_info=True)
            return jsonify({
                "response": "I encountered an error processing your request. Please try again.",
                "error": str(e),
                "success": False
            }), 500
            
    except Exception as e:
        logger.error(f"AI chat endpoint error: {e}", exc_info=True)
        return jsonify({
            "error": "An unexpected error occurred",
            "success": False
        }), 500

@ai_bp.route("/quick-insight", methods=["POST"])
@login_required
@limiter.limit("30 per minute")
def ai_quick_insight():
    """Quick AI insights without conversation context"""
    try:
        data = request.get_json()
        query = data.get("query", "").strip()
        user_id = request.user_id if hasattr(request, 'user_id') else 1
        
        if not query:
            return jsonify({"error": "Query required"}), 400
        
        insight = quick_insight(query, user_id)
        return jsonify({"insight": insight})
        
    except Exception as e:
        logger.error(f"Quick insight failed: {e}")
        return jsonify({"error": str(e)}), 500

# ========================================
# LESOTHO MARKET INTELLIGENCE
# ========================================

@ai_bp.route("/predict-product", methods=["POST"])
@login_required
@limiter.limit("30 per minute")
def ai_predict_product():
    """AI-powered product prediction with Lesotho market intelligence"""
    try:
        data = request.get_json()
        if not data:
            raise BadRequest("Missing JSON in request")

        product_name = data.get("product_name", "").strip()
        user_category = data.get("category", "").strip()

        if not product_name:
            return jsonify({"error": "Product name is required"}), 400
        
        engine = get_ai_engine()
        if not engine:
            return jsonify({"error": "AI system unavailable"}), 503
        
        # Predict category
        if user_category:
            category = user_category
            confidence = 1.0
        else:
            category, confidence = engine.predict_category(product_name)
        
        # Get Lesotho market price intelligence
        price_data = engine.suggest_price_with_intelligence(product_name, category)
        
        # Stock recommendation
        stock_rec = {
            "recommended_qty": 50,
            "min_qty": 20,
            "max_qty": 100,
            "reasoning": f"Standard stock for {category} in Lesotho market"
        }
        
        return jsonify({
            "category": {
                "predicted": category, 
                "confidence": round(confidence * 100, 1)
            },
            "price": price_data,
            "stock": stock_rec,
            "similar_products": []
        })
        
    except Exception as e:
        logger.error(f"AI product prediction failed: {e}", exc_info=True)
        return jsonify({"error": "Prediction failed"}), 500

@ai_bp.route("/forecast/<int:product_id>", methods=["GET"])
@login_required
@limiter.limit("30 per minute")
def ai_forecast_product(product_id: int):
    """Simple sales forecasting"""
    try:
        product = execute_query(
            "SELECT name, qty FROM products WHERE id = ?", 
            (product_id,), fetchone=True
        )
        if not product:
            return jsonify({"error": "Product not found"}), 404

        days_ahead = request.args.get('days', 7, type=int)
        
        # Simple 7-day average forecast
        avg_sales = execute_query("""
            SELECT COALESCE(SUM(qty), 0) / 7.0 FROM sales 
            WHERE product_id = ? AND date >= date('now', '-7 days')
        """, (product_id,), fetchone=True)[0]
        
        forecast_data = []
        for i in range(1, days_ahead + 1):
            date = (datetime.now() + timedelta(days=i)).strftime('%Y-%m-%d')
            forecast_data.append({
                "date": date,
                "predicted_qty": round(avg_sales, 1)
            })
        
        return jsonify({
            "trend": "stable" if avg_sales > 0 else "no_data",
            "confidence": 0.7 if avg_sales > 0 else 0.0,
            "forecast": forecast_data,
            "recommendation": f"Average daily sales: {avg_sales:.1f} units"
        })
        
    except Exception as e:
        logger.error(f"Forecast failed: {e}", exc_info=True)
        return jsonify({"error": "Forecast failed"}), 500

@ai_bp.route("/reorder-alerts", methods=["GET"])
@login_required
@limiter.limit("15 per minute")
def ai_reorder_alerts():
    """Intelligent reorder alerts"""
    try:
        lead_time = request.args.get('lead_time', 7, type=int)
        safety_stock = request.args.get('safety_stock', 3, type=int)
        alerts = get_reorder_alerts(lead_time_days=lead_time, safety_stock_days=safety_stock)
        
        return jsonify({"alerts": alerts})
        
    except Exception as e:
        logger.error(f"Reorder alerts failed: {e}", exc_info=True)
        return jsonify({"error": "Failed to generate alerts"}), 500

# ========================================
# SYSTEM STATUS
# ========================================

@ai_bp.route("/status", methods=["GET"])
@login_required
def ai_system_status():
    """Check AI system status"""
    try:
        engine = get_ai_engine()
        
        status = {
            "available": engine is not None,
            "capabilities": []
        }
        
        if engine:
            status["capabilities"] = [
                "conversational_chat",
                "lesotho_market_intelligence",
                "price_optimization",
                "sales_forecasting",
                "product_prediction",
                "reorder_automation"
            ]
            status["handler"] = "llama.cpp (local)"
        
        return jsonify(status)
        
    except Exception as e:
        logger.error(f"Status check failed: {e}")
        return jsonify({"available": False, "error": str(e)}), 500
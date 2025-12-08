# ========================================
# biztrack/ai_engine/store_intelligence.py
# ========================================
import logging
from typing import Dict

logger = logging.getLogger(__name__)

def analyze_store_performance(db_connection) -> Dict:
    """
    Gathers comprehensive store performance metrics from the database.
    
    This function queries various aspects of the business (sales, customers,
    products) and aggregates them into a structured dictionary that the LLM
    can analyze to provide business health insights.
    
    Returns:
        A dictionary containing key business performance indicators.
    """
    from ..biztrack_db import execute_query
    logger.info("Gathering data for store performance analysis...")
    
    try:
        # Using a single, more efficient query to gather multiple stats
        stats = execute_query("""
            SELECT
                (SELECT COALESCE(SUM(total), 0) FROM invoices WHERE date >= date('now', '-30 days')) as revenue_30d,
                (SELECT COUNT(DISTINCT customer_id) FROM invoices WHERE date >= date('now', '-30 days')) as active_customers_30d,
                (SELECT COUNT(*) FROM products WHERE qty < low_stock_threshold) as low_stock_items,
                (SELECT COUNT(*) FROM products) as total_products
        """, fetchone=True)

        return {
            "revenue_last_30_days": float(stats[0] if stats else 0),
            "active_customers_last_30_days": int(stats[1] if stats else 0),
            "items_with_low_stock": int(stats[2] if stats else 0),
            "total_product_count": int(stats[3] if stats else 0),
            "analysis_timestamp": "now"
        }
    except Exception as e:
        logger.error(f"Error gathering store performance data: {e}")
        return {"error": str(e)}
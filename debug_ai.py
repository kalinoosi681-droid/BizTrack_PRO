#!/usr/bin/env python
"""Debug AI endpoints directly"""
import sys
sys.path.insert(0, '.')

# Test without server - directly call functions
print("=" * 60)
print("DIRECT FUNCTION TESTS")
print("=" * 60)

# Test 1: Direct database query
print("\n1. Testing execute_query for forecast...")
try:
    from biztrack.biztrack_db import execute_query
    result = execute_query(
        "SELECT COALESCE(SUM(qty), 0) / 7.0 FROM sales WHERE product_id = ? AND date >= date('now', '-7 days')",
        (1,),
        fetchone=True
    )
    print(f"   Result type: {type(result)}")
    print(f"   Result: {result}")
    if result:
        avg = result[0] if result else 0.0
        print(f"   avg_sales: {avg}")
except Exception as e:
    print(f"   ERROR: {e}")
    import traceback
    traceback.print_exc()

# Test 2: Direct get_reorder_alerts
print("\n2. Testing get_reorder_alerts...")
try:
    from biztrack.biztrack_db import get_reorder_alerts
    alerts = get_reorder_alerts(lead_time_days=7, safety_stock_days=3)
    print(f"   Result type: {type(alerts)}")
    print(f"   Result length: {len(alerts) if isinstance(alerts, list) else 'N/A'}")
    print(f"   Is list: {isinstance(alerts, list)}")
    if alerts:
        print(f"   First alert: {alerts[0]}")
except Exception as e:
    print(f"   ERROR: {e}")
    import traceback
    traceback.print_exc()

# Test 3: Test with Flask app context
print("\n" + "=" * 60)
print("FLASK APP CONTEXT TESTS")
print("=" * 60)

try:
    from biztrack import create_app
    app = create_app()
    
    with app.app_context():
        print("\n3. Testing with app context - execute_query...")
        from biztrack.biztrack_db import execute_query
        result = execute_query(
            "SELECT COUNT(*) FROM products",
            fetchone=True
        )
        print(f"   Products count: {result}")
        
        print("\n4. Testing with app context - get_reorder_alerts...")
        from biztrack.biztrack_db import get_reorder_alerts
        alerts = get_reorder_alerts(lead_time_days=7, safety_stock_days=3)
        print(f"   Alerts type: {type(alerts)}")
        print(f"   Alerts count: {len(alerts) if isinstance(alerts, list) else 'N/A'}")
        
        print("\n5. Testing with app context - AI endpoints...")
        from biztrack.ai_routes import ai_forecast_product, ai_reorder_alerts, ai_quick_insight
        print(f"   ai_forecast_product: {ai_forecast_product}")
        print(f"   ai_reorder_alerts: {ai_reorder_alerts}")
        print(f"   ai_quick_insight: {ai_quick_insight}")
        
except Exception as e:
    print(f"   ERROR: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("Tests completed")
print("=" * 60)

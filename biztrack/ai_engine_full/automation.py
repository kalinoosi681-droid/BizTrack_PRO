# ========================================
# biztrack/automation.py - Business Automation
# Automated alerts, reports, reorders, and insights
# ========================================
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import json
from biztrack import biztrack_db
from .ai_engine_free import get_ai_engine

logger = logging.getLogger(__name__)

# ========================================
# AUTOMATED ALERTS
# ========================================

class AlertSystem:
    """Automated business alerts and notifications"""
    
    @staticmethod
    def check_low_stock_alerts() -> List[Dict]:
        """
        Check for low stock and generate intelligent alerts.
        Returns list of alerts with AI recommendations.
        """
        alerts = biztrack_db.get_reorder_alerts(lead_time_days=7, safety_stock_days=3)
        
        if not alerts:
            return []
        
        # Prioritize critical items
        critical = [a for a in alerts if a['urgency'] == 'critical']
        high = [a for a in alerts if a['urgency'] == 'high']
        
        result = {
            'timestamp': datetime.now().isoformat(),
            'total_alerts': len(alerts),
            'critical': critical,
            'high_priority': high,
            'action_needed': len(critical) > 0
        }
        
        logger.info(f"Stock alerts: {len(alerts)} total, {len(critical)} critical")
        return result
    
    @staticmethod
    def check_sales_anomalies() -> Dict:
        """
        Detect unusual sales patterns using AI analysis.
        """
        # Get last 7 days average
        avg_sales = biztrack_db.execute_query("""
            SELECT AVG(daily_total) FROM (
                SELECT date, SUM(total) as daily_total
                FROM invoices
                WHERE date >= date('now', '-7 days')
                GROUP BY date(date)
            )
        """, fetchone=True)
        
        # Get today's sales
        today_sales = biztrack_db.execute_query("""
            SELECT COALESCE(SUM(total), 0)
            FROM invoices
            WHERE date(date) = date('now')
        """, fetchone=True)
        
        avg = float(avg_sales[0] or 0)
        today = float(today_sales[0] or 0)
        
        # Detect anomaly (>50% deviation)
        if avg > 0:
            deviation = ((today - avg) / avg) * 100
            is_anomaly = abs(deviation) > 50
            
            return {
                'is_anomaly': is_anomaly,
                'today_sales': today,
                'avg_sales': avg,
                'deviation_percent': round(deviation, 1),
                'type': 'spike' if deviation > 0 else 'drop',
                'alert_level': 'high' if abs(deviation) > 75 else 'medium'
            }
        
        return {'is_anomaly': False}
    
    @staticmethod
    def check_customer_retention() -> Dict:
        """
        Identify at-risk customers who haven't purchased recently.
        """
        # Get customers who haven't purchased in 30+ days
        at_risk = biztrack_db.execute_query("""
            SELECT c.id, c.name, c.phone, 
                   MAX(i.date) as last_purchase,
                   CAST(JULIANDAY('now') - JULIANDAY(MAX(i.date)) AS INTEGER) as days_since,
                   SUM(i.total) as lifetime_value
            FROM customers c
            LEFT JOIN invoices i ON c.id = i.customer_id
            GROUP BY c.id, c.name, c.phone
            HAVING days_since > 30
            ORDER BY lifetime_value DESC
            LIMIT 10
        """, fetch=True)
        
        return {
            'at_risk_customers': [{
                'id': r[0],
                'name': r[1],
                'phone': r[2],
                'last_purchase': r[3],
                'days_since': r[4],
                'lifetime_value': float(r[5] or 0)
            } for r in at_risk or []],
            'total_at_risk': len(at_risk or []),
            'recommendation': 'Send personalized offers or check-in messages to re-engage'
        }


# ========================================
# AUTOMATED REPORTING
# ========================================

class ReportGenerator:
    """Generate automated business reports"""
    
    @staticmethod
    def generate_daily_summary() -> str:
        """
        Generate comprehensive daily business summary.
        Returns formatted markdown report.
        """
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Get key metrics
        metrics = biztrack_db.execute_query("""
            SELECT 
                COUNT(*) as transactions,
                COALESCE(SUM(total), 0) as revenue,
                COALESCE(AVG(total), 0) as avg_transaction
            FROM invoices
            WHERE date(date) = date('now')
        """, fetchone=True)
        
        # Get top products
        top_products = biztrack_db.execute_query("""
            SELECT p.name, SUM(s.qty) as qty, SUM(s.total_price) as revenue
            FROM sales s
            JOIN products p ON s.product_id = p.id
            WHERE date(s.date) = date('now')
            GROUP BY p.name
            ORDER BY revenue DESC
            LIMIT 5
        """, fetch=True)
        
        # Get low stock count
        low_stock_count = len(biztrack_db.get_low_stock_products())
        
        # Format report
        report = f"""
# Daily Business Summary - {today}

## 📊 Key Performance Indicators

- **Revenue**: M{metrics[1]:.2f}
- **Transactions**: {metrics[0]}
- **Average Transaction**: M{metrics[2]:.2f}

## ✨ Top Selling Products

"""
        for i, (name, qty, revenue) in enumerate(top_products or [], 1):
            report += f"{i}. **{name}** - {int(qty)} units, M{revenue:.2f}\n"
        
        report += f"""

## ⚠️ Alerts

- **Low Stock Items**: {low_stock_count} ⚠️

## 💡 Recommendations

"""
        if metrics[0] == 0:
            report += "- No sales today. Consider running a promotion or checking inventory visibility.\n"
        elif metrics[1] > 0:
            report += "- Great work! Keep momentum with upselling strategies.\n"
        
        if low_stock_count > 0:
            report += f"- {low_stock_count} products need reordering. Review stock levels.\n"
        
        return report
    
    @staticmethod
    def generate_weekly_report() -> str:
        """
        Generate comprehensive weekly business report with trends.
        """
        # Get this week's data
        this_week = biztrack_db.execute_query("""
            SELECT 
                COUNT(*) as transactions,
                COALESCE(SUM(total), 0) as revenue,
                COUNT(DISTINCT customer_id) as unique_customers
            FROM invoices
            WHERE date >= date('now', '-7 days')
        """, fetchone=True)
        
        # Get last week's data for comparison
        last_week = biztrack_db.execute_query("""
            SELECT 
                COUNT(*) as transactions,
                COALESCE(SUM(total), 0) as revenue,
                COUNT(DISTINCT customer_id) as unique_customers
            FROM invoices
            WHERE date >= date('now', '-14 days') AND date < date('now', '-7 days')
        """, fetchone=True)
        
        # Calculate growth
        revenue_growth = ((this_week[1] - last_week[1]) / last_week[1] * 100) if last_week[1] > 0 else 0
        
        report = f"""
# Weekly Business Report - Week of {datetime.now().strftime('%B %d, %Y')}

## 📈 Performance Overview

- **Revenue**: M{this_week[1]:.2f} ({revenue_growth:+.1f}% vs last week)
- **Transactions**: {this_week[0]}
- **Unique Customers**: {this_week[2]}

## 🏆 Top Performers

"""
        # Get top products of the week
        top_weekly = biztrack_db.get_top_sellers(limit=10)
        for i, product in enumerate(top_weekly, 1):
            report += f"{i}. **{product['name']}** - M{product['revenue']:.2f}\n"
        
        report += """

## 💡 AI Insights

"""
        if revenue_growth > 10:
            report += "- Excellent growth! Consider expanding inventory of top sellers.\n"
        elif revenue_growth > 0:
            report += "- Positive trend. Focus on customer retention strategies.\n"
        else:
            report += "- Revenue declined. Analyze what changed and adjust strategy.\n"
        
        return report
    
    @staticmethod
    def generate_ai_enhanced_report(period='week') -> str:
        """
        Generate AI-enhanced report with natural language insights.
        """
        engine = get_ai_engine()
        if not engine:
            return "AI system not available for enhanced reporting."
        
        # Get base report
        if period == 'day':
            base_report = ReportGenerator.generate_daily_summary()
        else:
            base_report = ReportGenerator.generate_weekly_report()
        
        # Ask AI to enhance with insights
        prompt = f"""Analyze this business report and provide:
1. Key insights (3-5 points)
2. Actionable recommendations (5 items)
3. Potential risks to watch
4. Growth opportunities

Report:
{base_report}

Provide analysis in a clear, actionable format for a business owner in Lesotho.
"""
        
        ai_analysis = ""
        for token in engine.chat(prompt, user_id=1, stream=False): # user_id=1 is hardcoded, consider making dynamic if needed
            ai_analysis += token
        
        return f"{base_report}\n\n## 🤖 AI-Enhanced Analysis\n\n{ai_analysis}"


# ========================================
# AUTOMATED REORDERING
# ========================================

class AutoReorder:
    """Automated reorder suggestions and purchase order generation"""
    
    @staticmethod
    def generate_reorder_list() -> Dict:
        """
        Generate intelligent reorder list with quantities.
        """
        alerts = biztrack_db.get_reorder_alerts(lead_time_days=7, safety_stock_days=3)
        
        if not alerts:
            return {'status': 'no_action_needed', 'items': []}
        
        # Group by urgency
        reorder_list = {
            'order_now': [],  # Critical items
            'order_soon': [],  # High priority
            'monitor': []      # Low priority
        }
        
        for alert in alerts:
            item = {
                'product_id': alert['product_id'],
                'product_name': alert['product_name'],
                'current_stock': alert['current_stock'],
                'reorder_qty': alert['reorder_qty'],
                'estimated_cost': 0  # Would calculate from supplier data
            }
            
            if alert['urgency'] == 'critical':
                reorder_list['order_now'].append(item)
            elif alert['urgency'] == 'high':
                reorder_list['order_soon'].append(item)
            else:
                reorder_list['monitor'].append(item)
        
        return {
            'status': 'action_required',
            'generated_at': datetime.now().isoformat(),
            'reorder_list': reorder_list,
            'total_items': len(alerts),
            'urgent_count': len(reorder_list['order_now'])
        }
    
    @staticmethod
    def generate_purchase_order(supplier_name: str = "Default Supplier") -> str:
        """
        Generate formatted purchase order document.
        """
        reorder_data = AutoReorder.generate_reorder_list()
        
        if reorder_data['status'] == 'no_action_needed':
            return "No items need reordering at this time."
        
        po_number = f"PO-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
        po_document = f"""
PURCHASE ORDER
==============

PO Number: {po_number}
Date: {datetime.now().strftime('%B %d, %Y')}
Supplier: {supplier_name}

URGENT ITEMS (Order Immediately):
---------------------------------
"""
        total_items = 0
        
        for item in reorder_data['reorder_list']['order_now']:
            po_document += f"{item['product_name']:40} Qty: {item['reorder_qty']:5} (Current: {item['current_stock']})\n"
            total_items += item['reorder_qty']
        
        po_document += "\nHIGH PRIORITY (Order This Week):\n"
        po_document += "-" * 50 + "\n"
        
        for item in reorder_data['reorder_list']['order_soon']:
            po_document += f"{item['product_name']:40} Qty: {item['reorder_qty']:5} (Current: {item['current_stock']})\n"
            total_items += item['reorder_qty']
        
        po_document += f"\n\nTotal Items: {total_items}\n"
        po_document += "\nNotes:\n"
        po_document += "- Please confirm availability and delivery timeline\n"
        po_document += "- Urgent items needed within 3-5 days\n"
        
        return po_document


# ========================================
# SCHEDULED TASKS
# ========================================

class ScheduledTasks:
    """Background tasks that run on schedule"""
    
    @staticmethod
    def run_daily_tasks():
        """
        Execute all daily automated tasks.
        Call this from a cron job or scheduler.
        """
        logger.info("=== Running daily automated tasks ===")
        
        try:
            # 1. Compute metrics
            logger.info("Computing daily metrics...")
            biztrack_db.compute_daily_store_metrics()
            biztrack_db.compute_daily_product_metrics()
            
            # 2. Check alerts
            logger.info("Checking alerts...")
            stock_alerts = AlertSystem.check_low_stock_alerts()
            if stock_alerts and stock_alerts.get('action_needed'):
                logger.warning(f"URGENT: {len(stock_alerts.get('critical', []))} products critically low on stock!")
            
            sales_anomaly = AlertSystem.check_sales_anomalies()
            if sales_anomaly.get('is_anomaly'):
                logger.warning(f"Sales anomaly detected: {sales_anomaly['deviation_percent']}% deviation")
            
            # 3. Generate daily report
            logger.info("Generating daily report...")
            report = ReportGenerator.generate_daily_summary()
            
            # Save report to file
            report_dir = 'reports/daily'
            import os
            os.makedirs(report_dir, exist_ok=True)
            
            report_file = f"{report_dir}/report_{datetime.now().strftime('%Y%m%d')}.md"
            with open(report_file, 'w') as f:
                f.write(report)
            
            logger.info(f"Daily report saved to {report_file}")
            
            # 4. Backup database
            logger.info("Backing up database...")
            backup_path = biztrack_db.backup_db()
            if backup_path:
                logger.info(f"Backup created at {backup_path}")
            
            logger.info("=== Daily tasks completed successfully ===")
            return True
            
        except Exception as e:
            logger.error(f"Error in daily tasks: {e}", exc_info=True)
            return False
    
    @staticmethod
    def run_weekly_tasks():
        """
        Execute all weekly automated tasks.
        """
        logger.info("=== Running weekly automated tasks ===")
        
        try:
            # 1. Generate comprehensive weekly report
            logger.info("Generating weekly report...")
            report = ReportGenerator.generate_weekly_report()
            
            # 2. AI-enhanced insights
            logger.info("Getting AI insights...")
            ai_report = ReportGenerator.generate_ai_enhanced_report(period='week')
            
            # Save reports
            report_dir = 'reports/weekly'
            import os
            os.makedirs(report_dir, exist_ok=True)
            
            week_num = datetime.now().strftime('%Y-W%V')
            report_file = f"{report_dir}/report_{week_num}.md"
            ai_report_file = f"{report_dir}/report_{week_num}_ai.md"
            
            with open(report_file, 'w') as f:
                f.write(report)
            
            with open(ai_report_file, 'w') as f:
                f.write(ai_report)
            
            logger.info(f"Weekly reports saved to {report_dir}")
            
            # 3. Check customer retention
            logger.info("Checking customer retention...")
            retention = AlertSystem.check_customer_retention()
            if retention['total_at_risk'] > 0:
                logger.warning(f"{retention['total_at_risk']} customers at risk of churning")
            
            # 4. Generate reorder recommendations
            logger.info("Generating reorder recommendations...")
            reorder_list = AutoReorder.generate_reorder_list()
            if reorder_list['urgent_count'] > 0:
                po = AutoReorder.generate_purchase_order()
                
                po_dir = 'reports/purchase_orders'
                os.makedirs(po_dir, exist_ok=True)
                po_file = f"{po_dir}/po_{datetime.now().strftime('%Y%m%d')}.txt"
                
                with open(po_file, 'w') as f:
                    f.write(po)
                
                logger.info(f"Purchase order saved to {po_file}")
            
            logger.info("=== Weekly tasks completed successfully ===")
            return True
            
        except Exception as e:
            logger.error(f"Error in weekly tasks: {e}", exc_info=True)
            return False


# ========================================
# REAL-TIME MONITORING
# ========================================

class RealTimeMonitor:
    """Real-time business monitoring and alerts"""
    
    @staticmethod
    def check_live_metrics() -> Dict:
        """
        Get current business status for live monitoring.
        """
        # Current hour's sales
        current_hour_sales = biztrack_db.execute_query("""
            SELECT COUNT(*), COALESCE(SUM(total), 0)
            FROM invoices
            WHERE datetime(date) >= datetime('now', '-1 hour')
        """, fetchone=True)
        
        # Low stock count
        low_stock = len(biztrack_db.get_low_stock_products())
        
        # Active customers today
        active_customers = biztrack_db.execute_query("""
            SELECT COUNT(DISTINCT customer_id)
            FROM invoices
            WHERE date(date) = date('now')
        """, fetchone=True)
        
        return {
            'timestamp': datetime.now().isoformat(),
            'current_hour': {
                'transactions': current_hour_sales[0],
                'revenue': float(current_hour_sales[1])
            },
            'alerts': {
                'low_stock_count': low_stock,
                'active_customers_today': active_customers[0]
            },
            'status': 'healthy' if low_stock < 5 else 'needs_attention'
        }
    
    @staticmethod
    def get_performance_score() -> Dict:
        """
        Calculate overall business performance score (0-100).
        """
        scores = {
            'sales': 0,
            'inventory': 0,
            'customers': 0,
            'growth': 0
        }
        
        # Sales score (based on today vs average)
        avg_daily = biztrack_db.execute_query("""
            SELECT AVG(daily_total) FROM (
                SELECT date, SUM(total) as daily_total
                FROM invoices
                WHERE date >= date('now', '-30 days')
                GROUP BY date(date)
            )
        """, fetchone=True)
        
        today_sales = biztrack_db.execute_query("""
            SELECT COALESCE(SUM(total), 0)
            FROM invoices
            WHERE date(date) = date('now')
        """, fetchone=True)
        
        if avg_daily[0] and avg_daily[0] > 0:
            sales_ratio = today_sales[0] / avg_daily[0]
            scores['sales'] = min(100, int(sales_ratio * 100))
        
        # Inventory score (based on stock health)
        low_stock = len(biztrack_db.get_low_stock_products())
        total_products = biztrack_db.execute_query("SELECT COUNT(*) FROM products", fetchone=True)[0]
        
        if total_products > 0:
            stock_health = 1 - (low_stock / total_products)
            scores['inventory'] = int(stock_health * 100)
        
        # Customer score (based on repeat customers)
        repeat_rate = biztrack_db.execute_query("""
            SELECT 
                CAST(SUM(CASE WHEN purchase_count > 1 THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) * 100
            FROM (
                SELECT customer_id, COUNT(*) as purchase_count
                FROM invoices
                WHERE date >= date('now', '-30 days')
                GROUP BY customer_id
            )
        """, fetchone=True)
        
        scores['customers'] = int(repeat_rate[0] or 50)
        
        # Growth score (week over week)
        this_week = biztrack_db.execute_query("""
            SELECT COALESCE(SUM(total), 0)
            FROM invoices
            WHERE date >= date('now', '-7 days')
        """, fetchone=True)
        
        last_week = biztrack_db.execute_query("""
            SELECT COALESCE(SUM(total), 0)
            FROM invoices
            WHERE date >= date('now', '-14 days') AND date < date('now', '-7 days')
        """, fetchone=True)
        
        if last_week[0] and last_week[0] > 0:
            growth_rate = ((this_week[0] - last_week[0]) / last_week[0]) * 100
            scores['growth'] = max(0, min(100, int(50 + growth_rate)))
        else:
            scores['growth'] = 50
        
        # Calculate overall score
        overall = sum(scores.values()) // 4
        
        return {
            'overall_score': overall,
            'breakdown': scores,
            'rating': (
                'Excellent' if overall >= 85 else
                'Good' if overall >= 70 else
                'Fair' if overall >= 50 else
                'Needs Improvement'
            )
        }


# ========================================
# CLI COMMANDS FOR AUTOMATION
# ========================================

def run_daily_automation():
    """CLI command: python -m biztrack.automation daily"""
    print("🤖 Running daily automation tasks...")
    result = ScheduledTasks.run_daily_tasks()
    print("✅ Daily tasks completed!" if result else "❌ Daily tasks failed!")
    return result

def run_weekly_automation():
    """CLI command: python -m biztrack.automation weekly"""
    print("📊 Running weekly automation tasks...")
    result = ScheduledTasks.run_weekly_tasks()
    print("✅ Weekly tasks completed!" if result else "❌ Weekly tasks failed!")
    return result

def check_alerts():
    """CLI command: python -m biztrack.automation alerts"""
    print("\n🔔 Checking business alerts...\n")

    # Stock alerts
    stock = AlertSystem.check_low_stock_alerts()
    if stock and stock.get('action_needed'):
        print(f"âš ï¸ STOCK ALERT: {stock['total_alerts']} items need attention")
        print(f"   - Critical: {len(stock.get('critical', []))} 🔴")
        print(f"   - High Priority: {len(stock.get('high_priority', []))} 🟡")
    else:
        print("✅ Stock levels healthy")

    # Sales anomalies
    anomaly = AlertSystem.check_sales_anomalies()
    if anomaly.get('is_anomaly'):
        print(f"\n📈 SALES ANOMALY: {anomaly['deviation_percent']}% deviation from average")
    else:
        print("\n👌 Sales patterns normal")
    
    # Customer retention
    retention = AlertSystem.check_customer_retention()
    if retention['total_at_risk'] > 0:
        print(f"\n💔 RETENTION ALERT: {retention['total_at_risk']} customers at risk")
    else:
        print("\n🤝 Customer engagement healthy") # Replaced with a more positive emoji

    print("\n") # Added a newline for better readability

def generate_report(period='day'):
    """CLI command: python -m biztrack.automation report [day|week]"""
    print(f"📊 Generating {period}ly report...")
    
    if period == 'week':
        report = ReportGenerator.generate_weekly_report()
    else:
        report = ReportGenerator.generate_daily_summary()
    
    print(report) # Print the generated report content
    print("\n✅ Report generated successfully!")

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("""
BizTrack Automation CLI

Commands:
  daily    - Run daily automation tasks
  weekly   - Run weekly automation tasks
  alerts   - Check current alerts
  report [day|week] - Generate report
  
Example:
  python -m biztrack.automation daily
  python -m biztrack.automation report week
        """)
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    if command == 'daily':
        run_daily_automation()
    elif command == 'weekly':
        run_weekly_automation()
    elif command == 'alerts':
        check_alerts()
    elif command == 'report':
        period = sys.argv[2] if len(sys.argv) > 2 else 'day'
        generate_report(period)
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
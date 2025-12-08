# ========================================
# biztrack/ai_engine_unified.py - COMPLETE AI SYSTEM
# conversational AI + Lesotho market intelligence
# ========================================
import logging
from typing import List, Dict, Optional, Generator
from datetime import datetime, timedelta
import json
import statistics
import re
from collections import defaultdict
import requests
from bs4 import BeautifulSoup
import functools

from .biztrack_db import execute_query, get_reorder_alerts

logger = logging.getLogger(__name__)

# ========================================
# LESOTHO MARKET CONFIGURATION
# ========================================
CURRENCY = "M"  # Maloti
VAT_RATE = 0.15  # 15% VAT in Lesotho
SEASONAL_ADJUSTMENTS = {
    "Food": {12: 1.15, 1: 1.15, 4: 0.95, 7: 0.95},  # High in Dec/Jan (holidays), low mid-year
    "Beverages": {12: 1.20, 1: 1.20, 6: 1.10, 7: 1.10},  # High holidays & winter
    "Clothing": {11: 1.25, 12: 1.30, 1: 0.85},  # Black Friday/Christmas spike
    "Electronics": {11: 1.20, 12: 1.25, 1: 0.80},  # Holiday season
    "School": {1: 1.40, 2: 1.30, 7: 0.70},  # Back to school spike
}

# Products exempt from VAT in Lesotho
VAT_EXEMPT_CATEGORIES = {
    "Maize meal", "Bread", "Flour", "Rice", "Milk", "Fresh produce",
    "Vegetables", "Fruits", "Meat", "Medicine", "Educational materials"
}

LESOTHO_PRICE_RANGES = {
    "Beverages": (15.0, 150.0),
    "Food": (20.0, 500.0),
    "Health": (50.0, 1000.0),
    "Stationery": (5.0, 300.0),
    "Electronics": (200.0, 5000.0),
    "Home": (100.0, 2000.0),
    "Cleaning": (30.0, 300.0),
    "Clothing": (100.0, 800.0),
    "School": (10.0, 500.0),
}

# ========================================
# UNIFIED AI ENGINE
# ========================================
class UnifiedAIEngine:
    """
    Complete AI system combining:
    - Conversational chat (RAG + LLM)
    - Lesotho market intelligence
    - Price optimization with seasonal trends
    - Sales forecasting
    - Automated business insights
    """
    
    def __init__(self, db_connection):
        self.db = db_connection
        self.llm = None
        self.rag = None
        self.conversation_manager = None
        
        self.system_prompt = """You are BizBot, an expert business advisor for small businesses in Lesotho, Southern Africa.

Your capabilities:
- Sales analysis and forecasting
- Inventory optimization for Lesotho market
- Customer insights
- Pricing strategies (considering Maloti currency and 15% VAT)
- Growth recommendations specific to Lesotho economy
- Understanding of seasonal trends in Lesotho

You speak naturally in a mix of English and simple Sesotho phrases where appropriate.
You understand Lesotho's market: Maloti (M) currency, local suppliers, VAT at 15%, seasonal patterns.

Always:
✅ Be conversational and friendly
✅ Explain your reasoning clearly
✅ Provide specific numbers with M currency symbol
✅ Suggest concrete next steps
✅ Consider Lesotho seasonal trends (e.g., back-to-school in January, holidays in December)
✅ Mention if products are VAT-exempt

Never:
❌ Make up data - always query the database
❌ Give generic advice - be specific to Lesotho context
❌ Overwhelm with jargon - explain in simple terms
❌ Ignore local market conditions
"""
    
    def initialize(self):
        """Initialize all AI components"""
        try:
            from .ai_engine_full.llm_handler import get_llm_handler
            from .ai_engine_full.rag_engine import RAGEngine
            from .ai_engine_full.conversation_manager import ConversationManager
            
            logger.info("🤖 Initializing Unified AI Engine...")
            
            # 1. Initialize LLM (llama.cpp only)
            self.llm = get_llm_handler()
            if not self.llm:
                logger.error("❌ LLM handler initialization failed")
                return False
            
            # 2. Initialize RAG
            self.rag = RAGEngine(self.db)
            
            # Seed initial product data if RAG is empty
            try:
                cursor = self.db.cursor()
                cursor.execute("SELECT COUNT(*) FROM rag_documents")
                row = cursor.fetchone()
                count = row[0] if row else 0
                
                if count == 0:
                    logger.info("Seeding RAG with initial product data...")
                    products = execute_query(
                        "SELECT id, name, COALESCE(category, '') as category, price FROM products LIMIT 200",
                        fetch=True
                    )
                    for pid, name, category, price in products or []:
                        content = f"Product: {name}\nCategory: {category}\nPrice: M{price}"
                        self.rag.add_document(content, metadata={"product_id": pid}, llm_handler=self.llm)
                    logger.info(f"✅ Indexed {len(products or [])} products")
            except Exception as e:
                logger.warning(f"RAG seeding failed: {e}")
            
            # 3. Initialize conversation manager
            self.conversation_manager = ConversationManager(self.db)
            
            logger.info("✅ Unified AI Engine ready!")
            return True
            
        except Exception as e:
            logger.error(f"❌ AI Engine initialization failed: {e}", exc_info=True)
            return False
    
    # ========================================
    # CHAT INTERFACE
    # ========================================
    def chat(self, user_message: str, user_id: int, 
             conversation_id: Optional[str] = None, 
             stream: bool = True) -> Generator[str, None, None]:
        """
        Main chat interface with command support and context
        """
        try:
            # Handle conversation_id (might be dict or string)
            if isinstance(conversation_id, dict):
                conversation_id = conversation_id.get('id')
            
            # Get conversation history
            history = self.conversation_manager.get_history(user_id, conversation_id)
            
            # Check for commands first
            command_result = self._handle_command(user_message, user_id)
            if command_result:
                self.conversation_manager.save_turn(
                    user_id=user_id,
                    conversation_id=conversation_id,
                    user_message=user_message,
                    assistant_message=command_result,
                    context={}
                )
                yield command_result
                return
            
            # Get business context
            context = self._get_business_context(user_message, user_id)
            
            # Build prompt
            prompt = self._build_prompt(user_message, history, context)
            
            # Generate response
            full_response = ""
            for token in self.llm.generate(prompt, stream=stream):
                full_response += token
                yield token
            
            # Save conversation
            new_conv_id = self.conversation_manager.save_turn(
                user_id=user_id,
                conversation_id=conversation_id,
                user_message=user_message,
                assistant_message=full_response,
                context=context
            )
            
            # Return new conversation ID if created
            if not conversation_id and new_conv_id:
                yield f"\n\n<!-- NEW_CONVERSATION_ID: {new_conv_id} -->"
        
        except Exception as e:
            logger.error(f"Chat error: {e}", exc_info=True)
            yield f"I apologize, I encountered an error: {str(e)}\n\nPlease try again or rephrase your question."
    
    def _handle_command(self, message: str, user_id: int) -> Optional[str]:
        """Handle special commands"""
        msg = message.lower().strip()
        
        if msg.startswith('/sales') or 'show sales' in msg:
            return self._cmd_sales(user_id)
        
        if msg.startswith('/forecast'):
            parts = message.split()
            product_id = int(parts[1]) if len(parts) > 1 else None
            return self._cmd_forecast(product_id)
        
        if msg.startswith('/alerts') or 'low stock' in msg or 'reorder' in msg:
            return self._cmd_alerts(user_id)
        
        if 'hello' in msg or 'hi' in msg or 'dumela' in msg:
            return self._cmd_greeting()
        
        return None
    
    def _cmd_greeting(self) -> str:
        """Warm greeting"""
        return """**👋 Dumela! Hello!**

I'm BizBot, your AI business assistant for Lesotho market intelligence.

**I can help you with:**
- 📊 Sales insights and forecasts
- 💰 Pricing strategies (Maloti currency, VAT considerations)
- 📦 Inventory management and reorder alerts
- 👥 Customer insights
- 🚀 Business growth recommendations
- 🌍 Lesotho & South Africa market trends

**Try asking:**
- "What are my top sellers?"
- "Show me low stock items"
- "Suggest a price for [product name]"
- "What's today's sales?"

Ke a leboga! (Thank you!)"""
    
    def _cmd_sales(self, user_id: int) -> str:
        """Sales summary with Lesotho insights"""
        today = execute_query("""
            SELECT COUNT(*), COALESCE(SUM(total), 0)
            FROM invoices
            WHERE date(date) = date('now')
        """, fetchone=True)
        
        week = execute_query("""
            SELECT COUNT(*), COALESCE(SUM(total), 0)
            FROM invoices
            WHERE date >= date('now', '-7 days')
        """, fetchone=True)
        
        last_week = execute_query("""
            SELECT COUNT(*), COALESCE(SUM(total), 0)
            FROM invoices
            WHERE date >= date('now', '-14 days') AND date < date('now', '-7 days')
        """, fetchone=True)
        
        top_products = execute_query("""
            SELECT p.name, SUM(s.qty) as total_qty, SUM(s.total_price) as revenue
            FROM sales s
            JOIN products p ON s.product_id = p.id
            WHERE s.date >= date('now', '-7 days')
            GROUP BY p.name
            ORDER BY revenue DESC
            LIMIT 5
        """, fetch=True)
        
        week_rev = week[1] if week else 0
        last_week_rev = last_week[1] if last_week else 0
        growth = ((week_rev - last_week_rev) / last_week_rev * 100) if last_week_rev > 0 else 0
        growth_emoji = "📈" if growth > 0 else "📉" if growth < 0 else "➡️"
        
        response = f"""📊 **Sales Performance Report**

**📅 Today ({datetime.now().strftime('%B %d, %Y')})**
- Transactions: {today[0] if today else 0}
- Revenue: M{today[1] if today else 0:.2f}

**📈 This Week**
- Transactions: {week[0] if week else 0}
- Revenue: M{week[1] if week else 0:.2f}
- Growth: {growth_emoji} {abs(growth):.1f}% vs last week

**✨ Top Performers**
"""
        
        if top_products:
            for i, (name, qty, revenue) in enumerate(top_products, 1):
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "•"
                response += f"\n{medal} **{name}**\n   {int(qty)} units • M{revenue:.2f}"
        else:
            response += "\nNo sales data available yet."
        
        # Add AI insight
        if growth > 10:
            response += "\n\n🎉 **Excellent growth!** Consider stocking more top sellers for Lesotho market demand."
        elif growth < -10:
            response += "\n\n⚠️ **Sales declining.** Check competitor prices in Maseru. Consider promotions."
        
        return response
    
    def _cmd_forecast(self, product_id: Optional[int]) -> str:
        """Simple forecast"""
        if not product_id:
            return "Please specify a product ID. Example: `/forecast 1`"
        
        product = execute_query(
            "SELECT name, qty FROM products WHERE id = ?",
            (product_id,), fetchone=True
        )
        
        if not product:
            return f"Product ID {product_id} not found."
        
        avg_sales = execute_query("""
            SELECT COALESCE(SUM(qty), 0) / 7.0 FROM sales 
            WHERE product_id = ? AND date >= date('now', '-7 days')
        """, (product_id,), fetchone=True)[0]
        
        forecast_7d = round(avg_sales * 7)
        
        return f"""📈 **7-Day Sales Forecast: {product[0]}**

Based on recent trends:
- **Predicted sales**: {forecast_7d} units
- **Current stock**: {product[1]} units
- **Daily average**: {avg_sales:.1f} units

{'✅ Stock is sufficient' if product[1] >= forecast_7d else '⚠️ Consider reordering soon'}
"""
    
    def _cmd_alerts(self, user_id: int) -> str:
        """Low stock alerts"""
        alerts = get_reorder_alerts(lead_time_days=7, safety_stock_days=3)
        
        if not alerts:
            return "✅ All stock levels are healthy! No urgent reorders needed."
        
        response = f"⚠️ **Reorder Alerts** ({len(alerts)} items)\n\n"
        
        for alert in alerts[:5]:
            urgency_emoji = "🔴" if alert['urgency'] == 'critical' else "🟡"
            response += f"{urgency_emoji} **{alert['product_name']}**\n"
            response += f"   Current: {alert['current_stock']} units\n"
            response += f"   Reorder: {alert['reorder_qty']} units\n\n"
        
        response += "💡 *Contact your suppliers in Maseru to restock these items.*"
        return response
    
    def _get_business_context(self, query: str, user_id: int) -> Dict:
        """Retrieve relevant business context"""
        try:
            # RAG search
            relevant_docs = self.rag.search(query, top_k=3, llm_handler=self.llm)
            
            # Get metrics
            metrics = execute_query("""
                SELECT 
                    (SELECT COUNT(*) FROM products) as products,
                    (SELECT COUNT(*) FROM customers) as customers,
                    (SELECT COALESCE(SUM(total), 0) FROM invoices 
                     WHERE date >= date('now', '-30 days')) as revenue_30d,
                    (SELECT COUNT(*) FROM invoices 
                     WHERE date >= date('now', '-7 days')) as sales_7d
            """, fetchone=True)
            
            return {
                'relevant_data': relevant_docs,
                'metrics': {
                    'products': metrics[0] if metrics else 0,
                    'customers': metrics[1] if metrics else 0,
                    'revenue_30d': float(metrics[2]) if metrics else 0,
                    'sales_7d': metrics[3] if metrics else 0
                },
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Context retrieval error: {e}")
            return {}
    
    def _build_prompt(self, user_message: str, history: List[Dict], context: Dict) -> str:
        """Build complete prompt"""
        parts = [self.system_prompt, "\n\n"]
        
        # Add current metrics
        if context.get('metrics'):
            m = context['metrics']
            parts.append(f"""Current Business Overview:
- Products: {m['products']}
- Customers: {m['customers']}
- Revenue (30 days): M{m['revenue_30d']:.2f}
- Sales (7 days): {m['sales_7d']} transactions

""")
        
        # Add RAG context
        if context.get('relevant_data'):
            parts.append("Relevant data:\n")
            for i, doc in enumerate(context['relevant_data'][:3], 1):
                parts.append(f"{i}. {doc['content']}\n")
            parts.append("\n")
        
        # Add history
        if history:
            parts.append("Recent conversation:\n")
            for turn in history[-3:]:  # Last 3 turns only
                parts.append(f"User: {turn['user_message']}\n")
                parts.append(f"Assistant: {turn['assistant_message']}\n")
            parts.append("\n")
        
        # Add current message
        parts.append(f"User: {user_message}\n")
        parts.append("Assistant: ")
        
        return "".join(parts)
    
    # ========================================
    # LESOTHO MARKET INTELLIGENCE
    # ========================================
    
    @functools.lru_cache(maxsize=128)
    def scrape_lesotho_prices(self, product_name: str, category: Optional[str] = None) -> Dict:
        """
        Scrape prices from Lesotho & South Africa markets
        """
        results = {
            "scraped_prices": [],
            "market_avg": 0,
            "suggested_price": 0,
            "sources": [],
            "confidence": 0.0,
            "vat_applicable": True,
            "seasonal_adjustment": 1.0
        }
        
        try:
            # Check if VAT exempt
            is_vat_exempt = any(exempt.lower() in product_name.lower() for exempt in VAT_EXEMPT_CATEGORIES)
            results["vat_applicable"] = not is_vat_exempt
            
            # Get seasonal adjustment
            current_month = datetime.now().month
            seasonal_factor = 1.0
            if category and category in SEASONAL_ADJUSTMENTS:
                seasonal_factor = SEASONAL_ADJUSTMENTS[category].get(current_month, 1.0)
            results["seasonal_adjustment"] = seasonal_factor
            
            # Try to scrape real prices
            search_query = f"{product_name} price Lesotho Maseru shop"
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            
            # DuckDuckGo search
            try:
                ddg_url = f"https://duckduckgo.com/html/?q={search_query.replace(' ', '+')}"
                response = requests.get(ddg_url, headers=headers, timeout=5)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    text = soup.get_text()
                    
                    # Extract Maloti prices
                    maloti_prices = re.findall(r'M\s?(\d{1,5}\.?\d{0,2})', text)
                    for price_str in maloti_prices[:10]:
                        try:
                            price = float(price_str)
                            if 1.0 < price < 50000:
                                results["scraped_prices"].append(price)
                                results["sources"].append("Lesotho Market")
                        except ValueError:
                            continue
                    
                    # Extract Rand prices (convert 1:1)
                    rand_prices = re.findall(r'R\s?(\d{1,5}\.?\d{0,2})', text)
                    for price_str in rand_prices[:5]:
                        try:
                            price = float(price_str)
                            if 1.0 < price < 50000:
                                results["scraped_prices"].append(price)
                                results["sources"].append("SA Market (converted)")
                        except ValueError:
                            continue
            except Exception as e:
                logger.warning(f"Web scraping failed: {e}")
            
            # Fallback to market intelligence
            if not results["scraped_prices"]:
                min_price, max_price = LESOTHO_PRICE_RANGES.get(category, (50.0, 500.0))
                avg = (min_price + max_price) / 2
                results["scraped_prices"] = [avg * 0.85, avg, avg * 1.15]
                results["sources"].append("Lesotho Market Intelligence")
            
            # Calculate final price
            if results["scraped_prices"]:
                base_avg = statistics.mean(results["scraped_prices"])
                
                # Apply seasonal adjustment
                adjusted_avg = base_avg * seasonal_factor
                
                # Apply VAT if applicable
                if results["vat_applicable"]:
                    results["market_avg"] = round(adjusted_avg * (1 + VAT_RATE), 2)
                    results["suggested_price"] = round(results["market_avg"] * 0.95, 2)  # 5% below market
                else:
                    results["market_avg"] = round(adjusted_avg, 2)
                    results["suggested_price"] = round(results["market_avg"] * 0.95, 2)
                
                results["confidence"] = min(0.95, len(results["scraped_prices"]) / 10.0 + 0.5)
            
            return results
            
        except Exception as e:
            logger.error(f"Price scraping error: {e}")
            # Return safe defaults
            min_p, max_p = LESOTHO_PRICE_RANGES.get(category, (50.0, 300.0))
            avg_price = (min_p + max_p) / 2
            return {
                "scraped_prices": [avg_price],
                "market_avg": avg_price,
                "suggested_price": avg_price * 0.95,
                "sources": ["Default Estimate"],
                "confidence": 0.5,
                "vat_applicable": not is_vat_exempt,
                "seasonal_adjustment": seasonal_factor
            }
    
    def predict_category(self, product_name: str) -> tuple:
        """Predict product category with high accuracy"""
        CATEGORY_PATTERNS = {
            "Beverages": [r'\b(coffee|tea|juice|soda|water|drink|cola|sprite|fanta|maluti|beer)\b'],
            "Food": [r'\b(bread|rice|pasta|flour|sugar|meat|chicken|papa|pap|maize|mealie)\b'],
            "Health": [r'\b(medicine|vitamin|pill|soap|shampoo|sanitizer|clinic|pharmacy)\b'],
            "Stationery": [r'\b(pen|pencil|notebook|paper|eraser|ruler|exercise book|school)\b'],
            "Electronics": [r'\b(phone|charger|battery|headphone|laptop|tablet|computer|vodacom)\b'],
            "Home": [r'\b(towel|blanket|pillow|curtain|plate|cup|glass|basotho hat|kobo)\b'],
            "Cleaning": [r'\b(detergent|bleach|cleaner|disinfectant|mop|broom|jik|sunlight)\b'],
            "Clothing": [r'\b(shirt|pants|dress|shoes|jacket|hat|socks|uniform|leshoeshoe)\b'],
            "School": [r'\b(uniform|bag|lunch|supplies|textbook|calculator|backpack)\b'],
        }
        
        name_lower = product_name.lower()
        scores = defaultdict(int)
        
        for category, patterns in CATEGORY_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, name_lower):
                    scores[category] += 100
        
        if not scores:
            return ("Uncategorized", 0.5)
        
        best = max(scores.items(), key=lambda x: x[1])
        confidence = min(1.0, best[1] / 100.0)
        return (best[0], confidence)
    
    def suggest_price_with_intelligence(self, product_name: str, category: str) -> Dict:
        """
        Complete price suggestion with Lesotho market intelligence
        """
        market_data = self.scrape_lesotho_prices(product_name, category)
        
        current_month = datetime.now().month
        month_name = datetime.now().strftime("%B")
        
        reasoning = f"Based on Lesotho market data"
        if market_data["seasonal_adjustment"] != 1.0:
            if market_data["seasonal_adjustment"] > 1.0:
                reasoning += f" with {month_name} seasonal increase (+{(market_data['seasonal_adjustment']-1)*100:.0f}%)"
            else:
                reasoning += f" with {month_name} seasonal decrease ({(1-market_data['seasonal_adjustment'])*100:.0f}%)"
        
        if not market_data["vat_applicable"]:
            reasoning += ". VAT-exempt product."
        else:
            reasoning += f". Includes 15% VAT."
        
        return {
            "suggested_price": market_data["suggested_price"],
            "min_price": min(market_data["scraped_prices"]) if market_data["scraped_prices"] else 10.0,
            "max_price": max(market_data["scraped_prices"]) if market_data["scraped_prices"] else 100.0,
            "market_avg": market_data["market_avg"],
            "confidence": market_data["confidence"],
            "reasoning": reasoning,
            "sources": market_data["sources"],
            "vat_applicable": market_data["vat_applicable"],
            "seasonal_factor": market_data["seasonal_adjustment"],
            "currency": CURRENCY
        }


# ========================================
# HELPER FUNCTIONS
# ========================================
_engine_instance = None

def get_ai_engine():
    """Get singleton AI engine instance"""
    global _engine_instance
    if _engine_instance is None:
        from .biztrack_db import get_connection
        engine = UnifiedAIEngine(get_connection())
        if engine.initialize():
            _engine_instance = engine
    return _engine_instance

def get_ai_response(user_message: str, user_id: int, 
                   conversation_id: Optional[str] = None) -> Generator[str, None, None]:
    """Simple interface for AI responses"""
    engine = get_ai_engine()
    if not engine:
        yield "AI system is currently unavailable. Please ensure the llama.cpp model is properly loaded."
        return
    
    for token in engine.chat(user_message, user_id, conversation_id, stream=True):
        yield token

def quick_insight(query: str, user_id: int) -> str:
    """Quick AI insight without conversation context"""
    engine = get_ai_engine()
    if not engine:
        return "AI system unavailable."
    
    response = ""
    for token in engine.chat(query, user_id, stream=False):
        response += token
    return response

logger.info("✅ Unified AI Engine loaded successfully")
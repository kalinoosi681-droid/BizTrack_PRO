"""
Email utilities for BizTrack PRO
Handles invoice and notification email sending
"""
from flask import current_app
from flask_mail import Mail, Message
import logging

logger = logging.getLogger(__name__)

# Initialize Mail (will be set in app factory)
mail = Mail()


def init_email(app):
    """Initialize email extension with app"""
    mail.init_app(app)
    return mail


def send_invoice_email(recipient_email, invoice_data, items_data):
    """
    Send invoice via email with HTML formatting
    
    Args:
        recipient_email (str): Recipient email address
        invoice_data (dict): Invoice data with keys: id, invoice_number, total, date, customer_name
        items_data (list): List of invoice line items with keys: product_name, quantity, price, subtotal
    
    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        if not recipient_email:
            return False, "❌ Recipient email not provided"
        
        if not current_app.config['MAIL_USERNAME']:
            return False, "⚠️ Email not configured on server. Contact administrator."
        
        # Build HTML content for invoice
        html_content = _generate_invoice_html(invoice_data, items_data)
        
        # Create message
        msg = Message(
            subject=f"Invoice #{invoice_data.get('invoice_number', 'N/A')} from BizTrack",
            recipients=[recipient_email],
            html=html_content
        )
        
        # Send email
        mail.send(msg)
        logger.info(f"Invoice #{invoice_data.get('invoice_number')} sent to {recipient_email}")
        return True, "✅ Invoice sent successfully!"
        
    except Exception as e:
        logger.error(f"Email sending failed: {str(e)}")
        return False, f"❌ Email sending failed: {str(e)}"


def _generate_invoice_html(invoice_data, items_data):
    """Generate HTML email content for invoice"""
    
    # Build items table rows
    items_html = ""
    for item in items_data:
        items_html += f"""
        <tr>
            <td style="padding: 8px; border-bottom: 1px solid #ddd;">{item.get('product_name', 'N/A')}</td>
            <td style="padding: 8px; border-bottom: 1px solid #ddd; text-align: center;">{item.get('quantity', 0)}</td>
            <td style="padding: 8px; border-bottom: 1px solid #ddd; text-align: right;">${item.get('price', 0):.2f}</td>
            <td style="padding: 8px; border-bottom: 1px solid #ddd; text-align: right;">${item.get('subtotal', 0):.2f}</td>
        </tr>
        """
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: Arial, sans-serif; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background-color: #007bff; color: white; padding: 20px; text-align: center; border-radius: 5px; }}
            .invoice-details {{ margin: 20px 0; }}
            .detail-row {{ display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #eee; }}
            .detail-label {{ font-weight: bold; }}
            table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
            th {{ background-color: #f5f5f5; padding: 12px; text-align: left; border-bottom: 2px solid #ddd; }}
            td {{ padding: 8px; border-bottom: 1px solid #ddd; }}
            .total-row {{ background-color: #f5f5f5; font-weight: bold; }}
            .footer {{ margin-top: 30px; text-align: center; color: #666; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Invoice</h1>
            </div>
            
            <div class="invoice-details">
                <div class="detail-row">
                    <span class="detail-label">Invoice Number:</span>
                    <span>#{invoice_data.get('invoice_number', 'N/A')}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Customer:</span>
                    <span>{invoice_data.get('customer_name', 'N/A')}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Date:</span>
                    <span>{invoice_data.get('date', 'N/A')}</span>
                </div>
            </div>
            
            <table>
                <thead>
                    <tr>
                        <th>Product</th>
                        <th style="text-align: center;">Quantity</th>
                        <th style="text-align: right;">Unit Price</th>
                        <th style="text-align: right;">Subtotal</th>
                    </tr>
                </thead>
                <tbody>
                    {items_html}
                    <tr class="total-row">
                        <td colspan="3" style="text-align: right; padding-right: 8px;">Total:</td>
                        <td style="text-align: right;">${invoice_data.get('total', 0):.2f}</td>
                    </tr>
                </tbody>
            </table>
            
            <div class="footer">
                <p>Thank you for your business!</p>
                <p>This is an automated email from BizTrack PRO. Please do not reply.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return html

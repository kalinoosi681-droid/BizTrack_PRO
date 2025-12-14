"""
Enhanced Email utilities for BizTrack PRO
Professional invoice emails with Lesotho branding
Supports Gmail and Outlook/Office365
"""
from flask import current_app
from flask_mail import Mail, Message
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Initialize Mail (will be set in app factory)
mail = Mail()


def init_email(app):
    """Initialize email extension with app"""
    mail.init_app(app)
    
    # Log email configuration (without sensitive data)
    logger.info(f"✅ Email configured: {app.config.get('MAIL_SERVER')}:{app.config.get('MAIL_PORT')}")
    logger.info(f"📧 Sender: {app.config.get('MAIL_DEFAULT_SENDER')}")
    
    return mail


def send_invoice_email(recipient_email, invoice_data, items_data):
    """
    Send professional invoice via email with HTML formatting
    
    Args:
        recipient_email (str): Recipient email address
        invoice_data (dict): Invoice data with keys: id, invoice_number, total, date, customer_name
        items_data (list): List of invoice line items
    
    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        if not recipient_email:
            return False, "❌ Recipient email not provided"
        
        # Check if email is configured
        if not current_app.config.get('MAIL_USERNAME'):
            return False, ("⚠️ Email not configured. Please set MAIL_USERNAME and MAIL_PASSWORD "
                          "in your environment variables. See config.py for setup instructions.",)
        
        # Build professional HTML content
        html_content = _generate_professional_invoice_html(invoice_data, items_data)
        
        # Create message
        msg = Message(
            subject=f"Invoice #{invoice_data.get('invoice_number', 'N/A')} from BizTrack PRO",
            recipients=[recipient_email],
            html=html_content,
            sender=current_app.config.get('MAIL_DEFAULT_SENDER')
        )
        
        # Add reply-to if needed
        reply_to = current_app.config.get('MAIL_REPLY_TO', 
                                         current_app.config.get('MAIL_USERNAME'))
        if reply_to:
            msg.reply_to = reply_to
        
        # Send email
        mail.send(msg)
        
        logger.info(f"✅ Invoice #{invoice_data.get('invoice_number')} sent to {recipient_email}")
        return True, "✅ Invoice sent successfully!"
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Email sending failed: {error_msg}", exc_info=True)
        
        # Provide helpful error messages
        if "authentication" in error_msg.lower() or "username" in error_msg.lower():
            return False, ("❌ Email authentication failed. Please check your MAIL_USERNAME and MAIL_PASSWORD. "
                          "For Gmail, use an App Password (not your regular password). "
                          "See config.py for setup instructions.",)
        elif "connection" in error_msg.lower() or "timed out" in error_msg.lower():
            return False, f"❌ Connection error: Unable to connect to mail server. Check your internet connection."
        else:
            return False, f"❌ Email failed: {error_msg}"


def _generate_professional_invoice_html(invoice_data, items_data):
    """Generate professional HTML email content for invoice with Lesotho branding"""
    
    # Calculate subtotal and tax
    subtotal = sum(item.get('total_price', 0) for item in items_data)
    tax_rate = 0.15  # 15% VAT in Lesotho
    tax_amount = subtotal * tax_rate
    total = subtotal + tax_amount
    
    # Build items table rows
    items_html = ""
    for item in items_data:
        items_html += f"""
        <tr>
            <td style="padding: 12px; border-bottom: 1px solid #e5e7eb;">{item.get('product_name', 'N/A')}</td>
            <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; text-align: center;">{item.get('qty', 0)}</td>
            <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; text-align: right;">M{item.get('price', 0):.2f}</td>
            <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; text-align: right; font-weight: 600;">M{item.get('total_price', 0):.2f}</td>
        </tr>
        """
    
    # Format date nicely
    try:
        date_obj = datetime.strptime(invoice_data.get('date', ''), '%Y-%m-%d %H:%M:%S')
        formatted_date = date_obj.strftime('%B %d, %Y')
    except:
        formatted_date = invoice_data.get('date', 'N/A')
    
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Invoice #{invoice_data.get('invoice_number', 'N/A')}</title>
    </head>
    <body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f3f4f6;">
        <div style="max-width: 650px; margin: 40px auto; background-color: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
            
            <!-- Header with Lesotho Flag Colors -->
            <div style="background: linear-gradient(135deg, #002868 0%, #009543 100%); color: white; padding: 40px 30px; text-align: center;">
                <h1 style="margin: 0; font-size: 32px; font-weight: 700;">INVOICE</h1>
                <p style="margin: 10px 0 0 0; font-size: 18px; opacity: 0.9;">#{invoice_data.get('invoice_number', 'N/A')}</p>
            </div>
            
            <!-- Business Info -->
            <div style="padding: 30px; border-bottom: 2px solid #e5e7eb;">
                <div style="display: flex; justify-content: space-between; align-items: start;">
                    <div>
                        <h2 style="margin: 0 0 10px 0; font-size: 24px; color: #002868;">BizTrack PRO</h2>
                        <p style="margin: 0; color: #6b7280; line-height: 1.6;">
                            Lithabaneng, Maseru 100<br>
                            Lesotho, 4899<br>
                            📧 support@biztrackpro.ls<br>
                            📞 +266 5800 0000
                        </p>
                    </div>
                    <div style="text-align: right;">
                        <p style="margin: 0 0 5px 0; color: #6b7280; font-size: 14px;"><strong>Invoice Date:</strong></p>
                        <p style="margin: 0; font-size: 16px; color: #111827;">{formatted_date}</p>
                    </div>
                </div>
            </div>
            
            <!-- Customer Info -->
            <div style="padding: 30px; background-color: #f9fafb; border-bottom: 2px solid #e5e7eb;">
                <h3 style="margin: 0 0 15px 0; font-size: 18px; color: #002868;">Bill To:</h3>
                <p style="margin: 0; font-size: 16px; font-weight: 600; color: #111827;">{invoice_data.get('customer_name', 'Valued Customer')}</p>
                <p style="margin: 5px 0 0 0; color: #6b7280;">{invoice_data.get('customer_email', '')}</p>
            </div>
            
            <!-- Invoice Items -->
            <div style="padding: 30px;">
                <table style="width: 100%; border-collapse: collapse;">
                    <thead>
                        <tr style="background-color: #f3f4f6;">
                            <th style="padding: 12px; text-align: left; font-size: 14px; font-weight: 600; color: #374151; border-bottom: 2px solid #e5e7eb;">Item</th>
                            <th style="padding: 12px; text-align: center; font-size: 14px; font-weight: 600; color: #374151; border-bottom: 2px solid #e5e7eb;">Qty</th>
                            <th style="padding: 12px; text-align: right; font-size: 14px; font-weight: 600; color: #374151; border-bottom: 2px solid #e5e7eb;">Unit Price</th>
                            <th style="padding: 12px; text-align: right; font-size: 14px; font-weight: 600; color: #374151; border-bottom: 2px solid #e5e7eb;">Total</th>
                        </tr>
                    </thead>
                    <tbody>
                        {items_html}
                    </tbody>
                </table>
            </div>
            
            <!-- Totals -->
            <div style="padding: 0 30px 30px 30px;">
                <div style="background-color: #f9fafb; padding: 20px; border-radius: 8px;">
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr>
                            <td style="padding: 8px 0; text-align: right; color: #6b7280;">Subtotal:</td>
                            <td style="padding: 8px 0; text-align: right; font-weight: 600; color: #111827; width: 120px;">M{subtotal:.2f}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0; text-align: right; color: #6b7280;">VAT (15%):</td>
                            <td style="padding: 8px 0; text-align: right; font-weight: 600; color: #111827;">M{tax_amount:.2f}</td>
                        </tr>
                        <tr style="border-top: 2px solid #e5e7eb;">
                            <td style="padding: 12px 0 0 0; text-align: right; font-size: 18px; font-weight: 700; color: #002868;">TOTAL:</td>
                            <td style="padding: 12px 0 0 0; text-align: right; font-size: 24px; font-weight: 700; color: #009543;">M{total:.2f}</td>
                        </tr>
                    </table>
                </div>
            </div>
            
            <!-- Payment Info -->
            <div style="padding: 30px; background-color: #f0fdf4; border-top: 2px solid #e5e7eb;">
                <h3 style="margin: 0 0 15px 0; font-size: 16px; color: #166534;">💳 Payment Information</h3>
                <p style="margin: 0; color: #15803d; line-height: 1.6;">
                    <strong>Bank:</strong> Nedbank Lesotho<br>
                    <strong>Account:</strong> BizTrack PRO<br>
                    <strong>Account Number:</strong> 1234567890<br>
                    <strong>Reference:</strong> INV-{invoice_data.get('invoice_number', 'N/A')}
                </p>
            </div>
            
            <!-- Footer -->
            <div style="padding: 30px; text-align: center; background-color: #f9fafb; border-top: 2px solid #e5e7eb;">
                <p style="margin: 0 0 10px 0; font-size: 18px; font-weight: 600; color: #002868;">Thank you for your business!</p>
                <p style="margin: 0; font-size: 14px; color: #6b7280;">
                    This is an automated email from BizTrack PRO. Please do not reply directly to this email.<br>
                    For inquiries, contact us at support@biztrackpro.ls or call +266 5800 0000.
                </p>
                <p style="margin: 15px 0 0 0; font-size: 12px; color: #9ca3af;">
                    BizTrack PRO &copy; {datetime.now().year}. Proudly serving Lesotho 🇱🇸 
                </p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return html
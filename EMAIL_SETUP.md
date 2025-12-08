# Email Configuration Guide for BizTrack PRO

## Quick Setup

The invoice email feature is now configured and ready to use! Follow these steps to enable it:

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

This installs Flask-Mail which handles email sending.

### 2. Configure Email Provider

Choose one of the following email providers:

#### Option A: Gmail (Recommended for Testing)
1. Go to [Google Account Security](https://myaccount.google.com/security)
2. Enable "2-Step Verification" if not already enabled
3. Go to [App Passwords](https://myaccount.google.com/apppasswords)
4. Select "Mail" and "Windows Computer"
5. Google will generate a 16-character password
6. Copy this password to your `.env` file (see below)

#### Option B: SendGrid
1. Create account at [SendGrid](https://sendgrid.com)
2. Create API key with "Mail Send" permission
3. Use API key as password in config

#### Option C: Office 365 / Outlook
1. Use your Outlook email and password
2. If you have 2FA enabled, use an app-specific password

### 3. Create .env File

Copy `.env.example` to `.env` and fill in your email credentials:

```bash
cp .env.example .env
```

Edit `.env` with your chosen provider's settings:

**Gmail Example:**
```
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-16-char-app-password
MAIL_DEFAULT_SENDER=your-email@gmail.com
```

**SendGrid Example:**
```
MAIL_SERVER=smtp.sendgrid.net
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=apikey
MAIL_PASSWORD=SG.your-sendgrid-api-key-here
```

### 4. Restart Application

```bash
python run.py
```

## Using Email Feature

1. **Navigate to Invoice Detail Page**
   - Go to Invoices → Click on any invoice

2. **Click "Send via Email" Button**
   - Located next to Print and Download PDF buttons
   - Button is in the top-right toolbar

3. **Enter Recipient Email**
   - A prompt will ask for the email address
   - Pre-fills with customer email if available
   - Can send to any email address

4. **Confirmation**
   - You'll see a success message when email is sent
   - Invoice is sent as formatted HTML email
   - Includes invoice number, customer name, and all line items

## Testing Email Without Full Setup

You can test the feature without configuring real email:

1. **Development Mode**: Set these dummy values in `.env`:
   ```
   MAIL_SERVER=localhost
   MAIL_PORT=1025
   ```
   Then run a local test SMTP server:
   ```bash
   python -m smtpd -n -c DebuggingServer localhost:1025
   ```
   This will print emails to console instead of sending them.

2. **Troubleshooting**:
   - Check app logs for email errors
   - Verify credentials are correct
   - Ensure firewall allows SMTP port (usually 587)
   - Gmail users: use App Password, not regular password

## Features Implemented

✅ **Email Button**: Added to invoice detail page toolbar
✅ **API Endpoint**: `/api/invoice/<iid>/email` POST endpoint
✅ **HTML Template**: Professional invoice email layout
✅ **Error Handling**: User-friendly error messages
✅ **Async UI**: Loading state feedback with spinner
✅ **Pre-fill**: Auto-suggests customer email if available
✅ **Security**: CSRF token validation on API endpoint

## Email Content

The email includes:
- Professional HTML formatting with BizTrack branding
- Invoice number and reference
- Customer name and date
- Complete line item table with products, quantities, and prices
- Total invoice amount
- Thank you message

## Troubleshooting

**"Email not configured on server" error**
- Ensure MAIL_USERNAME is set in environment variables
- Check that `.env` file exists and is loaded

**"Email sending failed" error**
- Verify SMTP credentials are correct
- Check firewall/network allows outbound SMTP (port 587)
- Gmail users must use App Password, not regular password
- Check email account has "Less Secure App Access" enabled (if applicable)

**Button not responding**
- Check browser console for JavaScript errors
- Verify Flask-Mail is installed: `pip show Flask-Mail`
- Ensure API endpoint is registered: check app logs on startup

## Environment Variables Reference

| Variable | Purpose | Example |
|----------|---------|---------|
| MAIL_SERVER | SMTP server address | smtp.gmail.com |
| MAIL_PORT | SMTP port (usually 587 for TLS) | 587 |
| MAIL_USE_TLS | Enable TLS encryption | True |
| MAIL_USERNAME | Email account username | user@gmail.com |
| MAIL_PASSWORD | Email account password or app password | app-password-here |
| MAIL_DEFAULT_SENDER | Sender email (appears in "From" field) | noreply@biztrack.com |

## Next Steps

- Set up email provider credentials in `.env`
- Restart the application
- Test by sending an invoice to yourself
- Share feature with team members

For more help, check `CONFIG_GUIDE.md` or raise an issue on the project repository.

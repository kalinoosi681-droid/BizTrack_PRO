# ========================================
# config.py - Email Configuration
# ========================================
"""
Configuration management for BizTrack PRO
Supports Gmail and Outlook/Office365
"""
import os
import secrets
from datetime import timedelta

class Config:
    """Base configuration"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///biztrack.db')
    PERMANENT_SESSION_LIFETIME = timedelta(hours=2)
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    WTF_CSRF_ENABLED = True
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max
    
    # ========================================
    # EMAIL CONFIGURATION - GMAIL & OUTLOOK
    # ========================================
    
    # Email Provider Selection (gmail or outlook)
    EMAIL_PROVIDER = os.environ.get('EMAIL_PROVIDER', 'gmail').lower()
    
    # Gmail Configuration
    GMAIL_SERVER = 'smtp.gmail.com'
    GMAIL_PORT = 587
    GMAIL_USE_TLS = True
    
    # Outlook/Office365 Configuration
    OUTLOOK_SERVER = 'smtp-mail.outlook.com'
    OUTLOOK_PORT = 587
    OUTLOOK_USE_TLS = True
    
    # Dynamic Configuration Based on Provider
    @property
    def MAIL_SERVER(self):
        if self.EMAIL_PROVIDER == 'gmail':
            return self.GMAIL_SERVER
        elif self.EMAIL_PROVIDER in ['outlook', 'office365']:
            return self.OUTLOOK_SERVER
        return os.environ.get('MAIL_SERVER', self.GMAIL_SERVER)
    
    @property
    def MAIL_PORT(self):
        if self.EMAIL_PROVIDER == 'gmail':
            return self.GMAIL_PORT
        elif self.EMAIL_PROVIDER in ['outlook', 'office365']:
            return self.OUTLOOK_PORT
        return int(os.environ.get('MAIL_PORT', 587))
    
    @property
    def MAIL_USE_TLS(self):
        return True  # Both Gmail and Outlook use TLS
    
    # Email Credentials (Must be set in environment variables)
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 
                                         os.environ.get('MAIL_USERNAME', 'noreply@biztrack.com'))
    
    # Email Configuration Validation
    MAIL_SUPPRESS_SEND = False  # Set to True to prevent sending emails in development
    MAIL_MAX_EMAILS = 50  # Max emails per connection
    MAIL_ASCII_ATTACHMENTS = False
    
    
class DevelopmentConfig(Config):
    DEBUG = True
    SESSION_COOKIE_SECURE = False  # Allow HTTP in dev
    MAIL_SUPPRESS_SEND = False  # Enable emails in dev for testing
    
class ProductionConfig(Config):
    DEBUG = False
    
    @property
    def SECRET_KEY(self):
        key = os.environ.get('SECRET_KEY')
        if not key:
            raise ValueError("SECRET_KEY environment variable must be set in production!")
        return key
    
    @property
    def MAIL_USERNAME(self):
        username = os.environ.get('MAIL_USERNAME')
        if not username:
            raise ValueError("MAIL_USERNAME must be set in production!")
        return username
    
    @property
    def MAIL_PASSWORD(self):
        password = os.environ.get('MAIL_PASSWORD')
        if not password:
            raise ValueError("MAIL_PASSWORD must be set in production!")
        return password

class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    MAIL_SUPPRESS_SEND = True  # Never send real emails in tests

config_map = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig
}


# ========================================
# EMAIL SETUP INSTRUCTIONS
# ========================================
"""
GMAIL SETUP:
1. Go to https://myaccount.google.com/security
2. Enable 2-Step Verification
3. Generate an App Password: https://myaccount.google.com/apppasswords
4. Use the 16-character app password (not your Gmail password)

Environment Variables:
export EMAIL_PROVIDER=gmail
export MAIL_USERNAME=your_email@gmail.com
export MAIL_PASSWORD=your_16_char_app_password

OUTLOOK/OFFICE365 SETUP:
1. Go to https://account.microsoft.com/security
2. Enable 2-Step Verification
3. Generate an App Password
4. Use the app password (not your Outlook password)

Environment Variables:
export EMAIL_PROVIDER=outlook
export MAIL_USERNAME=your_email@outlook.com
export MAIL_PASSWORD=your_app_password

WINDOWS (.env file):
EMAIL_PROVIDER=gmail
MAIL_USERNAME=your_email@gmail.com
MAIL_PASSWORD=your_app_password
MAIL_DEFAULT_SENDER=BizTrack PRO <your_email@gmail.com>
"""
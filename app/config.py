import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess'
    MYSQL_HOST = os.environ.get('MYSQL_HOST') or 'localhost'
    MYSQL_USER = os.environ.get('MYSQL_USER') or 'root'
    MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD') or ''
    MYSQL_DB = os.environ.get('MYSQL_DB') or 'webarticle'
    
    # Payment configuration
    STRIPE_PUBLIC_KEY = os.environ.get('STRIPE_PUBLIC_KEY') or 'pk_test_yourkeyhere'
    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY') or 'sk_test_yourkeyhere'
    PAYPAL_CLIENT_ID = os.environ.get('PAYPAL_CLIENT_ID') or 'your-paypal-client-id'
    PAYPAL_CLIENT_SECRET = os.environ.get('PAYPAL_CLIENT_SECRET') or 'your-paypal-client-secret'
    
    # Email configuration with generic defaults instead of Gmail
    SMTP_SERVER = os.environ.get('SMTP_SERVER', '')
    SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
    SMTP_USERNAME = os.environ.get('SMTP_USERNAME', '')
    SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD', '')
    SENDER_EMAIL = os.environ.get('SENDER_EMAIL', SMTP_USERNAME)
    SENDER_NAME = os.environ.get('SENDER_NAME', 'WebArticle Admin')
    
    # Admin email for system notifications
    ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL') or SMTP_USERNAME
    
    # Email debugging and testing
    EMAIL_DEBUG = os.environ.get('EMAIL_DEBUG', 'True').lower() == 'true'
    EMAIL_STARTUP_TEST = os.environ.get('EMAIL_STARTUP_TEST', 'False').lower() == 'true'
    
    # Development mode
    DEV_MODE = os.environ.get('DEV_MODE', 'True').lower() == 'true'
    
    # When in dev mode, this enables console output of OTPs and emails
    CONSOLE_OUTPUT = os.environ.get('CONSOLE_OUTPUT', 'True').lower() == 'true'
    
    # Email debugging and testing
    CONSOLE_EMAIL_OUTPUT = os.environ.get('CONSOLE_EMAIL_OUTPUT', 'True').lower() == 'true' 
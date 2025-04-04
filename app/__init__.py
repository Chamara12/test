from flask import Flask
from app.config import Config
from app.models import Database, Settings, ModelSettings, EmailSettings, UserCredits, Article
from apscheduler.schedulers.background import BackgroundScheduler
import atexit
from datetime import datetime

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Make config available in templates
    @app.context_processor
    def inject_config():
        return {'config': app.config}
    
    # Initialize database tables
    with app.app_context():
        from app.models import Database
        Database.create_tables()
        
        # Migrate email settings from config to database
        migrate_email_settings(app)
        
        # Test email configuration on startup if enabled
        if app.config.get('EMAIL_STARTUP_TEST'):
            test_email_on_startup(app)
    
    # Register Jinja filters
    @app.template_filter('intcomma')
    def intcomma(value):
        """Format number with commas as thousands separator"""
        try:
            if isinstance(value, (int, float)):
                return "{:,}".format(int(value))
            return value
        except (ValueError, TypeError):
            return value
    
    @app.template_filter('price')
    def format_price(value):
        """Format value as price"""
        try:
            if isinstance(value, (int, float)):
                return "{:.2f}".format(float(value))
            return value
        except (ValueError, TypeError):
            return value
    
    @app.template_filter('datetime')
    def format_datetime(value):
        """Format datetime value"""
        if value is None:
            return "Never"
        elif isinstance(value, str):
            try:
                # Try to parse string to datetime
                from datetime import datetime
                value = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
            except:
                return value
        
        try:
            return value.strftime('%Y-%m-%d %H:%M')
        except:
            return value
    
    @app.template_filter('format_number')
    def format_number(value):
        """Format large numbers with commas as thousands separators"""
        if value is None:
            return '0'
        return "{:,}".format(int(value))
    
    # Ensure settings table exists
    try:
        Settings.create_settings_table()
    except Exception as e:
        print(f"Error creating settings table: {e}")
    
    # Make sure model settings table exists
    try:
        ModelSettings.create_model_settings_table()
    except Exception as e:
        print(f"Error creating model settings table: {e}")
    
    from app.routes.auth import auth_bp
    from app.routes.main import main_bp
    from app.routes.admin import admin_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp)
    
    @app.route('/start')
    def start():
        Database.create_tables()
        return "Database tables created successfully"
    
    # Set up scheduled tasks
    scheduler = BackgroundScheduler()
    
    # Check expired credits daily
    scheduler.add_job(func=check_expired_credits, trigger="interval", hours=24)
    
    # Auto-delete old articles daily
    scheduler.add_job(func=delete_old_articles, trigger="interval", hours=24)
    
    scheduler.start()
    
    # Shut down the scheduler when exiting the app
    atexit.register(lambda: scheduler.shutdown())
    
    return app 

def migrate_email_settings(app):
    """Migrate email settings from config to database if they don't exist"""
    from app.models import EmailSettings
    
    # Check if email settings exist in database
    try:
        settings = EmailSettings.get_all_settings()
        
        # If no settings found, copy from config if available
        if not settings:
            print("Initializing email settings from environment...")
            smtp_server = app.config.get('SMTP_SERVER')
            smtp_port = app.config.get('SMTP_PORT')
            smtp_username = app.config.get('SMTP_USERNAME')
            smtp_password = app.config.get('SMTP_PASSWORD')
            sender_email = app.config.get('SENDER_EMAIL')
            sender_name = app.config.get('SENDER_NAME')
            
            # Only update if we have at least server and username
            if smtp_server and smtp_username:
                EmailSettings.set_setting('smtp_server', smtp_server, False)
                EmailSettings.set_setting('smtp_port', str(smtp_port), False)
                EmailSettings.set_setting('smtp_username', smtp_username, False)
                
                if smtp_password:
                    EmailSettings.set_setting('smtp_password', smtp_password, True)
                
                if sender_email:
                    EmailSettings.set_setting('sender_email', sender_email, False)
                    
                if sender_name:
                    EmailSettings.set_setting('sender_name', sender_name, False)
                    
                # Default to disabled until explicitly enabled by admin
                EmailSettings.set_setting('email_enabled', 'false', False)
                
                print("Email settings migrated from environment to database")
    except Exception as e:
        print(f"Error migrating email settings: {e}")

def test_email_on_startup(app):
    """Test email settings on application startup"""
    from app.models import EmailSettings
    from app.utils import send_email
    from datetime import datetime  # Import the datetime class directly
    
    # Only run test if email is enabled in database
    email_enabled = EmailSettings.get_setting('email_enabled', 'false').lower() == 'true'
    if not email_enabled:
        print("Email startup test skipped: Email sending is disabled in settings")
        return
    
    # Get admin email to send test to
    admin_email = app.config.get('ADMIN_EMAIL')
    if not admin_email:
        print("Email startup test skipped: No ADMIN_EMAIL configured")
        return
    
    try:
        print(f"Testing email configuration by sending to {admin_email}...")
        
        subject = "WebArticle Startup Test"
        html_content = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 5px;">
            <h2 style="color: #7D4BCB; text-align: center;">WebArticle Startup Test</h2>
            <p style="font-size: 16px; line-height: 1.5; color: #333;">The application has started successfully and email functionality is working.</p>
            <p style="font-size: 16px; line-height: 1.5; color: #333;">Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
        """
        
        success = send_email(admin_email, subject, html_content)
        
        if success:
            print("✅ Email configuration test successful")
        else:
            print("❌ Email configuration test failed")
    except Exception as e:
        print(f"❌ Error during email startup test: {e}")

def check_expired_credits():
    """Check for and expire any credits that have passed their expiration date"""
    print(f"[{datetime.now()}] Checking for expired credits...")
    expired_count = UserCredits.check_and_expire_credits()
    print(f"[{datetime.now()}] Expired {expired_count} credit transactions")

def delete_old_articles():
    """Delete articles that are older than the auto-delete setting"""
    print(f"[{datetime.now()}] Checking for old articles to delete...")
    deleted_count = Article.delete_old_articles()
    print(f"[{datetime.now()}] Deleted {deleted_count} old articles") 
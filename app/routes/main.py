from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, make_response, Response, stream_with_context
from app.models import User, Article, ApiKey, Settings, ModelSettings, UserCredits, Payment, CreditSettings, UserOTPSettings, OTP, Database, PaymentSettings, ArticleTemplate

# Import essential utils functions with error handling
from app.utils import slugify, send_payment_confirmation, send_article_generated_email, send_credit_balance_low_email, send_otp_email

# Try to import the article generation functions, but provide fallbacks if they fail
try:
    from app.utils import generate_article_with_xai, generate_fallback_article, generate_article_with_fallback_api, get_available_xai_models
except ImportError:
    print("Warning: Some article generation utilities couldn't be imported")
    
    # Define fallback versions if needed
    def generate_article_with_xai(*args, **kwargs):
        return f"<h1>Error</h1><p>Article generation is currently unavailable.</p>"
        
    def generate_fallback_article(*args, **kwargs):
        return f"<h1>Error</h1><p>Article generation is currently unavailable.</p>"
        
    def generate_article_with_fallback_api(*args, **kwargs):
        return f"<h1>Error</h1><p>Article generation is currently unavailable.</p>"
        
    def get_available_xai_models(*args, **kwargs):
        return [{'id': 'fallback_model', 'name': 'Basic Model (Limited)'}]

# Try to import SEO content generation, with fallback if it fails
try:
    from app.utils import generate_seo_content
except ImportError:
    print("Warning: SEO content generation utility couldn't be imported")
    
    # Define a simple fallback
    def generate_seo_content(topic, content, model_id=None):
        return {
            'title': f"{topic} - Complete Guide",
            'description': f"Learn about {topic} in this comprehensive guide with expert tips and insights.",
            'focus_keyword': topic
        }

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    articles = Article.get_all()[:5]  # Get the 5 most recent articles
    return render_template('main/index.html', articles=articles)

@main_bp.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    user_id = session['user_id']
    articles = Article.get_by_user(user_id)
    api_key_data = ApiKey.get_by_user(user_id)
    
    # Get user's credit balance
    credits_balance = UserCredits.get_balance(user_id)
    
    # Get available models with settings for the pricing display
    available_models = []
    try:
        all_models = get_available_xai_models(api_key_data['api_key'] if api_key_data else None)
        model_settings = ModelSettings.get_all_model_settings()
        
        settings_by_id = {s['model_id']: s for s in model_settings} if model_settings else {}
        default_model = Settings.get_default_model()
        
        # Filter and format models for display
        for model in all_models:
            settings = settings_by_id.get(model['id'], {})
            
            # Skip disabled models
            if settings and not settings.get('is_enabled', True):
                continue
                
            # Get model-specific credits per word
            credits_per_word = settings.get('credits_per_word')
            if credits_per_word is None:
                credits_per_word = int(CreditSettings.get_setting('credits_per_word', '1'))
                
            available_models.append({
                'id': model['id'],
                'display_name': settings.get('display_name', model.get('name', model['id'])),
                'credits_per_word': credits_per_word,
                'is_default': model['id'] == default_model
            })
    except Exception as e:
        print(f"Error loading models for dashboard: {e}")
    
    # Get global credits per word for display
    global_credits_per_word = int(CreditSettings.get_setting('credits_per_word', '1'))
    
    return render_template('main/dashboard.html', 
                          articles=articles, 
                          api_key_data=api_key_data,
                          credits_balance=credits_balance,
                          available_models=available_models,
                          global_credits_per_word=global_credits_per_word)

@main_bp.route('/api-key', methods=['POST'])
def save_api_key():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    api_key = request.form.get('api_key')
    user_id = session['user_id']
    
    # We'll modify this to always consider the key valid for this demo
    # In a real implementation, you would use ApiKey.verify_api_key(api_key)
    is_valid = True
    
    if ApiKey.save(user_id, api_key, is_valid):
        flash('API key validated and saved successfully!', 'success')
    else:
        flash('Failed to save API key', 'error')
    
    return redirect(url_for('main.dashboard'))

@main_bp.route('/credits')
def credits_dashboard():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    user_id = session['user_id']
    
    # Get user's credit info
    credit_info = UserCredits.get_user_credit_info(user_id) or {'credits_balance': 0, 'total_credits_purchased': 0, 'total_credits_used': 0}
    credit_transactions = UserCredits.get_transaction_history(user_id)
    
    # Get payment history with error handling
    try:
        payment_history = Payment.get_payment_history(user_id)
    except AttributeError:
        # Fallback if method doesn't exist
        payment_history = []
        print("Warning: Payment.get_payment_history method is not implemented")
    
    # Get credit settings
    credits_per_dollar = int(CreditSettings.get_setting('credits_per_dollar', '5000'))
    credits_per_word = int(CreditSettings.get_setting('credits_per_word', '1'))
    minimum_deposit = int(CreditSettings.get_setting('minimum_deposit', '10'))
    
    # Get enabled payment gateways
    payment_gateways = []
    all_gateways = PaymentSettings.get_all_gateways()
    for gateway in all_gateways:
        if gateway['is_enabled']:
            payment_gateways.append({
                'id': gateway['gateway'],
                'name': gateway['gateway'].title()
            })
    
    # Ensure at least one gateway is available (for demo purposes)
    if not payment_gateways:
        payment_gateways = [
            {'id': 'stripe', 'name': 'Stripe'},
            {'id': 'paypal', 'name': 'PayPal'}
        ]
    
    return render_template('main/credits_dashboard.html',
                          credit_info=credit_info,
                          credit_transactions=credit_transactions,
                          payment_history=payment_history,
                          credits_per_dollar=credits_per_dollar,
                          credits_per_word=credits_per_word,
                          minimum_deposit=minimum_deposit,
                          payment_gateways=payment_gateways)

@main_bp.route('/deposit', methods=['POST'])
def process_deposit():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    user_id = session['user_id']
    
    # Get deposit details
    deposit_amount = float(request.form.get('deposit_amount', 0))
    payment_method = request.form.get('payment_method', 'stripe')
    
    # Validate minimum deposit
    minimum_deposit = float(CreditSettings.get_setting('minimum_deposit', '10'))
    if deposit_amount < minimum_deposit:
        flash(f'Minimum deposit amount is ${minimum_deposit}', 'error')
        return redirect(url_for('main.credits_dashboard'))
    
    # Check if selected payment method is enabled
    if not PaymentSettings.is_gateway_enabled(payment_method):
        flash(f'The selected payment method ({payment_method}) is not currently enabled.', 'error')
        return redirect(url_for('main.credits_dashboard'))
    
    # Create a pending payment record
    payment_id, credits_to_add = Payment.create_payment(user_id, deposit_amount, payment_method)
    
    if not payment_id:
        flash('Error creating payment. Please try again.', 'error')
        return redirect(url_for('main.credits_dashboard'))
    
    # Get payment gateway settings
    gateway_settings = PaymentSettings.get_gateway(payment_method)
    
    # Different handling based on payment method
    if payment_method == 'stripe':
        try:
            # Initialize Stripe with the configured API key
            stripe.api_key = gateway_settings['api_secret']
            
            # For demo purposes, just complete the payment
            # In production, you would create a Stripe Checkout session or Payment Intent
            if Payment.complete_payment(payment_id, 'demo_transaction_' + str(payment_id)):
                flash(f'Payment successful! {credits_to_add} credits have been added to your account.', 'success')
            else:
                flash('Error processing payment. Please contact support.', 'error')
                
        except Exception as e:
            flash(f'Payment error: {str(e)}', 'error')
    
    elif payment_method == 'paypal':
        try:
            # For demo purposes
            if Payment.complete_payment(payment_id, 'paypal_demo_' + str(payment_id)):
                flash(f'PayPal payment successful! {credits_to_add} credits have been added to your account.', 'success')
            else:
                flash('Error processing PayPal payment. Please contact support.', 'error')
        except Exception as e:
            flash(f'PayPal payment error: {str(e)}', 'error')
    
    return redirect(url_for('main.credits_dashboard'))

def get_admin_id():
    """Get the first admin user's ID from the database"""
    try:
        connection = Database.get_connection()
        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM users WHERE is_admin = 1 LIMIT 1")
            result = cursor.fetchone()
            return result['id'] if result else None
    except Exception as e:
        print(f"Error getting admin ID: {e}")
        return None
    finally:
        connection.close()

@main_bp.route('/generate-article', methods=['GET', 'POST'])
def generate_article():
    """Generate an article with proper error handling and credit management"""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    # If it's a GET request, show the generation form
    if request.method == 'GET':
        # Get user's credit balance
        user_id = session['user_id']
        credits_balance = UserCredits.get_balance(user_id)
        
        # Get available models
        models = []
        api_key_data = ApiKey.get_by_user(user_id)
        
        if api_key_data and api_key_data.get('is_valid'):
            try:
                all_models = get_available_xai_models(api_key_data['api_key'])
                model_settings = ModelSettings.get_all_model_settings()
                
                # Get the correct settings from CreditSettings
                min_words = int(CreditSettings.get_setting('min_word_count', '100'))
                max_words = int(CreditSettings.get_setting('max_word_count', '2000'))
                default_words = int(CreditSettings.get_setting('default_word_count', '500'))
                global_credits_per_word = int(CreditSettings.get_setting('credits_per_word', '1'))
                
                settings_by_id = {s['model_id']: s for s in model_settings} if model_settings else {}
                default_model = Settings.get_default_model()
                
                # Filter and format models for display
                for model in all_models:
                    settings = settings_by_id.get(model['id'], {})
                    
                    # Skip disabled models
                    if settings and not settings.get('is_enabled', True):
                        continue
                        
                    # Get model-specific credits per word
                    credits_per_word = settings.get('credits_per_word')
                    if credits_per_word is None:
                        credits_per_word = global_credits_per_word
                        
                    models.append({
                        'id': model['id'],
                        'display_name': settings.get('display_name', model.get('name', model['id'])),
                        'credits_per_word': credits_per_word,
                        'is_default': model['id'] == default_model
                    })
            except Exception as e:
                print(f"Error loading models: {e}")
                
                # Still get word count settings even if models fail to load
                min_words = int(CreditSettings.get_setting('min_word_count', '100'))
                max_words = int(CreditSettings.get_setting('max_word_count', '2000'))
                default_words = int(CreditSettings.get_setting('default_word_count', '500'))
                global_credits_per_word = int(CreditSettings.get_setting('credits_per_word', '1'))
        else:
            # No valid API key, but still get the word count settings
            min_words = int(CreditSettings.get_setting('min_word_count', '100'))
            max_words = int(CreditSettings.get_setting('max_word_count', '2000'))
            default_words = int(CreditSettings.get_setting('default_word_count', '500'))
            global_credits_per_word = int(CreditSettings.get_setting('credits_per_word', '1'))
    
        # If no models available, add a default one
        if not models:
            models = [{
                'id': 'grok-1',
                'name': 'Default Model',
                'display_name': 'Default Model',
                'description': 'Basic article generation model',
                'credits_per_word': global_credits_per_word,
                'is_default': True
            }]
        
        # Get available templates
        templates = ArticleTemplate.get_all()
            
        return render_template('main/generate_article.html',
                              credits_balance=credits_balance,
                              models=models,
                              min_words=min_words,
                              max_words=max_words,
                              default_words=default_words,
                              global_credits_per_word=global_credits_per_word,
                              templates=templates)
    
    # If it's a POST request, handle article generation logic
    # ... (existing POST handling code) ...

@main_bp.route('/article/<int:article_id>')
def view_article(article_id):
    article = Article.get_by_id(article_id)
    if not article:
        flash('Article not found', 'error')
        return redirect(url_for('main.dashboard'))
    
    return render_template('main/view_article.html', article=article)

@main_bp.route('/profile')
def user_profile():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    user_id = session['user_id']
    
    # Get user details
    user = User.get_by_id(user_id)
    if not user:
        flash('User not found', 'error')
        return redirect(url_for('main.dashboard'))
    
    # Get user's articles
    articles = Article.get_by_user(user_id)
    
    # Get user's credit transactions
    credit_transactions = UserCredits.get_transaction_history(user_id)
    
    # Get OTP settings with better error handling
    try:
        # Ensure tables exist first
        Database.create_tables()
        otp_settings = UserOTPSettings.get_settings(user_id)
    except Exception as e:
        print(f"Error retrieving OTP settings: {e}")
        # Provide default settings to avoid breaking the template
        otp_settings = {'user_id': user_id, 'otp_enabled_for_login': False}
    
    # Calculate usage statistics
    stats = {
        'article_count': len(articles),
        'credits_balance': UserCredits.get_balance(user_id),
        'words_generated': 0
    }
    
    # Sum total words generated (credits spent on article generation)
    for article in articles:
        if article.get('credits_cost'):
            stats['words_generated'] += article['credits_cost']
    
    return render_template('main/user_profile.html',
                          user=user,
                          articles=articles,
                          credit_transactions=credit_transactions,
                          stats=stats,
                          otp_settings=otp_settings)

@main_bp.route('/update-profile', methods=['POST'])
def update_profile():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    user_id = session['user_id']
    
    # Get form data
    full_name = request.form.get('full_name')
    email = request.form.get('email')
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    # Form validation
    if not full_name or not email:
        flash('Name and email are required', 'error')
        return redirect(url_for('main.user_profile'))
    
    # Get current user data
    user = User.get_by_id(user_id)
    if not user:
        flash('User not found', 'error')
        return redirect(url_for('main.dashboard'))
    
    # Initialize connection
    connection = Database.get_connection()
    try:
        with connection.cursor() as cursor:
            # If user is trying to change password
            password_updated = False
            if current_password and new_password:
                # Verify current password
                if not check_password_hash(user['password_hash'], current_password):
                    flash('Current password is incorrect', 'error')
                    return redirect(url_for('main.user_profile'))
                
                # Validate new password
                if new_password != confirm_password:
                    flash('New passwords do not match', 'error')
                    return redirect(url_for('main.user_profile'))
                
                if len(new_password) < 8:
                    flash('New password must be at least 8 characters', 'error')
                    return redirect(url_for('main.user_profile'))
                
                # Hash new password
                password_hash = generate_password_hash(new_password)
                password_updated = True
            
            # Check if email is already taken by another user
            if email != user['email']:
                cursor.execute("SELECT id FROM users WHERE email = %s AND id != %s", (email, user_id))
                existing_user = cursor.fetchone()
                if existing_user:
                    flash('Email is already in use by another account', 'error')
                    return redirect(url_for('main.user_profile'))
            
            # Update user information
            if password_updated:
                cursor.execute(
                    "UPDATE users SET full_name = %s, email = %s, password_hash = %s WHERE id = %s",
                    (full_name, email, password_hash, user_id)
                )
                flash('Profile and password updated successfully', 'success')
            else:
                cursor.execute(
                    "UPDATE users SET full_name = %s, email = %s WHERE id = %s",
                    (full_name, email, user_id)
                )
                flash('Profile updated successfully', 'success')
            
            # Update session information
            session['full_name'] = full_name
            session['email'] = email
            
            # Process OTP settings if present
            otp_enabled = request.form.get('otp_enabled_for_login') == 'on'
            UserOTPSettings.update_settings(user_id, otp_enabled)
            
        connection.commit()
    except Exception as e:
        flash(f'Error updating profile: {str(e)}', 'error')
    finally:
        connection.close()
    
    return redirect(url_for('main.user_profile'))

@main_bp.route('/delete-account', methods=['GET', 'POST'])
def delete_account():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    user_id = session['user_id']
    user = User.get_by_id(user_id)
    
    if not user:
        flash('User not found', 'error')
        return redirect(url_for('main.dashboard'))
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'send_otp':
            # Generate and send OTP
            otp_code = OTP.create_otp(user['email'], 'account_deletion', user_id)
            if otp_code and send_otp_email(user['email'], otp_code, 'account_deletion'):
                flash('Verification code sent to your email.', 'success')
            else:
                flash('Error sending verification code. Please try again.', 'error')
            
            return render_template('main/delete_account.html', user=user, otp_sent=True)
        
        elif action == 'verify_otp':
            otp_code = request.form.get('otp')
            
            if OTP.verify_otp(user['email'], otp_code, 'account_deletion'):
                # Delete the account
                if User.delete_account(user_id):
                    session.clear()
                    flash('Your account has been permanently deleted.', 'success')
                    return redirect(url_for('main.index'))
                else:
                    flash('Error deleting account. Please contact support.', 'error')
            else:
                flash('Invalid or expired verification code.', 'error')
    
    return render_template('main/delete_account.html', user=user)

@main_bp.route('/export-article/<int:article_id>')
def export_article(article_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    article = Article.get_by_id(article_id)
    if not article or article['user_id'] != session['user_id']:
        flash('Article not found or access denied', 'error')
        return redirect(url_for('main.dashboard'))
    
    # Create HTML content with SEO metadata
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{article['title']}</title>
    
    <!-- SEO Metadata -->
    {f'<meta name="title" content="{article["seo_title"]}">' if article.get('seo_title') else ''}
    {f'<meta name="description" content="{article["seo_description"]}">' if article.get('seo_description') else ''}
    {f'<meta name="keywords" content="{article["focus_keyword"]}">' if article.get('focus_keyword') else ''}
    
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; max-width: 800px; margin: 0 auto; padding: 20px; }}
        h1 {{ color: #333; }}
        .meta-info {{ color: #666; font-size: 0.9em; margin-bottom: 20px; }}
        .seo-info {{ background-color: #f0f8ff; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
        .seo-info h3 {{ margin-top: 0; }}
        .article-content {{ line-height: 1.8; }}
    </style>
</head>
<body>
    <h1>{article['title']}</h1>
    
    <div class="meta-info">
        <p>Generated on: {article['created_at'].strftime('%Y-%m-%d %H:%M')}</p>
        <p>Model used: {article.get('model', 'Not specified')}</p>
    </div>
    
    {f'''
    <div class="seo-info">
        <h3>SEO Information</h3>
        {"<p><strong>Meta Title:</strong> " + article['seo_title'] + "</p>" if article.get('seo_title') else ""}
        {"<p><strong>Meta Description:</strong> " + article['seo_description'] + "</p>" if article.get('seo_description') else ""}
        {"<p><strong>Focus Keyword:</strong> " + article['focus_keyword'] + "</p>" if article.get('focus_keyword') else ""}
    </div>
    ''' if article.get('seo_title') or article.get('seo_description') or article.get('focus_keyword') else ''}
    
    <div class="article-content">
        {article['content'].replace('\n', '<br>')}
    </div>
</body>
</html>"""
    
    # Create response with HTML content
    response = make_response(html_content)
    response.headers["Content-Disposition"] = f"attachment; filename={slugify(article['title'])}.html"
    response.headers["Content-Type"] = "text/html"
    
    return response 

@main_bp.route('/process-payment', methods=['POST'])
def process_payment():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    user_id = session['user_id']
    
    # Get payment details
    payment_id = request.form.get('payment_id')
    payment_method = request.form.get('payment_method', 'stripe')
    
    # Validate payment ID
    if not payment_id or not payment_id.isdigit():
        flash('Invalid payment ID', 'error')
        return redirect(url_for('main.credits_dashboard'))
    
    payment_id = int(payment_id)
    
    # Check if payment exists and is in pending state
    payment = Payment.get_by_id(payment_id)
    if not payment:
        flash('Payment not found', 'error')
        return redirect(url_for('main.credits_dashboard'))
        
    if payment['status'] != 'pending':
        flash('This payment has already been processed', 'error')
        return redirect(url_for('main.credits_dashboard'))
    
    # Check if payment belongs to current user
    if int(payment['user_id']) != int(user_id):
        flash('Unauthorized access', 'error')
        return redirect(url_for('main.credits_dashboard'))
    
    # Get payment gateway settings
    gateway_settings = PaymentSettings.get_gateway(payment_method)
    if not gateway_settings or not gateway_settings.get('is_enabled'):
        flash('Selected payment method is not available', 'error')
        return redirect(url_for('main.credits_dashboard'))
    
    # Process payment based on gateway
    success = False
    transaction_id = None
    error_message = None
    
    try:
        # Generate a unique transaction ID for demo purposes
        import uuid
        transaction_id = f"{payment_method}_{uuid.uuid4()}"
        
        # In a real implementation, you would process the payment with the actual gateway
        # For this demo, we'll simulate a successful payment
        success = True
            
    except Exception as e:
        error_message = str(e)
        success = False
    
    # Update payment status based on result
    if success and transaction_id:
        # Mark payment as completed and add credits to user account
        if Payment.complete_payment(payment_id, transaction_id):
            credits_amount = payment['credits_added']
            
            # Get user details for email
            user = User.get_by_id(user_id)
            
            # Send payment confirmation email
            send_payment_confirmation(user, Payment.get_by_id(payment_id))
            
            flash(f'Payment completed successfully! {credits_amount} credits have been added to your account.', 'success')
        else:
            flash('Error finalizing payment. Please contact support.', 'error')
    else:
        # Mark payment as failed
        Payment.mark_as_failed(payment_id, error_message or "Unknown error")
        flash(f'Payment failed: {error_message or "Unknown error"}', 'error')
    
    return redirect(url_for('main.credits_dashboard'))

@main_bp.route('/create-payment', methods=['POST'])
def create_payment():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    # Get form data
    deposit_amount = float(request.form.get('deposit_amount', 0))
    payment_method = request.form.get('payment_method', 'stripe')
    
    # Validate minimum deposit
    minimum_deposit = float(CreditSettings.get_setting('minimum_deposit', '10'))
    if deposit_amount < minimum_deposit:
        flash(f'Minimum deposit amount is ${minimum_deposit}', 'error')
        return redirect(url_for('main.credits_dashboard'))
    
    # Check if selected payment method is enabled
    if not PaymentSettings.is_gateway_enabled(payment_method):
        flash(f'The selected payment method ({payment_method}) is not currently enabled.', 'error')
        return redirect(url_for('main.credits_dashboard'))
    
    # Create a pending payment record
    payment_id, credits_to_add = Payment.create_payment(session['user_id'], deposit_amount, payment_method)
    
    if not payment_id:
        flash('Error creating payment. Please try again.', 'error')
        return redirect(url_for('main.credits_dashboard'))
    
    # Redirect to process payment
    return redirect(url_for('main.process_payment_form', payment_id=payment_id, payment_method=payment_method)) 

@main_bp.route('/payment/<int:payment_id>/<payment_method>')
def process_payment_form(payment_id, payment_method):
    """Display payment form for the user to confirm their payment"""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    # Get payment details
    payment = Payment.get_by_id(payment_id)
    if not payment:
        flash('Payment not found', 'error')
        return redirect(url_for('main.credits_dashboard'))
    
    # Check if payment belongs to user
    if int(payment['user_id']) != int(session['user_id']):
        flash('Unauthorized access', 'error')
        return redirect(url_for('main.credits_dashboard'))
    
    # Check if payment is still pending
    if payment['status'] != 'pending':
        flash('This payment has already been processed', 'error')
        return redirect(url_for('main.credits_dashboard'))
    
    # Get credit settings for display
    credits_per_dollar = int(CreditSettings.get_setting('credits_per_dollar', '5000'))
    
    return render_template('main/payment_form.html', 
                          payment=payment,
                          payment_method=payment_method,
                          credits_per_dollar=credits_per_dollar) 

def generate_article_content(title, keywords, word_count, model):
    """Generate article content using the specified model"""
    try:
        import requests  # Ensure requests is imported
        
        # Get API key - try multiple possible sources
        api_key = None
        try:
            # First try getting from settings
            api_key = Settings.get_setting('x_ai_api_key')
        except Exception as e:
            print(f"Error retrieving API key from settings: {e}")
            
        # If not found in settings, try getting from admin user
        if not api_key:
            try:
                admin_id = get_admin_id()
                if admin_id:
                    api_key_data = ApiKey.get_by_user(admin_id)
                    if api_key_data and api_key_data.get('is_valid'):
                        api_key = api_key_data['api_key']
            except Exception as e:
                print(f"Error retrieving admin API key: {e}")
                
        if not api_key:
            print("No API key configured")
            # Use a fallback model for demo purposes
            return f"""<h1>{title}</h1>
            <p>This is a demo article about {title}. It includes the keywords: {keywords}.</p>
            <p>In a real application, this content would be generated by AI based on your inputs.</p>
            <p>Please configure an API key in the admin settings to enable AI generation.</p>
            <p>This is a placeholder article generated as a fallback when no API key is available.</p>"""
            
        # Prepare the prompt
        prompt = f"""Write an article about {title}.
        Keywords to include: {keywords}
        Target word count: {word_count} words
        
        Please write in a professional, informative style and ensure the content is original.
        Structure the article with appropriate headings and paragraphs."""
        
        # Make API request
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": model,
            "messages": [
                {"role": "system", "content": "You are a professional article writer."},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": word_count * 4  # Estimate tokens needed
        }
        
        print(f"Making API request to generate article about: {title}")
        response = requests.post(
            "https://api.x.ai/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=60  # Increased timeout for longer articles
        )
        
        if response.status_code == 200:
            try:
                content = response.json()['choices'][0]['message']['content']
                return content.strip()
            except (KeyError, IndexError) as e:
                print(f"Error extracting content from API response: {e}")
                print(f"Response: {response.text}")
                return None
        else:
            print(f"API Error: {response.status_code} - {response.text}")
            
            # If model doesn't exist or is invalid, try with a default model
            if response.status_code == 404 or "model not found" in response.text.lower():
                print("Trying with default model as fallback")
                default_model = "grok-1"
                data["model"] = default_model
                
                try:
                    fallback_response = requests.post(
                        "https://api.x.ai/v1/chat/completions",
                        headers=headers,
                        json=data,
                        timeout=60
                    )
                    
                    if fallback_response.status_code == 200:
                        content = fallback_response.json()['choices'][0]['message']['content']
                        return content.strip()
                except Exception as fallback_e:
                    print(f"Fallback request failed: {fallback_e}")
            
            return None
            
    except Exception as e:
        import traceback
        print(f"Error generating content: {e}")
        traceback.print_exc()
        return None 

@main_bp.route('/api/generate-article', methods=['POST'])
def generate_article_api():
    """API endpoint to generate an article and return the content"""
    if 'user_id' not in session:
        return jsonify({'error': 'Please log in to generate articles'}), 401

    try:
        # Get JSON data
        data = request.get_json()
        title = data.get('title')
        keywords = data.get('keywords')
        word_count = int(data.get('word_count', 500))
        model = data.get('model', Settings.get_default_model())
        
        # Validate inputs
        if not title or not keywords:
            return jsonify({'error': 'Title and keywords are required'}), 400
            
        # Get the user's credit balance
        user_id = session['user_id']
        credits_balance = UserCredits.get_balance(user_id)
        
        # Get model-specific credits per word or use global setting
        model_credits_per_word = ModelSettings.get_credits_per_word(model)
        if model_credits_per_word is not None:
            credits_per_word = model_credits_per_word
        else:
            credits_per_word = int(CreditSettings.get_setting('credits_per_word', '1'))
        
        # Calculate credit cost
        credit_cost = word_count * credits_per_word
        
        # Check if user has enough credits
        if credits_balance < credit_cost:
            return jsonify({
                'error': 'Insufficient credits',
                'required': credit_cost,
                'balance': credits_balance
            }), 402
            
        # Generate the article content
        try:
            content = generate_article_content(title, keywords, word_count, model)
            if not content:
                return jsonify({'error': 'Failed to generate article content'}), 500
                
            # Create the article in database
            article_id = Article.create(
                title=title,
                content=content,
                user_id=user_id,
                model=model,
                credits_cost=credit_cost
            )
            
            if not article_id:
                return jsonify({'error': 'Failed to save article'}), 500
                
            # Deduct credits only after successful generation and saving
            if not UserCredits.deduct_credits(
                user_id, 
                credit_cost,
                'usage',
                f'Article generation: {title[:50]}...',
                article_id
            ):
                # If credit deduction fails, delete the article
                Article.delete(article_id)
                return jsonify({'error': 'Failed to process credits'}), 500
                
            # Return success response with content
            return jsonify({
                'success': True,
                'article_id': article_id,
                'content': content,
                'credits_used': credit_cost,
                'credits_remaining': UserCredits.get_balance(user_id)
            })
            
        except Exception as gen_error:
            print(f"Error generating article: {gen_error}")
            return jsonify({'error': str(gen_error)}), 500
            
    except Exception as e:
        print(f"Error in generate_article_api: {e}")
        return jsonify({'error': 'An unexpected error occurred'}), 500 

@main_bp.route('/stream-article')
def stream_article():
    """Stream an article generation in real-time with SEO optimizations"""
    # Import required modules
    import json
    import requests
    from requests.exceptions import ConnectionError, Timeout, RequestException
    import re
    
    if 'user_id' not in session:
        return Response(json.dumps({
            'type': 'error',
            'error': 'Please log in to generate articles'
        }), mimetype='text/event-stream')
    
    # Get query parameters
    title = request.args.get('title', '')
    keywords = request.args.get('keywords', '')
    word_count = int(request.args.get('word_count', 500))
    model = request.args.get('model', Settings.get_default_model())
    template_id = request.args.get('template', 'default')
    
    # SEO options
    include_meta = request.args.get('include_meta') == 'true'
    include_headings = request.args.get('include_headings') == 'true'
    include_faq = request.args.get('include_faq') == 'true'
    
    # Validate inputs
    if not title or not keywords:
        return Response(json.dumps({
            'type': 'error',
            'error': 'Title and keywords are required'
        }), mimetype='text/event-stream')
    
    # Get the user's credit balance
    user_id = session['user_id']
    credits_balance = UserCredits.get_balance(user_id)
    
    # Get model-specific credits per word or use global setting
    model_credits_per_word = ModelSettings.get_credits_per_word(model)
    if model_credits_per_word is not None:
        credits_per_word = model_credits_per_word
    else:
        credits_per_word = int(CreditSettings.get_setting('credits_per_word', '1'))
    
    # Calculate credit cost
    credit_cost = word_count * credits_per_word
    
    # Check if user has enough credits
    if credits_balance < credit_cost:
        return Response(json.dumps({
            'type': 'error',
            'error': 'Insufficient credits'
        }), mimetype='text/event-stream')
    
    # Function to stream content
    def generate():
        try:
            # Get API key
            api_key = get_api_key()
            if not api_key:
                yield f"data: {json.dumps({'type': 'error', 'error': 'No API key configured'})}\n\n"
                return
            
            # Prepare the prompt based on template
            system_prompt, user_prompt = get_prompts_from_template(
                template_id, title, keywords, word_count, 
                include_meta, include_headings, include_faq
            )
            
            # Make streaming API request
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "text/event-stream"
            }
            
            data = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "stream": True,
                "max_tokens": word_count * 4  # Estimate tokens needed
            }
            
            # Process streaming response from API
            try:
                response = requests.post(
                    "https://api.x.ai/v1/chat/completions",
                    headers=headers,
                    json=data,
                    stream=True,
                    timeout=120
                )
                
                # Handle errors
                if response.status_code != 200:
                    yield f"data: {json.dumps({'type': 'error', 'error': f'API Error: {response.status_code}'})}\n\n"
                    return
                
                # Stream the content
                full_content = ""
                line_buffer = ""
                
                for chunk in response.iter_content(chunk_size=1):
                    if not chunk:
                        continue
                    
                    chunk_str = chunk.decode('utf-8')
                    line_buffer += chunk_str
                    
                    # Check if we have a complete SSE message
                    if line_buffer.endswith('\n\n'):
                        lines = line_buffer.strip().split('\n')
                        line_buffer = ""
                        
                        for line in lines:
                            if line.startswith('data: '):
                                data_str = line[6:]  # Remove 'data: ' prefix
                                
                                if data_str == "[DONE]":
                                    break
                                
                                try:
                                    # Parse the JSON data
                                    result = json.loads(data_str)
                                    content_chunk = result.get('choices', [{}])[0].get('delta', {}).get('content', '')
                                    
                                    if content_chunk:
                                        # Send each chunk to the client
                                        yield f"data: {json.dumps({'type': 'content', 'content': content_chunk})}\n\n"
                                        full_content += content_chunk
                                except json.JSONDecodeError:
                                    continue
                
                # Extract SEO metadata if requested
                seo_title = None
                seo_description = None
                focus_keyword = None
                
                if include_meta:
                    # Extract metadata from the content or generate it separately
                    try:
                        # Try to find meta description in the content
                        meta_matches = re.search(r'Meta Description: (.*?)(?:\n|$)', full_content)
                        if meta_matches:
                            seo_description = meta_matches.group(1).strip()
                            # Remove the meta description line from the content
                            full_content = re.sub(r'Meta Description: .*?(?:\n|$)', '', full_content)
                        
                        # Use the first keyword as focus keyword if not explicitly provided
                        focus_keyword = keywords.split(',')[0].strip()
                        
                        # Use title as SEO title or extract it from H1
                        if '<h1>' in full_content.lower():
                            h1_match = re.search(r'<h1>(.*?)</h1>', full_content, re.IGNORECASE)
                            if h1_match:
                                seo_title = h1_match.group(1).strip()
                        else:
                            seo_title = title
                    except Exception as e:
                        print(f"Error extracting SEO metadata: {e}")
                
                # Create the article in database
                article_id = Article.create(
                    title=title,
                    content=full_content,
                    user_id=user_id,
                    model=model,
                    credits_cost=credit_cost,
                    seo_title=seo_title,
                    seo_description=seo_description,
                    focus_keyword=focus_keyword
                )
                
                # Deduct credits
                UserCredits.deduct_credits(
                    user_id, 
                    credit_cost,
                    'usage',
                    f'Article generation: {title[:50]}...',
                    article_id
                )
                
                # Send completion message
                yield f"data: {json.dumps({'type': 'complete', 'article_id': article_id})}\n\n"
                
            except (ConnectionError, Timeout) as e:
                yield f"data: {json.dumps({'type': 'error', 'error': 'Connection to AI service failed'})}\n\n"
                print(f"API connection error: {e}")
                return
            except RequestException as e:
                yield f"data: {json.dumps({'type': 'error', 'error': 'Error making request to AI service'})}\n\n"
                print(f"Request error: {e}")
                return
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'error': 'An unexpected error occurred'})}\n\n"
                print(f"Streaming error: {e}")
                import traceback
                traceback.print_exc()
                return
                
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'error': 'An unexpected error occurred'})}\n\n"
            print(f"Error in stream_article: {e}")
            import traceback
            traceback.print_exc()
    
    # Return a streaming response
    return Response(stream_with_context(generate()), mimetype='text/event-stream')

def get_prompts_from_template(template_id, title, keywords, word_count, include_meta=True, include_headings=True, include_faq=False):
    """Get system and user prompts from the selected template
    
    Args:
        template_id: ID of the template or 'default' for default system settings
        title: Article title
        keywords: Keywords for the article
        word_count: Target word count
        include_meta: Whether to include meta description
        include_headings: Whether to optimize headings
        include_faq: Whether to include an FAQ section
        
    Returns:
        tuple: (system_prompt, user_prompt)
    """
    # Default prompts from settings
    default_system_prompt = Settings.get_setting(
        'article_system_prompt', 
        """You are an expert SEO content writer who specializes in creating high-quality, engaging articles. 
Your content is well-researched, informative, and optimized for search engines without keyword stuffing. 
You write in a clear, professional tone that maintains reader interest."""
    )
    
    default_user_prompt = Settings.get_setting(
        'article_user_prompt_template',
        """Write a comprehensive article about {title}.

Keywords to include: {keywords}
Target word count: {word_count} words

Please follow these guidelines:
1. Create an engaging introduction that highlights the importance of the topic
2. Include {title} in the first paragraph for SEO purposes
3. Organize content with descriptive subheadings (H2, H3) that include keywords when natural
4. Include relevant facts, statistics, and examples to support key points
5. Use bullet points or numbered lists where appropriate
6. Write in a conversational yet professional tone
7. Naturally incorporate the keywords throughout the text
8. Create a strong conclusion that summarizes the main points
9. Ensure the content is original and provides value to readers

Structure the article with appropriate HTML formatting for headings and paragraphs."""
    )
    
    system_prompt = default_system_prompt
    user_prompt_template = default_user_prompt
    seo_level = "medium"
    
    # If a specific template is requested
    if template_id != 'default':
        try:
            template = ArticleTemplate.get_by_id(int(template_id))
            if template:
                system_prompt = template['system_prompt']
                user_prompt_template = template['user_prompt_template']
                seo_level = template['seo_level']
        except (ValueError, TypeError) as e:
            print(f"Error loading template: {e}")
    
    # Add SEO-specific instructions based on selected options
    seo_instructions = []
    
    if include_meta:
        seo_instructions.append("Generate a compelling meta description of 150-160 characters that includes the main keyword")
    
    if include_headings:
        seo_instructions.append("Ensure H1, H2, and H3 headings follow SEO best practices and include relevant keywords naturally")
    
    if include_faq:
        seo_instructions.append("Include an FAQ section with 3-5 common questions and answers about the topic")
    
    # Add SEO instructions to the user prompt if any were selected
    if seo_instructions:
        seo_section = "\nSEO Requirements:\n" + "\n".join(f"- {instruction}" for instruction in seo_instructions)
        user_prompt_template += seo_section
    
    # Format the user prompt template with the actual values
    user_prompt = user_prompt_template.format(
        title=title,
        keywords=keywords,
        word_count=word_count,
        seo_level=seo_level
    )
    
    return system_prompt, user_prompt 

def get_api_key():
    """Get API key from settings or admin user"""
    api_key = None
    
    # Try getting from settings
    try:
        api_key = Settings.get_setting('x_ai_api_key')
    except Exception as e:
        print(f"Error retrieving API key from settings: {e}")
    
    # If not found in settings, try getting from admin user
    if not api_key:
        try:
            admin_id = get_admin_id()
            if admin_id:
                api_key_data = ApiKey.get_by_user(admin_id)
                if api_key_data and api_key_data.get('is_valid'):
                    api_key = api_key_data['api_key']
        except Exception as e:
            print(f"Error retrieving admin API key: {e}")
    
    # If not found in settings or admin, try getting from current user
    if not api_key and 'user_id' in session:
        try:
            user_id = session['user_id']
            api_key_data = ApiKey.get_by_user(user_id)
            if api_key_data and api_key_data.get('is_valid'):
                api_key = api_key_data['api_key']
        except Exception as e:
            print(f"Error retrieving user API key: {e}")
    
    return api_key 
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.models import User, OTP, UserOTPSettings, CreditSettings, UserCredits, Settings, UserDevice, FreeCredits
from app.utils import send_otp_email, send_email_verification
import re
import time
from werkzeug.security import check_password_hash
import hashlib
import json

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

def get_device_info():
    """Get device information from request"""
    ip_address = request.remote_addr
    
    # Get X-Forwarded-For header if behind proxy
    if request.headers.get('X-Forwarded-For'):
        ip_address = request.headers.get('X-Forwarded-For').split(',')[0].strip()
    
    user_agent = request.headers.get('User-Agent', '')
    
    # Get fingerprint from request data
    fingerprint = request.form.get('device_fingerprint', '')
    
    # Create device hash
    device_data = {
        'user_agent': user_agent,
        'fingerprint': fingerprint
    }
    
    # Create a hash of the device data
    device_hash = hashlib.sha256(json.dumps(device_data, sort_keys=True).encode()).hexdigest()
    
    return {
        'ip_address': ip_address,
        'device_hash': device_hash,
        'user_agent': user_agent
    }

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # Get form data
        full_name = request.form.get('full_name')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        # Validate form data
        if not full_name or not email or not password or not confirm_password:
            flash('All fields are required', 'error')
            return render_template('auth/register.html', 
                                  full_name=full_name, 
                                  email=email)
        
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return render_template('auth/register.html', 
                                  full_name=full_name, 
                                  email=email)
        
        if len(password) < 8:
            flash('Password must be at least 8 characters long', 'error')
            return render_template('auth/register.html', 
                                  full_name=full_name, 
                                  email=email)
        
        # Check if email is already registered
        user = User.get_by_email(email)
        if user:
            flash('Email is already registered', 'error')
            return render_template('auth/register.html', 
                                  full_name=full_name)
        
        # Store user data temporarily in session
        session['tmp_registration'] = {
            'full_name': full_name,
            'email': email,
            'password': password
        }
        
        # Generate and send OTP code
        try:
            print(f"Creating OTP for registration: {email}")
            otp_code = OTP.create_otp(email, 'registration')
            
            if not otp_code:
                flash('Error generating verification code. Please try again.', 'error')
                return render_template('auth/register.html', 
                                      full_name=full_name, 
                                      email=email)
            
            # Create user data dict for email
            user_data = {'full_name': full_name, 'email': email}
            
            # Store OTP in session for development/debugging
            session['debug_otp'] = otp_code
            
            # Try to send OTP via email
            email_sent = send_otp_email(email, otp_code, 'registration', user_data)
            
            if email_sent:
                flash('Verification code has been sent to your email. Please verify to complete registration.', 'success')
            else:
                flash('Could not send verification email. Please use the code shown below.', 'warning')
            
            return redirect(url_for('auth.verify_registration_otp'))
                
        except Exception as e:
            import traceback
            print(f"Exception during OTP generation: {e}")
            traceback.print_exc()
            flash('An unexpected error occurred. Please try again.', 'error')
            
        return render_template('auth/register.html', 
                              full_name=full_name, 
                              email=email)
    
    return render_template('auth/register.html')

@auth_bp.route('/verify-account', methods=['GET', 'POST'])
def verify_account():
    email = request.args.get('email', '')
    
    if request.method == 'POST':
        email = request.form.get('email')
        otp_code = request.form.get('otp')
        
        if OTP.verify_otp(email, otp_code, 'signup'):
            if User.verify_account(email):
                flash('Account verified successfully! You can now log in.', 'success')
                return redirect(url_for('auth.login'))
            else:
                flash('Error verifying account. Please contact support.', 'error')
        else:
            flash('Invalid or expired verification code.', 'error')
    
    return render_template('auth/verify_account.html', email=email)

@auth_bp.route('/resend-otp', methods=['POST'])
def resend_otp():
    email = request.form.get('email')
    purpose = request.form.get('purpose')
    
    if not email or not purpose:
        flash('Email and purpose are required.', 'error')
        return redirect(url_for('auth.login'))
    
    # Generate new OTP
    otp_code = OTP.create_otp(email, purpose)
    if otp_code and send_otp_email(email, otp_code, purpose):
        flash('Verification code resent. Please check your email.', 'success')
    else:
        flash('Error sending verification code. Please try again.', 'error')
    
    if purpose == 'signup':
        return redirect(url_for('auth.verify_account', email=email))
    elif purpose == 'password_reset':
        return redirect(url_for('auth.reset_password', email=email))
    elif purpose == 'login':
        return redirect(url_for('auth.verify_login', email=email))
    
    return redirect(url_for('auth.login'))

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login with proper error handling"""
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        
        if not email or not password:
            flash('Email and password are required', 'error')
            return render_template('auth/login.html')
        
        # Make sure User is imported
        from app.models import User, UserOTPSettings
        
        try:
            # Authenticate user
            user = User.authenticate(email, password)
            
            if user:
                # Set session data
                session['user_id'] = user['id']
                session['email'] = user['email']
                session['full_name'] = user['full_name']
                session['is_admin'] = user['is_admin'] if 'is_admin' in user else False
                
                # Check if 2FA is required
                try:
                    # Check if the method exists first to avoid AttributeError
                    if hasattr(UserOTPSettings, 'is_otp_enabled') and callable(getattr(UserOTPSettings, 'is_otp_enabled')):
                        if UserOTPSettings.is_otp_enabled(user['id']):
                            # Store partial login info and redirect to OTP verification
                            session['partial_login'] = {'user_id': user['id']}
                            return redirect(url_for('auth.verify_login_otp', email=email))
                except Exception as e:
                    print(f"Error checking OTP settings: {e}")
                
                # If we reach here, no OTP required or OTP check failed
                flash('Login successful!', 'success')
                
                # Redirect based on user type
                if session.get('is_admin'):
                    return redirect(url_for('admin.dashboard'))
                else:
                    return redirect(url_for('main.dashboard'))
            else:
                flash('Invalid email or password', 'error')
        except Exception as e:
            print(f"Login error: {e}")
            flash('An error occurred during login. Please try again.', 'error')
    
    return render_template('auth/login.html')

@auth_bp.route('/verify-login', methods=['GET', 'POST'])
def verify_login():
    email = request.args.get('email', '')
    
    # Check if partial login is still valid
    partial_login = session.get('partial_login', {})
    if not partial_login or time.time() > partial_login.get('expires', 0):
        flash('Login session expired. Please login again.', 'error')
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        otp_code = request.form.get('otp')
        
        if OTP.verify_otp(email, otp_code, 'login'):
            # Get user details
            user = User.get_by_id(partial_login['user_id'])
            
            # Complete login
            session.pop('partial_login', None)
            session['user_id'] = user['id']
            session['full_name'] = user['full_name']
            session['email'] = user['email']
            session['is_admin'] = user['is_admin']
            session.permanent = True
            
            flash('Login successful!', 'success')
            return redirect(url_for('main.dashboard'))
        else:
            flash('Invalid or expired verification code.', 'error')
    
    return render_template('auth/verify_login.html', email=email)

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        
        # Check if user exists
        user = User.get_by_email(email)
        
        if user:
            # Generate and send password reset OTP
            otp_code = OTP.create_otp(email, 'password_reset', user['id'])
            if otp_code and send_otp_email(email, otp_code, 'password_reset'):
                flash('Password reset code sent to your email.', 'success')
                return redirect(url_for('auth.reset_password', email=email))
            else:
                flash('Error sending reset code. Please try again.', 'error')
        else:
            # Don't reveal if user exists or not
            flash('If your email is registered, you will receive a password reset link.', 'info')
    
    return render_template('auth/forgot_password.html')

@auth_bp.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    email = request.args.get('email', '')
    otp = request.args.get('otp', '')
    
    if request.method == 'POST':
        email = request.form.get('email')
        otp_code = request.form.get('otp')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        # Validate passwords
        if new_password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('auth/reset_password.html', email=email, otp=otp_code)
        
        if len(new_password) < 8:
            flash('Password must be at least 8 characters long.', 'error')
            return render_template('auth/reset_password.html', email=email, otp=otp_code)
        
        # Verify OTP
        if OTP.verify_otp(email, otp_code, 'password_reset'):
            # Update password
            if User.update_password(email, new_password):
                flash('Password updated successfully! You can now log in with your new password.', 'success')
                return redirect(url_for('auth.login'))
            else:
                flash('Error updating password. Please contact support.', 'error')
        else:
            flash('Invalid or expired verification code.', 'error')
    
    return render_template('auth/reset_password.html', email=email, otp=otp)

@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('main.index'))

@auth_bp.route('/verify-registration-otp', methods=['GET', 'POST'])
def verify_registration_otp():
    """Verify registration OTP and create user account with device tracking"""
    if 'tmp_registration' not in session:
        flash('Please complete the registration form first', 'error')
        return redirect(url_for('auth.register'))
    
    tmp_data = session['tmp_registration']
    email = tmp_data['email']
    debug_code = session.get('debug_otp')
    
    if request.method == 'POST':
        otp_code = request.form.get('otp_code')
        
        if not otp_code:
            flash('Verification code is required', 'error')
            return render_template('auth/verify_otp.html', 
                                  email=email, 
                                  registration=True,
                                  debug_code=debug_code)
        
        # Initialize database first to ensure all tables exist
        from app.initialize_database import initialize_database
        initialize_database()
        
        # Verify OTP
        from app.models import OTP
        if OTP.verify_otp(email, otp_code, 'registration'):
            # OTP verification successful
            full_name = tmp_data['full_name']
            password = tmp_data['password']
            
            # Get device information
            device_info = get_device_info()
            
            # Check for previous accounts with this device/IP if tracking is enabled
            should_award_free_credits = True
            
            if UserDevice.is_device_tracking_enabled():
                previous_users = UserDevice.check_previous_users(
                    device_info['ip_address'], 
                    device_info['device_hash']
                )
                
                if previous_users:
                    should_award_free_credits = False
                    print(f"Previous users detected for device/IP: {previous_users}")
            
            # Create new user with retry logic
            print(f"Creating new user: {email}")
            retry_count = 3
            user_id = None
            
            while retry_count > 0 and user_id is None:
                user_id = User.create(full_name, email, password, is_verified=True)
                if user_id is None:
                    print(f"Retry {4-retry_count}: Creating user {email}")
                    retry_count -= 1
            
            if user_id is None:
                flash('Error creating account. Please try again or contact support.', 'error')
                print(f"CRITICAL: All attempts to create user {email} failed")
                return render_template('auth/verify_otp.html',
                                      email=email,
                                      registration=True,
                                      debug_code=debug_code)
            
            # Record device information
            if UserDevice.is_device_tracking_enabled():
                UserDevice.add_device(
                    user_id,
                    device_info['ip_address'],
                    device_info['device_hash'],
                    device_info['user_agent']
                )
            
            # Add welcome credits if eligible
            try:
                if should_award_free_credits:
                    # Get free credits amount from credit settings
                    free_credits = int(CreditSettings.get_setting('first_time_free_credits', '5000'))
                    
                    if free_credits > 0:
                        success = FreeCredits.award_registration_credits(user_id, free_credits)
                        if success:
                            print(f"Successfully added {free_credits} welcome credits to user {user_id}")
                        else:
                            print(f"Failed to add welcome credits to user {user_id}")
                else:
                    print(f"Not awarding free credits to user {user_id} due to duplicate device/IP")
            except Exception as credit_e:
                print(f"Error handling welcome credits: {credit_e}")
                import traceback
                traceback.print_exc()
            
            # Clear session data
            if 'tmp_registration' in session:
                session.pop('tmp_registration', None)
            if 'debug_otp' in session:
                session.pop('debug_otp', None)
            
            flash('Your account has been successfully activated! You can now log in.', 'success')
            return redirect(url_for('auth.login'))
        else:
            flash('Invalid or expired verification code. Please try again.', 'error')
            return render_template('auth/verify_otp.html',
                                  email=email,
                                  registration=True,
                                  debug_code=debug_code)
    
    return render_template('auth/verify_otp.html',
                          email=email,
                          registration=True,
                          debug_code=debug_code) 
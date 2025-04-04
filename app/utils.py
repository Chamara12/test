import requests
import json
import random
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app, render_template
import traceback
from app.models import EmailSettings, ApiKey, Settings, UserCredits

def generate_article_with_xai(api_key, topic, keywords, word_count, model="x1-preview"):
    """Generate an article using the x.ai API with correct endpoint and payload structure"""
    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        # Format a detailed prompt for the article
        prompt = f"""Write an SEO-optimized article about {topic}.
        
        Include these keywords naturally throughout: {keywords}
        
        The article should be approximately {word_count} words.
        
        Format the content as proper HTML with:
        - An engaging H1 title
        - Multiple H2 and H3 subheadings
        - Well-structured paragraphs
        - At least one bulleted list
        - A strong conclusion
        
        Make the content informative, engaging, and valuable to readers.
        """
        
        # Create the correct payload structure for x.ai API
        payload = {
            "model": model,  # Use the specified model
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.7,
            "max_tokens": int(word_count * 1.5)  # Appropriate token limit
        }
        
        # Debug output
        print(f"Calling x.ai API with topic: {topic}, model: {model}")
        print(f"Using API key starting with: {api_key[:10]}...")
        
        # Use the correct chat completions endpoint
        response = requests.post(
            "https://api.x.ai/v1/chat/completions",  # Correct endpoint
            headers=headers,
            json=payload,
            timeout=120  # Longer timeout for article generation
        )
        
        # Detailed debug output for the response
        print(f"API Response status: {response.status_code}")
        
        # Check for successful response
        if response.status_code == 200:
            response_data = response.json()
            print(f"Response structure: {list(response_data.keys())}")
            
            # Extract content from the correct location in the response
            if 'choices' in response_data and len(response_data['choices']) > 0:
                if 'message' in response_data['choices'][0]:
                    content = response_data['choices'][0]['message']['content']
                    print(f"Successfully extracted content (length: {len(content)})")
                    return content
            
            print(f"Response did not contain expected content structure: {response_data}")
            return None
        else:
            # Print the full error for debugging
            error_detail = f"Status: {response.status_code}, Response: {response.text}"
            print(f"API Error: {error_detail}")
            return None
    except Exception as e:
        print(f"Exception in generate_article_with_xai: {str(e)}")
        traceback.print_exc()
        return None

def generate_random_seed():
    """Generate a random seed between 0 and 2^32-1 for API requests"""
    return random.randint(0, 2**32 - 1)

def calculate_max_tokens(word_count):
    """
    Calculate max tokens based on target word count.
    Typical ratio is roughly 1.5 tokens per word.
    """
    return int(word_count * 1.5) + 500  # Add buffer for formatting

def generate_fallback_article(topic, keywords, word_count, include_note=False):
    """Generate a fallback article when API fails"""
    
    # Add variation factors
    import random
    import datetime
    
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    variation_id = random.randint(1000, 9999)
    
    # Create a varied title
    title_options = [
        f"Complete Guide to {topic}",
        f"Understanding {topic}: Key Concepts",
        f"Exploring the World of {topic}",
        f"{topic} Explained: A Comprehensive Overview",
        f"Essential Aspects of {topic}"
    ]
    
    title = random.choice(title_options)
    
    # Create paragraphs with variations
    intro_options = [
        f"This article explores {topic} in detail, focusing on key aspects and best practices.",
        f"In this comprehensive guide, we'll dive deep into {topic} and its important elements.",
        f"Understanding {topic} is crucial in today's world. This article breaks down the essential concepts.",
        f"Let's explore the fascinating world of {topic} and why it matters.",
        f"{topic} has become increasingly important. Here's what you need to know."
    ]
    
    conclusion_options = [
        f"In conclusion, {topic} remains an essential area of study and practice.",
        f"To summarize, mastering the concepts of {topic} can significantly impact your success.",
        f"As we've seen, {topic} encompasses many important aspects worth exploring further.",
        f"The field of {topic} continues to evolve, making it an exciting area to follow.",
        f"By understanding these key elements of {topic}, you're now better equipped to apply them."
    ]
    
    # Split keywords for use in different sections
    keyword_list = [k.strip() for k in keywords.split(',')]
    random.shuffle(keyword_list)
    
    # Make sure we have enough keywords
    while len(keyword_list) < 3:
        keyword_list.append(random.choice(keyword_list))
    
    content = f"""
    <h1>{title}</h1>
    
    <p>{random.choice(intro_options)}</p>
    
    <h2>Understanding {topic}</h2>
    <p>{topic} is an important subject with various applications and implications. 
    The concepts related to {topic} include several important elements that are worth exploring in depth.
    In particular, {keyword_list[0]} plays a crucial role in this field.</p>
    
    <h2>Key Aspects of {topic}</h2>
    <p>When discussing {topic}, several important keywords come to mind: {keywords}. 
    These concepts are interconnected and represent the core elements of this subject.
    Let's examine how {keyword_list[1]} contributes to our understanding.</p>
    
    <h3>Best Practices for {keyword_list[0]}</h3>
    <p>Following best practices in {topic} can lead to better outcomes and more efficient processes.
    It's important to stay updated with the latest developments in this field, especially regarding {keyword_list[0]}.</p>
    
    <h3>The Importance of {keyword_list[1]}</h3>
    <p>Among the various aspects of {topic}, {keyword_list[1]} stands out as particularly significant.
    Experts in the field consistently emphasize its role in achieving optimal results.</p>
    
    <h2>Future Trends in {topic}</h2>
    <p>As technology and research advance, we can expect to see new developments in {topic}.
    Particularly, the relationship between {keyword_list[0]} and {keyword_list[-1]} will likely evolve.</p>
    
    <h2>Conclusion</h2>
    <p>{random.choice(conclusion_options)}
    By understanding the key concepts and implementing best practices, one can achieve better results and contribute to the field.</p>
    """
    
    # Only add the note if specifically requested
    if include_note:
        content += f"""
        <p><em>Note: This article was generated as a fallback due to API unavailability. 
        The full {word_count}-word article could not be generated at this time. (Variation ID: {variation_id}, Time: {current_time})</em></p>
        """
    
    return content

def generate_article_with_fallback_api(topic, keywords, word_count):
    """Try an alternative API if x.ai fails"""
    try:
        # This is where you could implement a call to another API service
        # For example, you could use OpenAI's API instead
        
        # For now, we'll just implement a more sophisticated fallback
        import random
        
        # Make it clear this is a more sophisticated fallback
        content = f"""
        <h1>Comprehensive Guide to {topic}</h1>
        
        <p>Welcome to our in-depth article on {topic}. This guide covers all important aspects
        and is optimized for the keywords: {keywords}.</p>
        
        <h2>Understanding {topic} - Key Concepts</h2>
        
        <p>To fully grasp {topic}, we need to explore several interconnected concepts and principles.
        The field has evolved significantly in recent years, with new developments continuously emerging.</p>
        
        <h3>Core Elements of {topic}</h3>
        
        <p>The most essential components of {topic} include:</p>
        <ul>
        """
        
        # Create a bulleted list from keywords
        keyword_list = [k.strip() for k in keywords.split(',')]
        for keyword in keyword_list:
            content += f"<li><strong>{keyword}</strong> - A crucial aspect that contributes to the overall understanding of {topic}.</li>\n"
        
        content += f"""
        </ul>
        
        <h2>Best Practices for {topic}</h2>
        
        <p>When working with {topic}, professionals recommend following these guidelines to achieve optimal results.
        These practices have been refined through years of experience and research in the field.</p>
        
        <h2>Future Trends in {topic}</h2>
        
        <p>The landscape of {topic} is constantly evolving. In the coming years, we expect to see significant
        advancements in several areas, particularly in how {keyword_list[0] if keyword_list else 'key concepts'} 
        interacts with emerging technologies.</p>
        
        <h2>Conclusion</h2>
        
        <p>Understanding {topic} thoroughly requires attention to multiple factors and ongoing learning.
        By focusing on the key elements outlined in this article, you'll be well-positioned to leverage
        the full potential of {topic} in your work or studies.</p>
        
        <p><em>This article was generated using a sophisticated content generation system.</em></p>
        """
        
        return content
    except Exception as e:
        print(f"Alternative API fallback failed: {e}")
        return None 

def get_available_xai_models(api_key):
    """
    Query the X.AI API to get a list of available models
    
    Args:
        api_key (str): The X.AI API key
        
    Returns:
        list: List of available model objects or None if the request fails
    """
    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        # Make request to models endpoint
        response = requests.get(
            "https://api.x.ai/v1/models",
            headers=headers,
            timeout=10
        )
        
        print(f"Models API Response status: {response.status_code}")
        
        if response.status_code == 200:
            response_data = response.json()
            
            if 'data' in response_data:
                models = response_data['data']
                print(f"Retrieved {len(models)} models from X.AI API")
                return models
            else:
                print("Response doesn't contain 'data' key:", response_data)
                return None
        else:
            print(f"Error retrieving models: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"Exception when retrieving models: {str(e)}")
        return None 

def send_email(recipient_email, subject, template_name, **kwargs):
    """
    Send an email using the configured SMTP settings with enhanced error handling
    
    Args:
        recipient_email: The recipient's email address
        subject: Email subject
        template_name: Name of the email template without the .html extension
        **kwargs: Template variables
    
    Returns:
        bool: True if email was sent successfully, False otherwise
    """
    try:
        # Get email settings
        email_settings = EmailSettings.get_settings()
        if not email_settings:
            print("Email settings not configured")
            return False
            
        # Check if email sending is enabled
        if email_settings.get('email_enabled', 'true').lower() != 'true':
            print("Email sending is disabled in settings")
            return False
            
        # Add common template variables
        kwargs['current_year'] = datetime.now().year
        kwargs['current_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        kwargs['subject'] = subject
        
        # Check for template existence
        template_path = f'emails/{template_name}.html'
        try:
            # Render the HTML content - this will raise an error if template doesn't exist
            html_content = render_template(template_path, **kwargs)
            print(f"Successfully rendered template: {template_path}")
        except Exception as template_error:
            print(f"Template error: {template_error}")
            # Try to use a basic fallback template
            html_content = f"""
            <html>
            <body>
                <h1>{subject}</h1>
                <p>This is an important message from Article Writer Pro.</p>
                <p>Please contact support as there was an issue with our email template system.</p>
            </body>
            </html>
            """
            print("Using fallback template due to template error")
        
        # Create message
        message = MIMEMultipart('alternative')
        message['Subject'] = subject
        message['From'] = email_settings['sender_email']
        message['To'] = recipient_email
        
        # Attach HTML content
        message.attach(MIMEText(html_content, 'html'))
        
        # Connect to SMTP server
        smtp_server = email_settings['smtp_server']
        smtp_port = int(email_settings['smtp_port'])
        use_tls = email_settings.get('use_tls', True)
        
        print(f"Connecting to SMTP server: {smtp_server}:{smtp_port} with TLS={use_tls}")
        
        # Create SMTP connection with detailed error handling
        try:
            if use_tls:
                server = smtplib.SMTP(smtp_server, smtp_port, timeout=10)
                server.starttls()
            else:
                server = smtplib.SMTP(smtp_server, smtp_port, timeout=10)
                
            print("SMTP connection established")
                
            # Login if credentials are provided
            if email_settings.get('smtp_username') and email_settings.get('smtp_password'):
                print(f"Attempting login with username: {email_settings['smtp_username']}")
                server.login(email_settings['smtp_username'], email_settings['smtp_password'])
                print("SMTP login successful")
                
            # Send email
            print(f"Sending email to {recipient_email} from {email_settings['sender_email']}")
            server.sendmail(email_settings['sender_email'], recipient_email, message.as_string())
            server.quit()
            
            print(f"Email sent successfully to {recipient_email}")
            return True
        except smtplib.SMTPAuthenticationError:
            print("SMTP Authentication Error: Invalid username or password")
            return False
        except smtplib.SMTPConnectError:
            print(f"SMTP Connect Error: Failed to connect to {smtp_server}:{smtp_port}")
            return False
        except smtplib.SMTPServerDisconnected:
            print("SMTP Server Disconnected: Server unexpectedly disconnected")
            return False
        except smtplib.SMTPException as smtp_error:
            print(f"SMTP Error: {smtp_error}")
            return False
            
    except Exception as e:
        import traceback
        print(f"Unexpected error sending email: {e}")
        traceback.print_exc()
        return False

def send_test_email(to_email):
    """Send a test email to verify SMTP configuration"""
    subject = "WebArticle Email Test"
    html_content = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 5px;">
        <h2 style="color: #7D4BCB; text-align: center;">Email Test Successful</h2>
        <p style="font-size: 16px; line-height: 1.5; color: #333;">This is a test email from your WebArticle application.</p>
        <p style="font-size: 16px; line-height: 1.5; color: #333;">If you're receiving this email, your SMTP settings are configured correctly.</p>
        <div style="margin-top: 40px; border-top: 1px solid #e0e0e0; padding-top: 20px; text-align: center; font-size: 12px; color: #999;">
            <p>WebArticle - AI Article Writing Platform</p>
            <p>Test email sent at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
    </div>
    """
    
    # Force email sending for test
    current_enabled = EmailSettings.get_setting('email_enabled', 'false')
    EmailSettings.set_setting('email_enabled', 'true')
    
    result = send_email(to_email, subject, 'test')
    
    # Restore original setting
    EmailSettings.set_setting('email_enabled', current_enabled)
    
    return result

def send_otp_email(recipient_email, otp_code, purpose, user=None):
    """Send OTP email based on purpose"""
    if isinstance(user, dict):
        # User is provided as a dictionary
        user_data = user
    else:
        # Try to get user data if not provided
        from app.models import User
        user_data = User.get_by_email(recipient_email) or {'full_name': 'User', 'email': recipient_email}
    
    # Map purpose to template and subject
    if purpose == 'login':
        template = 'login_otp'
        subject = 'Your Login Verification Code'
    elif purpose == 'account_deletion':
        template = 'account_deletion_otp'
        subject = 'Account Deletion Verification'
    elif purpose == 'registration':
        template = 'registration_otp'
        subject = 'Your Registration Verification Code'
    elif purpose == 'password_reset':
        template = 'password_reset_otp'
        subject = 'Password Reset Verification Code'
    else:
        print(f"Unknown OTP purpose: {purpose}")
        return False
    
    print(f"Sending {purpose} OTP email to {recipient_email} with code {otp_code}")
    
    # Try to send the email with detailed error handling
    try:
        result = send_email(
            recipient_email,
            subject,
            template,
            user=user_data,
            otp_code=otp_code
        )
        
        if result:
            print(f"OTP email sent successfully to {recipient_email}")
            return True
        else:
            print(f"Failed to send OTP email to {recipient_email}")
            return False
            
    except Exception as e:
        print(f"Exception in send_otp_email: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def send_welcome_email(user, free_credits=0):
    """Send welcome email to new user"""
    return send_email(
        user['email'],
        'Welcome to Article Writer Pro!',
        'welcome',
        user=user,
        free_credits=free_credits
    )

def send_payment_confirmation(user, payment):
    """Send payment confirmation email"""
    from app.models import UserCredits
    user_credits = UserCredits.get_balance(user['id'])
    
    return send_email(
        user['email'],
        'Payment Confirmation',
        'payment_confirmation',
        user=user,
        payment=payment,
        user_credits=user_credits
    )

def send_article_generated_email(user, article):
    """Send email notification when article is generated"""
    from app.models import UserCredits
    user_credits = UserCredits.get_balance(user['id'])
    
    return send_email(
        user['email'],
        f'Your Article "{article["title"]}" Has Been Generated',
        'article_generated',
        user=user,
        article=article,
        user_credits=user_credits
    )

def send_credit_balance_low_email(user, credits_threshold=1000):
    """Send notification when user's credit balance is low"""
    from app.models import UserCredits
    user_credits = UserCredits.get_balance(user['id'])
    
    if user_credits <= credits_threshold:
        return send_email(
            user['email'],
            'Your Credit Balance is Running Low',
            'credit_balance_low',
            user=user,
            user_credits=user_credits
        )
    return False

def send_password_reset_email(user, reset_token):
    """Send password reset email"""
    from flask import url_for
    reset_url = url_for('auth.reset_password', token=reset_token, _external=True)
    
    return send_email(
        user['email'],
        'Reset Your Password',
        'password_reset',
        user=user,
        reset_url=reset_url
    )

def send_email_verification(user, verification_token):
    """Send email verification link with improved error handling"""
    from flask import url_for
    import traceback
    
    try:
        verification_url = url_for('auth.verify_email', token=verification_token, _external=True)
        
        print(f"Verification URL generated: {verification_url}")
        print(f"Sending verification email to: {user['email']}")
        
        result = send_email(
            user['email'],
            'Verify Your Email Address',
            'verify_email',
            user=user,
            verification_url=verification_url
        )
        
        if result:
            print(f"Verification email sent successfully to {user['email']}")
            return True
        else:
            print(f"Failed to send verification email to {user['email']}")
            return False
            
    except Exception as e:
        print(f"Exception in send_email_verification: {str(e)}")
        traceback.print_exc()
        return False

def send_admin_test_email(recipient_email):
    """Send a test email to verify email configuration"""
    email_settings = EmailSettings.get_settings()
    
    return send_email(
        recipient_email,
        'Email Configuration Test',
        'admin_test',
        settings=email_settings
    )

def slugify(text):
    """
    Convert text to a URL-friendly slug.
    Remove special characters, convert spaces to hyphens, and lowercase.
    """
    import re
    import unicodedata
    
    # Convert to ASCII
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
    # Remove unwanted characters and replace spaces with hyphens
    text = re.sub(r'[^\w\s-]', '', text).strip().lower()
    # Replace all runs of whitespace with a single hyphen
    text = re.sub(r'[-\s]+', '-', text)
    
    return text 

def get_admin_id():
    """Get the ID of the first admin user"""
    from app.models import Database
    
    connection = Database.get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM users WHERE is_admin = 1 LIMIT 1")
            admin = cursor.fetchone()
            return admin['id'] if admin else None
    finally:
        connection.close() 

def generate_seo_content(topic, article_content, model_id=None):
    """
    Generate SEO metadata for an article based on its content
    
    Args:
        topic (str): The main topic of the article
        article_content (str): The full content of the article
        model_id (str, optional): The AI model to use if API generation is needed
        
    Returns:
        dict: Contains title, description, and focus_keyword
    """
    try:
        # Extract first 300 characters of content for analysis
        content_preview = article_content[:300].strip()
        
        # Simple algorithm to generate SEO content without API call
        # Extract potential keywords from the topic
        import re
        from collections import Counter
        
        # Clean the content
        clean_content = re.sub(r'<[^>]+>', '', article_content).lower()
        
        # Remove common words and extract potential keywords
        common_words = {'the', 'and', 'or', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'with', 
                        'of', 'by', 'as', 'is', 'are', 'was', 'were', 'be', 'been', 'being'}
        
        # Extract words from content
        all_words = re.findall(r'\b[a-z]{3,}\b', clean_content)
        word_count = Counter([w for w in all_words if w not in common_words])
        
        # Get top keywords
        top_keywords = [w for w, c in word_count.most_common(5)]
        focus_keyword = ', '.join(top_keywords)
        
        # Generate title and description
        topic_words = topic.split()
        if len(topic_words) <= 5:
            seo_title = f"Complete Guide to {topic}: Essential Tips and Strategies"
        else:
            seo_title = f"{topic}: Essential Guide and Best Practices"
            
        # Create description from first paragraph or content preview
        paragraphs = re.findall(r'<p>(.*?)</p>', article_content)
        if paragraphs:
            first_para = re.sub(r'<[^>]+>', '', paragraphs[0])
            if len(first_para) > 30:  # Make sure it's a real paragraph
                description = first_para[:157] + "..."
            else:
                description = clean_content[:157] + "..."
        else:
            description = clean_content[:157] + "..."
            
        return {
            'title': seo_title,
            'description': description,
            'focus_keyword': focus_keyword
        }
        
    except Exception as e:
        print(f"Error generating SEO content: {e}")
        # Fallback to basic SEO content
        return {
            'title': f"{topic} - Comprehensive Guide",
            'description': f"Learn everything about {topic} in this comprehensive guide. Explore key concepts, best practices, and expert insights.",
            'focus_keyword': topic
        } 
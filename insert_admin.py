from app import create_app
from app.models import Database
from werkzeug.security import generate_password_hash

# Admin credentials
email = 'admin@example.com'
password = 'admin123'
full_name = 'Admin User'

# Create app context
app = create_app()
with app.app_context():
    # Create tables if they don't exist
    Database.create_tables()
    
    # Generate password hash
    password_hash = generate_password_hash(password)
    
    # Connect to database
    connection = Database.get_connection()
    try:
        with connection.cursor() as cursor:
            # Check if user exists
            cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()
            
            if user:
                # Update existing user to admin
                cursor.execute(
                    "UPDATE users SET is_admin = 1, password_hash = %s WHERE email = %s",
                    (password_hash, email)
                )
                print(f"Existing user '{email}' updated to admin with new password")
            else:
                # Insert new admin user
                cursor.execute(
                    "INSERT INTO users (full_name, email, password_hash, is_admin) VALUES (%s, %s, %s, %s)",
                    (full_name, email, password_hash, 1)
                )
                print(f"New admin user '{email}' created")
        
        connection.commit()
        print("\nAdmin credentials:")
        print(f"Email: {email}")
        print(f"Password: {password}")
    finally:
        connection.close() 
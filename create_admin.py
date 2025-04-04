import sys
import os
from werkzeug.security import generate_password_hash
from app.models import Database, User

def create_admin_user(email, password, full_name):
    """Create an admin user with proper error handling"""
    try:
        # Validate inputs
        if not email or not password or not full_name:
            print("Error: All fields (email, password, full_name) are required")
            return False
            
        if len(password) < 8:
            print("Error: Password must be at least 8 characters long")
            return False
            
        # Initialize database connection
        connection = Database.get_connection()
        
        try:
            with connection.cursor() as cursor:
                # Check if user already exists
                cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
                existing_user = cursor.fetchone()
                
                if existing_user:
                    print(f"Error: User with email {email} already exists")
                    return False
                
                # Create admin user
                password_hash = generate_password_hash(password)
                
                # Insert user with admin privileges
                cursor.execute("""
                    INSERT INTO users (email, password_hash, full_name, is_admin, is_verified)
                    VALUES (%s, %s, %s, 1, 1)
                """, (email, password_hash, full_name))
                
                user_id = cursor.lastrowid
                
                # Initialize user settings
                cursor.execute("""
                    INSERT INTO user_settings (user_id, theme_preference, language_preference)
                    VALUES (%s, 'light', 'en')
                """, (user_id,))
                
                # Initialize user credits
                cursor.execute("""
                    INSERT INTO user_credits (user_id, credits_balance)
                    VALUES (%s, 0)
                """, (user_id,))
                
                connection.commit()
                print(f"Admin user created successfully: {email}")
                return True
                
        except Exception as e:
            connection.rollback()
            print(f"Database error: {str(e)}")
            return False
            
        finally:
            connection.close()
            
    except Exception as e:
        print(f"Error creating admin user: {str(e)}")
        return False

def ensure_tables_exist():
    """Ensure all required tables exist"""
    connection = Database.get_connection()
    try:
        with connection.cursor() as cursor:
            # Create users table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    full_name VARCHAR(255) NOT NULL,
                    is_admin BOOLEAN DEFAULT FALSE,
                    is_verified BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                )
            """)
            
            # Create user_settings table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_settings (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    theme_preference VARCHAR(50) DEFAULT 'light',
                    language_preference VARCHAR(10) DEFAULT 'en',
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)
            
            # Create user_credits table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_credits (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    credits_balance INT DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)
            
            connection.commit()
            print("Database tables verified successfully")
            
    except Exception as e:
        print(f"Error creating tables: {str(e)}")
        return False
    finally:
        connection.close()

def main():
    """Main function to handle admin creation"""
    if len(sys.argv) != 4:
        print("Usage: python create_admin.py <email> <password> <full_name>")
        print("Example: python create_admin.py admin@example.com mypassword 'Admin User'")
        sys.exit(1)
        
    email = sys.argv[1]
    password = sys.argv[2]
    full_name = sys.argv[3]
    
    print("Ensuring database tables exist...")
    ensure_tables_exist()
    
    print(f"Creating admin user: {email}")
    if create_admin_user(email, password, full_name):
        print("Admin user created successfully!")
        sys.exit(0)
    else:
        print("Failed to create admin user")
        sys.exit(1)

if __name__ == "__main__":
    main() 
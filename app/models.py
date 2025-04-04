import pymysql
from app.config import Config
from werkzeug.security import generate_password_hash, check_password_hash
import time
import requests
from datetime import datetime, timedelta
import random
import string
import secrets

class Database:
    @staticmethod
    def get_connection():
        return pymysql.connect(
            host=Config.MYSQL_HOST,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
            db=Config.MYSQL_DB,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
    
    @staticmethod
    def create_tables():
        connection = Database.get_connection()
        try:
            with connection.cursor() as cursor:
                # Create users table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    full_name VARCHAR(100) NOT NULL,
                    email VARCHAR(100) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    is_admin BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                )
                """)
                
                # Create articles table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS articles (
                    id INT PRIMARY KEY AUTO_INCREMENT,
                    user_id INT NOT NULL,
                    title VARCHAR(255) NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    model VARCHAR(50),
                    credits_cost INT DEFAULT 0,
                    seo_title VARCHAR(255),
                    seo_description VARCHAR(500),
                    focus_keyword VARCHAR(255),
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
                """)
                
                # Create api_keys table with all required columns
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS api_keys (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    api_key VARCHAR(255) NOT NULL,
                    is_valid BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
                """)
                
                # Check if verification_message column exists, if not add it
                try:
                    cursor.execute("""
                    SELECT * FROM INFORMATION_SCHEMA.COLUMNS 
                    WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'api_keys' AND COLUMN_NAME = 'verification_message'
                    """, (Config.MYSQL_DB,))
                    if not cursor.fetchone():
                        cursor.execute("ALTER TABLE api_keys ADD COLUMN verification_message VARCHAR(255)")
                        print("Added verification_message column to api_keys table")
                except Exception as e:
                    print(f"Error checking/adding verification_message column: {e}")
                
                # Check if last_verified column exists, if not add it
                try:
                    cursor.execute("""
                    SELECT * FROM INFORMATION_SCHEMA.COLUMNS 
                    WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'api_keys' AND COLUMN_NAME = 'last_verified'
                    """, (Config.MYSQL_DB,))
                    if not cursor.fetchone():
                        cursor.execute("ALTER TABLE api_keys ADD COLUMN last_verified TIMESTAMP NULL DEFAULT NULL")
                        print("Added last_verified column to api_keys table")
                except Exception as e:
                    print(f"Error checking/adding last_verified column: {e}")
                
                # Create settings table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    setting_name VARCHAR(100) UNIQUE NOT NULL,
                    setting_value VARCHAR(255) NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                )
                """)
                
                # Create model_settings table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS model_settings (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    model_id VARCHAR(100) UNIQUE NOT NULL,
                    display_name VARCHAR(255),
                    is_enabled BOOLEAN DEFAULT 1,
                    custom_description TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                )
                """)
                
                # Create credits table to track user credit balances
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_credits (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    credits_balance INT DEFAULT 0,
                    total_credits_purchased INT DEFAULT 0,
                    total_credits_used INT DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
                """)
                
                # Create payments table to track deposits
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS payments (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    amount DECIMAL(10, 2) NOT NULL,
                    credits_added INT NOT NULL,
                    payment_method VARCHAR(50) NOT NULL,
                    transaction_id VARCHAR(100),
                    status VARCHAR(20) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
                """)
                
                # Create credit_transactions table to track all credit operations
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS credit_transactions (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    credits_amount INT NOT NULL,
                    transaction_type ENUM('purchase', 'usage', 'refund', 'adjustment') NOT NULL,
                    description VARCHAR(255),
                    reference_id INT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
                """)
                
                # Create credit_settings table for admin configuration
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS credit_settings (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    setting_name VARCHAR(100) UNIQUE NOT NULL,
                    setting_value VARCHAR(255) NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                )
                """)
                
                # Check if articles table has SEO columns
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS articles (
                        id INT PRIMARY KEY AUTO_INCREMENT,
                        user_id INT NOT NULL,
                        title VARCHAR(255) NOT NULL,
                        content TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        model VARCHAR(50),
                        credits_cost INT DEFAULT 0,
                        seo_title VARCHAR(255),
                        seo_description VARCHAR(500),
                        focus_keyword VARCHAR(255),
                        FOREIGN KEY (user_id) REFERENCES users(id)
                    )
                """)
                
                # Check if we need to add SEO columns to an existing table
                columns_to_add = [
                    ('seo_title', 'VARCHAR(255)'),
                    ('seo_description', 'VARCHAR(500)'),
                    ('focus_keyword', 'VARCHAR(255)')
                ]
                
                for column_name, column_type in columns_to_add:
                    try:
                        cursor.execute(f"""
                            SELECT * FROM INFORMATION_SCHEMA.COLUMNS 
                            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'articles' AND COLUMN_NAME = %s
                        """, (Config.MYSQL_DB, column_name))
                        
                        if not cursor.fetchone():
                            cursor.execute(f"ALTER TABLE articles ADD COLUMN {column_name} {column_type}")
                            print(f"Added {column_name} column to articles table")
                    except Exception as e:
                        print(f"Error checking/adding {column_name} column: {e}")
                
                # Create OTP table - with fixed expires_at field
                try:
                    cursor.execute("""
                    CREATE TABLE IF NOT EXISTS user_otp (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        user_id INT,
                        email VARCHAR(100),
                        otp_code VARCHAR(8) NOT NULL,
                        purpose ENUM('signup', 'password_reset', 'login', 'account_deletion') NOT NULL,
                        is_used BOOLEAN DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        expires_at TIMESTAMP NULL,
                        INDEX (user_id),
                        INDEX (email)
                    )
                    """)
                    print("Created or verified user_otp table")
                except Exception as e:
                    print(f"Error creating user_otp table: {e}")
                
                # Create user OTP settings table
                try:
                    cursor.execute("""
                    CREATE TABLE IF NOT EXISTS user_otp_settings (
                        user_id INT PRIMARY KEY,
                        otp_enabled_for_login BOOLEAN DEFAULT 0,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                    )
                    """)
                    print("Created or verified user_otp_settings table")
                except Exception as e:
                    print(f"Error creating user_otp_settings table: {e}")
                
                # Add account verified column to users table if it doesn't exist
                try:
                    cursor.execute("""
                    SELECT * FROM INFORMATION_SCHEMA.COLUMNS 
                    WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'users' AND COLUMN_NAME = 'is_verified'
                    """, (Config.MYSQL_DB,))
                    if not cursor.fetchone():
                        cursor.execute("ALTER TABLE users ADD COLUMN is_verified BOOLEAN DEFAULT 1")
                        print("Added is_verified column to users table")
                except Exception as e:
                    print(f"Error checking/adding is_verified column: {e}")
                
                # Check and fix expires_at column in user_otp table if it exists
                try:
                    cursor.execute("""
                    SELECT * FROM INFORMATION_SCHEMA.COLUMNS 
                    WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'user_otp' AND COLUMN_NAME = 'expires_at'
                    """, (Config.MYSQL_DB,))
                    expires_at_col = cursor.fetchone()
                    
                    if expires_at_col and expires_at_col.get('IS_NULLABLE') == 'NO':
                        # Column exists but is not nullable, alter it
                        cursor.execute("ALTER TABLE user_otp MODIFY expires_at TIMESTAMP NULL")
                        print("Modified expires_at column in user_otp table to be nullable")
                except Exception as e:
                    print(f"Error checking/fixing expires_at column: {e}")
                
                # Create email_settings table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS email_settings (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    setting_name VARCHAR(100) UNIQUE NOT NULL,
                    setting_value TEXT NOT NULL,
                    is_encrypted BOOLEAN DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                )
                """)
                
                # Check if credit_transactions table has expiry_date column
                try:
                    cursor.execute("""
                    SELECT * FROM INFORMATION_SCHEMA.COLUMNS 
                    WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'credit_transactions' AND COLUMN_NAME = 'expiry_date'
                    """, (Config.MYSQL_DB,))
                    if not cursor.fetchone():
                        cursor.execute("ALTER TABLE credit_transactions ADD COLUMN expiry_date TIMESTAMP NULL")
                        print("Added expiry_date column to credit_transactions table")
                except Exception as e:
                    print(f"Error checking/adding expiry_date column: {e}")
                
            connection.commit()
            
            # Initialize default settings
            Settings.get_setting('min_word_count', '300')
            Settings.get_setting('max_word_count', '1500')
            
            # Initialize default credit settings
            CreditSettings.initialize_default_settings()
            
            # Initialize default email settings
            EmailSettings.initialize_default_settings()

            # Update credit transactions table to support welcome_bonus
            try:
                Database.update_credit_transactions_table()
            except Exception as e:
                print(f"Error updating credit transactions table: {e}")

            # Update foreign key constraints
            Database.update_foreign_key_constraints()

            # Create payment settings table
            try:
                PaymentSettings.create_payment_settings_table()
                PaymentSettings.initialize_default_gateways()
            except Exception as e:
                print(f"Error creating payment settings table: {e}")
        except Exception as e:
            print(f"Error in create_tables: {e}")
        finally:
            connection.close()

    @staticmethod
    def update_credit_transactions_table():
        """Update the credit_transactions table to support welcome_bonus"""
        connection = Database.get_connection()
        try:
            with connection.cursor() as cursor:
                # Check the current transaction_type column
                cursor.execute("""
                    SELECT COLUMN_TYPE 
                    FROM INFORMATION_SCHEMA.COLUMNS 
                    WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'credit_transactions' AND COLUMN_NAME = 'transaction_type'
                """, (Config.MYSQL_DB,))
                column_info = cursor.fetchone()
                
                if column_info:
                    column_type = column_info['COLUMN_TYPE']
                    if column_type.startswith('enum') and 'welcome_bonus' not in column_type:
                        # Extract enum values
                        values = column_type[5:-1]  # Remove 'enum(' and ')'
                        values_list = [v.strip().strip("'") for v in values.split(',')]
                        
                        if 'welcome_bonus' not in values_list:
                            values_list.append('welcome_bonus')
                            new_enum = "ENUM(" + ",".join([f"'{v}'" for v in values_list]) + ")"
                            cursor.execute(f"ALTER TABLE credit_transactions MODIFY COLUMN transaction_type {new_enum}")
                            connection.commit()
                            print("Added 'welcome_bonus' to transaction_type enum")
                    elif not column_type.startswith('enum'):
                        # If it's not an enum, convert to VARCHAR to support any value
                        cursor.execute("ALTER TABLE credit_transactions MODIFY COLUMN transaction_type VARCHAR(50)")
                        connection.commit()
                        print("Changed transaction_type to VARCHAR(50)")
            
            # Also check the amount column to ensure it exists and matches credits_amount
            try:
                cursor.execute("""
                    SELECT COLUMN_NAME
                    FROM INFORMATION_SCHEMA.COLUMNS 
                    WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'credit_transactions' AND COLUMN_NAME = 'amount'
                """, (Config.MYSQL_DB,))
                if not cursor.fetchone():
                    # If amount doesn't exist, try credits_amount
                    cursor.execute("""
                        SELECT COLUMN_NAME
                        FROM INFORMATION_SCHEMA.COLUMNS 
                        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'credit_transactions' AND COLUMN_NAME = 'credits_amount'
                    """, (Config.MYSQL_DB,))
                    if cursor.fetchone():
                        # Add amount column as alias for credits_amount
                        cursor.execute("ALTER TABLE credit_transactions ADD COLUMN amount INT GENERATED ALWAYS AS (credits_amount) STORED")
                        connection.commit()
                        print("Added amount column as alias for credits_amount")
            except Exception as e:
                print(f"Error checking amount column: {e}")
            
            return True
        except Exception as e:
            print(f"Error updating credit_transactions table: {e}")
            return False
        finally:
            connection.close()

    @staticmethod
    def update_foreign_key_constraints():
        """Update foreign key constraints to use ON DELETE CASCADE where appropriate"""
        connection = Database.get_connection()
        try:
            with connection.cursor() as cursor:
                # Check if the constraint exists
                cursor.execute("""
                    SELECT CONSTRAINT_NAME FROM INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS
                    WHERE CONSTRAINT_SCHEMA = %s AND TABLE_NAME = 'credit_transactions' 
                    AND REFERENCED_TABLE_NAME = 'users'
                """, (Config.MYSQL_DB,))
                constraint = cursor.fetchone()
                
                if constraint:
                    constraint_name = constraint['CONSTRAINT_NAME']
                    # Drop the existing constraint
                    cursor.execute(f"ALTER TABLE credit_transactions DROP FOREIGN KEY {constraint_name}")
                    
                    # Add the new constraint with ON DELETE CASCADE
                    cursor.execute(f"""
                        ALTER TABLE credit_transactions
                        ADD CONSTRAINT {constraint_name}
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                    """)
                    
                    print(f"Updated foreign key constraint {constraint_name} with ON DELETE CASCADE")
            
            connection.commit()
            return True
        except Exception as e:
            print(f"Error updating foreign key constraints: {e}")
            return False
        finally:
            connection.close()

    @staticmethod
    def update_all_foreign_key_constraints():
        """Update all foreign key constraints to use ON DELETE CASCADE"""
        tables_with_user_fk = [
            'credit_transactions', 
            'user_credits', 
            'payments', 
            'user_otp_settings',
            'user_otp',
            'articles',
            'api_keys'
        ]
        
        connection = Database.get_connection()
        try:
            for table in tables_with_user_fk:
                try:
                    with connection.cursor() as cursor:
                        # Check if the constraint exists
                        cursor.execute("""
                            SELECT CONSTRAINT_NAME FROM INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS
                            WHERE CONSTRAINT_SCHEMA = %s AND TABLE_NAME = %s 
                            AND REFERENCED_TABLE_NAME = 'users'
                        """, (Config.MYSQL_DB, table))
                        constraint = cursor.fetchone()
                        
                        if constraint:
                            constraint_name = constraint['CONSTRAINT_NAME']
                            # Drop the existing constraint
                            cursor.execute(f"ALTER TABLE {table} DROP FOREIGN KEY {constraint_name}")
                            
                            # Add the new constraint with ON DELETE CASCADE
                            cursor.execute(f"""
                                ALTER TABLE {table}
                                ADD CONSTRAINT {constraint_name}
                                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                            """)
                            
                            print(f"Updated foreign key constraint {constraint_name} on table {table} with ON DELETE CASCADE")
                    
                    connection.commit()
                except Exception as e:
                    print(f"Error updating foreign key constraints for table {table}: {e}")
                    
            return True
        except Exception as e:
            print(f"Error in update_all_foreign_key_constraints: {e}")
            return False
        finally:
            connection.close()

    @staticmethod
    def ensure_user_tables():
        """Ensure that all required user-related tables exist"""
        try:
            connection = Database.get_connection()
            with connection.cursor() as cursor:
                # Check/create users table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        full_name VARCHAR(255) NOT NULL,
                        email VARCHAR(255) NOT NULL UNIQUE,
                        password_hash VARCHAR(255) NOT NULL,
                        is_verified BOOLEAN NOT NULL DEFAULT FALSE,
                        is_admin BOOLEAN NOT NULL DEFAULT FALSE,
                        created_at DATETIME NOT NULL,
                        updated_at DATETIME NOT NULL,
                        INDEX(email)
                    );
                """)
                
                # Check/create user_settings table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS user_settings (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        user_id INT NOT NULL,
                        otp_enabled_for_login BOOLEAN NOT NULL DEFAULT FALSE,
                        created_at DATETIME NOT NULL,
                        updated_at DATETIME NOT NULL,
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                    );
                """)
                
                # Check/create user_credits table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS user_credits (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        user_id INT NOT NULL,
                        credits_balance INT NOT NULL DEFAULT 0,
                        last_updated DATETIME NOT NULL,
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                    );
                """)
                
                connection.commit()
                return True
        except Exception as e:
            print(f"Error ensuring user tables: {e}")
            return False
        finally:
            connection.close()

class User:
    @staticmethod
    def create(full_name, email, password, is_verified=False):
        """Create a new user with proper error handling"""
        try:
            # Hash the password
            from werkzeug.security import generate_password_hash
            password_hash = generate_password_hash(password)
            from datetime import datetime
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            connection = Database.get_connection()
            try:
                with connection.cursor() as cursor:
                    # Check if user already exists
                    cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
                    if cursor.fetchone():
                        print(f"User with email {email} already exists")
                        return None
                    
                    # Create the user
                    try:
                        # Try with updated_at and created_at as explicit DATETIME values
                        cursor.execute("""
                            INSERT INTO users 
                            (full_name, email, password_hash, is_verified, created_at, updated_at) 
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """, (full_name, email, password_hash, is_verified, now, now))
                    except Exception as inner_e:
                        print(f"Initial insert attempt failed: {inner_e}")
                        # Fall back to DEFAULT or NOW() for timestamps if explicit values fail
                        try:
                            cursor.execute("""
                                INSERT INTO users 
                                (full_name, email, password_hash, is_verified) 
                                VALUES (%s, %s, %s, %s)
                            """, (full_name, email, password_hash, is_verified))
                        except Exception as fallback_e:
                            print(f"Fallback insert attempt failed: {fallback_e}")
                            # Final fallback - try to adapt to possible schema variations
                            cursor.execute("""
                                INSERT INTO users 
                                (full_name, email, password_hash, is_verified, created_at, updated_at) 
                                VALUES (%s, %s, %s, %s, NOW(), NOW())
                            """, (full_name, email, password_hash, is_verified))
                    
                    user_id = cursor.lastrowid
                    print(f"Successfully created user with ID: {user_id}")
                    
                    # Create user settings and credits records
                    try:
                        # First try with timestamps
                        cursor.execute("""
                            INSERT INTO user_settings 
                            (user_id, created_at, updated_at) 
                            VALUES (%s, %s, %s)
                        """, (user_id, now, now))
                    except Exception as settings_e:
                        print(f"Settings insert with timestamps failed: {settings_e}")
                        # Fall back to NOW()
                        cursor.execute("""
                            INSERT INTO user_settings 
                            (user_id, created_at, updated_at) 
                            VALUES (%s, NOW(), NOW())
                        """, (user_id,))
                    
                    try:
                        cursor.execute("""
                            INSERT INTO user_credits 
                            (user_id, credits_balance, last_updated) 
                            VALUES (%s, 0, %s)
                        """, (user_id, now))
                    except Exception as credits_e:
                        print(f"Credits insert with timestamp failed: {credits_e}")
                        # Try alternate schema
                        try:
                            cursor.execute("""
                                INSERT INTO user_credits 
                                (user_id, credits_balance, last_updated) 
                                VALUES (%s, 0, NOW())
                            """, (user_id,))
                        except:
                            # Final fallback - try most common schema
                            cursor.execute("""
                                INSERT INTO user_credits 
                                (user_id, credits_balance) 
                                VALUES (%s, 0)
                            """, (user_id,))
                    
                    connection.commit()
                    return user_id
                
            except Exception as db_error:
                connection.rollback()
                print(f"Database error creating user: {str(db_error)}")
                import traceback
                traceback.print_exc()
                return None
            finally:
                connection.close()
        
        except Exception as e:
            print(f"Unexpected error creating user: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
    
    @staticmethod
    def verify(email, password):
        connection = Database.get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
                user = cursor.fetchone()
                if user and check_password_hash(user['password_hash'], password):
                    return user
            return None
        finally:
            connection.close()
    
    @staticmethod
    def get_by_id(user_id):
        connection = Database.get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
                user = cursor.fetchone()
                return user
        finally:
            connection.close()
    
    @staticmethod
    def get_all():
        connection = Database.get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT id, full_name, email, is_admin, created_at FROM users")
                return cursor.fetchall()
        finally:
            connection.close()
    
    @staticmethod
    def create_unverified(full_name, email, password):
        """Create a new unverified user account"""
        password_hash = generate_password_hash(password)
        connection = Database.get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO users (full_name, email, password_hash, is_verified) VALUES (%s, %s, %s, 0)",
                    (full_name, email, password_hash)
                )
            connection.commit()
            
            # Get the user ID of the newly created user
            with connection.cursor() as cursor:
                cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
                user = cursor.fetchone()
                return user['id'] if user else None
        except pymysql.IntegrityError:
            return None
        finally:
            connection.close()
    
    @staticmethod
    def verify_account(email):
        """Mark a user account as verified"""
        connection = Database.get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE users SET is_verified = 1 WHERE email = %s",
                    (email,)
                )
                result = cursor.rowcount > 0
            connection.commit()
            return result
        finally:
            connection.close()
    
    @staticmethod
    def update_password(email, new_password):
        """Update a user's password"""
        password_hash = generate_password_hash(new_password)
        connection = Database.get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE users SET password_hash = %s WHERE email = %s",
                    (password_hash, email)
                )
                result = cursor.rowcount > 0
            connection.commit()
            return result
        finally:
            connection.close()
    
    @staticmethod
    def delete_account(user_id):
        """Delete a user account"""
        return User.delete(user_id)
    
    @staticmethod
    def requires_otp_for_login(email):
        """Check if a user has OTP enabled for login"""
        connection = Database.get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT us.otp_enabled_for_login 
                    FROM users u
                    LEFT JOIN user_otp_settings us ON u.id = us.user_id
                    WHERE u.email = %s
                """, (email,))
                result = cursor.fetchone()
                return result and result.get('otp_enabled_for_login', False)
        except Exception as e:
            print(f"Error checking OTP requirement: {e}")
            return False
        finally:
            connection.close()
    
    @staticmethod
    def get_by_email(email):
        """Get user by email"""
        connection = Database.get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
                user = cursor.fetchone()
                return user
        finally:
            connection.close()
    
    @staticmethod
    def create_with_settings(full_name, email, password, is_verified=True, is_admin=False):
        """Create a new user with specified settings"""
        # First check if email already exists
        existing_user = User.get_by_email(email)
        if existing_user:
            return None
        
        password_hash = generate_password_hash(password)
        connection = Database.get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO users (full_name, email, password_hash, is_verified, is_admin) VALUES (%s, %s, %s, %s, %s)",
                    (full_name, email, password_hash, is_verified, is_admin)
                )
                user_id = cursor.lastrowid
            connection.commit()
            
            # Initialize credit record
            if user_id:
                UserCredits.initialize(user_id)
            
            return user_id
        except pymysql.IntegrityError:
            return None
        finally:
            connection.close()
    
    @staticmethod
    def update(user_id, full_name, email, is_verified, is_admin):
        """Update user information"""
        # Get current user data to check if email is changing
        current_user = User.get_by_id(user_id)
        if not current_user:
            return False
            
        # If email is changing, check if the new email already exists
        if email != current_user['email']:
            existing_user = User.get_by_email(email)
            if existing_user and existing_user['id'] != user_id:
                return False
        
        connection = Database.get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE users SET full_name = %s, email = %s, is_verified = %s, is_admin = %s WHERE id = %s",
                    (full_name, email, is_verified, is_admin, user_id)
                )
                success = cursor.rowcount > 0
            connection.commit()
            return success
        except pymysql.IntegrityError:
            return False
        finally:
            connection.close()
    
    @staticmethod
    def update_password_by_id(user_id, new_password):
        """Update a user's password by user_id"""
        password_hash = generate_password_hash(new_password)
        connection = Database.get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE users SET password_hash = %s WHERE id = %s",
                    (password_hash, user_id)
                )
                result = cursor.rowcount > 0
            connection.commit()
            return result
        finally:
            connection.close()
    
    @staticmethod
    def update_admin_status(user_id, is_admin):
        """Update a user's admin status"""
        connection = Database.get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE users SET is_admin = %s WHERE id = %s",
                    (is_admin, user_id)
                )
                result = cursor.rowcount > 0
            connection.commit()
            return result
        finally:
            connection.close()
    
    @staticmethod
    def delete(user_id):
        """Delete a user and all associated data"""
        connection = Database.get_connection()
        try:
            # Using transactions to ensure all deletions succeed or fail together
            connection.begin()
            with connection.cursor() as cursor:
                # Delete user credits
                cursor.execute("DELETE FROM user_credits WHERE user_id = %s", (user_id,))
                
                # Delete credit transactions
                cursor.execute("DELETE FROM credit_transactions WHERE user_id = %s", (user_id,))
                
                # Delete payments
                cursor.execute("DELETE FROM payments WHERE user_id = %s", (user_id,))
                
                # Delete OTP settings
                cursor.execute("DELETE FROM user_otp_settings WHERE user_id = %s", (user_id,))
                
                # Delete OTP records
                cursor.execute("DELETE FROM user_otp WHERE user_id = %s", (user_id,))
                
                # Delete login history if it exists
                try:
                    cursor.execute("DELETE FROM user_login_history WHERE user_id = %s", (user_id,))
                except:
                    pass  # Table might not exist
                
                # Delete articles (or you could choose to keep them but mark them as orphaned)
                cursor.execute("DELETE FROM articles WHERE user_id = %s", (user_id,))
                
                # Finally delete the user
                cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
                result = cursor.rowcount > 0
            
            connection.commit()
            return result
        except Exception as e:
            connection.rollback()
            print(f"Error deleting user: {e}")
            return False
        finally:
            connection.close()
    
    @staticmethod
    def add_first_time_free_credits(user_id):
        """Add first-time free credits to a new user with improved error handling"""
        try:
            # Default free credits amount
            free_credits = 5000
            
            # Get the amount from settings
            connection = Database.get_connection()
            try:
                with connection.cursor() as cursor:
                    # First check credit_settings table
                    cursor.execute(
                        "SELECT setting_value FROM credit_settings WHERE setting_name = 'first_time_free_credits'"
                    )
                    result = cursor.fetchone()
                    if result:
                        free_credits = int(result['setting_value'])
                    else:
                        # Try settings table as fallback
                        cursor.execute(
                            "SELECT setting_value FROM settings WHERE setting_name = 'first_time_free_credits'"
                        )
                        result = cursor.fetchone()
                        if result:
                            free_credits = int(result['setting_value'])
            finally:
                connection.close()

            if free_credits > 0:
                # Add credits using UserCredits class
                success = UserCredits.add_credits(
                    user_id,
                    free_credits,
                    'welcome_bonus',
                    'Welcome bonus - Free credits for new account'
                )
                
                if success:
                    print(f"Successfully added {free_credits} welcome credits to user {user_id}")
                    return True
                else:
                    print(f"Failed to add welcome credits to user {user_id}")
                    return False
                    
            return True  # Return true if no credits to add (not an error)
            
        except Exception as e:
            print(f"Error adding first-time credits: {e}")
            import traceback
            traceback.print_exc()
            return False

    @staticmethod
    def store_verification_token(user_id, token):
        """Store a verification token for a user"""
        # Since there's no dedicated table for verification tokens,
        # we'll use the OTP system with a special purpose
        connection = Database.get_connection()
        try:
            with connection.cursor() as cursor:
                # First, check if we need to expand the purpose enum
                cursor.execute("""
                    SELECT COLUMN_TYPE 
                    FROM INFORMATION_SCHEMA.COLUMNS 
                    WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'user_otp' AND COLUMN_NAME = 'purpose'
                """, (Config.MYSQL_DB,))
                column_type = cursor.fetchone()
                
                if column_type and 'account_verification' not in column_type['COLUMN_TYPE']:
                    # Add account_verification to purpose enum if it doesn't exist
                    try:
                        # Extract current enum values and add new one
                        enum_str = column_type['COLUMN_TYPE']
                        start_idx = enum_str.find("(") + 1
                        end_idx = enum_str.find(")")
                        enum_values = enum_str[start_idx:end_idx].split(",")
                        enum_values = [v.strip("'") for v in enum_values]
                        
                        if 'account_verification' not in enum_values:
                            enum_values.append('account_verification')
                        
                        # Rebuild enum string
                        new_enum_str = "ENUM(" + ",".join([f"'{v}'" for v in enum_values]) + ")"
                        cursor.execute(f"ALTER TABLE user_otp MODIFY COLUMN purpose {new_enum_str} NOT NULL")
                        print("Added 'account_verification' to purpose enum")
                    except Exception as e:
                        print(f"Error modifying purpose enum: {e}")
                        # If we can't modify the enum, use signup as fallback
                        user_email = None
                        cursor.execute("SELECT email FROM users WHERE id = %s", (user_id,))
                        user = cursor.fetchone()
                        if user:
                            user_email = user['email']
                        
                        # Create new token entry (using token as the OTP code)
                        expiry_time = datetime.now() + timedelta(days=3)  # Token valid for 3 days
                        cursor.execute(
                            """INSERT INTO user_otp 
                               (user_id, email, otp_code, purpose, is_used, expires_at) 
                               VALUES (%s, %s, %s, 'signup', 0, %s)""",
                            (user_id, user_email, token, expiry_time)
                        )
                        connection.commit()
                        return True
                
                # If we got here, we can use account_verification or the enum modification succeeded
                # First, invalidate any existing tokens for this user
                cursor.execute(
                    "UPDATE user_otp SET is_used = 1 WHERE user_id = %s AND purpose = 'signup'",
                    (user_id,)
                )
                
                # Get user email
                cursor.execute("SELECT email FROM users WHERE id = %s", (user_id,))
                user = cursor.fetchone()
                if not user:
                    return False
                    
                # Create new token entry (using token as the OTP code)
                expiry_time = datetime.now() + timedelta(days=3)  # Token valid for 3 days
                cursor.execute(
                    """INSERT INTO user_otp 
                       (user_id, email, otp_code, purpose, is_used, expires_at) 
                       VALUES (%s, %s, %s, 'signup', 0, %s)""",
                    (user_id, user['email'], token, expiry_time)
                )
            connection.commit()
            return True
        except Exception as e:
            print(f"Error storing verification token: {e}")
            return False
        finally:
            connection.close()

    @staticmethod
    def initialize(user_id):
        """Initialize user credit record with zero balance"""
        connection = Database.get_connection()
        try:
            with connection.cursor() as cursor:
                # Check if record already exists
                cursor.execute("SELECT id FROM user_credits WHERE user_id = %s", (user_id,))
                if not cursor.fetchone():
                    # Check if columns exist in the table
                    try:
                        cursor.execute(
                            "INSERT INTO user_credits (user_id, credits_balance, total_credits_purchased, total_credits_used) VALUES (%s, 0, 0, 0)",
                            (user_id,)
                        )
                    except pymysql.err.OperationalError:
                        # Fallback if some columns don't exist
                        cursor.execute(
                            "INSERT INTO user_credits (user_id, credits_balance) VALUES (%s, 0)",
                            (user_id,)
                        )
                    connection.commit()
                    return True
                return True  # Already initialized is still a success
        except Exception as e:
            print(f"Error initializing user credits: {e}")
            return False
        finally:
            connection.close()

    @staticmethod
    def authenticate(email, password):
        """Authenticate a user by email and password
        
        Args:
            email: The user's email address
            password: The plain text password to verify
            
        Returns:
            dict: User data if authentication is successful, None otherwise
        """
        if not email or not password:
            return None
            
        connection = Database.get_connection()
        try:
            with connection.cursor() as cursor:
                # Get user by email
                cursor.execute(
                    "SELECT * FROM users WHERE email = %s", 
                    (email,)
                )
                user = cursor.fetchone()
                
                # Check if user exists and password matches
                if user and check_password_hash(user['password_hash'], password):
                    # Update last login timestamp
                    try:
                        cursor.execute(
                            "UPDATE users SET last_login = NOW() WHERE id = %s",
                            (user['id'],)
                        )
                        connection.commit()
                    except Exception as e:
                        # Log error but continue (non-critical)
                        print(f"Error updating last login: {e}")
                    
                    # Try to record login history if table exists
                    try:
                        ip_address = request.remote_addr if 'request' in globals() else '0.0.0.0'
                        user_agent = request.headers.get('User-Agent', '') if 'request' in globals() else ''
                        
                        cursor.execute("""
                            INSERT INTO user_login_history 
                            (user_id, ip_address, user_agent, success) 
                            VALUES (%s, %s, %s, 1)
                        """, (user['id'], ip_address, user_agent))
                        connection.commit()
                    except Exception:
                        # Table may not exist, which is fine
                        pass
                        
                    return user
                    
                # Failed login attempt - try to record if tracking table exists
                try:
                    if user:
                        ip_address = request.remote_addr if 'request' in globals() else '0.0.0.0'
                        user_agent = request.headers.get('User-Agent', '') if 'request' in globals() else ''
                        
                        cursor.execute("""
                            INSERT INTO user_login_history 
                            (user_id, ip_address, user_agent, success) 
                            VALUES (%s, %s, %s, 0)
                        """, (user['id'], ip_address, user_agent))
                        connection.commit()
                except Exception:
                    # Table may not exist, which is fine
                    pass
                
                return None
                
        except Exception as e:
            print(f"Authentication error: {e}")
            return None
        finally:
            connection.close()

    @staticmethod
    def user_exists(email):
        """Check if a user with the given email exists
        
        Args:
            email: The email to check
            
        Returns:
            bool: True if user exists, False otherwise
        """
        if not email:
            return False
            
        connection = Database.get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
                return cursor.fetchone() is not None
        except Exception as e:
            print(f"Error checking if user exists: {e}")
            return False
        finally:
            connection.close()

class Article:
    @staticmethod
    def create(title, content, user_id, model=None, credits_cost=0, seo_title=None, seo_description=None, focus_keyword=None):
        """Create a new article"""
        connection = Database.get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO articles 
                       (title, content, user_id, model, credits_cost, seo_title, seo_description, focus_keyword) 
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                    (title, content, user_id, model, credits_cost, seo_title, seo_description, focus_keyword)
                )
                article_id = cursor.lastrowid
            connection.commit()
            return article_id
        except Exception as e:
            print(f"Error creating article: {e}")
            return None
        finally:
            connection.close()
    
    @staticmethod
    def get_by_id(article_id):
        connection = Database.get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                SELECT a.*, u.full_name as user_fullname
                FROM articles a
                JOIN users u ON a.user_id = u.id
                WHERE a.id = %s
            """, (article_id,))
                article = cursor.fetchone()
                return article
        finally:
            connection.close()
    
    @staticmethod
    def get_all():
        connection = Database.get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                SELECT a.*, u.full_name as author 
                FROM articles a 
                JOIN users u ON a.user_id = u.id 
                ORDER BY a.created_at DESC
                """)
                return cursor.fetchall()
        finally:
            connection.close()
    
    @staticmethod
    def get_by_user(user_id):
        connection = Database.get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                SELECT * FROM articles 
                WHERE user_id = %s 
                ORDER BY created_at DESC
                """, (user_id,))
                return cursor.fetchall()
        finally:
            connection.close()
    
    @staticmethod
    def delete_old_articles():
        """Delete articles older than the auto-delete days setting"""
        # Get the auto-delete days setting
        auto_delete_days = int(CreditSettings.get_setting('article_auto_delete_days', '90'))
        
        # If auto-delete is disabled (set to 0), don't delete anything
        if auto_delete_days <= 0:
            return 0
        
        connection = Database.get_connection()
        try:
            with connection.cursor() as cursor:
                # Find articles older than the specified days
                cursor.execute("""
                    DELETE FROM articles 
                    WHERE created_at < DATE_SUB(NOW(), INTERVAL %s DAY)
                """, (auto_delete_days,))
                
                deleted_count = cursor.rowcount
            connection.commit()
            return deleted_count
        except Exception as e:
            print(f"Error deleting old articles: {e}")
            return 0
        finally:
            connection.close()

class ApiKey:
    @staticmethod
    def save(user_id, api_key, is_valid=False, verification_message=None):
        connection = Database.get_connection()
        try:
            with connection.cursor() as cursor:
                # Check if user already has an API key
                cursor.execute("SELECT id FROM api_keys WHERE user_id = %s", (user_id,))
                existing = cursor.fetchone()
                
                current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                # Check if verification_message column exists
                try:
                    cursor.execute("""
                    SELECT * FROM INFORMATION_SCHEMA.COLUMNS 
                    WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'api_keys' AND COLUMN_NAME = 'verification_message'
                    """, (Config.MYSQL_DB,))
                    has_verification_message = bool(cursor.fetchone())
                except:
                    has_verification_message = False
                    
                # Check if last_verified column exists
                try:
                    cursor.execute("""
                    SELECT * FROM INFORMATION_SCHEMA.COLUMNS 
                    WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'api_keys' AND COLUMN_NAME = 'last_verified'
                    """, (Config.MYSQL_DB,))
                    has_last_verified = bool(cursor.fetchone())
                except:
                    has_last_verified = False
                
                if existing:
                    # Construct update SQL based on available columns
                    if has_verification_message and has_last_verified:
                        cursor.execute(
                            "UPDATE api_keys SET api_key = %s, is_valid = %s, verification_message = %s, last_verified = %s WHERE user_id = %s",
                            (api_key, is_valid, verification_message, current_time, user_id)
                        )
                    elif has_verification_message:
                        cursor.execute(
                            "UPDATE api_keys SET api_key = %s, is_valid = %s, verification_message = %s WHERE user_id = %s",
                            (api_key, is_valid, verification_message, user_id)
                        )
                    elif has_last_verified:
                        cursor.execute(
                            "UPDATE api_keys SET api_key = %s, is_valid = %s, last_verified = %s WHERE user_id = %s",
                            (api_key, is_valid, current_time, user_id)
                        )
                    else:
                        cursor.execute(
                            "UPDATE api_keys SET api_key = %s, is_valid = %s WHERE user_id = %s",
                            (api_key, is_valid, user_id)
                        )
                else:
                    # Construct insert SQL based on available columns
                    if has_verification_message and has_last_verified:
                        cursor.execute(
                            "INSERT INTO api_keys (user_id, api_key, is_valid, verification_message, last_verified) VALUES (%s, %s, %s, %s, %s)",
                            (user_id, api_key, is_valid, verification_message, current_time)
                        )
                    elif has_verification_message:
                        cursor.execute(
                            "INSERT INTO api_keys (user_id, api_key, is_valid, verification_message) VALUES (%s, %s, %s, %s)",
                            (user_id, api_key, is_valid, verification_message)
                        )
                    elif has_last_verified:
                        cursor.execute(
                            "INSERT INTO api_keys (user_id, api_key, is_valid, last_verified) VALUES (%s, %s, %s, %s)",
                            (user_id, api_key, is_valid, current_time)
                        )
                    else:
                        cursor.execute(
                            "INSERT INTO api_keys (user_id, api_key, is_valid) VALUES (%s, %s, %s)",
                            (user_id, api_key, is_valid)
                        )
                connection.commit()
                return True
        except Exception as e:
            print(f"Error saving API key: {e}")
            return False
        finally:
            connection.close()
    
    @staticmethod
    def get_by_user(user_id):
        connection = Database.get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM api_keys WHERE user_id = %s", (user_id,))
                return cursor.fetchone()
        finally:
            connection.close()
    
    @staticmethod
    def verify_api_key(api_key):
        """Verify an x.ai API key by making a test API call"""
        try:
            # Basic format check
            if not api_key or not api_key.startswith('xai-'):
                return False, "API key must start with 'xai-'"
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            # Simple test request to the models endpoint
            response = requests.get(
                "https://api.x.ai/v1/models",
                headers=headers,
                timeout=10
            )
            
            # Debug response
            print(f"API Key Verification Status: {response.status_code}")
            
            if 200 <= response.status_code < 300:
                return True, "API key successfully verified"
            else:
                return False, f"API verification failed: Status {response.status_code}"
            
        except Exception as e:
            return False, f"Error during verification: {str(e)}"

class Settings:
    @staticmethod
    def create_settings_table():
        connection = Database.get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    setting_name VARCHAR(100) UNIQUE NOT NULL,
                    setting_value VARCHAR(255) NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                )
                """)
            connection.commit()
        finally:
            connection.close()
    
    @staticmethod
    def get_setting(setting_name, default_value=None):
        connection = Database.get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT setting_value FROM settings WHERE setting_name = %s", (setting_name,))
                result = cursor.fetchone()
                if result:
                    return result['setting_value']
                else:
                    # Insert default value if it doesn't exist
                    if default_value is not None:
                        Settings.set_setting(setting_name, default_value)
                    return default_value
        finally:
            connection.close()
    
    @staticmethod
    def set_setting(setting_name, setting_value):
        connection = Database.get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                INSERT INTO settings (setting_name, setting_value) 
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE setting_value = %s
                """, (setting_name, setting_value, setting_value))
            connection.commit()
            return True
        except Exception as e:
            print(f"Error setting value: {e}")
            return False
        finally:
            connection.close()
    
    @staticmethod
    def get_default_model():
        """Get the default model for article generation"""
        default_model = Settings.get_setting('default_model')
        if not default_model:
            # Set grok-2-1212 as the initial default model if none is set
            Settings.set_setting('default_model', 'grok-2-1212')
            return 'grok-2-1212'
        return default_model
    
    @staticmethod
    def set_default_model(model_id):
        """Set the default model for article generation"""
        return Settings.set_setting('default_model', model_id)
    
    @staticmethod
    def update_setting(setting_name, setting_value):
        """Update a setting or create it if it doesn't exist
        
        Args:
            setting_name: Name of the setting
            setting_value: Value to set
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            connection = Database.get_connection()
            with connection.cursor() as cursor:
                # Create settings table if it doesn't exist
                Settings.create_settings_table()
                
                # Check if setting exists
                cursor.execute("SELECT value FROM settings WHERE name = %s", (setting_name,))
                result = cursor.fetchone()
                
                if result:
                    # Update existing setting
                    cursor.execute(
                        "UPDATE settings SET value = %s, updated_at = NOW() WHERE name = %s",
                        (setting_value, setting_name)
                    )
                else:
                    # Create new setting
                    cursor.execute(
                        "INSERT INTO settings (name, value, created_at, updated_at) VALUES (%s, %s, NOW(), NOW())",
                        (setting_name, setting_value)
                    )
                
                connection.commit()
                return True
        except Exception as e:
            print(f"Error updating setting '{setting_name}': {e}")
            if connection:
                connection.rollback()
            return False
        finally:
            if connection:
                connection.close()

class ModelSettings:
    @staticmethod
    def create_model_settings_table():
        """Create model settings table if it doesn't exist, with credits_per_word column"""
        connection = Database.get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS model_settings (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        model_id VARCHAR(50) UNIQUE NOT NULL,
                        display_name VARCHAR(100),
                        is_enabled BOOLEAN DEFAULT TRUE,
                        custom_description TEXT,
                        credits_per_word INT DEFAULT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                    )
                """)
                
                # Check if credits_per_word column exists, add it if not
                cursor.execute("""
                    SELECT COUNT(*) as count FROM information_schema.COLUMNS 
                    WHERE TABLE_SCHEMA = DATABASE() 
                    AND TABLE_NAME = 'model_settings' 
                    AND COLUMN_NAME = 'credits_per_word'
                """)
                result = cursor.fetchone()
                
                if result and result['count'] == 0:
                    cursor.execute("""
                        ALTER TABLE model_settings
                        ADD COLUMN credits_per_word INT DEFAULT NULL
                    """)
                    print("Added credits_per_word column to model_settings table")
                    
                connection.commit()
        except Exception as e:
            print(f"Error creating model settings table: {e}")
        finally:
            connection.close()
    
    @staticmethod
    def get_model_settings(model_id):
        connection = Database.get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM model_settings WHERE model_id = %s", (model_id,))
                return cursor.fetchone()
        finally:
            connection.close()
    
    @staticmethod
    def get_all_model_settings():
        connection = Database.get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM model_settings")
                return cursor.fetchall()
        finally:
            connection.close()
    
    @staticmethod
    def save_model_settings(model_id, display_name=None, is_enabled=True, custom_description=None, credits_per_word=None):
        """Save model settings with credit cost per word
        
        Args:
            model_id: The model ID
            display_name: Display name to show users
            is_enabled: Whether the model is enabled
            custom_description: Custom model description
            credits_per_word: Number of credits per word for this model
        """
        connection = Database.get_connection()
        try:
            with connection.cursor() as cursor:
                # Check if model settings already exist
                cursor.execute(
                    "SELECT id FROM model_settings WHERE model_id = %s",
                    (model_id,)
                )
                existing = cursor.fetchone()
                
                if existing:
                    # Update existing settings
                    cursor.execute(
                        """UPDATE model_settings 
                           SET display_name = %s, 
                               is_enabled = %s, 
                               custom_description = %s,
                               credits_per_word = %s,
                               updated_at = NOW()
                           WHERE model_id = %s""",
                        (display_name, is_enabled, custom_description, credits_per_word, model_id)
                    )
                else:
                    # Insert new settings
                    cursor.execute(
                        """INSERT INTO model_settings 
                           (model_id, display_name, is_enabled, custom_description, credits_per_word)
                           VALUES (%s, %s, %s, %s, %s)""",
                        (model_id, display_name, is_enabled, custom_description, credits_per_word)
                    )
                
                connection.commit()
                return True
                
        except Exception as e:
            connection.rollback()
            print(f"Error saving model settings: {e}")
            return False
        finally:
            connection.close()
    
    @staticmethod
    def get_credits_per_word(model_id):
        """Get credits per word for a specific model
        
        Args:
            model_id: The model ID
        
        Returns:
            int: Credits per word for this model, or None to use global setting
        """
        connection = Database.get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT credits_per_word FROM model_settings WHERE model_id = %s",
                    (model_id,)
                )
                result = cursor.fetchone()
                
                if result and result['credits_per_word'] is not None:
                    return result['credits_per_word']
                else:
                    # Return None to indicate using the global setting
                    return None
                    
        except Exception as e:
            print(f"Error getting model credits per word: {e}")
            return None
        finally:
            connection.close()

class CreditSettings:
    @staticmethod
    def initialize_default_settings():
        """Set default credit settings if they don't exist"""
        settings = [
            ('credits_per_dollar', '5000'),     # 1 USD = 5000 credits
            ('minimum_deposit', '10'),          # $10 minimum deposit
            ('credits_per_word', '1'),          # 1 credit per word
            ('payment_gateway', 'stripe'),      # Default payment gateway
            ('first_time_free_credits', '5000'), # Free credits for new users
            ('credit_expiry_days', '30'),        # Credits expire after 30 days
            ('article_auto_delete_days', '90')   # Auto-delete articles after 90 days
        ]
        
        connection = Database.get_connection()
        try:
            with connection.cursor() as cursor:
                # First ensure the table exists
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS credit_settings (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        setting_name VARCHAR(100) UNIQUE NOT NULL,
                        setting_value VARCHAR(255) NOT NULL,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                    )
                """)
                
                # Insert default settings
                for name, value in settings:
                    cursor.execute("""
                    INSERT INTO credit_settings (setting_name, setting_value) 
                    VALUES (%s, %s)
                    ON DUPLICATE KEY UPDATE setting_value = VALUES(setting_value)
                    """, (name, value))
                    
            connection.commit()
            print("Credit settings initialized successfully")
        except Exception as e:
            print(f"Error initializing credit settings: {e}")
        finally:
            connection.close()
    
    @staticmethod
    def get_setting(setting_name, default_value=None):
        """Get a credit setting value"""
        connection = Database.get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT setting_value FROM credit_settings WHERE setting_name = %s", (setting_name,))
                result = cursor.fetchone()
                if result:
                    return result['setting_value']
                else:
                    # Insert default value if it doesn't exist
                    if default_value is not None:
                        CreditSettings.set_setting(setting_name, default_value)
                    return default_value
        finally:
            connection.close()
    
    @staticmethod
    def set_setting(setting_name, setting_value):
        """Update a credit setting"""
        connection = Database.get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                INSERT INTO credit_settings (setting_name, setting_value) 
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE setting_value = %s
                """, (setting_name, setting_value, setting_value))
            connection.commit()
            return True
        except Exception as e:
            print(f"Error setting credit setting: {e}")
            return False
        finally:
            connection.close()
    
    @staticmethod
    def get_all_settings():
        """Get all credit settings"""
        connection = Database.get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT setting_name, setting_value FROM credit_settings")
                settings = cursor.fetchall()
                
                # If no results, try the old table format
                if not settings:
                    try:
                        cursor.execute("SELECT * FROM credit_settings LIMIT 1")
                        old_format_settings = cursor.fetchone()
                        
                        if old_format_settings:
                            # Convert old format to new format
                            settings = []
                            for key, value in old_format_settings.items():
                                # Skip non-setting columns like id, created_at, etc.
                                if key not in ['id', 'settings_last_updated']:
                                    settings.append({
                                        'setting_name': key,
                                        'setting_value': str(value)
                                    })
                    except Exception as e:
                        print(f"Error checking old settings format: {e}")
                
                return settings
        except Exception as e:
            print(f"Error getting credit settings: {e}")
            return []
        finally:
            connection.close()

class UserCredits:
    @staticmethod
    def get_balance(user_id):
        """Get the credit balance for a user"""
        connection = Database.get_connection()
        try:
            with connection.cursor() as cursor:
                # Check if user has a credit record
                cursor.execute("SELECT credits_balance FROM user_credits WHERE user_id = %s", (user_id,))
                result = cursor.fetchone()
                
                if result:
                    return result['credits_balance']
                else:
                    # Create initial record with 0 balance
                    cursor.execute(
                        "INSERT INTO user_credits (user_id, credits_balance) VALUES (%s, 0)",
                        (user_id,)
                    )
                    connection.commit()
                    return 0
        finally:
            connection.close()
    
    @staticmethod
    def add_credits(user_id, amount, source='purchase', description=None, reference_id=None):
        """Add credits to a user's balance"""
        if amount <= 0:
            return False
            
        # Map source to transaction_type
        transaction_type = source
        if source not in ['add', 'purchase', 'refund', 'adjustment', 'welcome_bonus']:
            transaction_type = 'adjustment'  # Default fallback
        
        # Calculate expiry date if applicable
        expiry_date = None
        if source in ['purchase', 'welcome_bonus']:  # Only apply expiration to purchased or bonus credits
            try:
                expiry_days = int(CreditSettings.get_setting('credit_expiry_days', '30'))
                if expiry_days > 0:  # If expiry is enabled
                    expiry_date = (datetime.now() + timedelta(days=expiry_days)).strftime('%Y-%m-%d %H:%M:%S')
            except Exception as e:
                print(f"Error calculating expiry date: {e}")
        
        connection = Database.get_connection()
        try:
            with connection.cursor() as cursor:
                # Get current balance
                cursor.execute("SELECT id, credits_balance FROM user_credits WHERE user_id = %s", (user_id,))
                result = cursor.fetchone()
                
                if result:
                    # Update existing record
                    new_balance = result['credits_balance'] + amount
                    cursor.execute(
                        "UPDATE user_credits SET credits_balance = %s, total_credits_purchased = total_credits_purchased + %s WHERE user_id = %s",
                        (new_balance, amount, user_id)
                    )
                else:
                    # Create new record
                    cursor.execute(
                        "INSERT INTO user_credits (user_id, credits_balance, total_credits_purchased) VALUES (%s, %s, %s)",
                        (user_id, amount, amount)
                    )
                
                # Record the transaction with expiry date
                try:
                    cursor.execute(
                        "INSERT INTO credit_transactions (user_id, credits_amount, transaction_type, description, reference_id, expiry_date) VALUES (%s, %s, %s, %s, %s, %s)",
                        (user_id, amount, transaction_type, description, reference_id, expiry_date)
                    )
                except Exception as e:
                    print(f"First attempt at recording transaction failed: {e}")
                    try:
                        # Try without expiry date if that was the issue
                        cursor.execute(
                            "INSERT INTO credit_transactions (user_id, credits_amount, transaction_type, description, reference_id) VALUES (%s, %s, %s, %s, %s)",
                            (user_id, amount, transaction_type, description, reference_id)
                        )
                    except Exception as e2:
                        print(f"Second attempt at recording transaction failed: {e2}")
            
            connection.commit()
            return True
        except Exception as e:
            print(f"Error adding credits: {e}")
            return False
        finally:
            connection.close()
    
    @staticmethod
    def deduct_credits(user_id, amount, transaction_type='usage', description=None, reference_id=None):
        """Deduct credits from a user's balance"""
        if amount <= 0:
            return False
            
        connection = Database.get_connection()
        try:
            with connection.cursor() as cursor:
                # Get current balance
                cursor.execute("SELECT id, credits_balance FROM user_credits WHERE user_id = %s", (user_id,))
                result = cursor.fetchone()
                
                if not result or result['credits_balance'] < amount:
                    # Insufficient credits
                    return False
                
                # Update balance
                new_balance = result['credits_balance'] - amount
                cursor.execute(
                    "UPDATE user_credits SET credits_balance = %s, total_credits_used = total_credits_used + %s WHERE user_id = %s",
                    (new_balance, amount, user_id)
                )
                
                # Record the transaction
                cursor.execute(
                    "INSERT INTO credit_transactions (user_id, credits_amount, transaction_type, description, reference_id) VALUES (%s, %s, %s, %s, %s)",
                    (user_id, -amount, transaction_type, description, reference_id)
                )
                
            connection.commit()
            return True
        except Exception as e:
            print(f"Error deducting credits: {e}")
            return False
        finally:
            connection.close()
    
    @staticmethod
    def get_transaction_history(user_id):
        """Get credit transaction history for a user"""
        connection = Database.get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                SELECT * FROM credit_transactions 
                WHERE user_id = %s 
                ORDER BY created_at DESC
                """, (user_id,))
                return cursor.fetchall()
        finally:
            connection.close()
    
    @staticmethod
    def get_user_credit_info(user_id):
        """Get detailed credit info for a user"""
        connection = Database.get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM user_credits WHERE user_id = %s", (user_id,))
                return cursor.fetchone()
        finally:
            connection.close()
    
    @staticmethod
    def get_transaction_history_paginated(user_id, page=1, per_page=15):
        """Get paginated transaction history for a user"""
        offset = (page - 1) * per_page
        connection = Database.get_connection()
        try:
            with connection.cursor() as cursor:
                # Get total count
                cursor.execute(
                    "SELECT COUNT(*) as count FROM credit_transactions WHERE user_id = %s",
                    (user_id,)
                )
                total = cursor.fetchone()['count']
                
                # Get transactions for current page
                cursor.execute(
                    """SELECT * FROM credit_transactions 
                       WHERE user_id = %s
                       ORDER BY created_at DESC
                       LIMIT %s OFFSET %s""",
                    (user_id, per_page, offset)
                )
                transactions = cursor.fetchall()
                
                return transactions, total
        finally:
            connection.close()
    
    @staticmethod
    def get_info(user_id):
        """Get credit information for a user including balance, total added and used"""
        connection = Database.get_connection()
        try:
            with connection.cursor() as cursor:
                # Get current balance
                cursor.execute(
                    "SELECT credits_balance FROM user_credits WHERE user_id = %s",
                    (user_id,)
                )
                balance_result = cursor.fetchone()
                credits_balance = balance_result['credits_balance'] if balance_result else 0
                
                # Get total credits added
                cursor.execute(
                    """SELECT COALESCE(SUM(amount), 0) as total_added 
                       FROM credit_transactions 
                       WHERE user_id = %s AND transaction_type = 'add'""",
                    (user_id,)
                )
                added_result = cursor.fetchone()
                total_added = added_result['total_added'] if added_result else 0
                
                # Get total credits used
                cursor.execute(
                    """SELECT COALESCE(SUM(amount), 0) as total_used 
                       FROM credit_transactions 
                       WHERE user_id = %s AND transaction_type = 'deduct'""",
                    (user_id,)
                )
                used_result = cursor.fetchone()
                total_used = used_result['total_used'] if used_result else 0
                
                return {
                    'credits_balance': credits_balance,
                    'total_added': total_added,
                    'total_used': total_used
                }
        except Exception as e:
            print(f"Error getting credit info: {e}")
            return {
                'credits_balance': 0,
                'total_added': 0,
                'total_used': 0
            }
        finally:
            connection.close()

    @staticmethod
    def get_all_transactions_paginated(page=1, per_page=20, status_filter='all', user_id=None):
        """Get all transactions with pagination and filters
        
        Args:
            page: The page number (starting from 1)
            per_page: Number of items per page
            status_filter: Filter by status ('all', 'pending', 'approved', 'cancelled')
            user_id: Filter by user ID
            
        Returns:
            dict: Contains transactions list, total count, and number of pages
        """
        connection = Database.get_connection()
        try:
            offset = (page - 1) * per_page
            
            # Build the query based on filters
            query = """
                SELECT t.*, u.email, u.full_name 
                FROM credit_transactions t
                LEFT JOIN users u ON t.user_id = u.id
                WHERE 1=1
            """
            count_query = "SELECT COUNT(*) as count FROM credit_transactions WHERE 1=1"
            params = []
            
            # Add status filter
            if status_filter and status_filter != 'all':
                query += " AND t.status = %s"
                count_query += " AND status = %s"
                params.append(status_filter)
                
            # Add user filter
            if user_id:
                query += " AND t.user_id = %s"
                count_query += " AND user_id = %s"
                params.append(user_id)
                
            # Add order and limit
            query += " ORDER BY t.created_at DESC LIMIT %s OFFSET %s"
            params.extend([per_page, offset])
            
            with connection.cursor() as cursor:
                # Get total count
                cursor.execute(count_query, params[:-2] if params else [])
                total = cursor.fetchone()['count']
                
                # Get transactions
                cursor.execute(query, params)
                transactions = cursor.fetchall()
                
                return {
                    'transactions': transactions,
                    'total': total,
                    'total_pages': (total + per_page - 1) // per_page
                }
                
        except Exception as e:
            print(f"Error getting transactions: {e}")
            return {'transactions': [], 'total': 0, 'total_pages': 0}
        finally:
            connection.close()

    @staticmethod
    def get_transaction_stats():
        """Get transaction statistics"""
        connection = Database.get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT 
                        SUM(CASE WHEN status = 'approved' AND amount > 0 THEN amount ELSE 0 END) as total_added,
                        SUM(CASE WHEN status = 'approved' AND amount < 0 THEN ABS(amount) ELSE 0 END) as total_deducted,
                        COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending_count,
                        SUM(CASE WHEN status = 'pending' AND amount > 0 THEN amount ELSE 0 END) as pending_amount
                    FROM credit_transactions
                """)
                return cursor.fetchone()
        except Exception as e:
            print(f"Error getting transaction stats: {e}")
            return {
                'total_added': 0, 
                'total_deducted': 0,
                'pending_count': 0,
                'pending_amount': 0
            }
        finally:
            connection.close()

    @staticmethod
    def approve_transaction(transaction_id):
        """Approve a pending transaction"""
        connection = Database.get_connection()
        try:
            with connection.cursor() as cursor:
                # Get transaction details
                cursor.execute(
                    "SELECT * FROM credit_transactions WHERE id = %s AND status = 'pending'",
                    (transaction_id,)
                )
                transaction = cursor.fetchone()
                
                if not transaction:
                    print(f"Transaction {transaction_id} not found or not pending")
                    return False
                    
                user_id = transaction['user_id']
                amount = transaction['amount']
                
                # Update transaction status
                cursor.execute(
                    "UPDATE credit_transactions SET status = 'approved', updated_at = NOW() WHERE id = %s",
                    (transaction_id,)
                )
                
                # Update user balance
                cursor.execute(
                    "UPDATE user_credits SET credits_balance = credits_balance + %s WHERE user_id = %s",
                    (amount, user_id)
                )
                
                connection.commit()
                return True
                
        except Exception as e:
            connection.rollback()
            print(f"Error approving transaction: {e}")
            return False
        finally:
            connection.close()

    @staticmethod
    def cancel_transaction(transaction_id, reason=None):
        """Cancel a pending transaction"""
        connection = Database.get_connection()
        try:
            with connection.cursor() as cursor:
                # Get transaction details
                cursor.execute(
                    "SELECT * FROM credit_transactions WHERE id = %s AND status = 'pending'",
                    (transaction_id,)
                )
                transaction = cursor.fetchone()
                
                if not transaction:
                    print(f"Transaction {transaction_id} not found or not pending")
                    return False
                
                # Update transaction status
                cursor.execute(
                    """UPDATE credit_transactions 
                       SET status = 'cancelled', 
                           updated_at = NOW(),
                           notes = CONCAT(COALESCE(notes, ''), ' | Cancelled: ', %s)
                       WHERE id = %s""",
                    (reason or 'Cancelled by administrator', transaction_id)
                )
                
                connection.commit()
                return True
                
        except Exception as e:
            connection.rollback()
            print(f"Error cancelling transaction: {e}")
            return False
        finally:
            connection.close()

    @staticmethod
    def cleanup_old_transactions(days=30):
        """Clean up old completed transactions
        
        This doesn't delete records, just archives them to save database space
        by moving data to a transactions_archive table.
        """
        connection = Database.get_connection()
        try:
            with connection.cursor() as cursor:
                # Create archive table if it doesn't exist
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS credit_transactions_archive
                    LIKE credit_transactions
                """)
                
                # Insert old completed transactions into archive
                cursor.execute("""
                    INSERT INTO credit_transactions_archive
                    SELECT * FROM credit_transactions
                    WHERE status IN ('approved', 'cancelled')
                    AND created_at < DATE_SUB(NOW(), INTERVAL %s DAY)
                """, (days,))
                
                rows_archived = cursor.rowcount
                
                # Delete archived transactions
                cursor.execute("""
                    DELETE FROM credit_transactions
                    WHERE status IN ('approved', 'cancelled')
                    AND created_at < DATE_SUB(NOW(), INTERVAL %s DAY)
                """, (days,))
                
                connection.commit()
                return rows_archived
                
        except Exception as e:
            connection.rollback()
            print(f"Error cleaning up transactions: {e}")
            return 0
        finally:
            connection.close()

class Payment:
    @staticmethod
    def create_payment(user_id, amount, payment_method='stripe'):
        """Create a new pending payment"""
        if amount <= 0:
            return None, 0
        
        # Calculate credits to add
        credits_per_dollar = int(CreditSettings.get_setting('credits_per_dollar', '5000'))
        credits_to_add = int(amount * credits_per_dollar)
        
        connection = Database.get_connection()
        try:
            with connection.cursor() as cursor:
                # Always create payment with 'pending' status first
                cursor.execute("""
                    INSERT INTO payments 
                    (user_id, amount, credits_added, payment_method, status, created_at) 
                    VALUES (%s, %s, %s, %s, 'pending', NOW())
                """, (user_id, amount, credits_to_add, payment_method))
                payment_id = cursor.lastrowid
            connection.commit()
            return payment_id, credits_to_add
        except Exception as e:
            print(f"Error creating payment: {e}")
            return None, 0
        finally:
            connection.close()
    
    @staticmethod
    def complete_payment(payment_id, transaction_id):
        """Complete a payment and add credits to user account"""
        connection = Database.get_connection()
        try:
            # Start transaction
            connection.begin()
            
            with connection.cursor() as cursor:
                # Get payment details
                cursor.execute("SELECT * FROM payments WHERE id = %s AND status = 'pending'", (payment_id,))
                payment = cursor.fetchone()
                
                if not payment:
                    # Payment not found or not in pending state
                    connection.rollback()
                    return False
                
                user_id = payment['user_id']
                credits_amount = payment['credits_added']
                
                # Update payment status
                cursor.execute(
                    "UPDATE payments SET status = 'completed', transaction_id = %s, completed_at = NOW() WHERE id = %s",
                    (transaction_id, payment_id)
                )
                
                # Get current user credits
                cursor.execute("SELECT * FROM user_credits WHERE user_id = %s", (user_id,))
                user_credits = cursor.fetchone()
                
                if user_credits:
                    # Update existing credits
                    new_balance = user_credits['credits_balance'] + credits_amount
                    new_total_purchased = user_credits['total_credits_purchased'] + credits_amount
                    
                    cursor.execute("""
                        UPDATE user_credits 
                        SET credits_balance = %s, total_credits_purchased = %s 
                        WHERE user_id = %s
                    """, (new_balance, new_total_purchased, user_id))
                else:
                    # Create new credits record
                    cursor.execute("""
                        INSERT INTO user_credits 
                        (user_id, credits_balance, total_credits_purchased, total_credits_used) 
                        VALUES (%s, %s, %s, 0)
                    """, (user_id, credits_amount, credits_amount))
                
                # Record transaction
                cursor.execute("""
                    INSERT INTO credit_transactions 
                    (user_id, credits_amount, transaction_type, description, reference_id)
                    VALUES (%s, %s, 'purchase', %s, %s)
                """, (
                    user_id, 
                    credits_amount, 
                    f"Credit purchase (${payment['amount']})", 
                    payment_id
                ))
            
            # Commit all changes
            connection.commit()
            return True
            
        except Exception as e:
            # Roll back all changes in case of error
            connection.rollback()
            print(f"Error completing payment: {e}")
            return False
        finally:
            connection.close()
    
    @staticmethod
    def get_by_id(payment_id):
        """Get a payment by ID"""
        connection = Database.get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM payments WHERE id = %s", (payment_id,))
                return cursor.fetchone()
        finally:
            connection.close()
    
    @staticmethod
    def mark_as_failed(payment_id, error_message=None):
        """Mark a payment as failed with optional error message"""
        connection = Database.get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE payments SET status = 'failed', notes = %s WHERE id = %s",
                    (error_message or "Payment failed", payment_id)
                )
            connection.commit()
            return True
        except Exception as e:
            print(f"Error marking payment as failed: {e}")
            return False
        finally:
            connection.close()

    @staticmethod
    def get_payment_history(user_id=None):
        """Get payment history for a user or all payments if user_id is None"""
        connection = Database.get_connection()
        try:
            with connection.cursor() as cursor:
                if user_id:
                    # Get payments for a specific user
                    cursor.execute("""
                        SELECT * FROM payments
                        WHERE user_id = %s
                        ORDER BY created_at DESC
                    """, (user_id,))
                else:
                    # Get all payments (for admin)
                    cursor.execute("""
                        SELECT * FROM payments
                        ORDER BY created_at DESC
                        LIMIT 100
                    """)
                    
                return cursor.fetchall()
        except Exception as e:
            print(f"Error retrieving payment history: {e}")
            return []
        finally:
            connection.close()

class OTP:
    """
    OTP class for managing verification codes
    """
    @staticmethod
    def create_otp(email, purpose, expires_in_minutes=10):
        """Generate a new OTP code"""
        import random
        from datetime import datetime, timedelta
        
        try:
            # Validate parameters
            if not email or not purpose:
                print("Error: Email or purpose missing")
                return None
                
            # Ensure purpose is valid for the database
            valid_purposes = ['login', 'registration', 'account_deletion', 'password_reset']
            if purpose not in valid_purposes:
                print(f"Error: Invalid purpose '{purpose}'. Must be one of {valid_purposes}")
                return None
            
            connection = Database.get_connection()
            try:
                with connection.cursor() as cursor:
                    # Check if the OTP table exists
                    cursor.execute("""
                        SELECT COUNT(*) as count FROM information_schema.tables 
                        WHERE table_schema = %s AND table_name = 'otp'
                    """, (Config.MYSQL_DB,))
                    
                    result = cursor.fetchone()
                    if not result or result['count'] == 0:
                        print("OTP table doesn't exist, initializing database...")
                        connection.close()
                        from app.initialize_database import initialize_database
                        initialize_database()
                        connection = Database.get_connection()
                    
                    # Delete existing OTPs for this email and purpose
                    with connection.cursor() as cursor:
                        cursor.execute("""
                            DELETE FROM otp 
                            WHERE email = %s AND purpose = %s
                        """, (email, purpose))
                        
                        # Generate a new 6-digit OTP
                        otp_code = ''.join(random.choices('0123456789', k=6))
                        expires_at = datetime.now() + timedelta(minutes=expires_in_minutes)
                        
                        # Insert the new OTP
                        cursor.execute("""
                            INSERT INTO otp (email, otp_code, purpose, expires_at, created_at)
                            VALUES (%s, %s, %s, %s, %s)
                        """, (email, otp_code, purpose, expires_at, datetime.now()))
                        
                        connection.commit()
                        print(f"OTP generated successfully for {email} (purpose: {purpose})")
                        return otp_code
            except Exception as db_error:
                print(f"Database error in create_otp: {str(db_error)}")
                return None
            finally:
                connection.close()
                
        except Exception as e:
            print(f"Unexpected error in create_otp: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

    @staticmethod
    def verify_otp(email, otp_code, purpose):
        """Verify an OTP code"""
        from datetime import datetime
        
        try:
            if not email or not otp_code or not purpose:
                print("Missing required parameters for OTP verification")
                return False
                
            connection = Database.get_connection()
            try:
                with connection.cursor() as cursor:
                    # Find a valid, unexpired OTP
                    cursor.execute("""
                        SELECT * FROM otp 
                        WHERE email = %s AND otp_code = %s AND purpose = %s AND expires_at > %s
                    """, (email, otp_code, purpose, datetime.now()))
                    
                    otp_record = cursor.fetchone()
                    
                    if otp_record:
                        # Delete the used OTP to prevent reuse
                        cursor.execute("""
                            DELETE FROM otp 
                            WHERE email = %s AND purpose = %s
                        """, (email, purpose))
                        
                        connection.commit()
                        print(f"OTP verified successfully for {email} (purpose: {purpose})")
                        return True
                    else:
                        print(f"Invalid or expired OTP for {email} (purpose: {purpose})")
                        return False
            except Exception as db_error:
                print(f"Database error in verify_otp: {str(db_error)}")
                return False
            finally:
                connection.close()
                
        except Exception as e:
            print(f"Unexpected error in verify_otp: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

class UserOTPSettings:
    @staticmethod
    def get_settings(user_id):
        """Get OTP settings for a user"""
        # First make sure the table exists
        Database.create_tables()
        
        connection = Database.get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM user_otp_settings WHERE user_id = %s", (user_id,))
                settings = cursor.fetchone()
                
                if not settings:
                    # Create default settings
                    cursor.execute(
                        "INSERT INTO user_otp_settings (user_id, otp_enabled_for_login) VALUES (%s, 0)",
                        (user_id,)
                    )
                    connection.commit()
                    return {'user_id': user_id, 'otp_enabled_for_login': False}
                
                return settings
        except Exception as e:
            print(f"Error getting OTP settings: {e}")
            # Return a default value to avoid breaking the app
            return {'user_id': user_id, 'otp_enabled_for_login': False}
        finally:
            connection.close()
    
    @staticmethod
    def update_settings(user_id, otp_enabled_for_login):
        """Update OTP settings for a user"""
        # First make sure the table exists
        Database.create_tables()
        
        connection = Database.get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO user_otp_settings (user_id, otp_enabled_for_login) 
                       VALUES (%s, %s)
                       ON DUPLICATE KEY UPDATE otp_enabled_for_login = %s""",
                    (user_id, otp_enabled_for_login, otp_enabled_for_login)
                )
            connection.commit()
            return True
        except Exception as e:
            print(f"Error updating OTP settings: {e}")
            return False
        finally:
            connection.close()
    
    @staticmethod
    def is_otp_enabled(user_id):
        """Check if OTP is enabled for a user
        
        Args:
            user_id: The user ID to check
            
        Returns:
            bool: True if OTP is enabled, False otherwise
        """
        try:
            connection = Database.get_connection()
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT otp_enabled_for_login FROM user_settings
                    WHERE user_id = %s
                """, (user_id,))
                
                result = cursor.fetchone()
                
                # Return True if the record exists and otp_enabled_for_login is True
                return result and result['otp_enabled_for_login']
                
        except Exception as e:
            print(f"Error checking OTP status: {e}")
            return False  # Default to not requiring OTP if there's an error
        finally:
            connection.close()

class EmailSettings:
    @staticmethod
    def create_email_settings_table():
        connection = Database.get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS email_settings (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    setting_name VARCHAR(100) UNIQUE NOT NULL,
                    setting_value TEXT NOT NULL,
                    is_encrypted BOOLEAN DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                )
                """)
            connection.commit()
        finally:
            connection.close()
    
    @staticmethod
    def initialize_default_settings():
        """Set default email settings if they don't exist"""
        settings = [
            ('smtp_server', 'smtp.gmail.com', False),
            ('smtp_port', '587', False),
            ('smtp_username', '', False),
            ('smtp_password', '', True),  # This will be encrypted
            ('sender_email', '', False),
            ('sender_name', 'WebArticle Admin', False),
            ('email_enabled', 'false', False)
        ]
        
        connection = Database.get_connection()
        try:
            with connection.cursor() as cursor:
                for name, value, is_encrypted in settings:
                    # Only insert if it doesn't exist
                    cursor.execute(
                        "SELECT id FROM email_settings WHERE setting_name = %s", 
                        (name,)
                    )
                    if not cursor.fetchone():
                        cursor.execute("""
                        INSERT INTO email_settings (setting_name, setting_value, is_encrypted) 
                        VALUES (%s, %s, %s)
                        """, (name, value, is_encrypted))
            connection.commit()
        finally:
            connection.close()
    
    @staticmethod
    def get_setting(setting_name, default_value=None):
        """Get an email setting value"""
        connection = Database.get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT setting_value, is_encrypted FROM email_settings WHERE setting_name = %s", (setting_name,))
                result = cursor.fetchone()
                if result:
                    value = result['setting_value']
                    # Could add decryption here if needed
                    return value
                else:
                    return default_value
        finally:
            connection.close()
    
    @staticmethod
    def set_setting(setting_name, setting_value, is_encrypted=False):
        """Update an email setting"""
        # You could add encryption here for sensitive values like passwords
        connection = Database.get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                INSERT INTO email_settings (setting_name, setting_value, is_encrypted) 
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE setting_value = %s, is_encrypted = %s
                """, (setting_name, setting_value, is_encrypted, setting_value, is_encrypted))
            connection.commit()
            return True
        except Exception as e:
            print(f"Error setting email setting: {e}")
            return False
        finally:
            connection.close()
    
    @staticmethod
    def get_all_settings():
        """Get all email settings"""
        connection = Database.get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT id, setting_name, setting_value, is_encrypted, updated_at FROM email_settings")
                return cursor.fetchall()
        finally:
            connection.close()

class PaymentSettings:
    @staticmethod
    def create_payment_settings_table():
        """Create the payment settings table if it doesn't exist"""
        connection = Database.get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS payment_settings (
                        id INT PRIMARY KEY AUTO_INCREMENT,
                        gateway VARCHAR(50) NOT NULL,
                        is_enabled BOOLEAN DEFAULT FALSE,
                        test_mode BOOLEAN DEFAULT TRUE,
                        api_key VARCHAR(255),
                        api_secret VARCHAR(255),
                        webhook_secret VARCHAR(255),
                        additional_settings TEXT,
                        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                    )
                """)
            connection.commit()
        finally:
            connection.close()
    
    @staticmethod
    def initialize_default_gateways():
        """Initialize default payment gateways"""
        gateways = [
            ('stripe', False, True, '', '', '', '{}'),
            ('paypal', False, True, '', '', '', '{}')
        ]
        
        connection = Database.get_connection()
        try:
            with connection.cursor() as cursor:
                for gateway, is_enabled, test_mode, api_key, api_secret, webhook_secret, additional_settings in gateways:
                    # Check if gateway already exists
                    cursor.execute("SELECT id FROM payment_settings WHERE gateway = %s", (gateway,))
                    if not cursor.fetchone():
                        cursor.execute("""
                            INSERT INTO payment_settings 
                            (gateway, is_enabled, test_mode, api_key, api_secret, webhook_secret, additional_settings) 
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """, (gateway, is_enabled, test_mode, api_key, api_secret, webhook_secret, additional_settings))
            connection.commit()
        finally:
            connection.close()
    
    @staticmethod
    def get_all_gateways():
        """Get all payment gateways"""
        connection = Database.get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM payment_settings")
                return cursor.fetchall()
        finally:
            connection.close()
    
    @staticmethod
    def get_gateway(gateway):
        """Get a specific payment gateway"""
        connection = Database.get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM payment_settings WHERE gateway = %s", (gateway,))
                return cursor.fetchone()
        finally:
            connection.close()
    
    @staticmethod
    def update_gateway(gateway, is_enabled, test_mode, api_key, api_secret, webhook_secret, additional_settings=None):
        """Update payment gateway settings"""
        connection = Database.get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    UPDATE payment_settings 
                    SET is_enabled = %s, test_mode = %s, api_key = %s, api_secret = %s, webhook_secret = %s, 
                    additional_settings = %s
                    WHERE gateway = %s
                """, (is_enabled, test_mode, api_key, api_secret, webhook_secret, 
                     additional_settings if additional_settings else '{}', gateway))
            connection.commit()
            return True
        except Exception as e:
            print(f"Error updating payment gateway: {e}")
            return False
        finally:
            connection.close()
    
    @staticmethod
    def is_gateway_enabled(gateway):
        """Check if a payment gateway is enabled"""
        gateway_data = PaymentSettings.get_gateway(gateway)
        return gateway_data and gateway_data.get('is_enabled', False) 

class UserDevice:
    """Class to handle user device tracking"""
    
    @staticmethod
    def add_device(user_id, ip_address, device_hash, user_agent):
        """Add or update a user device"""
        connection = Database.get_connection()
        try:
            with connection.cursor() as cursor:
                # Check if device exists for this user
                cursor.execute(
                    "SELECT id FROM user_devices WHERE user_id = %s AND device_hash = %s",
                    (user_id, device_hash)
                )
                device = cursor.fetchone()
                
                if device:
                    # Update last seen
                    cursor.execute(
                        "UPDATE user_devices SET last_seen = NOW(), ip_address = %s, user_agent = %s WHERE id = %s",
                        (ip_address, user_agent, device['id'])
                    )
                else:
                    # Insert new device
                    cursor.execute(
                        """INSERT INTO user_devices 
                           (user_id, ip_address, device_hash, user_agent) 
                           VALUES (%s, %s, %s, %s)""",
                        (user_id, ip_address, device_hash, user_agent)
                    )
                
                connection.commit()
                return True
                
        except Exception as e:
            print(f"Error adding user device: {e}")
            return False
        finally:
            connection.close()
    
    @staticmethod
    def check_previous_users(ip_address, device_hash):
        """Check if this device/IP has been used by other users"""
        connection = Database.get_connection()
        try:
            with connection.cursor() as cursor:
                # Find all users who have used this device or IP
                cursor.execute(
                    """SELECT DISTINCT user_id FROM user_devices 
                       WHERE ip_address = %s OR device_hash = %s""",
                    (ip_address, device_hash)
                )
                return [row['user_id'] for row in cursor.fetchall()]
                
        except Exception as e:
            print(f"Error checking previous users: {e}")
            return []
        finally:
            connection.close()
    
    @staticmethod
    def is_device_tracking_enabled():
        """Check if device tracking is enabled in settings"""
        return Settings.get_setting('enable_device_tracking', 'true').lower() == 'true'
    
    @staticmethod
    def should_remove_free_credits():
        """Check if free credits should be removed for duplicate devices"""
        return Settings.get_setting('remove_free_credits_on_duplicate', 'true').lower() == 'true'


class FreeCredits:
    """Class to handle free credit awards and management"""
    
    @staticmethod
    def award_registration_credits(user_id, amount):
        """Award free registration credits to a user"""
        connection = Database.get_connection()
        try:
            with connection.cursor() as cursor:
                # Record the free credit award
                cursor.execute(
                    """INSERT INTO free_credit_awards 
                       (user_id, amount, award_type) 
                       VALUES (%s, %s, 'registration')""",
                    (user_id, amount)
                )
                
                # Add the credits to user balance
                cursor.execute(
                    """UPDATE user_credits 
                       SET credits_balance = credits_balance + %s 
                       WHERE user_id = %s""",
                    (amount, user_id)
                )
                
                connection.commit()
                return True
                
        except Exception as e:
            connection.rollback()
            print(f"Error awarding free credits: {e}")
            return False
        finally:
            connection.close()
    
    @staticmethod
    def remove_free_credits(user_id, reason="Duplicate device/IP detected"):
        """Remove free registration credits from a user"""
        connection = Database.get_connection()
        try:
            with connection.cursor() as cursor:
                # Find all non-removed free credit awards
                cursor.execute(
                    """SELECT id, amount FROM free_credit_awards 
                       WHERE user_id = %s AND is_removed = FALSE 
                       AND award_type = 'registration'""",
                    (user_id,)
                )
                awards = cursor.fetchall()
                
                if not awards:
                    return True  # No free credits to remove
                
                total_to_remove = sum(award['amount'] for award in awards)
                
                # Mark the awards as removed
                for award in awards:
                    cursor.execute(
                        """UPDATE free_credit_awards 
                           SET is_removed = TRUE, removed_at = NOW(), 
                           removal_reason = %s 
                           WHERE id = %s""",
                        (reason, award['id'])
                    )
                
                # Deduct the credits from user balance
                cursor.execute(
                    """UPDATE user_credits 
                       SET credits_balance = GREATEST(0, credits_balance - %s) 
                       WHERE user_id = %s""",
                    (total_to_remove, user_id)
                )
                
                connection.commit()
                return True
                
        except Exception as e:
            connection.rollback()
            print(f"Error removing free credits: {e}")
            return False
        finally:
            connection.close()
    
    @staticmethod
    def has_free_credits(user_id):
        """Check if user has been awarded free registration credits"""
        connection = Database.get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """SELECT SUM(amount) as total FROM free_credit_awards 
                       WHERE user_id = %s AND is_removed = FALSE 
                       AND award_type = 'registration'""",
                    (user_id,)
                )
                result = cursor.fetchone()
                return result and result['total'] and result['total'] > 0
                
        except Exception as e:
            print(f"Error checking free credits: {e}")
            return False
        finally:
            connection.close()

# Default prompts
DEFAULT_SYSTEM_PROMPT = """You are an expert SEO content writer who specializes in creating high-quality, engaging articles. 
Your content is well-researched, informative, and optimized for search engines without keyword stuffing. 
You write in a clear, professional tone that maintains reader interest."""

DEFAULT_USER_PROMPT = """Write a comprehensive article about {title}.

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

class ArticleTemplate:
    """Class to handle article generation templates"""
    
    @staticmethod
    def create(name, system_prompt, user_prompt_template, description="", seo_level="medium"):
        """Create a new article template
        
        Args:
            name: Template name
            system_prompt: System prompt for the AI
            user_prompt_template: User prompt template
            description: Template description
            seo_level: SEO optimization level (low, medium, high)
            
        Returns:
            int: Template ID if successful, None otherwise
        """
        connection = Database.get_connection()
        try:
            with connection.cursor() as cursor:
                # Create table if it doesn't exist
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS article_templates (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        name VARCHAR(100) NOT NULL,
                        description TEXT,
                        system_prompt TEXT NOT NULL,
                        user_prompt_template TEXT NOT NULL,
                        seo_level ENUM('low', 'medium', 'high') DEFAULT 'medium',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                    )
                """)
                
                # Insert the template
                cursor.execute(
                    """INSERT INTO article_templates 
                       (name, description, system_prompt, user_prompt_template, seo_level)
                       VALUES (%s, %s, %s, %s, %s)""",
                    (name, description, system_prompt, user_prompt_template, seo_level)
                )
                
                connection.commit()
                return cursor.lastrowid
                
        except Exception as e:
            connection.rollback()
            print(f"Error creating article template: {e}")
            return None
        finally:
            connection.close()
    
    @staticmethod
    def get_all():
        """Get all article templates
        
        Returns:
            list: List of template dictionaries
        """
        connection = Database.get_connection()
        try:
            with connection.cursor() as cursor:
                # Create table if it doesn't exist
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS article_templates (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        name VARCHAR(100) NOT NULL,
                        description TEXT,
                        system_prompt TEXT NOT NULL,
                        user_prompt_template TEXT NOT NULL,
                        seo_level ENUM('low', 'medium', 'high') DEFAULT 'medium',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                    )
                """)
                
                cursor.execute("SELECT * FROM article_templates ORDER BY name")
                return cursor.fetchall()
                
        except Exception as e:
            print(f"Error getting article templates: {e}")
            return []
        finally:
            connection.close()
    
    @staticmethod
    def get_by_id(template_id):
        """Get template by ID
        
        Args:
            template_id: Template ID
            
        Returns:
            dict: Template data or None
        """
        connection = Database.get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM article_templates WHERE id = %s", (template_id,))
                return cursor.fetchone()
                
        except Exception as e:
            print(f"Error getting article template: {e}")
            return None
        finally:
            connection.close()
    
    @staticmethod
    def delete(template_id):
        """Delete a template
        
        Args:
            template_id: Template ID
            
        Returns:
            bool: True if successful, False otherwise
        """
        connection = Database.get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM article_templates WHERE id = %s", (template_id,))
                connection.commit()
                return cursor.rowcount > 0
                
        except Exception as e:
            connection.rollback()
            print(f"Error deleting article template: {e}")
            return False
        finally:
            connection.close()
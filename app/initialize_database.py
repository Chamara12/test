def initialize_database():
    """Initialize required tables in the database with fixed schema compatibility"""
    from app.models import Database
    from app.config import Config
    
    connection = Database.get_connection()
    try:
        # Make sure our database operations support both current and legacy schemas
        with connection.cursor() as cursor:
            # Create users table with flexible schema
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    full_name VARCHAR(255) NOT NULL,
                    email VARCHAR(255) NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    is_verified BOOLEAN DEFAULT 0,
                    is_admin BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    UNIQUE INDEX (email)
                );
            """)
            
            # Create user_settings table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_settings (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    otp_enabled_for_login BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                );
            """)
            
            # Create OTP table with proper schema and indexes
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS otp (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    email VARCHAR(255) NOT NULL,
                    otp_code VARCHAR(10) NOT NULL,
                    purpose ENUM('login', 'registration', 'account_deletion', 'password_reset') NOT NULL,
                    expires_at TIMESTAMP NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX (email)
                );
            """)
            
            # Create user_credits table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_credits (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    credits_balance INT DEFAULT 0,
                    total_credits_purchased INT DEFAULT 0,
                    total_credits_used INT DEFAULT 0,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                );
            """)
            
            # Ensure otp.purpose enum includes 'registration'
            cursor.execute("SHOW COLUMNS FROM otp WHERE Field = 'purpose'")
            column_info = cursor.fetchone()
            
            if column_info and 'registration' not in column_info['Type']:
                new_type = column_info['Type'].replace('enum(', 'ENUM(')
                new_type = new_type.replace(')', ",'registration')")
                cursor.execute(f"ALTER TABLE otp MODIFY COLUMN purpose {new_type}")
                print("Updated OTP table to include 'registration' in purpose enum")
            
            # Make sure expires_at is nullable
            cursor.execute("""
                ALTER TABLE otp MODIFY COLUMN expires_at TIMESTAMP NULL
            """)
            
            # In your initialize_database function, add this check
            cursor.execute("""
                SELECT COUNT(*) as count FROM information_schema.columns 
                WHERE table_schema = DATABASE() 
                AND table_name = 'user_settings' 
                AND column_name = 'otp_enabled_for_login'
            """)
            result = cursor.fetchone()
            
            # If the column doesn't exist, add it
            if result['count'] == 0:
                cursor.execute("""
                    ALTER TABLE user_settings
                    ADD COLUMN otp_enabled_for_login BOOLEAN DEFAULT 0
                """)
                print("Added otp_enabled_for_login column to user_settings table")
            
            # Create device tracking table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_devices (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    ip_address VARCHAR(45) NOT NULL,
                    device_hash VARCHAR(255) NOT NULL,
                    user_agent TEXT,
                    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    INDEX (ip_address),
                    INDEX (device_hash),
                    UNIQUE KEY (user_id, device_hash)
                )
            """)
            
            # Create table to track free credits awarded
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS free_credit_awards (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    amount INT NOT NULL,
                    awarded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    award_type VARCHAR(50) DEFAULT 'registration',
                    is_removed BOOLEAN DEFAULT FALSE,
                    removed_at TIMESTAMP NULL,
                    removal_reason VARCHAR(255) NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)
            
            # Add anti-fraud settings to admin settings
            cursor.execute("""
                INSERT INTO settings (setting_name, setting_value, setting_description)
                VALUES 
                ('enable_device_tracking', 'true', 'Track user devices and IPs to prevent duplicate free credits'),
                ('remove_free_credits_on_duplicate', 'true', 'Remove free credits when duplicate devices/IPs are detected')
                ON DUPLICATE KEY UPDATE setting_description = VALUES(setting_description)
            """)
            
        connection.commit()
        print("Database initialized successfully!")
    except Exception as e:
        print(f"Error initializing database: {e}")
        import traceback
        traceback.print_exc()
    finally:
        connection.close() 
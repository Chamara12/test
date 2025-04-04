from app import create_app
from app.models import Database

app = create_app()
with app.app_context():
    connection = Database.get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id, email, is_admin FROM users")
            users = cursor.fetchall()
            
            if users:
                print(f"Found {len(users)} users:")
                for user in users:
                    print(f"ID: {user['id']}, Email: {user['email']}, Admin: {'Yes' if user['is_admin'] else 'No'}")
            else:
                print("No users found in the database")
    finally:
        connection.close() 
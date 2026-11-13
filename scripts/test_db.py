from app.core.database import test_connection

try:
    test_connection()
    print("SUCCESS: Connected to PostgreSQL!")
except Exception as error:
    print("FAILED: Could not connect to PostgreSQL.")
    print(f"Error: {error}")

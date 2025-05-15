import os
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Get database connection details from environment variables 
# (adjust these to match your environment variables)
DB_HOST = os.environ.get("DB_HOST", "localhost:5051")
DB_NAME = os.environ.get("DB_NAME", "hello_dev")
DB_USER = os.environ.get("DB_USER", "hello_flask")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "hello_flask")

# Connect directly to PostgreSQL
try:
    # Connect to the database
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    
    # Set isolation level to be able to create index
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    
    # Create a cursor
    cur = conn.cursor()
    
    # Check if index already exists
    cur.execute("""
    SELECT 1 FROM pg_indexes 
    WHERE indexname = 'idx_messages_fts'
    """)
    
    exists = cur.fetchone()
    
    if not exists:
        # Create the GIN index for full-text search
        print("Creating FTS index...")
        cur.execute("""
        CREATE INDEX idx_messages_fts ON messages 
        USING gin(to_tsvector('english', message_text))
        """)
        print("✅ FTS index created successfully")
    else:
        print("ℹ️ FTS index already exists")
    
    # Close cursor and connection
    cur.close()
    conn.close()
    
except Exception as e:
    print(f"❌ Error creating FTS index: {e}")

#!/usr/bin/python3

import sqlalchemy
from sqlalchemy import text
import time

def create_rum_indexes():
    """Create RUM indexes to optimize database queries for text search with ranking and ordering."""
    
    print("Connecting to database...")
    engine = sqlalchemy.create_engine('postgresql://hello_flask:hello_flask@localhost:5052/hello_flask_dev')
    
    with engine.begin() as connection:
        print("Connected successfully. Setting up RUM indexes...")
        
        # 1. Check if RUM extension is available
        try:
            print("Checking if RUM extension is available...")
            check_extension_sql = text("""
            SELECT 1 FROM pg_available_extensions WHERE name = 'rum'
            """)
            
            rum_available = connection.execute(check_extension_sql).scalar() is not None
            
            if not rum_available:
                print("\n⚠️ ERROR: The RUM extension is not available on this PostgreSQL installation.")
                print("You may need to install the postgresql-contrib package and/or the rum extension.")
                print("For Ubuntu/Debian: sudo apt-get install postgresql-contrib")
                print("For Docker: Add the rum extension to your PostgreSQL image")
                return
                
            # 2. Install RUM extension if not already installed
            print("Creating RUM extension...")
            extension_sql = text("""
            CREATE EXTENSION IF NOT EXISTS rum
            """)
            
            connection.execute(extension_sql)
            print("RUM extension created successfully")
            
            # 3. Create RUM index for full-text search with timestamp ordering
            print("Creating RUM index on messages.message_text with timestamp ordering...")
            start_time = time.time()
            
            # Check if index already exists
            check_index_sql = text("""
            SELECT 1 FROM pg_indexes 
            WHERE indexname = 'idx_messages_rum_text_timestamp'
            """)
            
            index_exists = connection.execute(check_index_sql).scalar() is not None
            
            if not index_exists:
                # Create RUM index with text search and timestamp ordering
                # This allows efficiently searching text and sorting by created_at
                create_index_sql = text("""
                CREATE INDEX idx_messages_rum_text_timestamp 
                ON messages USING rum(
                    to_tsvector('english', message_text) rum_tsvector_ops,
                    created_at
                )
                """)
                
                connection.execute(create_index_sql)
                print(f"RUM index created in {time.time() - start_time:.2f} seconds")
            else:
                print("RUM index already exists")
                
            # 4. Create RUM index for combining relevance and recency
            print("Creating RUM index with ranking capabilities...")
            start_time = time.time()
            
            check_index_sql = text("""
            SELECT 1 FROM pg_indexes 
            WHERE indexname = 'idx_messages_rum_advanced'
            """)
            
            index_exists = connection.execute(check_index_sql).scalar() is not None
            
            if not index_exists:
                # This more advanced RUM index adds support for relevance ranking
                create_index_sql = text("""
                CREATE INDEX idx_messages_rum_advanced
                ON messages USING rum(
                    to_tsvector('english', message_text) rum_tsvector_ops,
                    created_at,
                    id_users
                )
                """)
                
                connection.execute(create_index_sql)
                print(f"Advanced RUM index created in {time.time() - start_time:.2f} seconds")
            else:
                print("Advanced RUM index already exists")
                
            print("\nRUM indexes created successfully!")
            print("\nHere are the current indexes:")
            
            # List all indexes
            list_indexes_sql = text("""
            SELECT
                tablename,
                indexname,
                indexdef
            FROM
                pg_indexes
            WHERE
                schemaname = 'public'
                AND (tablename = 'messages' OR indexname LIKE '%rum%')
            ORDER BY
                tablename,
                indexname;
            """)
            
            results = connection.execute(list_indexes_sql)
            
            for row in results:
                print(f"Table: {row.tablename}")
                print(f"Index: {row.indexname}")
                print(f"Definition: {row.indexdef}")
                print("-" * 80)
                
        except Exception as e:
            print(f"Error creating RUM indexes: {e}")
            print("Please make sure the RUM extension is installed in your PostgreSQL instance.")

if __name__ == "__main__":
    create_rum_indexes()

#!/usr/bin/python3

import sqlalchemy
from sqlalchemy import text
import argparse
import sys
import time

def cleanup_duplicate_accounts():
    """
    Identifies duplicate username-password combinations and removes duplicates
    while maintaining referential integrity across all tables.
    """
    print("Starting duplicate account cleanup process...")
    start_time = time.time()
    
    # Create database connection with appropriate timeout settings
    engine = sqlalchemy.create_engine(
        'postgresql://hello_flask:hello_flask@localhost:5052/hello_flask_dev',
        pool_size=5,
        max_overflow=10,
        pool_timeout=30,
        pool_recycle=1800,
        # Set statement timeout to 5 minutes for long-running operations
        connect_args={"options": "-c statement_timeout=300000"}
    )
    
    # First step: Identify duplicate username-password combinations
    duplicate_query = """
    SELECT username, password, array_agg(id_users) as user_ids
    FROM accounts
    GROUP BY username, password
    HAVING COUNT(*) > 1
    ORDER BY COUNT(*) DESC
    """
    
    with engine.connect() as connection:
        # Start a transaction - we'll perform all our operations within a single transaction
        with connection.begin():
            print("Finding duplicate username-password combinations...")
            result = connection.execute(text(duplicate_query))
            duplicate_rows = result.fetchall()
            
            if not duplicate_rows:
                print("No duplicate username-password combinations found!")
                return
            
            print(f"Found {len(duplicate_rows)} duplicate username-password combinations.")
            
            total_accounts_to_delete = 0
            total_users_to_delete = 0
            
            # For each set of duplicates, process them individually
            for row in duplicate_rows:
                username = row[0]
                password = row[1]
                user_ids = row[2]  # This is an array of user IDs with the same username/password
                
                # Keep the first ID, delete the rest
                keeper_id = user_ids[0]
                delete_ids = user_ids[1:]
                total_accounts_to_delete += len(delete_ids)
                
                print(f"Processing duplicate for username '{username}': Keeping user ID {keeper_id}, "
                      f"deleting {len(delete_ids)} duplicate accounts.")
                
                # For each user ID to delete, clean up related records in all tables
                # Use parameterized queries for safety
                for user_id in delete_ids:
                    total_users_to_delete += 1
                    
                    print(f"Deleting data for user ID {user_id}...")
                    
                    # Step 1: Delete related tweet data
                    # First get all tweets by this user
                    tweets_query = text("SELECT id_tweets FROM tweets WHERE id_users = :user_id")
                    tweet_result = connection.execute(tweets_query, {"user_id": user_id})
                    tweet_ids = [row[0] for row in tweet_result]
                    
                    if tweet_ids:
                        print(f"Found {len(tweet_ids)} tweets to delete for user {user_id}")
                        
                        # Create a temporary table for the tweet IDs for more efficient joins
                        connection.execute(text("CREATE TEMP TABLE temp_tweet_ids (id_tweets BIGINT PRIMARY KEY) ON COMMIT DROP"))
                        
                        # Insert tweet IDs in batches
                        batch_size = 1000
                        for i in range(0, len(tweet_ids), batch_size):
                            batch = tweet_ids[i:i+batch_size]
                            # Convert batch to string format for SQL IN clause
                            id_list = ','.join(str(id) for id in batch)
                            connection.execute(text(f"INSERT INTO temp_tweet_ids VALUES {','.join(f'({id})' for id in batch)}"))
                        
                        # Delete from dependent tables using the temp table for efficiency
                        print("Deleting tweet relations...")
                        connection.execute(text("""
                            DELETE FROM tweet_tags
                            WHERE id_tweets IN (SELECT id_tweets FROM temp_tweet_ids)
                        """))
                        
                        connection.execute(text("""
                            DELETE FROM tweet_mentions
                            WHERE id_tweets IN (SELECT id_tweets FROM temp_tweet_ids)
                        """))
                        
                        connection.execute(text("""
                            DELETE FROM tweet_urls
                            WHERE id_tweets IN (SELECT id_tweets FROM temp_tweet_ids)
                        """))
                        
                        connection.execute(text("""
                            DELETE FROM tweet_media
                            WHERE id_tweets IN (SELECT id_tweets FROM temp_tweet_ids)
                        """))
                        
                        # Delete the tweets themselves
                        connection.execute(text("""
                            DELETE FROM tweets
                            WHERE id_tweets IN (SELECT id_tweets FROM temp_tweet_ids)
                        """))
                        
                        # Drop temp table (will be dropped at end of transaction anyway)
                        connection.execute(text("DROP TABLE IF EXISTS temp_tweet_ids"))
                    
                    # Step 2: Delete user's messages
                    messages_result = connection.execute(
                        text("DELETE FROM messages WHERE id_users = :user_id RETURNING id_message"),
                        {"user_id": user_id}
                    )
                    deleted_messages = messages_result.rowcount
                    print(f"Deleted {deleted_messages} messages for user {user_id}")
                    
                    # Step 3: Delete from tweet_mentions (references where this user is mentioned)
                    mentions_result = connection.execute(
                        text("DELETE FROM tweet_mentions WHERE id_users = :user_id"),
                        {"user_id": user_id}
                    )
                    deleted_mentions = mentions_result.rowcount
                    print(f"Deleted {deleted_mentions} tweet mentions for user {user_id}")
                    
                    # Step 4: Delete the account
                    account_result = connection.execute(
                        text("DELETE FROM accounts WHERE id_users = :user_id"),
                        {"user_id": user_id}
                    )
                    deleted_accounts = account_result.rowcount
                    print(f"Deleted {deleted_accounts} account for user {user_id}")
                    
                    # Step 5: Delete the user
                    user_result = connection.execute(
                        text("DELETE FROM users WHERE id_users = :user_id"),
                        {"user_id": user_id}
                    )
                    deleted_users = user_result.rowcount
                    print(f"Deleted {deleted_users} user record for ID {user_id}")
            
            # Refresh materialized views if they exist
            try:
                print("Refreshing materialized views...")
                connection.execute(text('REFRESH MATERIALIZED VIEW IF EXISTS tweet_tags_total'))
                connection.execute(text('REFRESH MATERIALIZED VIEW IF EXISTS tweet_tags_cooccurrence'))
                print("Materialized views refreshed")
            except Exception as e:
                print(f"Could not refresh materialized views: {e}")
            
            end_time = time.time()
            duration = end_time - start_time
            print(f"Cleanup complete in {duration:.2f} seconds")
            print(f"Removed {total_accounts_to_delete} duplicate accounts and {total_users_to_delete} users")

def analyze_duplicate_distribution():
    """Analyze and report on the distribution of duplicate accounts without deleting"""
    engine = sqlalchemy.create_engine(
        'postgresql://hello_flask:hello_flask@localhost:5052/hello_flask_dev'
    )
    
    query = """
    SELECT 
        COUNT(*) - COUNT(DISTINCT (username, password)) AS total_duplicates,
        COUNT(*) AS total_accounts,
        ROUND((COUNT(*) - COUNT(DISTINCT (username, password))) * 100.0 / COUNT(*), 2) AS duplicate_percentage,
        MAX(duplicate_count) AS max_duplicates_for_one_combination
    FROM (
        SELECT 
            username, 
            password, 
            COUNT(*) AS duplicate_count
        FROM accounts 
        GROUP BY username, password
    ) subquery
    """
    
    with engine.connect() as connection:
        print("Analyzing duplicate distribution...")
        result = connection.execute(text(query))
        stats = result.fetchone()
        
        print("\n=== DUPLICATE ACCOUNT ANALYSIS ===")
        print(f"Total accounts: {stats[1]}")
        print(f"Total unique username-password combinations: {stats[1] - stats[0]}")
        print(f"Total duplicate accounts: {stats[0]}")
        print(f"Duplicate percentage: {stats[2]}%")
        print(f"Maximum duplicates for a single combination: {stats[3]}")
        
        # Get top 10 most duplicated combinations
        top_duplicates_query = """
        SELECT 
            username,
            COUNT(*) AS duplicate_count
        FROM accounts 
        GROUP BY username, password
        HAVING COUNT(*) > 1
        ORDER BY COUNT(*) DESC
        LIMIT 10
        """
        
        top_result = connection.execute(text(top_duplicates_query))
        top_duplicates = top_result.fetchall()
        
        if top_duplicates:
            print("\nTop 10 most duplicated usernames:")
            for i, (username, count) in enumerate(top_duplicates, 1):
                print(f"{i}. Username '{username}' appears {count} times")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Clean up duplicate accounts in the database')
    parser.add_argument('--analyze-only', action='store_true', help='Only analyze duplicates without deleting')
    parser.add_argument('--force', action='store_true', help='Skip confirmation prompt')
    args = parser.parse_args()
    
    if args.analyze_only:
        analyze_duplicate_distribution()
    else:
        analyze_duplicate_distribution()
        
        if not args.force:
            confirmation = input("\nWARNING: This will permanently delete duplicate accounts and all associated data.\n"
                               "Type 'DELETE' (all caps) to confirm or anything else to abort: ")
            
            if confirmation != "DELETE":
                print("Operation aborted. No changes were made.")
                sys.exit(0)
        
        # Execute the cleanup
        cleanup_duplicate_accounts()

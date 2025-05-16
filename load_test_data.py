#!/usr/bin/python3

import sqlalchemy
import random
import datetime
from faker import Faker
from sqlalchemy import text
import string
from random import choice, randint, uniform, sample, choices
from datetime import timedelta
import uuid
from postgis import Geometry, Point, MultiPolygon, Polygon
import postgis.psycopg
import time
import os
from dotenv import load_dotenv

# Check if running on host or in container
if os.path.exists('/.dockerenv'):
    if os.path.exists('/home/app/web/.env.prod'):
        env_file = '/home/app/web/.env.prod'
        print("Running in production Docker environment")
    else:
        env_file = '.env.dev.container'
        print("Running in development Docker environment")
else:
    # Running on host
    env_file = '.env.dev.host'

# Load environment variables from the appropriate file
load_dotenv(env_file)


db_url = os.environ['DATABASE_URL']

def generate_random_data(num_users=50, num_tweets=100, user_id_start=-1, tweet_id_start=-1):
    """Generate random data for the database schema"""
    print(f"Process {os.getpid()} starting with user_id_start={user_id_start}, tweet_id_start={tweet_id_start}")
    start_time = time.time()
    
    fake = Faker()
    
    # Add connection pooling parameters
    engine = sqlalchemy.create_engine(
        db_url,
        pool_size=20,  # Maintain a pool of connections
        max_overflow=10,  # Allow up to 10 connections beyond pool_size
        pool_timeout=30,  # Wait up to 30 seconds for a connection
        pool_recycle=1800  # Recycle connections after 30 minutes
    )
    
    # Define batch sizes - larger batches for better performance
    USER_BATCH_SIZE = 100000  # Increased batch size
    TWEET_BATCH_SIZE = 10000  # Increased batch size
    MESSAGE_BATCH_SIZE = 100000
    ACCOUNT_BATCH_SIZE = 200000
    RELATION_BATCH_SIZE = 20000
    
    id_users = user_id_start
    id_tweets = tweet_id_start
    
    # Step 1: Generate and insert users
    print(f"Process {os.getpid()}: Generating users...")
    user_batches = []
    current_batch = []
    
    for i in range(num_users):
        # Generate random user data
        id_users += 1
        created_at = fake.date_time_between(start_date='-10y', end_date='-1y')
        updated_at = fake.date_time_between(start_date=created_at, end_date='now')
        url = fake.url() if random.random() > 0.3 else None
        friends_count = randint(0, 5000)
        listed_count = randint(0, 500)
        favourites_count = randint(0, 10000)
        statuses_count = randint(0, 50000)
        protected = random.choice([True, False])
        verified = random.choice([True, False])
        screen_name = fake.user_name()
        name = fake.name()
        location = fake.city() if random.random() > 0.3 else None
        description = fake.text(max_nb_chars=160) if random.random() > 0.2 else None
        
        # Random countries array (sometimes empty)
        countries = []
        if random.random() > 0.9:  # 10% chance of having withheld countries
            num_countries = randint(1, 5)
            for _ in range(num_countries):
                countries.append(fake.country_code())
        
        # Add to current batch
        current_batch.append({
            'id_users': id_users,
            'created_at': created_at,
            'updated_at': updated_at,
            'url': url,
            'friends_count': friends_count,
            'listed_count': listed_count,
            'favourites_count': favourites_count,
            'statuses_count': statuses_count,
            'protected': protected,
            'verified': verified,
            'screen_name': screen_name,
            'name': name,
            'location': location,
            'description': description,
            'withheld_in_countries': countries if countries else None
        })
        
        # When batch is full, add to batch list
        if len(current_batch) >= USER_BATCH_SIZE:
            user_batches.append(current_batch)
            current_batch = []
    
    # Add any remaining users
    if current_batch:
        user_batches.append(current_batch)
    
    # Insert users in separate transaction
    with engine.begin() as connection:
        sql = text('''
        INSERT INTO users 
            (id_users, created_at, updated_at, url, friends_count, listed_count, 
            favourites_count, statuses_count, protected, verified, screen_name, 
            name, location, description, withheld_in_countries)
        VALUES 
            (:id_users, :created_at, :updated_at, :url, :friends_count, :listed_count, 
            :favourites_count, :statuses_count, :protected, :verified, :screen_name, 
            :name, :location, :description, :withheld_in_countries)
        ON CONFLICT (id_users) DO NOTHING
        ''')
        
        total_users = 0
        for batch in user_batches:
            connection.execute(sql, batch)
            total_users += len(batch)
            print(f"Process {os.getpid()}: Inserted {total_users} users of {num_users}")
    
    # Step 2: Get user IDs for tweet references - in a new connection
    with engine.connect() as connection:
        # Only grab user IDs from our range to avoid contention
        sql = text('SELECT id_users FROM users WHERE id_users >= :start AND id_users <= :end')
        user_ids = [row[0] for row in connection.execute(sql, 
                                                        {'start': user_id_start, 
                                                         'end': user_id_start + num_users - 1})]
    
    # Step 3: Insert accounts in a separate transaction
    print(f"Process {os.getpid()}: Generating accounts...")
    with engine.begin() as connection:
        accounts_batch = []
        
        # Create accounts for users
        for user_id in user_ids:
            # 100% chance a user has an account
            if random.random() > 0:
                # Create account for user
                username = fake.user_name()
                password = fake.password(length=10)
                
                # Add to accounts batch
                accounts_batch.append({
                    'id_users': user_id,
                    'username': username,
                    'password': password
                })
                
                # If accounts batch is full, insert and clear
                if len(accounts_batch) >= ACCOUNT_BATCH_SIZE:
                    sql = text('''
                    INSERT INTO accounts (id_users, username, password)
                    VALUES (:id_users, :username, :password)
                    ON CONFLICT (id_users) DO NOTHING
                    ''')
                    
                    connection.execute(sql, accounts_batch)
                    print(f"Process {os.getpid()}: Inserted {len(accounts_batch)} accounts")
                    accounts_batch = []
        
        # Insert any remaining accounts
        if accounts_batch:
            sql = text('''
            INSERT INTO accounts (id_users, username, password)
            VALUES (:id_users, :username, :password)
            ON CONFLICT (id_users) DO NOTHING
            ''')
            
            connection.execute(sql, accounts_batch)
            print(f"Process {os.getpid()}: Inserted final {len(accounts_batch)} accounts")
    
    # Step 4: Get account user IDs and insert messages
    print(f"Process {os.getpid()}: Generating messages...")
    with engine.begin() as connection:
        # Get accounts we just created
        sql = text('SELECT id_users FROM accounts WHERE id_users >= :start AND id_users <= :end')
        account_user_ids = [row[0] for row in connection.execute(sql,
                                                               {'start': user_id_start, 
                                                                'end': user_id_start + num_users - 1})]
        
        # Generate messages in batches
        messages_batch = []
        for user_id in account_user_ids:
            # Generate 0-5 messages for this account
            num_messages = randint(0, 5)
            for _ in range(num_messages):
                message_id = randint(10000000000, 99999999999)
                message_text = fake.paragraph()
                created_at = fake.date_time_between(start_date='-30d', end_date='now')
                
                # Add to messages batch
                messages_batch.append({
                    'id_users': user_id,
                    'id_message': message_id,
                    'message_text': message_text,
                    'created_at': created_at
                })
                
                # If messages batch is full, insert and clear
                if len(messages_batch) >= MESSAGE_BATCH_SIZE:
                    sql = text('''
                    INSERT INTO messages (id_users, id_message, message_text, created_at)
                    VALUES (:id_users, :id_message, :message_text, :created_at)
                    ON CONFLICT (id_users, id_message) DO NOTHING
                    ''')
                    
                    connection.execute(sql, messages_batch)
                    print(f"Process {os.getpid()}: Inserted {len(messages_batch)} messages")
                    messages_batch = []
        
        # Insert any remaining messages
        if messages_batch:
            sql = text('''
            INSERT INTO messages (id_users, id_message, message_text, created_at)
            VALUES (:id_users, :id_message, :message_text, :created_at)
            ON CONFLICT (id_users, id_message) DO NOTHING
            ''')
            
            connection.execute(sql, messages_batch)
            print(f"Process {os.getpid()}: Inserted final {len(messages_batch)} messages")
    
    # Step 5: Generate and insert tweets in a separate transaction
    print(f"Process {os.getpid()}: Generating tweets...")
    with engine.begin() as connection:
        # Prepare for batched processing
        tweet_ids = []  # Track all tweet IDs for relations
        tweet_batches = []
        current_batch = []
        
        # Prepare batches of tweet data
        for i in range(num_tweets):
            id_tweets += 1
            tweet_ids.append(id_tweets)  # Save for relations
            id_users = random.choice(user_ids)
            created_at = fake.date_time_between(start_date='-5y', end_date='now')
            
            # References to other tweets/users (nullable)
            in_reply_to_status_id = random.choice(user_ids) if random.random() > 0.7 else None
            in_reply_to_user_id = random.choice(user_ids) if random.random() > 0.7 else None
            quoted_status_id = random.choice(user_ids) if random.random() > 0.8 else None
            
            retweet_count = randint(0, 10000)
            favorite_count = randint(0, 20000)
            quote_count = randint(0, 5000)
            withheld_copyright = random.choice([True, False]) if random.random() > 0.9 else False
            
            countries = []
            if random.random() > 0.9:
                num_countries = randint(1, 3)
                for _ in range(num_countries):
                    countries.append(fake.country_code())
            
            source = f"<a href='{fake.url()}'>Twitter for {random.choice(['iPhone', 'Android', 'Web', 'iPad'])}</a>"
            tweet_text = fake.text(max_nb_chars=280)
            
            # Location data
            country_code = fake.country_code().lower() if random.random() > 0.6 else None
            state_code = fake.state_abbr().lower() if country_code == 'us' and random.random() > 0.5 else None
            lang = random.choice(['en', 'es', 'fr', 'de', 'ja', 'pt', 'ru', 'zh'])
            place_name = fake.city() if random.random() > 0.6 else None
            
            # Generate random geographic point
            if random.random() > 0.7:  # 30% chance of having geo data
                lat = uniform(-90, 90)
                lng = uniform(-180, 180)
                geo = f"POINT({lng} {lat})"
            else:
                geo = None
            
            # Add to current batch with ALL fields
            current_batch.append({
                'id_tweets': id_tweets,
                'id_users': id_users,
                'created_at': created_at,
                'in_reply_to_status_id': in_reply_to_status_id,
                'in_reply_to_user_id': in_reply_to_user_id,
                'quoted_status_id': quoted_status_id,
                'retweet_count': retweet_count,
                'favorite_count': favorite_count,
                'quote_count': quote_count,
                'withheld_copyright': withheld_copyright,
                'withheld_in_countries': countries if countries else None,
                'source': source,
                'text': tweet_text,
                'country_code': country_code,
                'state_code': state_code,
                'lang': lang,
                'place_name': place_name,
                'geo': geo
            })
            
            # When batch is full, add to batch list
            if len(current_batch) >= TWEET_BATCH_SIZE:
                tweet_batches.append(current_batch)
                current_batch = []
        
        # Add any remaining tweets
        if current_batch:
            tweet_batches.append(current_batch)
        
        # Insert all tweet batches
        sql = text('''
        INSERT INTO tweets 
            (id_tweets, id_users, created_at, in_reply_to_status_id, in_reply_to_user_id, 
            quoted_status_id, retweet_count, favorite_count, quote_count, withheld_copyright, 
            withheld_in_countries, source, text, country_code, state_code, lang, place_name, geo)
        VALUES 
            (:id_tweets, :id_users, :created_at, :in_reply_to_status_id, :in_reply_to_user_id, 
            :quoted_status_id, :retweet_count, :favorite_count, :quote_count, :withheld_copyright, 
            :withheld_in_countries, :source, :text, :country_code, :state_code, :lang, :place_name, 
            ST_GeomFromText(:geo))
        ON CONFLICT (id_tweets) DO NOTHING
        ''')
        
        total_tweets = 0
        for batch in tweet_batches:
            connection.execute(sql, batch)
            total_tweets += len(batch)
            print(f"Process {os.getpid()}: Inserted {total_tweets} tweets of {num_tweets}")
    
    # Step 6: Handle relations in separate batches and transactions
    print(f"Process {os.getpid()}: Generating tweet relations...")
    
    # Generate all relations first
    tweet_tags = []
    tweet_mentions = []
    tweet_urls = []
    tweet_media = []
    
    for tweet_id in tweet_ids:
        # Tags
        used_tags = set()
        num_tags = randint(0, 6)
        for _ in range(num_tags):
            prefix = random.choice(['#', '$'])
            for attempt in range(5):
                if prefix == '#':
                    tag = prefix + fake.word()
                else:
                    tag = prefix + ''.join(random.choice(string.ascii_uppercase) for _ in range(4))
                
                if tag not in used_tags:
                    used_tags.add(tag)
                    tweet_tags.append({'id_tweets': tweet_id, 'tag': tag})
                    break
        
        # URLs
        num_urls = randint(0, 3)
        for _ in range(num_urls):
            url = fake.url()
            tweet_urls.append({'id_tweets': tweet_id, 'url': url})
        
        # Mentions
        num_mentions = randint(0, 5)
        mentioned_users = sample(user_ids, min(num_mentions, len(user_ids)))
        for mentioned_user in mentioned_users:
            tweet_mentions.append({'id_tweets': tweet_id, 'id_users': mentioned_user})
        
        # Media
        num_media = randint(0, 4)
        media_types = ['photo', 'video', 'animated_gif']
        for _ in range(num_media):
            media_type = random.choice(media_types)
            url = f"https://pbs.twimg.com/media/{uuid.uuid4().hex}.jpg"
            tweet_media.append({'id_tweets': tweet_id, 'url': url, 'type': media_type})
    
    # Insert tweet tags in a separate transaction
    if tweet_tags:
        with engine.begin() as connection:
            sql = text('''
            INSERT INTO tweet_tags (id_tweets, tag)
            VALUES (:id_tweets, :tag)
            ON CONFLICT (id_tweets, tag) DO NOTHING
            ''')
            
            for i in range(0, len(tweet_tags), RELATION_BATCH_SIZE):
                batch = tweet_tags[i:i+RELATION_BATCH_SIZE]
                connection.execute(sql, batch)
                print(f"Process {os.getpid()}: Inserted {min(i+RELATION_BATCH_SIZE, len(tweet_tags))} of {len(tweet_tags)} tweet tags")
    
    # Insert tweet mentions in a separate transaction
    if tweet_mentions:
        with engine.begin() as connection:
            sql = text('''
            INSERT INTO tweet_mentions (id_tweets, id_users)
            VALUES (:id_tweets, :id_users)
            ON CONFLICT (id_tweets, id_users) DO NOTHING
            ''')
            
            for i in range(0, len(tweet_mentions), RELATION_BATCH_SIZE):
                batch = tweet_mentions[i:i+RELATION_BATCH_SIZE]
                connection.execute(sql, batch)
                print(f"Process {os.getpid()}: Inserted {min(i+RELATION_BATCH_SIZE, len(tweet_mentions))} of {len(tweet_mentions)} tweet mentions")
    
    # Insert tweet URLs in a separate transaction
    if tweet_urls:
        with engine.begin() as connection:
            sql = text('''
            INSERT INTO tweet_urls (id_tweets, url)
            VALUES (:id_tweets, :url)
            ON CONFLICT (id_tweets, url) DO NOTHING
            ''')
            
            for i in range(0, len(tweet_urls), RELATION_BATCH_SIZE):
                batch = tweet_urls[i:i+RELATION_BATCH_SIZE]
                connection.execute(sql, batch)
                print(f"Process {os.getpid()}: Inserted {min(i+RELATION_BATCH_SIZE, len(tweet_urls))} of {len(tweet_urls)} tweet URLs")
    
    # Insert tweet media in a separate transaction
    if tweet_media:
        with engine.begin() as connection:
            sql = text('''
            INSERT INTO tweet_media (id_tweets, url, type)
            VALUES (:id_tweets, :url, :type)
            ON CONFLICT (id_tweets, url) DO NOTHING
            ''')
            
            for i in range(0, len(tweet_media), RELATION_BATCH_SIZE):
                batch = tweet_media[i:i+RELATION_BATCH_SIZE]
                connection.execute(sql, batch)
                print(f"Process {os.getpid()}: Inserted {min(i+RELATION_BATCH_SIZE, len(tweet_media))} of {len(tweet_media)} tweet media items")
    
    # Skip materialized view refreshes in parallel processes - let the main process handle this
    
    end_time = time.time()
    duration = end_time - start_time
    print(f"Process {os.getpid()}: Data generation complete in {duration:.2f} seconds")
    print(f"Process {os.getpid()}: Generated {num_users} users and {num_tweets} tweets")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Generate random data for Twitter database schema')
    parser.add_argument('--users', type=int, default=50, help='Number of users to generate')
    parser.add_argument('--tweets', type=int, default=100, help='Number of tweets to generate')
    parser.add_argument('--user_id_start', type=int, default=0, help='Starting ID for users')
    parser.add_argument('--tweet_id_start', type=int, default=0, help='Starting ID for tweets')
    args = parser.parse_args()
    
    generate_random_data(args.users, args.tweets, args.user_id_start, args.tweet_id_start)

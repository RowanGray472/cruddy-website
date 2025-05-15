import os
import time
from flask import Flask, jsonify, send_from_directory, request, render_template, make_response, redirect
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from geoalchemy2 import Geometry
import re

app = Flask(__name__)
app.config.from_object("project.config.Config")
db = SQLAlchemy(app)

# messages data

class Account(db.Model):
    __tablename__ = "accounts"

    id_users = db.Column(db.BigInteger, primary_key=True)
    username = db.Column(db.Text)
    password = db.Column(db.Text)

    # Relationship with User model
    user = db.relationship('User', backref=db.backref('account', uselist=False),
                          primaryjoin='Account.id_users == User.id_users',
                          foreign_keys='Account.id_users')

class Message(db.Model):
    __tablename__ = "messages"

    id_users = db.Column(db.BigInteger, db.ForeignKey('accounts.id_users'), primary_key=True)
    id_message = db.Column(db.BigInteger, primary_key=True)
    message_text = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True))  # Consistent with other tables

    # Relationship with Account model
    account = db.relationship('Account', backref=db.backref('messages', lazy=True))

# tweet data

class User(db.Model):
    __tablename__ = "users"
    
    id_users = db.Column(db.BigInteger, primary_key=True)
    created_at = db.Column(db.DateTime(timezone=True))
    updated_at = db.Column(db.DateTime(timezone=True))
    url = db.Column(db.Text)
    friends_count = db.Column(db.Integer)
    listed_count = db.Column(db.Integer)
    favourites_count = db.Column(db.Integer)
    statuses_count = db.Column(db.Integer)
    protected = db.Column(db.Boolean)
    verified = db.Column(db.Boolean)
    screen_name = db.Column(db.Text)
    name = db.Column(db.Text)
    location = db.Column(db.Text)
    description = db.Column(db.Text)
    withheld_in_countries = db.Column(db.ARRAY(db.String(2)))

class Tweet(db.Model):
    __tablename__ = "tweets"
    
    id_tweets = db.Column(db.BigInteger, primary_key=True)
    id_users = db.Column(db.BigInteger, db.ForeignKey('users.id_users'))
    created_at = db.Column(db.DateTime(timezone=True))
    in_reply_to_status_id = db.Column(db.BigInteger)
    in_reply_to_user_id = db.Column(db.BigInteger)
    quoted_status_id = db.Column(db.BigInteger)
    retweet_count = db.Column(db.SmallInteger)
    favorite_count = db.Column(db.SmallInteger)
    quote_count = db.Column(db.SmallInteger)
    withheld_copyright = db.Column(db.Boolean)
    withheld_in_countries = db.Column(db.ARRAY(db.String(2)))
    source = db.Column(db.Text)
    text = db.Column(db.Text)
    country_code = db.Column(db.String(2))
    state_code = db.Column(db.String(2))
    lang = db.Column(db.Text)
    place_name = db.Column(db.Text)
    geo = db.Column(Geometry)
    
    # Relationship with User
    user = db.relationship('User', backref=db.backref('tweets', lazy=True))

class TweetUrl(db.Model):
    __tablename__ = "tweet_urls"
    
    id_tweets = db.Column(db.BigInteger, db.ForeignKey('tweets.id_tweets'), primary_key=True)
    url = db.Column(db.Text, primary_key=True)
    
    # Relationship with Tweet
    tweet = db.relationship('Tweet', backref=db.backref('urls', lazy=True))

class TweetMention(db.Model):
    __tablename__ = "tweet_mentions"
    
    id_tweets = db.Column(db.BigInteger, db.ForeignKey('tweets.id_tweets'), primary_key=True)
    id_users = db.Column(db.BigInteger, db.ForeignKey('users.id_users'), primary_key=True)
    
    # Relationships
    tweet = db.relationship('Tweet', backref=db.backref('mentions', lazy=True))
    user = db.relationship('User', backref=db.backref('mentioned_in', lazy=True))

class TweetTag(db.Model):
    __tablename__ = "tweet_tags"
    
    id_tweets = db.Column(db.BigInteger, db.ForeignKey('tweets.id_tweets'), primary_key=True)
    tag = db.Column(db.Text, primary_key=True)
    
    # Relationship with Tweet
    tweet = db.relationship('Tweet', backref=db.backref('tags', lazy=True))

class TweetMedia(db.Model):
    __tablename__ = "tweet_media"
    
    id_tweets = db.Column(db.BigInteger, db.ForeignKey('tweets.id_tweets'), primary_key=True)
    url = db.Column(db.Text, primary_key=True)
    type = db.Column(db.Text)
    
    # Relationship with Tweet
    tweet = db.relationship('Tweet', backref=db.backref('media', lazy=True))

# Don't use db.create_all() since tables are created by schema.sql
# Instead, just establish the connection

# For materialized views, you can create read-only models
class TweetTagTotal(db.Model):
    __tablename__ = "tweet_tags_total"
    
    row = db.Column(db.Integer, primary_key=True)
    tag = db.Column(db.Text)
    total = db.Column(db.Integer)

class TweetTagCooccurrence(db.Model):
    __tablename__ = "tweet_tags_cooccurrence"
    
    tag1 = db.Column(db.Text, primary_key=True)
    tag2 = db.Column(db.Text, primary_key=True)
    total = db.Column(db.Integer)

# Initialize database
with app.app_context():
    # db.create_all()
    pass

def print_debug_info():
    print('username:', request.form.get('username'))
    print('password:', request.form.get('password'))
    
    # cookies 
    print('username:', request.cookies.get('username'))
    print('password:', request.cookies.get('password'))
    

    

def check_credentials(username, password):
    """
    Check if the provided username and password match a record in the accounts table.
    Returns True if credentials are valid, False otherwise.
    """
    if not username or not password:
        return False
        
    try:
        # Query the accounts table to find a matching account
        account = Account.query.filter_by(username=username, password=password).first()
        
        # If we found a matching account, return True
        return account is not None
    except Exception as e:
        print(f"Error checking credentials: {e}")
        return False

@app.route("/")
def root():
    # login check
    username = request.cookies.get('username')
    password = request.cookies.get('password')
    user_id = request.cookies.get('id_users')
    good_credentials = check_credentials(username, password)

    # Query the 20 most recent messages from all users
    try:
        # Using a join to get both messages and usernames
        recent_messages = db.session.query(
            Message, Account.username
        ).join(
            Account, Message.id_users == Account.id_users
        ).order_by(
            Message.created_at.desc()
        ).limit(20).all()

        # Format messages with username
        messages = []
        for message, username in recent_messages:
            messages.append({
                'id': message.id_message,
                'text': message.message_text,
                'created_at': message.created_at,
                'username': username,
                # Optional: flag messages from the current user
                'is_own': str(message.id_users) == user_id if user_id else False
            })
            
    except Exception as e:
        print(f"Error fetching messages: {e}")
        messages = []

    return render_template('root.html', logged_in=good_credentials, messages=messages)

@app.route("/login", methods=['GET', 'POST'])
def login():
    # debugging + variables
    print_debug_info()
    username = request.form.get('username')
    password = request.form.get('password')
    good_credentials = check_credentials(username, password)

    # If no username was provided, show the login form
    if username is None:
        return render_template('login.html', bad_credentials=False)
    
    # Check if credentials are valid
    try:
        # Query the account directly to get the user ID
        account = Account.query.filter_by(username=username, password=password).first()
        
        if account:
            # Valid credentials - create response with cookies
            template = render_template('login.html', bad_credentials=False, logged_in=True)
            response = make_response(template)
            
            # Store username, password, and user ID in cookies
            response.set_cookie('username', username)
            response.set_cookie('password', password)
            response.set_cookie('id_users', str(account.id_users))  # Convert ID to string for cookie
            
            print(f"User {username} (ID: {account.id_users}) logged in successfully")
            return response
        else:
            # Invalid credentials
            print(f"Failed login attempt for username: {username}")
            return render_template('login.html', bad_credentials=True)
            
    except Exception as e:
        print(f"Error during login: {e}")
        return render_template('login.html', bad_credentials=True, error=str(e))

@app.route("/logout")
def logout():
    template = render_template('logout.html', logged_in = False)
    response = make_response(template)
    response.set_cookie('username', '')
    response.set_cookie('password', '')
    response.set_cookie('id_users', '')
    return response

@app.route("/api/test")
def test_db():
    """Simple test endpoint to verify database connection"""
    try:
        # Count users and tweets
        user_count = db.session.query(User).count()
        tweet_count = db.session.query(Tweet).count()

        # Get a sample user and tweet if available
        sample_user = db.session.query(User).first()
        sample_tweet = db.session.query(Tweet).first()

        user_data = None
        if sample_user:
            user_data = {
                "id": sample_user.id_users,
                "name": sample_user.name,
                "screen_name": sample_user.screen_name,
                "tweets_count": sample_user.statuses_count
            }

        tweet_data = None
        if sample_tweet:
            tweet_data = {
                "id": sample_tweet.id_tweets,
                "text": sample_tweet.text,
                "created_at": sample_tweet.created_at.isoformat() if sample_tweet.created_at else None
            }

        return jsonify({
            "status": "success",
            "database_info": {
                "user_count": user_count,
                "tweet_count": tweet_count
            },
            "sample_user": user_data,
            "sample_tweet": tweet_data
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@app.route("/api/data")
def get_data():
    """Simple endpoint to retrieve sample data from the database tables"""
    try:
        # Get 10 most recent tweets with related data
        tweets = db.session.query(Tweet).order_by(Tweet.created_at.desc()).limit(10).all()
        
        result = []
        for tweet in tweets:
            tweet_data = {
                "id": tweet.id_tweets,
                "text": tweet.text,
                "created_at": tweet.created_at.isoformat() if tweet.created_at else None,
                "retweet_count": tweet.retweet_count,
                "favorite_count": tweet.favorite_count,
                "user": {
                    "id": tweet.id_users,
                    "screen_name": tweet.user.screen_name if tweet.user else None,
                    "name": tweet.user.name if tweet.user else None
                },
                "tags": [tag.tag for tag in tweet.tags],
                "mentions": [
                    {
                        "id": mention.id_users,
                        "screen_name": mention.user.screen_name if mention.user else None
                    } 
                    for mention in tweet.mentions
                ],
                "media": [
                    {
                        "url": media.url,
                        "type": media.type
                    }
                    for media in tweet.media
                ]
            }
            result.append(tweet_data)
        
        # Also get top 5 hashtags 
        top_tags = db.session.query(TweetTagTotal).order_by(TweetTagTotal.total.desc()).limit(5).all()
        tags_data = [{"tag": tag.tag, "count": tag.total} for tag in top_tags]
        
        return jsonify({
            "status": "success",
            "tweets": result,
            "top_tags": tags_data
        })
    
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@app.route("/api/messages/<username>")
def get_messages(username):
    """Get messages for a specific user"""
    try:
        # Find account by username
        account = Account.query.filter_by(username=username).first()

        if not account:
            return jsonify({
                "status": "error",
                "message": "Account not found"
            }), 404

        # Get messages for this account
        messages = Message.query.filter_by(id_users=account.id_users).all()

        # Format messages
        messages_data = [
            {
                "id": message.id_message,
                "text": message.message_text
            }
            for message in messages
        ]

        return jsonify({
            "status": "success",
            "username": username,
            "message_count": len(messages_data),
            "messages": messages_data
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route("/create_account", methods=['GET', 'POST'])
def create_account():
    if request.method == 'GET':
        return render_template('create_account.html')
    
    # For POST requests, process the form submission
    username = request.form.get('username')
    password = request.form.get('password')
    confirm_password = request.form.get('confirm_password')
    
    # Validate inputs
    if not username or not password:
        return render_template('create_account.html', error="Username and password are required")
    
    if password != confirm_password:
        return render_template('create_account.html', error="Passwords do not match")
    
    # Check if username already exists
    existing_account = Account.query.filter_by(username=username).first()
    if existing_account:
        return render_template('create_account.html', error="Username already exists")
    
    try:
        # Manually assign id_users to be one more than the current max
        max_account_id = db.session.query(db.func.max(Account.id_users)).scalar() or 0
        max_user_id = db.session.query(db.func.max(User.id_users)).scalar() or 0
        next_id = max(max_account_id, max_user_id) + 1

        # Create a new account with the computed id_users
        new_account = Account(
            id_users=next_id,
            username=username,
            password=password
        )
        db.session.add(new_account)
        db.session.flush()  # Get the ID before committing

        # Create a corresponding user record
        new_user = User(
            id_users=new_account.id_users,
            created_at=db.func.now(),
            updated_at=db.func.now(),
            screen_name=username,
            name=username
        )
        db.session.add(new_user)
        db.session.commit()
        
        return render_template('login.html', account_created=True)
    
    except Exception as e:
        db.session.rollback()
        return render_template('create_account.html', error=f"Error creating account: {str(e)}")



@app.route("/create_message", methods=['GET', 'POST'])
def create_message():
    # Check if user is logged in
    username = request.cookies.get('username')
    password = request.cookies.get('password')
    user_id = request.cookies.get('id_users')

    # Verify credentials
    if not check_credentials(username, password) or not user_id:
        # Redirect to login if not logged in
        return redirect('/login')

    if request.method == 'GET':
        return render_template('create_message.html', logged_in=True)

    # For POST requests, process the message submission
    message_text = request.form.get('message_text')

    if not message_text:
        return render_template('create_message.html', error="Message cannot be empty")

    try:
        # Find the next available message ID for this user
        last_message = Message.query.filter_by(id_users=user_id).order_by(Message.id_message.desc()).first()
        next_id = 1 if not last_message else last_message.id_message + 1

        # Create new message
        new_message = Message(
            id_users=user_id,
            id_message=next_id,
            message_text=message_text,
            created_at=db.func.now()
        )

        db.session.add(new_message)
        db.session.commit()

        # Redirect to home page where messages are displayed
        return redirect('/')

    except Exception as e:
        db.session.rollback()
        return render_template('create_message.html', error=f"Error creating message: {str(e)}", logged_in=True)


@app.route("/search", methods=['GET', 'POST'])
def search():
    # Check if user is logged in
    username = request.cookies.get('username')
    password = request.cookies.get('password')
    user_id = request.cookies.get('id_users')
    good_credentials = check_credentials(username, password)

    # Initialize variables
    results = []
    query_text = request.form.get('query', '') if request.method == 'POST' else request.args.get('query', '')
    page = int(request.args.get('page', 1))
    per_page = 30
    total_results = 0
    query_time_ms = None

    if query_text:
        try:
            from sqlalchemy import text
            import time

            start_time = time.time()

            # First get total count for pagination
            count_sql = text("""
            SELECT COUNT(*)
            FROM messages m
            JOIN accounts a ON m.id_users = a.id_users
            WHERE to_tsvector('english', m.message_text) @@ plainto_tsquery('english', :query)
            """)

            count_result = db.session.execute(count_sql, {'query': query_text}).scalar()
            total_results = count_result or 0

            # Then get paginated results
            search_sql = text("""
            SELECT 
                m.id_message, 
                m.message_text, 
                m.created_at, 
                m.id_users, 
                a.username,
                ts_rank(to_tsvector('english', m.message_text), plainto_tsquery('english', :query)) AS rank
            FROM messages m
            JOIN accounts a ON m.id_users = a.id_users
            WHERE to_tsvector('english', m.message_text) @@ plainto_tsquery('english', :query)
            ORDER BY 
                ts_rank(to_tsvector('english', m.message_text), plainto_tsquery('english', :query)) DESC,
                m.created_at DESC
            LIMIT :limit OFFSET :offset
            """)

            offset = (page - 1) * per_page
            result = db.session.execute(
                search_sql,
                {'query': query_text, 'limit': per_page, 'offset': offset}
            )
            query_time = time.time() - start_time
            query_time_ms = int(query_time * 1000)
            # Process results
            for row in result:
                # Get the message text and split the query into words
                message_text = row.message_text
                search_terms = query_text.lower().split()

                # Create highlighted version of the message
                highlighted_text = message_text
                for term in search_terms:
                    if len(term) > 2:  # Only highlight meaningful terms
                        pattern = re.compile(r'\b(' + re.escape(term) + r')\b', re.IGNORECASE)
                        highlighted_text = pattern.sub(r'<span class="highlight">\1</span>', highlighted_text)

                results.append({
                    'id': row.id_message,
                    'text': row.message_text,
                    'highlighted_text': highlighted_text,
                    'created_at': row.created_at,
                    'username': row.username,
                    'is_own': str(row.id_users) == user_id if user_id else False
                })


        except Exception as e:
            # Make sure to define all template variables even when an exception occurs
            return render_template('search.html',
                                logged_in=good_credentials,
                                error=f"Search error: {str(e)}",
                                query=query_text,
                                results=[],
                                total_results=0,
                                page=page,
                                total_pages=0,
                                has_prev=False,
                                has_next=False,
                                query_time_ms=None)

    # Calculate pagination info
    total_pages = max(1, (total_results + per_page - 1) // per_page)
    has_prev = page > 1
    has_next = page < total_pages

    # For both GET and POST
    return render_template('search.html',
                          logged_in=good_credentials,
                          results=results,
                          query=query_text,
                          page=page,
                          total_pages=total_pages,
                          total_results=total_results,
                          has_prev=has_prev,
                          has_next=has_next,
                          query_time_ms=query_time_ms)
    
@app.route("/all_messages")
def all_messages():
    # login check
    username = request.cookies.get('username')
    password = request.cookies.get('password')
    user_id = request.cookies.get('id_users')
    good_credentials = check_credentials(username, password)
    
    # Get pagination parameters
    page = int(request.args.get('page', 1))
    per_page = 50  # Show more messages per page
    
    try:
        # Get total count for pagination
        total_count = db.session.query(Message).count()
        
        # Get paginated messages
        paginated_messages = db.session.query(
            Message, Account.username
        ).join(
            Account, Message.id_users == Account.id_users
        ).order_by(
            Message.created_at.desc()
        ).limit(per_page).offset((page - 1) * per_page).all()

        # Format messages
        messages = []
        for message, username in paginated_messages:
            messages.append({
                'id': message.id_message,
                'text': message.message_text,
                'created_at': message.created_at,
                'username': username,
                'is_own': str(message.id_users) == user_id if user_id else False
            })
            
        # Calculate pagination values
        total_pages = max(1, (total_count + per_page - 1) // per_page)
        has_prev = page > 1
        has_next = page < total_pages
            
    except Exception as e:
        print(f"Error fetching messages: {e}")
        messages = []
        total_pages = 1
        has_prev = False
        has_next = False
        
    return render_template('all_messages.html', 
                           logged_in=good_credentials, 
                           messages=messages, 
                           page=page,
                           total_pages=total_pages,
                           has_prev=has_prev,
                           has_next=has_next)

@app.route("/tweets")
def tweets():
    # login check
    username = request.cookies.get('username')
    password = request.cookies.get('password')
    user_id = request.cookies.get('id_users')
    good_credentials = check_credentials(username, password)

    # Get pagination parameters
    page = int(request.args.get('page', 1))
    per_page = 20  # Show 20 tweets per page

    try:
        # Get total count for pagination
        total_count = db.session.query(Tweet).count()

        # Get paginated tweets with related data
        tweets_data = db.session.query(Tweet).join(
            User, Tweet.id_users == User.id_users
        ).order_by(
            Tweet.created_at.desc()
        ).limit(per_page).offset((page - 1) * per_page).all()

        # Format tweets
        tweets = []
        for tweet in tweets_data:
            # Get hashtags
            hashtags = [tag.tag for tag in tweet.tags]

            # Get mentions with user information
            mentions = []
            for mention in tweet.mentions:
                # Try to get the mentioned user's information
                mentioned_user = User.query.get(mention.id_users)
                if mentioned_user:
                    mentions.append({
                        'id': mention.id_users,
                        'screen_name': mentioned_user.screen_name,
                        'name': mentioned_user.name
                    })

            # Get media items
            media_items = [{'url': m.url, 'type': m.type} for m in tweet.media]

            # Format URLs
            urls = [{'url': u.url} for u in tweet.urls]

            # Check if it's a retweet/quote
            is_retweet = tweet.text.startswith('RT @')
            is_quote = tweet.quoted_status_id is not None

            # Get Tweet info
            tweet_info = {
                'id': tweet.id_tweets,
                'text': tweet.text,
                'created_at': tweet.created_at,
                'retweet_count': tweet.retweet_count,
                'favorite_count': tweet.favorite_count,
                'quote_count': tweet.quote_count,
                'source': tweet.source,
                'lang': tweet.lang,
                'user': {
                    'id': tweet.user.id_users,
                    'screen_name': tweet.user.screen_name,
                    'name': tweet.user.name,
                    'description': tweet.user.description,
                    'location': tweet.user.location,
                    'verified': tweet.user.verified,
                    'url': tweet.user.url
                },
                'hashtags': hashtags,
                'mentions': mentions,
                'media': media_items,
                'urls': urls,
                'is_retweet': is_retweet,
                'is_quote': is_quote,
                'location': {
                    'place_name': tweet.place_name,
                    'country_code': tweet.country_code,
                    'state_code': tweet.state_code
                }
            }
            tweets.append(tweet_info)

        # Calculate pagination values
        total_pages = max(1, (total_count + per_page - 1) // per_page)
        has_prev = page > 1
        has_next = page < total_pages

    except Exception as e:
        print(f"Error fetching tweets: {e}")
        tweets = []
        total_pages = 1
        has_prev = False
        has_next = False
        total_count = 0

    return render_template('tweets.html',
                          logged_in=good_credentials,
                          tweets=tweets,
                          page=page,
                          total_pages=total_pages,
                          total_count=total_count,
                          has_prev=has_prev,
                          has_next=has_next)

import os

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    # Get configuration from environment variables (set by Docker)
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev")
    DEBUG = os.environ.get("DEBUG", "True").lower() in ["true", "t", "1"]
    TESTING = os.environ.get("TESTING", "False").lower() in ["true", "t", "1"]
    
    # Database configuration
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "postgresql://hello_flask:hello_flask@db:5432/hello_flask_dev")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

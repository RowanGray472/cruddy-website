from flask.cli import FlaskGroup
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

from project import app, db, User


cli = FlaskGroup(app)


@cli.command("create_db")
def create_db():
    # Function to safely execute a drop command
    def safe_drop(drop_command):
        try:
            db.session.execute(text(drop_command))
            db.session.commit()
        except Exception as e:
            print(f"Error executing {drop_command}: {e}")
            db.session.rollback()  # Important: rollback the failed transaction
    
    # Try different approaches to drop the views/tables
    safe_drop('DROP MATERIALIZED VIEW IF EXISTS tweet_tags_cooccurrence CASCADE')
    safe_drop('DROP TABLE IF EXISTS tweet_tags_cooccurrence CASCADE')
    
    safe_drop('DROP MATERIALIZED VIEW IF EXISTS tweet_tags_total CASCADE')
    safe_drop('DROP TABLE IF EXISTS tweet_tags_total CASCADE')
    
    # Now drop and recreate all tables
    try:
        db.drop_all()
        db.create_all()
        db.session.commit()
        print("Database recreated successfully!")
    except Exception as e:
        db.session.rollback()
        print(f"Error recreating database: {e}")
        raise


@cli.command("seed_db")
def seed_db():
    db.session.add(User(email="michael@mherman.org"))
    db.session.commit()


if __name__ == "__main__":
    cli()

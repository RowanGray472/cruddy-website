#!/bin/sh

if [ "$DATABASE" = "postgres" ]
then
    echo "Waiting for postgres..."

    while ! nc -z $SQL_HOST $SQL_PORT; do
      sleep 0.1
    done

    echo "PostgreSQL started"
fi

# Check if the database needs to be initialized (first time setup)
if [ "$POSTGRES_DB_INIT" = "true" ]
then
    echo "Initializing database..."
    python manage.py create_db
    echo "Database initialized"
fi

exec "$@"

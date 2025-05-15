FROM postgis/postgis:13-3.1

# Install the RUM extension
RUN apt-get update \
    && apt-get install -y postgresql-13-rum \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy initialization scripts
COPY schema.sql /docker-entrypoint-initdb.d/10-schema.sql

# Add a script to create extensions
COPY create_extensions.sql /docker-entrypoint-initdb.d/00-create_extensions.sql

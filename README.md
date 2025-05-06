## flask-on-docker

This repo contains the code for a demo Flask app built using the full Instagram tech stack. Specifically, it uses nginx for the web load balancer, Flask+Gunicorn  for the web framework, pg\_bouncer for the database load balancer, and PostgreSQL for the database itself. 

Everything is coordinated with Docker and the project has dev and prod environments.

The website itself is super minimalistic—the challenge here was assembling the stack so I can use it again for projects that might actually require it.

But it can upload and render GIFs! Check it out—apologies for the low video quality :(

![Demo of uploading and rendering the gif!](https://github.com/RowanGray472/flask-on-docker/blob/main/9lhe8x.gif)

### Build Instructions

To build up this service for yourself you'll need to add three .env files after cloning the repo.

First is .env.prod.db. This is the file for your db passwords. It should look like this

```
POSTGRES_USER={your username}
POSTGRES_PASSWORD={your password}
POSTGRES_DB={your db name}
```

Next you'll need an .env.prod—it should look like this.

```
FLASK_APP=project/__init__.py
FLASK_DEBUG=0
DATABASE_URL=postgresql://{your username}:{your password}@db:5432/{your db name}
SQL_HOST=db
SQL_PORT=5432
DATABASE=postgres
APP_FOLDER=/home/app/web
```

Finally you need to make a .env.dev.

```
FLASK_APP=project/__init__.py
FLASK_DEBUG=1
DATABASE_URL=postgresql://{your username}:{your password}@db:5432/{your db name}
SQL_HOST=db
SQL_PORT=5432
DATABASE=postgres
APP_FOLDER=/usr/src/app
```

Once you've got these files built you're ready to go! All you need to do now is run the following to build and start all the services.

```
$ docker compose -f docker-compose.prod.yml up -d --build
$ docker compose -f docker-compose.prod.yml exec web python manage.py create_db
```

To spin down the containers when you're done run this.

```
$ docker-compose down -v
```

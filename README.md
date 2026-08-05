# Flask + MySQL + Redis — Hello World App

A 3-tier app: a Flask web service, a MySQL database, and a Redis cache,
containerized with Docker Compose.

## What it does

- `GET /` — increments a visit counter using the cache-aside pattern: checks
  Redis first, falls back to MySQL on a cache miss, then repopulates Redis
  with a short TTL.
- `GET /health` — checks MySQL and Redis connectivity independently. Returns
  `200` if both are reachable, `503` otherwise. Used by health checks /
  probes.

## Stack

| Component | Image / Version |
|---|---|
| Web app | Python 3.12, Flask 3, Gunicorn |
| Database | `mysql:8.0` |
| Cache | `redis:7-alpine` |

## Configuration

All config is via environment variables — see `.env`.

| Variable | Description |
|---|---|
| `PORT` | Port the app listens on (default `5000`) |
| `DB_HOST` | MySQL host — service name `db` in Docker, `localhost` outside |
| `DB_PORT` | MySQL port (`3306`) |
| `DB_USER` | MySQL user |
| `DB_PASSWORD` | MySQL password (also used as root password in Compose) |
| `DB_NAME` | MySQL database name |
| `REDIS_HOST` | Redis host — service name `cache` in Docker, `localhost` outside |
| `REDIS_PORT` | Redis port (`6379`) |
| `REDIS_DB` | Redis logical DB index (`0`) |
| `CACHE_TTL_SECONDS` | How long a cached count is valid (`10`) |

## Running with Docker (recommended)

```bash
cp .env.example .env
# edit .env if needed

docker compose up -d --build
```

App available at `http://localhost:5000`. Check `http://localhost:5000/health`
to confirm both dependencies are reachable.

**First-time setup / resetting the database:** MySQL only runs its user and
database initialization on an empty data volume. If you change `DB_USER`,
`DB_PASSWORD`, or `DB_NAME` after the first run, reset the volume:

```bash
docker compose down -v
docker compose up -d --build
```

## Running locally without Docker

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# set DB_HOST=localhost and REDIS_HOST=localhost, and point to a local
# MySQL/Redis instance

python app.py
```

## Notes

- The app is stateless — safe to run multiple `webapp` replicas behind a
  load balancer.
- `docker-compose.yml` uses `depends_on` with `condition: service_healthy`
  on both `db` and `cache`, so the web app only starts once MySQL and Redis
  are actually ready to accept connections, not just once their containers
  have started.
- The container runs Gunicorn (`gunicorn --bind 0.0.0.0:$PORT --workers 3
  app:app`), not the Flask development server.

## Project structure

```
.
├── app.py
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── .gitignore
└── README.md
```

from dotenv import load_dotenv
load_dotenv()

import os
import logging

from flask import Flask, jsonify
import pymysql
import redis

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Configuration — everything comes from environment variables.
# No hardcoded hosts/credentials, so this runs the same on a laptop,
# in Docker Compose, or in Kubernetes.
# ---------------------------------------------------------------------------
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = int(os.environ.get("DB_PORT", 3306))
DB_USER = os.environ.get("DB_USER", "root")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
DB_NAME = os.environ.get("DB_NAME", "appdb")

REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
REDIS_DB = int(os.environ.get("REDIS_DB", 0))

CACHE_TTL_SECONDS = int(os.environ.get("CACHE_TTL_SECONDS", 10))


def get_db_connection():
    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        connect_timeout=5,
        cursorclass=pymysql.cursors.DictCursor,
    )


def get_redis_client():
    return redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        socket_connect_timeout=5,
        decode_responses=True,
    )


def init_db():
    """Create the visits table on first run if it doesn't exist yet."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS visits (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    count INT NOT NULL DEFAULT 0
                )
                """
            )
            cursor.execute("SELECT COUNT(*) AS cnt FROM visits")
            if cursor.fetchone()["cnt"] == 0:
                cursor.execute("INSERT INTO visits (count) VALUES (0)")
        conn.commit()
    finally:
        conn.close()


@app.route("/")
def home():
    """
    Cache-aside pattern:
    1. Try Redis first.
    2. On a miss, fall back to MySQL, then repopulate the cache.
    """
    r = get_redis_client()
    cached = r.get("visit_count")
    if cached is not None:
        return jsonify(
            {
                "message": "Hello, World!",
                "visit_count": int(cached),
                "source": "cache",
            }
        )

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE visits SET count = count + 1 WHERE id = 1")
            conn.commit()
            cursor.execute("SELECT count FROM visits WHERE id = 1")
            count = cursor.fetchone()["count"]
    finally:
        conn.close()

    r.setex("visit_count", CACHE_TTL_SECONDS, count)

    return jsonify(
        {
            "message": "Hello, World!",
            "visit_count": count,
            "source": "database",
        }
    )


@app.route("/health")
def health():
    """
    Liveness/readiness endpoint. Checks both dependencies independently
    so DevOps can wire this into a container HEALTHCHECK or a Kubernetes probe.
    """
    status = {"status": "ok", "database": "unknown", "cache": "unknown"}
    http_status = 200

    try:
        conn = get_db_connection()
        conn.close()
        status["database"] = "ok"
    except Exception as exc:
        logger.error("Database health check failed: %s", exc)
        status["database"] = "unreachable"
        status["status"] = "degraded"
        http_status = 503

    try:
        r = get_redis_client()
        r.ping()
        status["cache"] = "ok"
    except Exception as exc:
        logger.error("Redis health check failed: %s", exc)
        status["cache"] = "unreachable"
        status["status"] = "degraded"
        http_status = 503

    return jsonify(status), http_status


# Try to set up the table at startup. If the DB isn't ready yet (e.g. the
# container is still initializing), don't crash — log it and let /health
# report it. This is a known ordering issue between containers; see README.
with app.app_context():
    try:
        init_db()
    except Exception as exc:
        logger.warning("DB not ready at startup, will not block boot: %s", exc)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

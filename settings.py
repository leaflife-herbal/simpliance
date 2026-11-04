"""Configuration from environment variables only (set in the Render dashboard; never commit secrets)."""
import os

APP_NAME = "Factory Compliance Manager"
APP_ENV = os.getenv("APP_ENV", "production")          # set APP_ENV=development locally
DEBUG = APP_ENV == "development"


def _database_url() -> str:
    url = os.getenv("DATABASE_URL", "")
    if not url:
        if DEBUG:
            return "sqlite+pysqlite:///./dev.db"   # local convenience only; production needs Postgres
        raise RuntimeError("DATABASE_URL is not set (use the Aiven PostgreSQL service URI).")
    # Aiven gives postgres://...?sslmode=require ; SQLAlchemy + psycopg3 needs this prefix.
    for old in ("postgres://", "postgresql://"):
        if url.startswith(old):
            url = "postgresql+psycopg://" + url[len(old):]
    return url


DATABASE_URL = _database_url()
# Optional: contents of Aiven's CA certificate (PEM) to verify the database server.
AIVEN_CA_CERT = os.getenv("AIVEN_CA_CERT", "")

SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-secret" if DEBUG else "")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY is not set.")

SESSION_HOURS = int(os.getenv("SESSION_HOURS", "8"))
COOKIE_SECURE = not DEBUG
MAX_FAILED_LOGINS = 5
LOCKOUT_MINUTES = 15

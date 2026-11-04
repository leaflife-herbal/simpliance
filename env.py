from alembic import context

from app import models  # noqa: F401  (registers tables)
from app.db import Base, engine

target_metadata = Base.metadata


def run_migrations_online():
    # Use MIGRATION_DATABASE_URL (owner/admin role) if provided, else the app's engine.
    import os
    from sqlalchemy import create_engine
    from app import settings
    url = os.getenv("MIGRATION_DATABASE_URL")
    eng = create_engine(url.replace("postgres://", "postgresql+psycopg://", 1)
                        if url and url.startswith("postgres://") else url) if url else engine
    with eng.connect() as conn:
        context.configure(connection=conn, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()

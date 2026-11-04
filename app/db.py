import os
import tempfile

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from . import settings


class Base(DeclarativeBase):
    pass


def _engine():
    kwargs = {}
    if settings.DATABASE_URL.startswith("postgresql"):
        kwargs.update(pool_size=5, max_overflow=5, pool_pre_ping=True, pool_recycle=1800)
        if settings.AIVEN_CA_CERT:
            path = os.path.join(tempfile.gettempdir(), "aiven-ca.pem")
            with open(path, "w") as f:
                f.write(settings.AIVEN_CA_CERT)
            kwargs["connect_args"] = {"sslmode": "verify-ca", "sslrootcert": path}
    return create_engine(settings.DATABASE_URL, **kwargs)


engine = _engine()
SessionLocal = sessionmaker(engine, expire_on_commit=False)


def get_db():
    """One transaction per request: commit on success, roll back on error."""
    with SessionLocal() as s:
        try:
            yield s
            s.commit()
        except Exception:
            s.rollback()
            raise


def set_tenant(session, company_id):
    """Scope this transaction to one company for Postgres row-level security (used by business tables)."""
    if engine.dialect.name == "postgresql":
        session.execute(text("SELECT set_config('app.company_id', :v, true)"), {"v": str(int(company_id))})

"""Service-layer tests on SQLite (CI):  APP_ENV=development python -m pytest tests -q
They cover Super-Admin-only user creation, licence limits, tenant boundaries and lockout."""
import os
os.environ.setdefault("APP_ENV", "development")
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models, services
from app.db import Base

CO = dict(name="Acme", short_code="AC", factory_licence_no="L1", address1="x", city="Ludhiana", state="Punjab",
          occupier_name="o", manager_name="m", wage_divisor="Calendar days", doc_language="English only", hours_per_day="8",
          pf_wage_ceiling="15000", esi_threshold="21000")


@pytest.fixture()
def db():
    eng = create_engine("sqlite+pysqlite:///:memory:", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(eng)
    with sessionmaker(eng)() as s:
        yield s


@pytest.fixture()
def world(db):
    sa = services.create_super_admin(db, "boss", "Boss", "Passw0rd-long1")
    org = services.save_organisation(db, sa, "Org A", 2, 2, "", True)
    org2 = services.save_organisation(db, sa, "Org B", 1, 1, "", True)
    c1 = services.save_company(db, sa, org.id, CO)
    c2 = services.save_company(db, sa, org2.id, {**CO, "name": "Other", "short_code": "OT"})
    return sa, org, org2, c1, c2


def test_only_super_admin_creates_users(db, world):
    sa, org, org2, c1, c2 = world
    op = services.create_user(db, sa, org.id, "oper1", "Op", "Secret-pass12", "OPERATOR", True, [c1.id])
    with pytest.raises(services.Denied):
        services.create_user(db, op, org.id, "oper2", "X", "Secret-pass12", "OPERATOR", False, [c1.id])
    with pytest.raises(services.Denied):
        services.save_company(db, op, org.id, {**CO, "short_code": "ZZ"})


def test_single_super_admin_and_role_rules(db, world):
    sa, org, *_ = world
    with pytest.raises(services.Denied):
        services.create_super_admin(db, "boss2", "B2", "Passw0rd-long1")
    with pytest.raises(services.Invalid):
        services.create_user(db, sa, org.id, "x1x", "X", "Secret-pass12", "SUPER_ADMIN", True, [])


def test_tenant_boundaries(db, world):
    sa, org, org2, c1, c2 = world
    with pytest.raises(services.Invalid):   # user of Org A cannot be given Org B's company
        services.create_user(db, sa, org.id, "oper1", "Op", "Secret-pass12", "OPERATOR", False, [c2.id])
    op = services.create_user(db, sa, org.id, "oper1", "Op", "Secret-pass12", "OPERATOR", False, [c1.id])
    assert [c.id for c in services.companies_for(db, op)] == [c1.id]
    assert {c.id for c in services.companies_for(db, sa)} == {c1.id, c2.id}


def test_licence_limits(db, world):
    sa, org, org2, c1, c2 = world
    with pytest.raises(services.Invalid):   # Org B allows 1 company
        services.save_company(db, sa, org2.id, {**CO, "name": "Third", "short_code": "T3"})
    services.create_user(db, sa, org2.id, "bobuser", "B", "Secret-pass12", "VIEWER", False, [c2.id])
    with pytest.raises(services.Invalid):   # Org B allows 1 user
        services.create_user(db, sa, org2.id, "bobtwo", "B2", "Secret-pass12", "VIEWER", False, [c2.id])


def test_lockout_and_login(db, world):
    sa, org, org2, c1, c2 = world
    services.create_user(db, sa, org.id, "oper1", "Op", "Secret-pass12", "OPERATOR", False, [c1.id])
    for _ in range(5):
        with pytest.raises(services.Invalid):
            services.authenticate(db, "oper1", "wrong-password")
    with pytest.raises(services.Invalid) as e:
        services.authenticate(db, "oper1", "Secret-pass12")
    assert "locked" in str(e.value).lower()
    u = db.query(models.User).filter_by(username="oper1").one()
    services.reset_password(db, sa, u.id, "New-secret-pass9")
    assert services.authenticate(db, "oper1", "New-secret-pass9").id == u.id

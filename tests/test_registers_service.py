"""Register service tests on SQLite (CI):  APP_ENV=development python -m pytest tests -q"""
import os
os.environ.setdefault("APP_ENV", "development")
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import hr, registers, services
from app.core.specs import REGISTER_BY_KEY
from app.db import Base
from tests.test_services import CO
from tests.test_registers_pure import RAW


@pytest.fixture()
def w():
    eng = create_engine("sqlite+pysqlite:///:memory:", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(eng)
    with sessionmaker(eng)() as db:
        sa = services.create_super_admin(db, "boss", "Boss", "Passw0rd-long1")
        org = services.save_organisation(db, sa, "Org", 2, 5, "", True)
        c1 = services.save_company(db, sa, org.id, CO)
        c2 = services.save_company(db, sa, org.id, {**CO, "name": "Second", "short_code": "S2"})
        op = services.create_user(db, sa, org.id, "oper1", "Op", "Secret1", "OPERATOR", True, [c1.id])
        viewer = services.create_user(db, sa, org.id, "view1", "V", "Secret1", "VIEWER", False, [c1.id])
        yield db, sa, op, viewer, c1, c2


def test_register_crud_rules_and_isolation(w):
    db, sa, op, viewer, c1, c2 = w
    kid = REGISTER_BY_KEY["child_labour"]
    with pytest.raises(services.Invalid):                       # under 14
        registers.save(db, op, c1.id, kid, {**RAW["child_labour"], "date_of_birth": "2014-01-01"})
    o = registers.save(db, op, c1.id, kid, RAW["child_labour"])
    assert (o.category, float(o.daily_hours)) == ("Child (14-15)", 3.0)
    acc = REGISTER_BY_KEY["accidents"]
    with pytest.raises(hr.Warn):                                # fatal without notice
        registers.save(db, op, c1.id, acc, {**RAW["accidents"], "severity": "Fatal", "notice_date": ""})
    a = registers.save(db, op, c1.id, acc, RAW["accidents"])
    assert registers.get_row(db, c2.id, acc, a.id) is None      # other company cannot see it
    assert registers.list_rows(db, c2.id, acc) == []
    with pytest.raises(services.Denied):
        registers.save(db, viewer, c1.id, acc, RAW["accidents"])
    with pytest.raises(services.Denied):
        registers.save(db, sa, c1.id, acc, RAW["accidents"])    # Super Admin is read-only on data
    registers.delete(db, op, c1.id, acc, a.id)
    assert registers.list_rows(db, c1.id, acc) == []

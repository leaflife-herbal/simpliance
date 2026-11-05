"""Service tests on SQLite (run in CI / locally):  APP_ENV=development python -m pytest tests -q"""
import os
os.environ.setdefault("APP_ENV", "development")
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import hr, models, services
from app.db import Base
from tests.test_services import CO


def emp(code, **kw):
    d = dict(emp_code=code, name="Worker " + code, gender="Male", date_of_birth="1990-01-01",
             date_of_joining="2020-01-01", shift_in="09:00", shift_out="18:00", weekly_off="Sunday",
             salary_type="MONTHLY", basic="10000", da="2000", hra="0", other_allowance="0", is_active="1",
             pf_applicable="1", esi_applicable="1", pt_applicable="1")
    d.update(kw)
    return d


@pytest.fixture()
def w():
    eng = create_engine("sqlite+pysqlite:///:memory:", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(eng)
    with sessionmaker(eng)() as db:
        sa = services.create_super_admin(db, "boss", "Boss", "Passw0rd-long1")
        org = services.save_organisation(db, sa, "Org", 2, 5, "", True)
        c1 = services.save_company(db, sa, org.id, CO)
        c2 = services.save_company(db, sa, org.id, {**CO, "name": "Second", "short_code": "S2"})
        op = services.create_user(db, sa, org.id, "oper1", "Op", "Secret-pass12", "OPERATOR", True, [c1.id])
        viewer = services.create_user(db, sa, org.id, "view1", "V", "Secret-pass12", "VIEWER", False, [c1.id])
        yield db, sa, op, viewer, c1, c2


def test_month_flow_and_numbers(w):
    db, sa, op, viewer, c1, c2 = w
    e1 = hr.save_employee(db, op, c1.id, emp("E1"))
    e2 = hr.save_employee(db, op, c1.id, emp("E2", basic="8000", da="1000"))
    hr.save_inputs(db, op, c1.id, 2026, 10, [
        dict(employee_id=e1.id, days_worked="27", ot_hours="0", advance="0", other_deduction="0"),
        dict(employee_id=e2.id, days_worked="24", ot_hours="10", advance="500", other_deduction="0")])
    assert hr.generate_attendance(db, op, c1.id, 2026, 10) == []
    hr.calculate_salary(db, op, c1.id, 2026, 10)
    L = {l["emp_code"]: l for l in hr.get_lines(db, c1.id, 2026, 10)}
    assert L["E1"]["gross"] == 12000 and L["E1"]["pf_employee"] == 1440 and L["E1"]["esi_employee"] == 90
    assert L["E2"]["earned_basic"] == 7226 and L["E2"]["ot_amount"] == 726 and L["E2"]["esi_employee"] == 61
    hr.finalise(db, op, c1.id, 2026, 10)
    with pytest.raises(services.Invalid):
        hr.generate_attendance(db, op, c1.id, 2026, 10)
    hr.unlock(db, op, c1.id, 2026, 10)


def test_permissions_and_tenancy(w):
    db, sa, op, viewer, c1, c2 = w
    with pytest.raises(services.Denied):
        hr.save_employee(db, viewer, c1.id, emp("E9"))
    with pytest.raises(services.Denied):
        hr.save_employee(db, sa, c1.id, emp("E9"))          # Super Admin is read-only on data
    e = hr.save_employee(db, op, c1.id, emp("E1"))
    assert hr.get_employee(db, c2.id, e.id) is None         # other company cannot see it
    assert hr.list_employees(db, c2.id) == []
    with pytest.raises(services.Denied):
        hr.need_salary(db, viewer, write=False)
    with pytest.raises(services.Invalid):                   # duplicate code
        hr.save_employee(db, op, c1.id, emp("e1"))
    with pytest.raises(hr.Warn):                            # zero basic -> warning, needs confirmation
        hr.save_employee(db, op, c1.id, emp("E5", basic="0"))

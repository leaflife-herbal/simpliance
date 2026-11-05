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


def test_holidays_dashboard_backup(w):
    import io, zipfile
    from datetime import date
    from app import backup
    db, sa, op, viewer, c1, c2 = w
    hr.add_holiday(db, op, c1.id, "2026-10-20", "Diwali")
    with pytest.raises(services.Invalid):
        hr.add_holiday(db, op, c1.id, "2026-10-20", "Again")
    assert hr.holiday_dates(db, c1.id, 2026, 10) == {date(2026, 10, 20)}
    with pytest.raises(services.Denied):
        hr.add_holiday(db, viewer, c1.id, "2026-10-21", "X")
    acc = REGISTER_BY_KEY["accidents"]
    with pytest.raises(hr.Warn):
        registers.save(db, op, c1.id, acc, {**RAW["accidents"], "severity": "Fatal", "notice_date": ""})
    registers.save(db, op, c1.id, acc, {**RAW["accidents"], "severity": "Fatal", "notice_date": ""}, ignore_warnings=True)
    d = hr.dashboard(db, c1.id, date(2026, 11, 4))
    assert d["pending_notices"] == 1 and d["employees"] == 0
    z = zipfile.ZipFile(io.BytesIO(backup.build_zip(db, c1.id)))
    assert "employees.csv" in z.namelist() and "reg_accidents.csv" in z.namelist() and "holidays.csv" in z.namelist()
    lic, subs = services.expiring(db, date(2026, 11, 4))
    assert lic == [] and subs == []


def test_leave_summary(w):
    from datetime import date
    db, sa, op, viewer, c1, c2 = w
    from tests.test_hr import emp
    e = hr.save_employee(db, op, c1.id, emp("E1"))
    hr.save_inputs(db, op, c1.id, 2026, 10, [dict(employee_id=e.id, days_worked="27", ot_hours="0", advance="0",
                                                  other_deduction="0")])
    assert hr.generate_attendance(db, op, c1.id, 2026, 10) == []
    hr.update_day(db, op, c1.id, e.id, "2026-10-05", "PL", None, None)
    hr.save_leave_openings(db, op, c1.id, 2026, {e.id: "3"})
    rows, n = hr.leave_summary(db, c1.id, 2026)
    r = rows[0]
    assert n == 20 and r["taken"] == 1 and r["opening"] == 3.0 and r["days_worked"] == 27     # 26 present + 1 PL
    assert r["accrued"] == 1 and r["balance"] == 3.0                                          # 27/20 = 1.35 -> 1
    with pytest.raises(services.Denied):
        hr.save_leave_openings(db, viewer, c1.id, 2026, {e.id: "1"})

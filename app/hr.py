"""Employees, monthly inputs, attendance and salary. Every function takes the company id that the web layer
has already verified against the user's assigned companies, and filters every query by it."""
from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from . import services
from .core import attendance_engine as ae, payroll_engine as pe, validators
from .core.forms import clean_values
from .core.specs import EMPLOYEE_FIELDS
from .core.util import valid_time
from .core.leave import leave_row
from .core.specs import ACCIDENT_SEVERITY
from .core.util import days_left, expiry_level
from .models import (Attendance, Company, Employee, Holiday, LeaveOpening, MonthlyInput, REGISTER_MODELS, SalaryLine, SalaryRun)
from .services import Denied, Invalid


class Warn(Exception):
    def __init__(self, warnings):
        super().__init__("; ".join(warnings))
        self.warnings = list(warnings)


def now():
    return datetime.now(timezone.utc)


def row(o) -> dict:
    return {c.name: getattr(o, c.name) for c in o.__table__.columns}


# ------------------------------------------------------------------ permissions
def can_edit(db, user) -> bool:
    return user.can_write and not services.read_only_reason(db, user)


def need_edit(db, user):
    if not can_edit(db, user):
        raise Denied(services.read_only_reason(db, user) or "Your account is read-only.")


def need_salary(db, user, write=False):
    if write:
        need_edit(db, user)
        if not user.can_salary:
            raise Denied("You do not have permission to process salaries.")
    elif not user.can_view_salary:
        raise Denied("You do not have permission to view salaries.")


def month_bounds(y, m):
    return date(y, m, 1), date(y, m, monthrange(y, m)[1])


def is_final(db, cid, y, m) -> bool:
    run = db.scalar(select(SalaryRun).where(SalaryRun.company_id == cid, SalaryRun.year == y, SalaryRun.month == m))
    return bool(run and run.status == "FINAL")


def _need_unlocked(db, cid, y, m):
    if is_final(db, cid, y, m):
        raise Invalid(["Salary for this month is finalised. Unlock it first."])


# ------------------------------------------------------------------ employees
def list_employees(db, cid, active_only=True, q=""):
    stmt = select(Employee).where(Employee.company_id == cid)
    if active_only:
        stmt = stmt.where(Employee.is_active.is_(True))
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(or_(func.lower(Employee.name).like(like), func.lower(Employee.emp_code).like(like)))
    return list(db.scalars(stmt.order_by(Employee.emp_code)))


def get_employee(db, cid, emp_id):
    e = db.get(Employee, emp_id)
    return e if e and e.company_id == cid else None


def save_employee(db, user, cid, raw, emp_id=None, ip=None, ignore_warnings=False):
    need_edit(db, user)
    clean, errors = clean_values(EMPLOYEE_FIELDS, raw)
    warnings = []
    if not errors:
        e_, w_ = validators.employee(clean, cid, emp_id)
        errors += e_
        warnings += w_
        dup = db.scalar(select(Employee.id).where(Employee.company_id == cid,
                                                  func.lower(Employee.emp_code) == clean["emp_code"].lower(),
                                                  Employee.id != (emp_id or 0)))
        if dup:
            errors.append("Employee code already exists in this company")
    if errors:
        raise Invalid(errors)
    if warnings and not ignore_warnings:
        raise Warn(warnings)
    if emp_id:
        e = get_employee(db, cid, emp_id)
        if not e:
            raise Invalid(["Employee not found"])
    else:
        e = Employee(company_id=cid, created_by=user.id)
    for k, v in clean.items():
        setattr(e, k, v)
    e.updated_at = now()
    db.add(e)
    db.flush()
    services.audit(db, user, "UPDATE" if emp_id else "CREATE", "employees", e.id,
                   {"code": e.emp_code, "name": e.name}, ip, cid)
    return e


def import_employees(db, user, cid, rows, update_existing=False, ip=None):
    """rows: [(excel_row_number, raw dict)] from core.importer. All-or-nothing: any error imports nothing."""
    need_edit(db, user)
    existing = {e.emp_code.lower(): e for e in db.scalars(select(Employee).where(Employee.company_id == cid))}
    seen, plan, errors, warnings = {}, [], [], []
    for n, raw in rows:
        clean, errs = clean_values(EMPLOYEE_FIELDS, raw)
        row_w = []
        if not errs:
            e_, w_ = validators.employee(clean, cid, None)
            errs += e_
            row_w += w_
        code = (clean.get("emp_code") or "").lower()
        ex = None
        if code:
            if code in seen:
                errs.append(f"employee code repeated (also on row {seen[code]})")
            seen[code] = n
            ex = existing.get(code)
            if ex and not update_existing:
                errs.append("employee code already exists (tick 'update existing' to overwrite)")
        if errs:
            errors.append(f"Row {n}: " + "; ".join(errs))
        else:
            plan.append((clean, ex))
            warnings += [f"Row {n}: {w}" for w in row_w]
    if errors:
        raise Invalid(errors[:60] + ([f"... and {len(errors) - 60} more rows with errors"] if len(errors) > 60 else []))
    created = updated = 0
    for clean, ex in plan:
        e = ex or Employee(company_id=cid, created_by=user.id)
        for k, v in clean.items():
            setattr(e, k, v)
        e.updated_at = now()
        db.add(e)
        updated += 1 if ex else 0
        created += 0 if ex else 1
    db.flush()
    services.audit(db, user, "IMPORT_EMPLOYEES", "employees", None, {"created": created, "updated": updated}, ip, cid)
    return {"created": created, "updated": updated, "warnings": warnings}


def eligible(db, cid, y, m):
    """Employees on the rolls at any time during the month."""
    start, end = month_bounds(y, m)
    stmt = select(Employee).where(
        Employee.company_id == cid, Employee.date_of_joining <= end,
        or_(Employee.date_of_leaving >= start,
            (Employee.date_of_leaving.is_(None)) & (Employee.is_active.is_(True)))).order_by(Employee.emp_code)
    return list(db.scalars(stmt))


# ------------------------------------------------------------------ monthly inputs
def get_inputs(db, cid, y, m):
    have = {r.employee_id: r for r in db.scalars(select(MonthlyInput).where(
        MonthlyInput.company_id == cid, MonthlyInput.year == y, MonthlyInput.month == m))}
    out = []
    for e in eligible(db, cid, y, m):
        r = have.get(e.id)
        out.append({"employee_id": e.id, "emp_code": e.emp_code, "name": e.name,
                    "days_worked": r.days_worked if r else 0, "ot_hours": r.ot_hours if r else 0,
                    "advance": r.advance if r else 0, "other_deduction": r.other_deduction if r else 0,
                    "remarks": (r.remarks if r else "") or ""})
    return out


def _dec(v):
    try:
        return Decimal(str(v or "0").replace(",", ""))
    except InvalidOperation:
        raise ValueError


def save_inputs(db, user, cid, y, m, items):
    """items: [{employee_id, days_worked, ot_hours, advance, other_deduction, remarks}] (raw strings)."""
    need_edit(db, user)
    _need_unlocked(db, cid, y, m)
    ok_ids = {e.id: e for e in eligible(db, cid, y, m)}
    dim = monthrange(y, m)[1]
    errors, clean = [], []
    for it in items:
        e = ok_ids.get(it["employee_id"])
        if not e:
            errors.append("An employee is not on the rolls for this month")
            continue
        try:
            dw, ot, adv, od = (_dec(it.get(k)) for k in ("days_worked", "ot_hours", "advance", "other_deduction"))
        except ValueError:
            errors.append(f"{e.name}: numbers only")
            continue
        if min(dw, ot, adv, od) < 0:
            errors.append(f"{e.name}: values cannot be negative")
        elif (dw * 2) != int(dw * 2):
            errors.append(f"{e.name}: days worked must be in steps of 0.5")
        elif dw > dim:
            errors.append(f"{e.name}: days worked exceeds days in the month")
        else:
            clean.append((e, dw, ot, adv, od, (it.get("remarks") or "").strip()[:255] or None))
    if errors:
        raise Invalid(errors)
    existing = {r.employee_id: r for r in db.scalars(select(MonthlyInput).where(
        MonthlyInput.company_id == cid, MonthlyInput.year == y, MonthlyInput.month == m))}
    for e, dw, ot, adv, od, rem in clean:
        r = existing.get(e.id) or MonthlyInput(company_id=cid, employee_id=e.id, year=y, month=m)
        r.days_worked, r.ot_hours, r.advance, r.other_deduction, r.remarks = dw, ot, adv, od, rem
        db.add(r)
    db.flush()
    services.audit(db, user, "SAVE_INPUTS", "monthly_inputs", None, {"year": y, "month": m, "count": len(clean)},
                   None, cid)


# ------------------------------------------------------------------ attendance
def generate_attendance(db, user, cid, y, m):
    """(Re)generate the month's register for everyone on the rolls. Returns a list of problems (empty = done)."""
    need_edit(db, user)
    _need_unlocked(db, cid, y, m)
    inputs = {i["employee_id"]: i for i in get_inputs(db, cid, y, m)}
    emps = eligible(db, cid, y, m)
    var = db.get(Company, cid).attendance_variation
    var = 10 if var is None else int(var)
    hol = holiday_dates(db, cid, y, m)
    built, problems = {}, []
    for e in emps:
        try:
            built[e.id] = ae.build_month(y, m, float(inputs[e.id]["days_worked"]), e.weekly_off, e.shift_in,
                                         e.shift_out, e.date_of_joining, e.date_of_leaving, var, f"{cid}-{e.id}", hol)
        except ValueError as ex:
            problems.append(f"{e.emp_code} {e.name}: {ex}")
    if problems:
        return problems
    start, end = month_bounds(y, m)
    ids = [e.id for e in emps]
    if ids:
        db.execute(delete(Attendance).where(Attendance.company_id == cid, Attendance.employee_id.in_(ids),
                                            Attendance.att_date >= start, Attendance.att_date <= end))
    for e in emps:
        for r in built[e.id]:
            db.add(Attendance(company_id=cid, employee_id=e.id, att_date=date.fromisoformat(r["date"]),
                              status=r["status"], in_time=r["in_time"], out_time=r["out_time"], is_generated=True))
    db.flush()
    services.audit(db, user, "GENERATE_ATTENDANCE", "attendance", None, {"year": y, "month": m, "employees": len(emps)},
                   None, cid)
    return []


def attendance_map(db, cid, y, m):
    """{employee_id: [dict rows with ISO att_date]} for the company and month."""
    start, end = month_bounds(y, m)
    out = {}
    for a in db.scalars(select(Attendance).where(Attendance.company_id == cid, Attendance.att_date >= start,
                                                 Attendance.att_date <= end).order_by(Attendance.employee_id,
                                                                                       Attendance.att_date)):
        out.setdefault(a.employee_id, []).append({
            "att_date": a.att_date.isoformat(), "status": a.status, "in_time": a.in_time, "out_time": a.out_time,
            "is_generated": a.is_generated})
    return out


def update_day(db, user, cid, emp_id, att_date_iso, status, in_time, out_time):
    need_edit(db, user)
    try:
        d = date.fromisoformat(att_date_iso)
    except ValueError:
        raise Invalid(["Invalid date"])
    _need_unlocked(db, cid, d.year, d.month)
    if status not in ae.STATUS_LABELS:
        raise Invalid(["Invalid status"])
    in_time, out_time = (in_time or "").strip() or None, (out_time or "").strip() or None
    for t in (in_time, out_time):
        if t and not valid_time(t):
            raise Invalid(["Times must be HH:MM (24-hour)"])
    if status in ("A", "WO", "NE", "PL", "PH"):
        in_time = out_time = None
    elif not (in_time and out_time):
        raise Invalid(["Present / half-day rows need both in-time and out-time"])
    a = db.scalar(select(Attendance).where(Attendance.company_id == cid, Attendance.employee_id == emp_id,
                                           Attendance.att_date == d))
    if not a:
        raise Invalid(["Attendance row not found - generate attendance first"])
    a.status, a.in_time, a.out_time, a.is_generated = status, in_time, out_time, False
    services.audit(db, user, "EDIT_ATTENDANCE", "attendance", emp_id, {"date": att_date_iso, "status": status},
                   None, cid)


# ------------------------------------------------------------------ salary
def get_run(db, cid, y, m):
    return db.scalar(select(SalaryRun).where(SalaryRun.company_id == cid, SalaryRun.year == y, SalaryRun.month == m))


def get_lines(db, cid, y, m):
    run = get_run(db, cid, y, m)
    if not run:
        return []
    return [row(l) for l in db.scalars(select(SalaryLine).where(SalaryLine.run_id == run.id,
                                                                SalaryLine.company_id == cid)
                                       .order_by(SalaryLine.emp_code))]


LINE_COLS = pe.LINE_COLS


def calculate_salary(db, user, cid, y, m):
    need_salary(db, user, write=True)
    run = get_run(db, cid, y, m)
    if run and run.status == "FINAL":
        raise Invalid(["This month is finalised. Unlock it to recalculate."])
    emps = eligible(db, cid, y, m)
    if not emps:
        raise Invalid(["No employees on the rolls for this month."])
    att = attendance_map(db, cid, y, m)
    dim = monthrange(y, m)[1]
    missing = [f"{e.emp_code} {e.name}" for e in emps if len(att.get(e.id, [])) != dim]
    if missing:
        raise Invalid(["Generate the attendance register first. Missing for: " + ", ".join(missing[:10])
                       + (" ..." if len(missing) > 10 else "")])
    company = db.get(Company, cid)
    st = pe.settings_for(row(company))
    inputs = {i["employee_id"]: i for i in get_inputs(db, cid, y, m)}
    if run:
        run.calculated_at, run.calculated_by = now(), user.id
        db.execute(delete(SalaryLine).where(SalaryLine.run_id == run.id))
    else:
        run = SalaryRun(company_id=cid, year=y, month=m, calculated_at=now(), calculated_by=user.id)
        db.add(run)
    db.flush()
    for e in emps:
        ed = row(e)
        line = pe.compute_line(ed, ae.summarise(att[e.id]), inputs[e.id], st, y, m)
        db.add(SalaryLine(run_id=run.id, company_id=cid, employee_id=e.id, emp_code=e.emp_code, emp_name=e.name,
                          designation=e.designation, department=e.department, uan=e.uan, esic_no=e.esic_no,
                          salary_type=e.salary_type, **{c: line[c] for c in LINE_COLS}))
    db.flush()
    services.audit(db, user, "CALCULATE_SALARY", "salary_runs", run.id, {"year": y, "month": m, "employees": len(emps)},
                   None, cid)
    return run


def finalise(db, user, cid, y, m):
    need_salary(db, user, write=True)
    run = get_run(db, cid, y, m)
    if not run:
        raise Invalid(["Calculate the salary first."])
    run.status, run.finalised_at = "FINAL", now()
    services.audit(db, user, "FINALISE_SALARY", "salary_runs", run.id, {"year": y, "month": m}, None, cid)


def unlock(db, user, cid, y, m):
    need_salary(db, user, write=True)
    run = get_run(db, cid, y, m)
    if not run:
        raise Invalid(["No salary run for this month."])
    run.status, run.finalised_at = "DRAFT", None
    services.audit(db, user, "UNLOCK_SALARY", "salary_runs", run.id, {"year": y, "month": m}, None, cid)


# ------------------------------------------------------------------ holidays
def holiday_dates(db, cid, y, m):
    start, end = month_bounds(y, m)
    return set(db.scalars(select(Holiday.holiday_date).where(
        Holiday.company_id == cid, Holiday.holiday_date >= start, Holiday.holiday_date <= end)))


def list_holidays(db, cid, year):
    return list(db.scalars(select(Holiday).where(
        Holiday.company_id == cid, Holiday.holiday_date >= date(year, 1, 1), Holiday.holiday_date <= date(year, 12, 31))
        .order_by(Holiday.holiday_date)))


def add_holiday(db, user, cid, date_iso, name, ip=None):
    need_edit(db, user)
    try:
        d = date.fromisoformat((date_iso or "").strip())
    except ValueError:
        raise Invalid(["Enter a valid holiday date"])
    name = (name or "").strip()
    if not name:
        raise Invalid(["Enter the holiday name"])
    if db.scalar(select(Holiday.id).where(Holiday.company_id == cid, Holiday.holiday_date == d)):
        raise Invalid(["That date is already a holiday"])
    h = Holiday(company_id=cid, holiday_date=d, name=name[:120])
    db.add(h)
    db.flush()
    services.audit(db, user, "CREATE", "holidays", h.id, {"date": d.isoformat(), "name": name}, ip, cid)


def delete_holiday(db, user, cid, hid, ip=None):
    need_edit(db, user)
    h = db.get(Holiday, hid)
    if not h or h.company_id != cid:
        raise Invalid(["Holiday not found"])
    services.audit(db, user, "DELETE", "holidays", hid, {"date": h.holiday_date.isoformat()}, ip, cid)
    db.delete(h)


# ------------------------------------------------------------------ dashboard
def dashboard(db, cid, today=None):
    today = today or date.today()
    co = db.get(Company, cid)
    Acc, Dang = REGISTER_MODELS["accidents"], REGISTER_MODELS["dangerous"]
    count = lambda stmt: db.scalar(stmt) or 0
    py, pm = (today.year, today.month - 1) if today.month > 1 else (today.year - 1, 12)
    run = get_run(db, cid, py, pm)
    d_lic = days_left(co.licence_valid_to, today)
    return {
        "employees": count(select(func.count()).select_from(Employee).where(Employee.company_id == cid,
                                                                             Employee.is_active.is_(True))),
        "pending_notices": count(select(func.count()).select_from(Acc).where(
            Acc.company_id == cid, Acc.severity != ACCIDENT_SEVERITY[0], Acc.notice_date.is_(None))),
        "open_dangerous": count(select(func.count()).select_from(Dang).where(Dang.company_id == cid,
                                                                              Dang.status != "Closed")),
        "accidents_year": count(select(func.count()).select_from(Acc).where(
            Acc.company_id == cid, Acc.accident_date >= today - timedelta(days=365))),
        "licence_days": d_lic, "licence_level": expiry_level(d_lic), "licence_to": co.licence_valid_to,
        "prev_year": py, "prev_month": pm,
        "prev_salary": ("not calculated" if not run else "finalised" if run.status == "FINAL" else "draft"),
    }


# ------------------------------------------------------------------ earned leave
def leave_summary(db, cid, year):
    co = db.get(Company, cid)
    n = co.leave_accrual_days or 20
    start, end = date(year, 1, 1), date(year, 12, 31)
    counts = {}
    for emp_id, st, c in db.execute(select(Attendance.employee_id, Attendance.status, func.count()).where(
            Attendance.company_id == cid, Attendance.att_date >= start, Attendance.att_date <= end)
            .group_by(Attendance.employee_id, Attendance.status)).all():
        counts.setdefault(emp_id, {})[st] = c
    openings = {o.employee_id: o.opening for o in db.scalars(select(LeaveOpening).where(
        LeaveOpening.company_id == cid, LeaveOpening.year == year))}
    emps = db.scalars(select(Employee).where(
        Employee.company_id == cid, Employee.date_of_joining <= end,
        or_(Employee.date_of_leaving >= start, (Employee.date_of_leaving.is_(None)) & (Employee.is_active.is_(True))))
        .order_by(Employee.emp_code))
    return [dict(employee_id=e.id, emp_code=e.emp_code, name=e.name, opening=float(openings.get(e.id) or 0),
                 **leave_row(openings.get(e.id), counts.get(e.id, {}), n)) for e in emps], n


def save_leave_openings(db, user, cid, year, raw):
    """raw: {employee_id: text}"""
    need_edit(db, user)
    ids = {e.id: e for e in db.scalars(select(Employee).where(Employee.company_id == cid))}
    have = {o.employee_id: o for o in db.scalars(select(LeaveOpening).where(
        LeaveOpening.company_id == cid, LeaveOpening.year == year))}
    errors = []
    for eid, txt in raw.items():
        e = ids.get(eid)
        if not e:
            continue
        try:
            v = Decimal(str(txt or "0").replace(",", ""))
        except InvalidOperation:
            errors.append(f"{e.name}: opening balance must be a number")
            continue
        if v < 0 or v > 365 or (v * 2) != int(v * 2):
            errors.append(f"{e.name}: opening balance must be between 0 and 365 in steps of 0.5")
            continue
        o = have.get(eid) or LeaveOpening(company_id=cid, employee_id=eid, year=year)
        o.opening = v
        db.add(o)
    if errors:
        raise Invalid(errors)
    db.flush()
    services.audit(db, user, "SAVE_LEAVE_OPENING", "leave_openings", None, {"year": year}, None, cid)

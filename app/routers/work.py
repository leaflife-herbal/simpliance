"""Day-to-day pages: employees, monthly processing, attendance, salary and downloads."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse, Response

from .. import hr, reports, services
from ..core import attendance_engine as ae
from ..core.specs import EMPLOYEE_FIELDS
from ..core.util import MONTHS
from ..deps import Ctx, client_ip, csrf_protect, flash, form_values, render, work_ctx

router = APIRouter()
C = Depends(work_ctx)
CSRF = Depends(csrf_protect)
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def ym(year, month):
    t = date.today()
    y = year if year and 2000 <= year <= 2100 else t.year
    m = month if month and 1 <= month <= 12 else t.month
    return y, m


def download(data: bytes, name: str, kind: str):
    if kind == "pdf":
        return Response(data, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{name}.pdf"'})
    return Response(data, media_type=XLSX, headers={"Content-Disposition": f'attachment; filename="{name}.xlsx"'})


def _co(c: Ctx):
    return hr.row(c.company)


# ------------------------------------------------------------------ employees
@router.get("/employees")
def employees(request: Request, q: str = "", former: int = 0, c: Ctx = C):
    rows = hr.list_employees(c.db, c.cid, active_only=not former, q=q.strip())
    return render(request, "employees.html", c.user, c=c, rows=rows, q=q, former=former)


@router.get("/employees/export.{kind}")
def employees_export(kind: str, c: Ctx = C):
    if kind not in ("pdf", "xlsx"):
        raise HTTPException(404)
    rep = reports.employee_report([hr.row(e) for e in hr.list_employees(c.db, c.cid, active_only=False)])
    data = reports.report_pdf(_co(c), rep) if kind == "pdf" else reports.report_xlsx(_co(c), rep)
    return download(data, "Employee_Master", kind)


def _emp_form(request, c, emp=None, raw=None, errors=None, warnings=None):
    return render(request, "employee_form.html", c.user, c=c, emp=emp, fields=EMPLOYEE_FIELDS,
                  values=raw if raw is not None else form_values(emp, EMPLOYEE_FIELDS), errors=errors or [],
                  warnings=warnings or [])


@router.get("/employees/new")
def employee_new(request: Request, c: Ctx = C):
    return _emp_form(request, c)


@router.get("/employees/{emp_id:int}")
def employee_edit(emp_id: int, request: Request, c: Ctx = C):
    e = hr.get_employee(c.db, c.cid, emp_id)
    if not e:
        raise HTTPException(404, "Employee not found")
    return _emp_form(request, c, e)


async def _emp_save(request, c, emp_id):
    raw = dict(await request.form())
    try:
        e = hr.save_employee(c.db, c.user, c.cid, raw, emp_id, client_ip(request), bool(raw.get("ignore_warnings")))
    except services.Invalid as ex:
        return _emp_form(request, c, c.db.get(hr.Employee, emp_id) if emp_id else None, raw, ex.errors)
    except hr.Warn as w:
        return _emp_form(request, c, c.db.get(hr.Employee, emp_id) if emp_id else None, raw, None, w.warnings)
    flash(request, f"Employee {e.emp_code} saved.")
    return RedirectResponse("/employees", 303)


@router.post("/employees/new", dependencies=[CSRF])
async def employee_create(request: Request, c: Ctx = C):
    return await _emp_save(request, c, None)


@router.post("/employees/{emp_id:int}", dependencies=[CSRF])
async def employee_update(emp_id: int, request: Request, c: Ctx = C):
    return await _emp_save(request, c, emp_id)


# ------------------------------------------------------------------ monthly processing
def _monthly_page(request, c, y, m, overlay=None, errors=None):
    items = hr.get_inputs(c.db, c.cid, y, m)
    if overlay:
        for it in items:
            o = overlay.get(it["employee_id"])
            if o:
                it.update(days_worked=o["days_worked"], ot_hours=o["ot_hours"], advance=o["advance"],
                          other_deduction=o["other_deduction"], remarks=o["remarks"])
    att = hr.attendance_map(c.db, c.cid, y, m)
    run = hr.get_run(c.db, c.cid, y, m) if c.user.can_view_salary else None
    return render(request, "monthly.html", c.user, c=c, y=y, m=m, items=items, errors=errors or [],
                  have_att=bool(att), run=run, final=hr.is_final(c.db, c.cid, y, m))


@router.get("/monthly")
def monthly(request: Request, year: int = 0, month: int = 0, c: Ctx = C):
    y, m = ym(year, month)
    return _monthly_page(request, c, y, m)


@router.post("/monthly", dependencies=[CSRF])
async def monthly_post(request: Request, c: Ctx = C):
    form = await request.form()
    y, m = ym(int(form.get("year") or 0), int(form.get("month") or 0))
    items = []
    for sid in form.getlist("emp_id"):
        i = int(sid)
        items.append({"employee_id": i, "days_worked": form.get(f"days_{i}"), "ot_hours": form.get(f"ot_{i}"),
                      "advance": form.get(f"adv_{i}"), "other_deduction": form.get(f"od_{i}"),
                      "remarks": form.get(f"rem_{i}")})
    action = form.get("action", "save")
    try:
        hr.save_inputs(c.db, c.user, c.cid, y, m, items)
        if action == "generate":
            problems = hr.generate_attendance(c.db, c.user, c.cid, y, m)
            if problems:
                return _monthly_page(request, c, y, m, errors=["Attendance could not be generated:"] + problems)
            flash(request, "Attendance register generated. Review it under Attendance; correct any day if needed.")
            return RedirectResponse(f"/attendance?year={y}&month={m}", 303)
        if action == "calculate":
            hr.calculate_salary(c.db, c.user, c.cid, y, m)
            flash(request, "Salary calculated. Review it below, print slips, then finalise.")
            return RedirectResponse(f"/salary?year={y}&month={m}", 303)
    except services.Invalid as ex:
        return _monthly_page(request, c, y, m, {i["employee_id"]: i for i in items}, ex.errors)
    flash(request, "Days worked saved.")
    return RedirectResponse(f"/monthly?year={y}&month={m}", 303)


# ------------------------------------------------------------------ attendance
@router.get("/attendance")
def attendance(request: Request, year: int = 0, month: int = 0, emp: int = 0, c: Ctx = C):
    y, m = ym(year, month)
    emps = hr.eligible(c.db, c.cid, y, m)
    sel = next((e for e in emps if e.id == emp), emps[0] if emps else None)
    att = hr.attendance_map(c.db, c.cid, y, m)
    rows = att.get(sel.id, []) if sel else []
    for r in rows:
        r["day"] = date.fromisoformat(r["att_date"]).strftime("%a")
        r["hours"] = round(ae.day_hours(r), 2)
    return render(request, "attendance.html", c.user, c=c, y=y, m=m, emps=emps, sel=sel, rows=rows,
                  summary=ae.summarise(rows) if rows else None, STATUS=ae.STATUS_LABELS)


@router.post("/attendance/edit", dependencies=[CSRF])
async def attendance_edit(request: Request, c: Ctx = C):
    f = await request.form()
    y, m, emp = int(f["year"]), int(f["month"]), int(f["emp"])
    try:
        hr.update_day(c.db, c.user, c.cid, emp, f["att_date"], f.get("status", ""), f.get("in_time"), f.get("out_time"))
    except services.Invalid as ex:
        flash(request, "; ".join(ex.errors), "err")
    return RedirectResponse(f"/attendance?year={y}&month={m}&emp={emp}", 303)


@router.get("/attendance/file/{kind}")
def attendance_file(kind: str, year: int = 0, month: int = 0, emp: int = 0, c: Ctx = C):
    y, m = ym(year, month)
    emps = [hr.row(e) for e in hr.eligible(c.db, c.cid, y, m)]
    att = hr.attendance_map(c.db, c.cid, y, m)
    muster = reports.muster_report(emps, att, y, m)
    blocks = reports.attendance_blocks(emps, att, emp or None)
    name = f"Attendance_{MONTHS[m - 1]}_{y}"
    if kind in ("register.pdf", "register.xlsx") and not blocks:
        raise HTTPException(404, "Generate the attendance register first.")
    if kind == "register.pdf":
        return download(reports.attendance_pdf(_co_of(c), y, m, blocks), name, "pdf")
    if kind == "register.xlsx":
        return download(reports.attendance_xlsx(_co_of(c), y, m, blocks, muster), name, "xlsx")
    if kind == "muster.pdf":
        return download(reports.report_pdf(_co_of(c), muster), "Muster_" + name, "pdf")
    if kind == "muster.xlsx":
        return download(reports.report_xlsx(_co_of(c), muster), "Muster_" + name, "xlsx")
    raise HTTPException(404)


def _co_of(c):
    return hr.row(c.company)


# ------------------------------------------------------------------ salary
@router.get("/salary")
def salary(request: Request, year: int = 0, month: int = 0, c: Ctx = C):
    hr.need_salary(c.db, c.user)
    y, m = ym(year, month)
    return render(request, "salary.html", c.user, c=c, y=y, m=m, lines=hr.get_lines(c.db, c.cid, y, m),
                  run=hr.get_run(c.db, c.cid, y, m))


@router.post("/salary/{action}", dependencies=[CSRF])
async def salary_action(action: str, request: Request, c: Ctx = C):
    f = await request.form()
    y, m = ym(int(f.get("year") or 0), int(f.get("month") or 0))
    fn = {"calculate": hr.calculate_salary, "finalise": hr.finalise, "unlock": hr.unlock}.get(action)
    if not fn:
        raise HTTPException(404)
    try:
        fn(c.db, c.user, c.cid, y, m)
        flash(request, {"calculate": "Salary recalculated.", "finalise": "Month finalised and locked.",
                        "unlock": "Month unlocked."}[action])
    except services.Invalid as ex:
        flash(request, "; ".join(ex.errors), "err")
    return RedirectResponse(f"/salary?year={y}&month={m}", 303)


@router.get("/salary/file/{kind}")
def salary_file(kind: str, year: int = 0, month: int = 0, emp: int = 0, c: Ctx = C):
    hr.need_salary(c.db, c.user)
    y, m = ym(year, month)
    lines = hr.get_lines(c.db, c.cid, y, m)
    if not lines:
        raise HTTPException(404, "Calculate the salary first.")
    co = _co_of(c)
    name = f"{MONTHS[m - 1]}_{y}"
    if kind in ("slips.pdf", "slips.xlsx"):
        chosen = [l for l in lines if not emp or l["employee_id"] == emp]
        if not chosen:
            raise HTTPException(404)
        if kind == "slips.pdf":
            return download(reports.slips_pdf(co, y, m, chosen), "Salary_Slips_" + name, "pdf")
        return download(reports.slips_xlsx(co, y, m, chosen), "Salary_Slips_" + name, "xlsx")
    rep = reports.salary_register(lines, y, m)
    if kind == "register.pdf":
        return download(reports.report_pdf(co, rep), "Salary_Register_" + name, "pdf")
    if kind == "register.xlsx":
        return download(reports.report_xlsx(co, rep), "Salary_Register_" + name, "xlsx")
    raise HTTPException(404)

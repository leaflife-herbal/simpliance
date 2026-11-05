"""Bilingual printable documents (notice of work periods, pay slips) and the holidays list."""
from datetime import date

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse

from .. import hr, reports, services
from ..core import i18n
from ..core.notice import group_shifts
from ..core.util import amount_in_words
from ..deps import Ctx, client_ip, csrf_protect, flash, render, work_ctx
from .work import download, ym

router = APIRouter()
C = Depends(work_ctx)
CSRF = Depends(csrf_protect)


@router.get("/print/notice")
def print_notice(request: Request, lang: str = "", rest: str = "", on: str = "", c: Ctx = C):
    emps = [hr.row(e) for e in hr.list_employees(c.db, c.cid, active_only=True)]
    code = i18n.lang_code(c.company.doc_language, lang or None)
    return render(request, "print_notice.html", c.user, c=c, co=c.company, groups=group_shifts(emps), lang=code,
                  rest=rest.strip(), on=on or date.today().isoformat(), path="/print/notice")


@router.get("/print/slips")
def print_slips(request: Request, year: int = 0, month: int = 0, emp: int = 0, lang: str = "", c: Ctx = C):
    hr.need_salary(c.db, c.user)
    y, m = ym(year, month)
    lines = [l for l in hr.get_lines(c.db, c.cid, y, m) if not emp or l["employee_id"] == emp]
    if not lines:
        raise HTTPException(404, "Calculate the salary first.")
    local = {e.id: e.name_local for e in hr.list_employees(c.db, c.cid, active_only=False)}
    for l in lines:
        l["name_local"] = local.get(l["employee_id"])
        l["words"] = amount_in_words(l["net_pay"])
    return render(request, "print_slips.html", c.user, c=c, co=c.company, lines=lines, y=y, m=m,
                  lang=i18n.lang_code(c.company.doc_language, lang or None), emp=emp, path="/print/slips")


@router.get("/holidays")
def holidays(request: Request, year: int = 0, c: Ctx = C):
    y = year if 2000 <= year <= 2100 else date.today().year
    return render(request, "holidays.html", c.user, c=c, y=y, rows=hr.list_holidays(c.db, c.cid, y))


@router.post("/holidays/add", dependencies=[CSRF])
def holiday_add(request: Request, holiday_date: str = Form(""), name: str = Form(""), c: Ctx = C):
    try:
        hr.add_holiday(c.db, c.user, c.cid, holiday_date, name, client_ip(request))
        flash(request, "Holiday added. Regenerate the month's attendance for it to take effect.")
    except services.Invalid as ex:
        flash(request, "; ".join(ex.errors), "err")
    y = holiday_date[:4] if holiday_date[:4].isdigit() else date.today().year
    return RedirectResponse(f"/holidays?year={y}", 303)


@router.post("/holidays/{hid:int}/delete", dependencies=[CSRF])
def holiday_delete(hid: int, request: Request, year: int = Form(0), c: Ctx = C):
    try:
        hr.delete_holiday(c.db, c.user, c.cid, hid, client_ip(request))
    except services.Invalid as ex:
        flash(request, "; ".join(ex.errors), "err")
    return RedirectResponse(f"/holidays?year={year or date.today().year}", 303)


@router.get("/leave")
def leave(request: Request, year: int = 0, c: Ctx = C):
    y = year if 2000 <= year <= 2100 else date.today().year
    rows, n = hr.leave_summary(c.db, c.cid, y)
    return render(request, "leave.html", c.user, c=c, y=y, rows=rows, n=n)


@router.post("/leave", dependencies=[CSRF])
async def leave_save(request: Request, c: Ctx = C):
    f = await request.form()
    y = int(f.get("year") or date.today().year)
    raw = {int(k[5:]): v for k, v in f.items() if k.startswith("open_") and k[5:].isdigit()}
    try:
        hr.save_leave_openings(c.db, c.user, c.cid, y, raw)
        flash(request, "Opening balances saved.")
    except services.Invalid as ex:
        flash(request, "; ".join(ex.errors), "err")
    return RedirectResponse(f"/leave?year={y}", 303)


@router.get("/leave/file/{kind}")
def leave_file(kind: str, year: int = 0, c: Ctx = C):
    y = year if 2000 <= year <= 2100 else date.today().year
    rows, n = hr.leave_summary(c.db, c.cid, y)
    rep = reports.leave_report(rows, y, n)
    co = hr.row(c.company)
    if kind == "pdf":
        return download(reports.report_pdf(co, rep), f"Leave_{y}", "pdf")
    if kind == "xlsx":
        return download(reports.report_xlsx(co, rep), f"Leave_{y}", "xlsx")
    raise HTTPException(404)

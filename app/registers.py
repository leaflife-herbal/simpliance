from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse

from .. import hr, registers, reports, services
from ..core.specs import REGISTERS, REGISTER_BY_KEY
from ..deps import Ctx, client_ip, csrf_protect, flash, form_values, render, work_ctx
from .work import download

router = APIRouter(prefix="/registers")
C = Depends(work_ctx)
CSRF = Depends(csrf_protect)


def _spec(key):
    spec = REGISTER_BY_KEY.get(key)
    if not spec:
        raise HTTPException(404, "Unknown register")
    return spec


def _d(s):
    try:
        return date.fromisoformat(s) if s else None
    except ValueError:
        return None


@router.get("")
def index(request: Request, c: Ctx = C):
    return render(request, "registers.html", c.user, c=c, specs=REGISTERS)


@router.get("/{key}")
def listing(key: str, request: Request, date_from: str = Query("", alias="from"), date_to: str = Query("", alias="to"),
            c: Ctx = C):
    spec = _spec(key)
    rows = registers.list_rows(c.db, c.cid, spec, _d(date_from), _d(date_to))
    rep = reports.register_report(spec, [hr.row(r) for r in rows], date_from, date_to)
    return render(request, "register_list.html", c.user, c=c, spec=spec, headers=rep.headers,
                  table=list(zip([r.id for r in rows], reports.display_rows(rep))), date_from=date_from, date_to=date_to)


@router.get("/{key}/file/{kind}")
def file(key: str, kind: str, date_from: str = Query("", alias="from"), date_to: str = Query("", alias="to"),
         id: int = 0, c: Ctx = C):
    spec = _spec(key)
    co = hr.row(c.company)
    if kind == "entry.pdf":
        o = registers.get_row(c.db, c.cid, spec, id)
        if not o:
            raise HTTPException(404)
        return download(reports.report_pdf(co, reports.register_detail(spec, hr.row(o))), f"{spec.key}_entry_{id}", "pdf")
    rows = registers.list_rows(c.db, c.cid, spec, _d(date_from), _d(date_to))
    rep = reports.register_report(spec, [hr.row(r) for r in reversed(rows)], date_from, date_to)   # oldest first on paper
    if kind == "list.pdf":
        return download(reports.report_pdf(co, rep), spec.key, "pdf")
    if kind == "list.xlsx":
        return download(reports.report_xlsx(co, rep), spec.key, "xlsx")
    raise HTTPException(404)


def _form(request, c, spec, obj=None, raw=None, errors=None, warnings=None):
    if raw is None:
        raw = form_values(obj, spec.fields)
        if obj is None:
            raw[registers.date_key(spec)] = date.today().isoformat()
    return render(request, "register_form.html", c.user, c=c, spec=spec, obj=obj, fields=spec.fields, values=raw,
                  emps=hr.list_employees(c.db, c.cid, active_only=False), errors=errors or [], warnings=warnings or [])


@router.get("/{key}/new")
def new(key: str, request: Request, c: Ctx = C):
    hr.need_edit(c.db, c.user)
    return _form(request, c, _spec(key))


@router.get("/{key}/{row_id:int}")
def edit(key: str, row_id: int, request: Request, c: Ctx = C):
    spec = _spec(key)
    o = registers.get_row(c.db, c.cid, spec, row_id)
    if not o:
        raise HTTPException(404, "Entry not found")
    return _form(request, c, spec, o)


async def _save(request, c, spec, row_id):
    raw = dict(await request.form())
    obj = registers.get_row(c.db, c.cid, spec, row_id) if row_id else None
    try:
        registers.save(c.db, c.user, c.cid, spec, raw, row_id, client_ip(request), bool(raw.get("ignore_warnings")))
    except services.Invalid as ex:
        return _form(request, c, spec, obj, raw, ex.errors)
    except hr.Warn as w:
        return _form(request, c, spec, obj, raw, None, w.warnings)
    flash(request, "Entry saved.")
    return RedirectResponse(f"/registers/{spec.key}", 303)


@router.post("/{key}/new", dependencies=[CSRF])
async def create(key: str, request: Request, c: Ctx = C):
    return await _save(request, c, _spec(key), None)


@router.post("/{key}/{row_id:int}", dependencies=[CSRF])
async def update(key: str, row_id: int, request: Request, c: Ctx = C):
    return await _save(request, c, _spec(key), row_id)


@router.post("/{key}/{row_id:int}/delete", dependencies=[CSRF])
def remove(key: str, row_id: int, request: Request, c: Ctx = C):
    spec = _spec(key)
    try:
        registers.delete(c.db, c.user, c.cid, spec, row_id, client_ip(request))
        flash(request, "Entry deleted (recorded in the audit log).")
    except services.Invalid as ex:
        flash(request, "; ".join(ex.errors), "err")
    return RedirectResponse(f"/registers/{spec.key}", 303)

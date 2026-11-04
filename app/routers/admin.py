"""Super Admin area: organisations (licence limits), companies, users, audit log."""
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import services
from ..core.specs import COMPANY_FIELDS
from ..db import get_db
from ..deps import client_ip, csrf_protect, flash, form_values, render, super_user
from ..models import AuditLog, Company, Organisation, ROLE_OPERATOR, ROLE_VIEWER, User, UserCompany

router = APIRouter(prefix="/admin")
SU = Depends(super_user)
CSRF = Depends(csrf_protect)


def _orgs(db):
    return list(db.scalars(select(Organisation).order_by(Organisation.name)))


# ------------------------------------------------------------ organisations
@router.get("/organisations")
def orgs(request: Request, user=SU, db: Session = Depends(get_db), edit: int = 0):
    return render(request, "admin/orgs.html", user, orgs=_orgs(db), edit=db.get(Organisation, edit) if edit else None)


@router.post("/organisations", dependencies=[CSRF])
def orgs_save(request: Request, org_id: int = Form(0), name: str = Form(""), max_companies: str = Form("1"),
              max_users: str = Form("5"), valid_until: str = Form(""), is_active: str = Form(""),
              user=SU, db: Session = Depends(get_db)):
    try:
        services.save_organisation(db, user, name, max_companies, max_users, valid_until, bool(is_active),
                                   org_id or None, client_ip(request))
    except services.Invalid as e:
        return render(request, "admin/orgs.html", user, orgs=_orgs(db), errors=e.errors, edit=None)
    flash(request, "Organisation saved.")
    return RedirectResponse("/admin/organisations", 303)


# ------------------------------------------------------------ companies
@router.get("/companies")
def companies(request: Request, user=SU, db: Session = Depends(get_db)):
    rows = list(db.scalars(select(Company).order_by(Company.name)))
    return render(request, "admin/companies.html", user, rows=rows, orgs={o.id: o.name for o in _orgs(db)})


def _company_form(request, user, db, company=None, org_id=None, values=None, errors=None):
    return render(request, "admin/company_form.html", user, fields=COMPANY_FIELDS, company=company,
                  orgs=_orgs(db), org_id=org_id or (company.organisation_id if company else None),
                  values=values or form_values(company, COMPANY_FIELDS), errors=errors or [])


@router.get("/companies/new")
def company_new(request: Request, org_id: int = 0, user=SU, db: Session = Depends(get_db)):
    return _company_form(request, user, db, org_id=org_id or None)


@router.get("/companies/{cid}")
def company_edit(cid: int, request: Request, user=SU, db: Session = Depends(get_db)):
    c = db.get(Company, cid)
    if not c:
        raise HTTPException(404)
    return _company_form(request, user, db, c)


async def _save_company(request, user, db, cid):
    form = await request.form()
    raw = dict(form)
    org_id = int(raw.get("organisation_id") or 0)
    try:
        c = services.save_company(db, user, org_id, raw, cid, client_ip(request))
    except services.Invalid as e:
        return _company_form(request, user, db, db.get(Company, cid) if cid else None, org_id, raw, e.errors)
    flash(request, f"Company '{c.name}' saved.")
    return RedirectResponse("/admin/companies", 303)


@router.post("/companies/new", dependencies=[CSRF])
async def company_create(request: Request, user=SU, db: Session = Depends(get_db)):
    return await _save_company(request, user, db, None)


@router.post("/companies/{cid}", dependencies=[CSRF])
async def company_update(cid: int, request: Request, user=SU, db: Session = Depends(get_db)):
    return await _save_company(request, user, db, cid)


@router.post("/companies/{cid}/toggle", dependencies=[CSRF])
def company_toggle(cid: int, request: Request, user=SU, db: Session = Depends(get_db)):
    c = db.get(Company, cid)
    if not c:
        raise HTTPException(404)
    try:
        services.set_company_active(db, user, cid, not c.is_active, client_ip(request))
        flash(request, "Company activated." if c.is_active else "Company deactivated.")
    except services.Invalid as e:
        flash(request, e.errors[0], "err")
    return RedirectResponse("/admin/companies", 303)


# ------------------------------------------------------------ users
def _user_form(request, user, db, target=None, errors=None, values=None):
    org_id = (target.organisation_id if target else None) or int((values or {}).get("organisation_id") or 0) or None
    cos = list(db.scalars(select(Company).where(Company.organisation_id == org_id).order_by(Company.name))) if org_id else []
    selected = {uc.company_id for uc in db.scalars(select(UserCompany).where(UserCompany.user_id == target.id))} if target else set()
    return render(request, "admin/user_form.html", user, target=target, orgs=_orgs(db), org_id=org_id, cos=cos,
                  selected=selected, errors=errors or [], values=values or {},
                  roles=[(ROLE_OPERATOR, "Operator (data entry)"), (ROLE_VIEWER, "Viewer (read-only)")])


@router.get("/users")
def users(request: Request, user=SU, db: Session = Depends(get_db)):
    rows = list(db.scalars(select(User).order_by(User.role != "SUPER_ADMIN", User.username)))
    return render(request, "admin/users.html", user, rows=rows, orgs={o.id: o.name for o in _orgs(db)})


@router.get("/users/new")
def user_new(request: Request, org_id: int = 0, user=SU, db: Session = Depends(get_db)):
    return _user_form(request, user, db, values={"organisation_id": org_id})


@router.get("/users/{uid}")
def user_edit(uid: int, request: Request, user=SU, db: Session = Depends(get_db)):
    t = db.get(User, uid)
    if not t or t.is_super:
        raise HTTPException(404)
    return _user_form(request, user, db, t)


@router.post("/users/new", dependencies=[CSRF])
async def user_create(request: Request, user=SU, db: Session = Depends(get_db)):
    form = await request.form()
    raw = dict(form)
    cids = form.getlist("company_ids")
    try:
        services.create_user(db, user, int(raw.get("organisation_id") or 0), raw.get("username", "").strip(),
                             raw.get("full_name", ""), raw.get("password", ""), raw.get("role", ""),
                             bool(raw.get("can_salary")), cids, client_ip(request))
    except services.Invalid as e:
        return _user_form(request, user, db, errors=e.errors, values={k: v for k, v in raw.items() if k != "password"})
    flash(request, "User created. They must change the temporary password at first sign-in.")
    return RedirectResponse("/admin/users", 303)


@router.post("/users/{uid}", dependencies=[CSRF])
async def user_update(uid: int, request: Request, user=SU, db: Session = Depends(get_db)):
    form = await request.form()
    t = db.get(User, uid)
    try:
        services.update_user(db, user, uid, form.get("full_name", ""), form.get("role", ""), bool(form.get("can_salary")),
                             bool(form.get("is_active")), form.getlist("company_ids"), client_ip(request))
    except services.Invalid as e:
        return _user_form(request, user, db, t, e.errors)
    flash(request, "User updated.")
    return RedirectResponse("/admin/users", 303)


@router.post("/users/{uid}/reset", dependencies=[CSRF])
def user_reset(uid: int, request: Request, new_password: str = Form(""), user=SU, db: Session = Depends(get_db)):
    try:
        services.reset_password(db, user, uid, new_password, client_ip(request))
        flash(request, "Password reset. The user must change it at next sign-in; any lock is cleared.")
    except services.Invalid as e:
        flash(request, e.errors[0], "err")
    return RedirectResponse("/admin/users", 303)


# ------------------------------------------------------------ audit
@router.get("/audit")
def audit(request: Request, user=SU, db: Session = Depends(get_db)):
    rows = list(db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(500)))
    return render(request, "admin/audit.html", user, rows=rows)

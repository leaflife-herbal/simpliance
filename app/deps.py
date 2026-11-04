import secrets

from fastapi import Depends, HTTPException, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from . import hr, security, services, settings
from .db import get_db
from .models import ROLE_LABELS, User
from .core.util import MONTHS, fmt_date, inr, num

templates = Jinja2Templates(directory="app/templates")
templates.env.filters.update(dmy=fmt_date, inr=inr, num=num)
templates.env.globals.update(APP_NAME=settings.APP_NAME, ROLE_LABELS=ROLE_LABELS, MONTHS=MONTHS)


class LoginRequired(Exception):
    pass


class PasswordChangeRequired(Exception):
    pass


def client_ip(request: Request):
    return request.client.host if request.client else None


def user_any(request: Request, db: Session = Depends(get_db)) -> User:
    uid = request.session.get("uid")
    if not uid:
        raise LoginRequired()
    u = db.get(User, uid)
    if not u or not u.is_active or u.session_version != request.session.get("ver"):
        request.session.clear()
        raise LoginRequired()
    return u


def current_user(u: User = Depends(user_any)) -> User:
    if u.must_change_password:
        raise PasswordChangeRequired()
    return u


def super_user(u: User = Depends(current_user)) -> User:
    if not u.is_super:
        raise HTTPException(status_code=403, detail="Only the Super Admin can open this page.")
    return u


def csrf_token(request: Request) -> str:
    tok = request.session.get("csrf")
    if not tok:
        tok = request.session["csrf"] = security.new_csrf()
    return tok


async def csrf_protect(request: Request):
    form = await request.form()
    sent, want = form.get("csrf_token", ""), request.session.get("csrf", "")
    if not want or not secrets.compare_digest(str(sent), want):
        raise HTTPException(status_code=403, detail="Your session form expired. Go back, refresh and try again.")


def flash(request: Request, message: str, kind="ok"):
    request.session.setdefault("flash", []).append([kind, message])


def render(request: Request, name: str, user=None, **ctx):
    ctx.update(user=user, csrf=csrf_token(request), flash=request.session.pop("flash", []),
               company_id=request.session.get("company_id"))
    return templates.TemplateResponse(request, name, ctx)


def form_values(obj, fields):
    """Display values for a spec-driven form from an ORM object (dates as ISO for <input type=date>)."""
    out = {}
    for f in fields:
        v = getattr(obj, f.key, None) if obj is not None else f.default
        if v is None:
            out[f.key] = ""
        elif f.type == "date":
            out[f.key] = v.isoformat()
        elif f.type == "bool":
            out[f.key] = bool(v)
        else:
            out[f.key] = str(v).rstrip("0").rstrip(".") if f.type == "number" and "." in str(v) else str(v)
    return out


class NoCompany(Exception):
    pass


class Ctx:
    """The signed-in user plus the one company they are currently working in (verified against their assignments)."""

    def __init__(self, db, user, company):
        self.db, self.user, self.company, self.cid = db, user, company, company.id
        self.can_edit = hr.can_edit(db, user)


def work_ctx(request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)) -> Ctx:
    cid = request.session.get("company_id")
    company = next((c for c in services.companies_for(db, user) if c.id == cid), None)
    if not company:
        raise NoCompany()
    return Ctx(db, user, company)

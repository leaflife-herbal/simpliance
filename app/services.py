"""Business operations for organisations, companies and users. Every function takes the acting user and
checks permission itself, so the rules hold no matter which route (or future API) calls them."""
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import security, settings
from .core.forms import clean_values
from .core.payroll_engine import parse_pt_slabs
from .core.specs import COMPANY_FIELDS
from .models import (AuditLog, Company, Organisation, ROLE_OPERATOR, ROLE_SUPER, ROLE_VIEWER, User, UserCompany)


class Denied(Exception):
    pass


class Invalid(Exception):
    def __init__(self, errors):
        super().__init__("; ".join(errors))
        self.errors = list(errors)


def now():
    return datetime.now(timezone.utc)


def audit(db: Session, actor, action, entity=None, entity_id=None, detail=None, ip=None, company_id=None):
    db.add(AuditLog(user_id=getattr(actor, "id", None), username=getattr(actor, "username", "system"),
                    organisation_id=getattr(actor, "organisation_id", None), company_id=company_id,
                    action=action, entity=entity, entity_id=entity_id, detail=detail, ip=ip))


def require_super(actor):
    if not actor.is_super:
        raise Denied("Only the Super Admin can do this.")


# ------------------------------------------------------------------ authentication

def authenticate(db: Session, username: str, password: str, ip=None) -> User:
    u = db.scalar(select(User).where(func.lower(User.username) == username.strip().lower()))
    generic = Invalid(["Incorrect username or password."])
    if not u:
        security.hash_password("timing-equaliser")   # keep response time similar for unknown users
        raise generic
    if u.locked_until and u.locked_until > now():
        raise Invalid(["Account temporarily locked after too many failed attempts. Try again later or ask the Super Admin."])
    if not security.verify_password(password, u.password_hash):
        u.failed_attempts += 1
        if u.failed_attempts >= settings.MAX_FAILED_LOGINS:
            u.locked_until = now() + timedelta(minutes=settings.LOCKOUT_MINUTES)
            u.failed_attempts = 0
        audit(db, u, "LOGIN_FAILED", "users", u.id, ip=ip)
        db.commit()   # persist the counter even though the request will report an error
        raise generic
    if not u.is_active:
        raise Invalid(["This account is disabled. Contact the Super Admin."])
    if not u.is_super:
        org = db.get(Organisation, u.organisation_id)
        if not org or not org.is_active:
            raise Invalid(["Your organisation's subscription is inactive. Contact the Super Admin."])
    if security.needs_rehash(u.password_hash):
        u.password_hash = security.hash_password(password)
    u.failed_attempts, u.locked_until, u.last_login = 0, None, now()
    audit(db, u, "LOGIN", "users", u.id, ip=ip)
    return u


def read_only_reason(db: Session, user: User):
    """Expired organisation licence makes the account read-only."""
    if user.is_super or not user.organisation_id:
        return ""
    org = db.get(Organisation, user.organisation_id)
    if org and org.valid_until and org.valid_until < datetime.now().date():
        return f"Subscription expired on {org.valid_until:%d-%m-%Y} - read-only mode."
    return ""


def change_password(db, user: User, old, new, ip=None):
    if not security.verify_password(old, user.password_hash):
        raise Invalid(["Current password is incorrect."])
    p = security.password_problem(new)
    if p:
        raise Invalid([p])
    if old == new:
        raise Invalid(["New password must differ from the current one."])
    user.password_hash = security.hash_password(new)
    user.must_change_password = False
    user.session_version += 1
    audit(db, user, "CHANGE_PASSWORD", "users", user.id, ip=ip)


# ------------------------------------------------------------------ organisations

def save_organisation(db, actor, name, max_companies, max_users, valid_until, is_active=True, org_id=None, ip=None):
    require_super(actor)
    errors = []
    name = (name or "").strip()
    if not name:
        errors.append("Organisation name is required")
    try:
        mc, mu = int(max_companies), int(max_users)
        if mc < 1 or mu < 1:
            errors.append("Limits must be at least 1")
    except (TypeError, ValueError):
        errors.append("Limits must be whole numbers")
        mc = mu = 1
    vu = None
    if valid_until:
        try:
            vu = datetime.strptime(valid_until, "%Y-%m-%d").date()
        except ValueError:
            errors.append("Valid-until date is invalid")
    dup = db.scalar(select(Organisation).where(func.lower(Organisation.name) == name.lower(), Organisation.id != (org_id or 0)))
    if dup:
        errors.append("An organisation with this name already exists")
    if errors:
        raise Invalid(errors)
    org = db.get(Organisation, org_id) if org_id else Organisation()
    org.name, org.max_companies, org.max_users, org.valid_until, org.is_active = name, mc, mu, vu, bool(is_active)
    db.add(org)
    db.flush()
    audit(db, actor, "UPDATE" if org_id else "CREATE", "organisations", org.id, {"name": name}, ip)
    return org


# ------------------------------------------------------------------ companies

def save_company(db, actor, org_id, raw, company_id=None, ip=None):
    require_super(actor)
    org = db.get(Organisation, org_id)
    if not org:
        raise Invalid(["Choose an organisation"])
    clean, errors = clean_values(COMPANY_FIELDS, raw)
    if not errors:
        dup = db.scalar(select(Company).where(Company.organisation_id == org_id,
                                              func.lower(Company.short_code) == clean["short_code"].lower(),
                                              Company.id != (company_id or 0)))
        if dup:
            errors.append("Another company in this organisation already uses this short code")
        a, b = clean.get("licence_valid_from"), clean.get("licence_valid_to")
        if a and b and b < a:
            errors.append("Licence 'valid up to' is before 'valid from'")
        for k, lab in (("pf_wage_ceiling", "PF wage ceiling"), ("esi_threshold", "ESI threshold"),
                       ("hours_per_day", "Working hours per day")):
            if not clean.get(k) or clean[k] <= 0:
                errors.append(f"{lab} must be greater than zero")
        if clean.get("attendance_variation") is not None and clean["attendance_variation"] > 60:
            errors.append("Attendance time variation must be between 0 and 60 minutes")
        try:
            parse_pt_slabs(clean.get("pt_slabs"))
        except ValueError as e:
            errors.append(str(e))
    if company_id is None and not errors:
        n = db.scalar(select(func.count()).select_from(Company).where(Company.organisation_id == org_id,
                                                                      Company.is_active.is_(True)))
        if n >= org.max_companies:
            errors.append(f"Licence limit reached: {org.max_companies} company(ies) allowed for {org.name}")
    if errors:
        raise Invalid(errors)
    c = db.get(Company, company_id) if company_id else Company(organisation_id=org_id, created_by=actor.id)
    if company_id and c.organisation_id != org_id:
        raise Invalid(["A company cannot be moved to another organisation"])
    for k, v in clean.items():
        setattr(c, k, v)
    db.add(c)
    db.flush()
    audit(db, actor, "UPDATE" if company_id else "CREATE", "companies", c.id, {"name": c.name}, ip, c.id)
    return c


def set_company_active(db, actor, company_id, active, ip=None):
    require_super(actor)
    c = db.get(Company, company_id)
    if not c:
        raise Invalid(["Company not found"])
    if active:
        org = db.get(Organisation, c.organisation_id)
        n = db.scalar(select(func.count()).select_from(Company).where(Company.organisation_id == c.organisation_id,
                                                                      Company.is_active.is_(True)))
        if n >= org.max_companies:
            raise Invalid([f"Licence limit reached: {org.max_companies} company(ies) allowed"])
    c.is_active = bool(active)
    audit(db, actor, "ACTIVATE" if active else "DEACTIVATE", "companies", c.id, None, ip, c.id)


def companies_for(db, user: User):
    """Companies this user may work in (tenant boundary used by every business page)."""
    if user.is_super:
        q = select(Company).where(Company.is_active.is_(True))
    else:
        q = (select(Company).join(UserCompany, UserCompany.company_id == Company.id)
             .where(UserCompany.user_id == user.id, Company.is_active.is_(True)))
    return list(db.scalars(q.order_by(Company.name)))


# ------------------------------------------------------------------ users

def _check_username(u):
    if not re.fullmatch(r"[A-Za-z0-9._-]{3,30}", u or ""):
        raise Invalid(["Username must be 3-30 characters: letters, digits, . _ -"])


def _validate_company_ids(db, org_id, company_ids):
    ids = {int(i) for i in company_ids}
    if not ids:
        raise Invalid(["Assign at least one company"])
    found = set(db.scalars(select(Company.id).where(Company.id.in_(ids), Company.organisation_id == org_id)))
    if found != ids:
        raise Invalid(["Companies must belong to the user's organisation"])
    return ids


def create_user(db, actor, org_id, username, full_name, password, role, can_salary, company_ids, ip=None):
    require_super(actor)
    _check_username(username)
    errors = []
    if role not in (ROLE_OPERATOR, ROLE_VIEWER):
        errors.append("Role must be Operator or Viewer")
    if not (full_name or "").strip():
        errors.append("Full name is required")
    p = security.password_problem(password or "")
    if p:
        errors.append(p)
    org = db.get(Organisation, org_id)
    if not org or not org.is_active:
        errors.append("Choose an active organisation")
    if errors:
        raise Invalid(errors)
    ids = _validate_company_ids(db, org_id, company_ids)
    n = db.scalar(select(func.count()).select_from(User).where(User.organisation_id == org_id, User.is_active.is_(True)))
    if n >= org.max_users:
        raise Invalid([f"Licence limit reached: {org.max_users} user(s) allowed for {org.name}"])
    if db.scalar(select(User).where(func.lower(User.username) == username.lower())):
        raise Invalid(["That username already exists"])
    u = User(username=username, full_name=full_name.strip(), role=role, organisation_id=org_id,
             can_salary=bool(can_salary), password_hash=security.hash_password(password), must_change_password=True,
             created_by=actor.id)
    db.add(u)
    db.flush()
    for cid in ids:
        db.add(UserCompany(user_id=u.id, company_id=cid))
    audit(db, actor, "CREATE", "users", u.id, {"username": username, "role": role, "companies": sorted(ids)}, ip)
    return u


def update_user(db, actor, user_id, full_name, role, can_salary, is_active, company_ids, ip=None):
    require_super(actor)
    u = db.get(User, user_id)
    if not u or u.is_super:
        raise Invalid(["That account cannot be edited here"])
    if role not in (ROLE_OPERATOR, ROLE_VIEWER):
        raise Invalid(["Role must be Operator or Viewer"])
    ids = _validate_company_ids(db, u.organisation_id, company_ids)
    u.full_name, u.role, u.can_salary, u.is_active = full_name.strip(), role, bool(can_salary), bool(is_active)
    u.session_version += 1   # access changes apply immediately
    for uc in db.scalars(select(UserCompany).where(UserCompany.user_id == u.id)):
        db.delete(uc)
    db.flush()
    for cid in ids:
        db.add(UserCompany(user_id=u.id, company_id=cid))
    audit(db, actor, "UPDATE", "users", u.id, {"role": role, "active": bool(is_active), "companies": sorted(ids)}, ip)


def reset_password(db, actor, user_id, new_password, ip=None):
    require_super(actor)
    u = db.get(User, user_id)
    if not u:
        raise Invalid(["User not found"])
    p = security.password_problem(new_password or "")
    if p:
        raise Invalid([p])
    u.password_hash = security.hash_password(new_password)
    u.must_change_password, u.failed_attempts, u.locked_until = True, 0, None
    u.session_version += 1
    audit(db, actor, "RESET_PASSWORD", "users", u.id, None, ip)


def create_super_admin(db, username, full_name, password):
    """Used only by `python -m app.bootstrap` (never exposed on the web)."""
    if db.scalar(select(func.count()).select_from(User).where(User.role == ROLE_SUPER)):
        raise Denied("A Super Admin already exists.")
    _check_username(username)
    p = security.password_problem(password)
    if p:
        raise Invalid([p])
    u = User(username=username, full_name=full_name, role=ROLE_SUPER, can_salary=True,
             password_hash=security.hash_password(password), must_change_password=True)
    db.add(u)
    db.flush()
    audit(db, u, "SETUP", "users", u.id)
    return u

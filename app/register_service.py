"""Factory Act registers: generic, spec-driven CRUD with the Factories Act rule checks in core/validators."""
from datetime import datetime, timezone

from sqlalchemy import select

from . import hr, services
from .core import validators
from .core.forms import clean_values
from .models import Employee, REGISTER_MODELS
from .services import Invalid


def date_key(spec):
    return next(f.key for f in spec.fields if f.type == "date")


def list_rows(db, cid, spec, date_from=None, date_to=None):
    M = REGISTER_MODELS[spec.key]
    col = getattr(M, date_key(spec))
    stmt = select(M).where(M.company_id == cid)
    if date_from:
        stmt = stmt.where(col >= date_from)
    if date_to:
        stmt = stmt.where(col <= date_to)
    return list(db.scalars(stmt.order_by(col.desc(), M.id.desc())))


def get_row(db, cid, spec, row_id):
    o = db.get(REGISTER_MODELS[spec.key], row_id)
    return o if o and o.company_id == cid else None


def save(db, user, cid, spec, raw, row_id=None, ip=None, ignore_warnings=False):
    hr.need_edit(db, user)
    clean, errors = clean_values(spec.fields, raw)
    warnings = []
    if not errors:
        e_, w_ = validators.BY_REGISTER[spec.key](clean, cid, row_id)   # may add computed values (age, hours...)
        errors += e_
        warnings += w_
    for f in spec.fields:
        if f.type == "employee" and clean.get(f.key):
            emp = db.get(Employee, clean[f.key])
            if not emp or emp.company_id != cid:
                errors.append(f"{f.label}: employee not found in this company")
    if errors:
        raise Invalid(errors)
    if warnings and not ignore_warnings:
        raise hr.Warn(warnings)
    if row_id:
        o = get_row(db, cid, spec, row_id)
        if not o:
            raise Invalid(["Record not found"])
    else:
        o = REGISTER_MODELS[spec.key](company_id=cid, created_by=user.id)
    for f in spec.fields:
        setattr(o, f.key, clean.get(f.key))
    o.updated_at = datetime.now(timezone.utc)
    db.add(o)
    db.flush()
    services.audit(db, user, "UPDATE" if row_id else "CREATE", spec.table, o.id, None, ip, cid)
    return o


def delete(db, user, cid, spec, row_id, ip=None):
    hr.need_edit(db, user)
    o = get_row(db, cid, spec, row_id)
    if not o:
        raise Invalid(["Record not found"])
    services.audit(db, user, "DELETE", spec.table, row_id, hr.row(o), ip, cid)
    db.delete(o)

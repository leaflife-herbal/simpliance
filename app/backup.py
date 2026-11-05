"""CSV backup of one company's data (zip). A pilot-stage safety net for the free database plan: it can be opened in
Excel and used to rebuild data. It is not a one-click restore."""
import csv
import io
import zipfile
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select

from .models import (Attendance, Company, Employee, Holiday, MonthlyInput, REGISTER_MODELS, SalaryLine, SalaryRun)


def _cell(v):
    if v is None:
        return ""
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return format(v, "f")
    return v


def _write(zf, name, model, rows):
    cols = [c.name for c in model.__table__.columns]
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(cols)
    for r in rows:
        w.writerow([_cell(getattr(r, c)) for c in cols])
    zf.writestr(name + ".csv", "\ufeff" + buf.getvalue())   # BOM so Excel shows Hindi/Punjabi text correctly


def build_zip(db, company_id: int) -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        _write(zf, "company", Company, db.scalars(select(Company).where(Company.id == company_id)))
        models = [Employee, MonthlyInput, Attendance, SalaryRun, SalaryLine, Holiday] + list(REGISTER_MODELS.values())
        for M in models:
            _write(zf, M.__tablename__, M, db.scalars(select(M).where(M.company_id == company_id).order_by(M.id)))
    return out.getvalue()

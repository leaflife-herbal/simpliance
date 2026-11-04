"""Spec-driven form cleaning (no database, no web framework): turns raw strings into typed values."""
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from .util import valid_time


def coerce(f, raw):
    """Return a typed value or None for blank. Raises ValueError with a user-friendly message."""
    if raw is None or (isinstance(raw, str) and raw.strip() == ""):
        return None
    t = f.type
    if t in ("text", "multiline"):
        return str(raw).strip()
    if t == "choice":
        v = str(raw).strip()
        if f.choices and v not in f.choices:
            raise ValueError(f"{f.label}: '{v}' is not a valid choice")
        return v
    if t == "date":
        if isinstance(raw, date):
            return raw
        try:
            return datetime.strptime(str(raw).strip(), "%Y-%m-%d").date()
        except ValueError:
            raise ValueError(f"{f.label}: invalid date '{raw}'")
    if t == "time":
        if not valid_time(str(raw).strip()):
            raise ValueError(f"{f.label}: time must be HH:MM (24-hour)")
        return str(raw).strip()
    if t == "int":
        try:
            v = int(Decimal(str(raw).replace(",", "")))
        except (InvalidOperation, ValueError):
            raise ValueError(f"{f.label}: invalid whole number '{raw}'")
        if v < 0:
            raise ValueError(f"{f.label} cannot be negative")
        return v
    if t == "number":
        try:
            v = Decimal(str(raw).replace(",", ""))
        except InvalidOperation:
            raise ValueError(f"{f.label}: invalid number '{raw}'")
        if v < 0:
            raise ValueError(f"{f.label} cannot be negative")
        return v
    if t == "bool":
        return str(raw).lower() in ("1", "true", "on", "yes")
    if t == "employee":
        try:
            return int(raw)
        except ValueError:
            raise ValueError(f"{f.label}: invalid selection")
    raise ValueError(f"{f.label}: unsupported type")


def clean_values(fields, values):
    """values: mapping of raw form strings. Returns (clean dict, errors list)."""
    out, errors = {}, []
    for f in fields:
        if f.readonly:
            continue
        raw = values.get(f.key)
        if f.type == "bool":
            out[f.key] = bool(raw) and str(raw).lower() in ("1", "true", "on", "yes")
            continue
        try:
            v = coerce(f, raw)
        except ValueError as e:
            errors.append(str(e))
            continue
        if v is None and f.required:
            errors.append(f"{f.label} is required")
        out[f.key] = v
    return out, errors

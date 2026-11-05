"""Earned (annual) leave: accrues at 1 day per N days worked (default 20, the Factories Act Sec. 79 rule that the
OSH Code carries forward - confirm against your State rules). Days worked = present days + half days x 0.5 + paid
leave days. A fraction of half a day or more rounds up to a full day; a smaller fraction is dropped."""
from math import floor


def accrue(days_worked, n=20):
    x = days_worked / n
    whole = floor(x + 1e-9)
    return whole + (1 if x - whole >= 0.5 - 1e-9 else 0)


def leave_row(opening, counts, n=20):
    """counts: {'P': .., 'HD': .., 'PL': ..} attendance status counts for the leave year."""
    worked = counts.get("P", 0) + 0.5 * counts.get("HD", 0) + counts.get("PL", 0)
    accrued = accrue(worked, n)
    taken = counts.get("PL", 0)
    opening = float(opening or 0)
    return {"days_worked": worked, "accrued": accrued, "taken": taken, "balance": opening + accrued - taken}

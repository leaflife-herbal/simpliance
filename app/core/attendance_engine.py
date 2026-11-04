"""Attendance: turns 'days worked' into a full-month register.

Rules (stated assumptions):
* Weekly-off days follow the employee's weekly off (default Sunday).
* Days before joining / after leaving are 'NE' (not employed).
* Absences are spread evenly across the employee's working days (not bunched at month end);
  the register can be edited day by day afterwards.
* If days worked exceeds the working days available, the surplus is placed on weekly-off days
  (marked P = worked on weekly off).
* A half day (x.5) becomes one 'HD' day whose out-time is half-way through the shift.
"""
from calendar import monthrange
from datetime import date
from math import floor

from .specs import WEEKDAYS
from .util import m2t, minutes_between, parse_iso, t2m

STATUS_LABELS = {"P": "Present", "A": "Absent", "WO": "Weekly off", "HD": "Half day",
                 "PL": "Paid leave", "NE": "Not employed"}


def _spread(n_items, k):
    """k indices spread evenly over range(n_items); distinct when k <= n_items."""
    if k <= 0:
        return set()
    return {((2 * i + 1) * n_items) // (2 * k) for i in range(k)}


def build_month(year, month, days_worked, weekly_off, shift_in, shift_out, joining=None, leaving=None):
    """Pure function. weekly_off is a weekday name. Returns list of dicts (one per calendar day)."""
    wo_idx = WEEKDAYS.index(weekly_off)
    n = monthrange(year, month)[1]
    days = [date(year, month, d) for d in range(1, n + 1)]
    status = {}
    working, woffs = [], []
    for d in days:
        if (joining and d < joining) or (leaving and d > leaving):
            status[d] = "NE"
        elif d.weekday() == wo_idx:
            status[d] = "WO"
            woffs.append(d)
        else:
            working.append(d)
    whole = int(floor(days_worked + 1e-9))
    half = (days_worked - whole) >= 0.5 - 1e-9
    capacity = len(working) + len(woffs)
    if days_worked < 0 or whole + (1 if half else 0) > capacity:
        raise ValueError(f"Days worked ({days_worked:g}) exceeds the {capacity} days available for this employee "
                         f"in {month:02d}/{year}")
    if whole <= len(working):
        absent_n = len(working) - whole
        absent_idx = sorted(_spread(len(working), absent_n))
        for i, d in enumerate(working):
            status[d] = "P"
        for i in absent_idx:
            status[working[i]] = "A"
        if half:   # the half day takes one of the absent days, else a weekly-off day
            if absent_idx:
                status[working[absent_idx[-1]]] = "HD"
            else:
                status[woffs[0]] = "HD"   # capacity check above guarantees a weekly off exists
    else:
        extra = whole - len(working)
        for d in working:
            status[d] = "P"
        for i in range(len(woffs)):
            status[woffs[i]] = "WO"
        for i in _spread(len(woffs), extra):
            status[woffs[i]] = "P"
        if half:
            for d in woffs:
                if status[d] == "WO":
                    status[d] = "HD"
                    break
    dur = minutes_between(shift_in, shift_out)
    half_out = m2t(t2m(shift_in) + dur // 2)
    rows = []
    for d in days:
        st = status[d]
        tin = tout = None
        if st in ("P", "PL"):
            tin, tout = (shift_in, shift_out) if st == "P" else (None, None)
        elif st == "HD":
            tin, tout = shift_in, half_out
        rows.append({"date": d.isoformat(), "status": st, "in_time": tin, "out_time": tout})
    return rows


def summarise(rows):
    """rows: iterable of dict-like with 'status'. Returns day counts used by payroll."""
    c = {"P": 0, "A": 0, "WO": 0, "HD": 0, "PL": 0, "NE": 0}
    for r in rows:
        c[r["status"]] += 1
    return {"present": c["P"] + 0.5 * c["HD"], "absent": c["A"] + 0.5 * c["HD"], "weekly_off": c["WO"],
            "paid_leave": c["PL"], "not_employed": c["NE"], "days": sum(c.values())}


def day_hours(r):
    if r["status"] in ("P", "HD") and r["in_time"] and r["out_time"]:
        return minutes_between(r["in_time"], r["out_time"]) / 60
    return 0.0

"""Formatting and small helpers shared by services, UI and exports."""
import re
from datetime import date, datetime, timedelta
from decimal import Decimal

MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
          "October", "November", "December"]


def fmt_date(iso):
    if not iso:
        return ""
    if isinstance(iso, (date, datetime)):
        return iso.strftime("%d-%m-%Y")
    try:
        return datetime.strptime(iso, "%Y-%m-%d").strftime("%d-%m-%Y")
    except ValueError:
        return str(iso)


def parse_iso(s):
    """Accepts an ISO string or a date (the web layer stores real dates)."""
    if isinstance(s, datetime):
        return s.date()
    if isinstance(s, date):
        return s
    return datetime.strptime(s, "%Y-%m-%d").date()


def inr(value, decimals=0):
    """Indian digit grouping: 1,23,45,678"""
    if value is None or value == "":
        return ""
    v = Decimal(str(value))
    neg = v < 0
    v = abs(v)
    s = f"{v:.{decimals}f}"
    whole, _, frac = s.partition(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        whole = ",".join(parts) + "," + tail
    out = whole + (("." + frac) if frac else "")
    return ("-" if neg else "") + out


def num(v, decimals=2):
    """Plain number text without trailing zeros (for days, hours)."""
    if v is None:
        return ""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)   # e.g. text the user typed that failed validation
    return str(int(f)) if f == int(f) else f"{f:.{decimals}f}".rstrip("0").rstrip(".")


_ONES = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Eleven",
         "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen"]
_TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]


def _below_100(n):
    return _ONES[n] if n < 20 else (_TENS[n // 10] + ((" " + _ONES[n % 10]) if n % 10 else ""))


def _below_1000(n):
    h, r = divmod(n, 100)
    parts = []
    if h:
        parts.append(_ONES[h] + " Hundred")
    if r:
        parts.append(_below_100(r))
    return " ".join(parts)


def amount_in_words(n: int) -> str:
    n = int(n)
    if n == 0:
        return "Rupees Zero Only"
    neg = n < 0
    n = abs(n)
    crore, n = divmod(n, 10_000_000)
    lakh, n = divmod(n, 100_000)
    thousand, n = divmod(n, 1000)
    parts = []
    if crore:
        parts.append(_below_1000(crore) + " Crore")
    if lakh:
        parts.append(_below_100(lakh) + " Lakh")
    if thousand:
        parts.append(_below_100(thousand) + " Thousand")
    if n:
        parts.append(_below_1000(n))
    return ("Minus " if neg else "") + "Rupees " + " ".join(parts) + " Only"


def valid_time(s):
    return bool(re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", s or ""))


def t2m(s):
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def m2t(m):
    m %= 1440
    return f"{m // 60:02d}:{m % 60:02d}"


def minutes_between(t_in, t_out):
    """Duration in minutes; handles shifts that cross midnight."""
    d = (t2m(t_out) - t2m(t_in)) % 1440
    return d


def age_on(dob: date, on: date) -> int:
    return on.year - dob.year - ((on.month, on.day) < (dob.month, dob.day))


def days_in_month(year, month):
    nxt = date(year + (month == 12), month % 12 + 1, 1)
    return (nxt - timedelta(days=1)).day

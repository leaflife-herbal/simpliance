"""Report objects and byte-stream exports (PDF / XLSX built in memory - Render's disk is not persistent)."""
from calendar import monthrange
from io import BytesIO

from .core import attendance_engine as ae
from .core.specs import EMPLOYEE_FIELDS
from .core.util import MONTHS, fmt_date, inr, num
from .export import excel, pdf
from .export.common import Report


def _val(f, v):
    if v is None:
        return ""
    if f.type == "date":
        return fmt_date(v)
    if f.type == "bool":
        return "Yes" if v else "No"
    if f.type == "int":
        return int(v)
    if f.type == "number":
        return float(v)
    return v


def employee_report(emps):
    keys = ("emp_code", "name", "father_name", "gender", "date_of_birth", "designation", "department",
            "date_of_joining", "shift_in", "shift_out", "weekly_off", "uan", "esic_no", "salary_type")
    cols = [f for f in EMPLOYEE_FIELDS if f.key in keys]
    return Report("Employee Master", [f.label for f in cols], [[_val(f, e[f.key]) for f in cols] for e in emps],
                  "", [1] * len(cols), True, 7.5)


def attendance_blocks(emps, att, only=None):
    out = []
    for e in emps:
        if only and e["id"] != only:
            continue
        rows = att.get(e["id"], [])
        if rows:
            out.append((e, rows, ae.summarise(rows)))
    return out


def muster_report(emps, att, y, m):
    n = monthrange(y, m)[1]
    code = {"P": "P", "A": "A", "WO": "WO", "HD": "HD", "PL": "PL", "NE": "-", "PH": "PH"}
    rows = []
    for e in emps:
        recs = att.get(e["id"], [])
        s = ae.summarise(recs) if recs else None
        rows.append([e["emp_code"], e["name"]] + [code[r["status"]] for r in recs] + [""] * (n - len(recs)) +
                    ([num(s["present"]), num(s["absent"]), s["weekly_off"]] if s else ["", "", ""]))
    headers = ["Code", "Name"] + [str(d) for d in range(1, n + 1)] + ["Present", "Absent", "WO"]
    return Report("Attendance Muster Roll", headers, rows,
                  f"{MONTHS[m - 1]} {y}   (P present, A absent, WO weekly off, PH paid holiday, HD half day, PL paid leave, - not employed)",
                  [1.3, 3] + [0.7] * n + [1, 1, 0.8], True, 6.5)


def salary_register(lines, y, m):
    headers = ["Code", "Name", "Days paid", "Basic", "DA", "HRA", "Other", "OT", "Gross", "PF", "ESI", "PT",
               "Advance", "Other ded.", "Total ded.", "Net pay"]
    rows = [[l["emp_code"], l["emp_name"], l["paid_days"], l["earned_basic"], l["earned_da"], l["earned_hra"],
             l["earned_other"], l["ot_amount"], l["gross"], l["pf_employee"], l["esi_employee"], l["prof_tax"],
             l["advance"], l["other_deduction"], l["total_deductions"], l["net_pay"]] for l in lines]
    tot = ["", "TOTAL", ""] + [sum(r[i] for r in rows) for i in range(3, 16)]
    return Report("Salary Register", headers, rows, f"{MONTHS[m - 1]} {y}",
                  [1, 3, 1, 1.2, 1.1, 1, 1, 1, 1.3, 1, 1, 0.9, 1, 1, 1.2, 1.4], True, 7.5, [tot])


def _buf(fn, *a):
    b = BytesIO()
    fn(b, *a)
    return b.getvalue()


def report_pdf(company, rep):
    return _buf(pdf.report_pdf, company, rep)


def report_xlsx(company, rep):
    return _buf(excel.report_xlsx, company, rep)


def slips_pdf(company, y, m, lines):
    return _buf(pdf.salary_slips_pdf, company, y, m, lines)


def slips_xlsx(company, y, m, lines):
    return _buf(excel.salary_slips_xlsx, company, y, m, lines)


def attendance_pdf(company, y, m, blocks):
    return _buf(pdf.attendance_pdf, company, y, m, blocks)


def attendance_xlsx(company, y, m, blocks, muster):
    return _buf(excel.attendance_xlsx, company, y, m, blocks, muster)


def register_report(spec, rows, date_from="", date_to=""):
    """rows: list of dicts. Columns are the fields flagged list_col in the spec."""
    cols = [f for f in spec.fields if f.list_col]
    headers = ["Sl."] + [f.label.replace(" (auto)", "") for f in cols]
    data = [[i] + [_val(f, r.get(f.key)) for f in cols] for i, r in enumerate(rows, 1)]
    sub = ""
    if date_from or date_to:
        sub = f"Period: {fmt_date(date_from) or 'start'} to {fmt_date(date_to) or 'date'}"
    widths = [0.4] + [3 if f.type == "multiline" else 1.5 if f.type in ("text", "choice") else 1.1 for f in cols]
    return Report(spec.title, headers, data, sub, widths)


def register_detail(spec, row):
    rows = [[f.label.replace(" (auto)", ""), _val(f, row.get(f.key))] for f in spec.fields]
    return Report(spec.title + " - entry", ["Field", "Value"], rows, "", [1, 3], landscape=False, font_size=9)


def display_rows(rep):
    """Cell text for HTML tables (Indian digit grouping for whole numbers)."""
    out = []
    for r in rep.rows:
        out.append([inr(v) if isinstance(v, int) and not isinstance(v, bool) else num(v) if isinstance(v, float) else v
                    for v in r])
    return out


def pf_statement(lines, ceiling, y, m):
    """Provident Fund contribution statement (reference copy; file returns on the EPFO portal in its own format)."""
    from .core.payroll_engine import r0
    from decimal import Decimal as D
    rows = []
    for l in lines:
        if not l["pf_employee"]:
            continue
        pf_wages = l["earned_basic"] + l["earned_da"]
        eps_wages = min(pf_wages, 15000)
        eps = r0(D(eps_wages) * D("0.0833"))
        er = l["pf_employer"]
        rows.append([l["emp_code"], l["emp_name"], l["uan"] or "", l["gross"], pf_wages, min(pf_wages, int(ceiling)),
                     eps_wages, l["pf_employee"], eps, er - eps, round(l["days_in_month"] - l["paid_days"], 1)])
    tot = ["", "TOTAL", ""] + [sum(r[i] for r in rows) for i in range(3, 10)] + [""]
    headers = ["Code", "Name", "UAN", "Gross wages", "PF wages (Basic+DA)", "Wages for EPF", "Wages for EPS",
               "Employee 12%", "Employer EPS 8.33%", "Employer EPF 3.67%", "Non-contributing days"]
    return Report("Provident Fund Contribution Statement", headers, rows,
                  f"{MONTHS[m - 1]} {y} - reference statement; employer 3.67% share shown is total employer 12% less EPS",
                  [1, 3, 2, 1.3, 1.4, 1.3, 1.3, 1.2, 1.3, 1.3, 1.2], True, 7.5, [tot])


def esi_statement(lines, y, m):
    rows = []
    for l in lines:
        if not l["esi_employee"]:
            continue
        wages = l["gross"] - l["ot_amount"]          # ESI wages exclude overtime
        rows.append([l["emp_code"], l["emp_name"], l["esic_no"] or "", l["paid_days"], wages, l["esi_employee"],
                     l["esi_employer"], l["esi_employee"] + l["esi_employer"]])
    tot = ["", "TOTAL", "", ""] + [sum(r[i] for r in rows) for i in range(4, 8)]
    headers = ["Code", "Name", "ESIC IP No.", "Days paid", "ESI wages", "Employee 0.75%", "Employer 3.25%", "Total"]
    return Report("ESI Contribution Statement", headers, rows,
                  f"{MONTHS[m - 1]} {y} - reference statement for the ESIC portal",
                  [1, 3, 2, 1, 1.4, 1.3, 1.3, 1.2], True, 8, [tot])


def leave_report(rows, year, n):
    headers = ["Code", "Name", "Opening", "Days worked", "Accrued", "Taken (PL)", "Balance"]
    data = [[r["emp_code"], r["name"], r["opening"], r["days_worked"], r["accrued"], r["taken"], r["balance"]]
            for r in rows]
    return Report("Earned Leave Register", headers, data,
                  f"Year {year} - 1 day for every {n} days worked; half a day or more rounds up",
                  [1, 3, 1, 1.2, 1, 1.2, 1], False, 9)

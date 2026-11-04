"""Report objects and byte-stream exports (PDF / XLSX built in memory - Render's disk is not persistent)."""
from calendar import monthrange
from io import BytesIO

from .core import attendance_engine as ae
from .core.specs import EMPLOYEE_FIELDS
from .core.util import MONTHS, fmt_date, num
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
    code = {"P": "P", "A": "A", "WO": "WO", "HD": "HD", "PL": "PL", "NE": "-"}
    rows = []
    for e in emps:
        recs = att.get(e["id"], [])
        s = ae.summarise(recs) if recs else None
        rows.append([e["emp_code"], e["name"]] + [code[r["status"]] for r in recs] + [""] * (n - len(recs)) +
                    ([num(s["present"]), num(s["absent"]), s["weekly_off"]] if s else ["", "", ""]))
    headers = ["Code", "Name"] + [str(d) for d in range(1, n + 1)] + ["Present", "Absent", "WO"]
    return Report("Attendance Muster Roll", headers, rows,
                  f"{MONTHS[m - 1]} {y}   (P present, A absent, WO weekly off, HD half day, PL paid leave, - not employed)",
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

"""Excel output with openpyxl (offline)."""
import re
from datetime import date

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from ..core.util import MONTHS, amount_in_words, fmt_date
from .common import Report, company_lines

THIN = Side(style="thin", color="888888")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
HEAD = PatternFill("solid", fgColor="DCE6F1")
BOLD = Font(bold=True)


def _sheet_name(wb, name):
    name = re.sub(r"[\[\]\*\?/\\:]", "_", name)[:31] or "Sheet"
    base, i = name, 1
    while name in wb.sheetnames:
        i += 1
        name = f"{base[:28]}_{i}"
    return name


def _letterhead(ws, company, title, subtitle, ncols):
    lines = [x for x in company_lines(company) if x]
    r = 1
    for i, ln in enumerate(lines):
        ws.cell(r, 1, ln).font = Font(bold=True, size=14 if i == 0 else 10)
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=max(ncols, 2))
        ws.cell(r, 1).alignment = Alignment(horizontal="center")
        r += 1
    ws.cell(r, 1, title).font = Font(bold=True, size=12)
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=max(ncols, 2))
    ws.cell(r, 1).alignment = Alignment(horizontal="center")
    r += 1
    if subtitle:
        ws.cell(r, 1, subtitle).alignment = Alignment(horizontal="center")
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=max(ncols, 2))
        r += 1
    return r + 1


def _page(ws, landscape=True):
    ws.page_setup.orientation = "landscape" if landscape else "portrait"
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.print_options.horizontalCentered = True


def _fill_table(ws, start, headers, rows, footer_rows=()):
    for c, h in enumerate(headers, 1):
        cell = ws.cell(start, c, h)
        cell.font, cell.fill, cell.border = BOLD, HEAD, BORDER
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    r = start
    for row in list(rows) + list(footer_rows):
        r += 1
        for c, v in enumerate(row, 1):
            cell = ws.cell(r, c, v)
            cell.border = BORDER
            cell.alignment = Alignment(vertical="top", wrap_text=isinstance(v, str),
                                       horizontal="right" if isinstance(v, (int, float)) and not isinstance(v, bool) else None)
            if row in footer_rows:
                cell.font = BOLD
    ws.freeze_panes = ws.cell(start + 1, 1)
    ws.print_title_rows = f"{start}:{start}"
    for c in range(1, len(headers) + 1):
        vals = [headers[c - 1]] + [row[c - 1] for row in list(rows)[:200] if c - 1 < len(row)]
        ln = max((len(str(v)) for v in vals if v is not None), default=8)
        ws.column_dimensions[get_column_letter(c)].width = min(max(ln + 2, 6), 45)
    return r


def report_xlsx(path, company, rep: Report):
    wb = Workbook()
    ws = wb.active
    ws.title = _sheet_name(wb, rep.title)
    start = _letterhead(ws, company, rep.title, rep.subtitle, len(rep.headers))
    rows = [[("Yes" if v is True else "No" if v is False else v) for v in r] for r in rep.rows]
    _fill_table(ws, start, rep.headers, rows, rep.footer_rows)
    _page(ws, rep.landscape)
    wb.save(path)
    return path


def salary_slips_xlsx(path, company, year, month, lines):
    wb = Workbook()
    wb.remove(wb.active)
    for ln in lines:
        ws = wb.create_sheet(_sheet_name(wb, f"{ln['emp_code']}"))
        r = _letterhead(ws, company, f"PAY SLIP FOR {MONTHS[month - 1].upper()} {year}", "", 4)
        info = [("Employee code", ln["emp_code"], "Name", ln["emp_name"]),
                ("Designation", ln["designation"], "Department", ln["department"]),
                ("UAN", ln["uan"], "ESIC No.", ln["esic_no"]),
                ("Days in month", ln["days_in_month"], "Days paid", ln["paid_days"]),
                ("Days present", ln["present_days"], "Absent (LOP)", ln["absent_days"]),
                ("Weekly offs", ln["weekly_offs"], "OT hours", ln["ot_hours"])]
        for a, b, c, d in info:
            for i, v in enumerate((a, b, c, d), 1):
                cell = ws.cell(r, i, v)
                cell.border = BORDER
                if i in (1, 3):
                    cell.font = BOLD
            r += 1
        r += 1
        for i, h in enumerate(("Earnings", "Rs.", "Deductions", "Rs."), 1):
            cell = ws.cell(r, i, h)
            cell.font, cell.fill, cell.border = BOLD, HEAD, BORDER
        earn = [("Basic", ln["earned_basic"]), ("Dearness allowance", ln["earned_da"]), ("HRA", ln["earned_hra"]),
                ("Other allowance", ln["earned_other"]), ("Overtime", ln["ot_amount"])]
        ded = [("Provident Fund", ln["pf_employee"]), ("ESI", ln["esi_employee"]),
               ("Professional Tax", ln["prof_tax"]), ("Advance", ln["advance"]),
               ("Other deduction", ln["other_deduction"])]
        for (a, av), (d, dv) in zip(earn, ded):
            r += 1
            for i, v in enumerate((a, av, d, dv), 1):
                ws.cell(r, i, v).border = BORDER
        r += 1
        for i, v in enumerate(("Gross earnings", ln["gross"], "Total deductions", ln["total_deductions"]), 1):
            c = ws.cell(r, i, v)
            c.font, c.border = BOLD, BORDER
        r += 1
        ws.cell(r, 1, "NET PAY").font = Font(bold=True, size=12)
        ws.cell(r, 2, ln["net_pay"]).font = Font(bold=True, size=12)
        r += 1
        ws.cell(r, 1, "In words: " + amount_in_words(ln["net_pay"]))
        r += 1
        ws.cell(r, 1, f"Employer contribution (info): PF Rs. {ln['pf_employer']}, ESI Rs. {ln['esi_employer']}")
        for col, w in zip("ABCD", (26, 16, 26, 16)):
            ws.column_dimensions[col].width = w
        _page(ws, False)
    if not lines:
        wb.create_sheet("Empty")
    wb.save(path)
    return path


def attendance_xlsx(path, company, year, month, blocks, muster: Report):
    from ..core.attendance_engine import STATUS_LABELS, day_hours
    wb = Workbook()
    ws = wb.active
    ws.title = "Muster"
    start = _letterhead(ws, company, muster.title, muster.subtitle, len(muster.headers))
    _fill_table(ws, start, muster.headers, muster.rows)
    _page(ws, True)
    for e, rows, s in blocks:
        w2 = wb.create_sheet(_sheet_name(wb, e["emp_code"]))
        r = _letterhead(w2, company, f"Attendance Register - {MONTHS[month - 1]} {year}",
                        f"{e['emp_code']} - {e['name']} | Shift {e['shift_in']} - {e['shift_out']}", 6)
        data = []
        for x in rows:
            d = date.fromisoformat(x["att_date"])
            h = day_hours(x)
            data.append([fmt_date(x["att_date"]), d.strftime("%a"), STATUS_LABELS[x["status"]],
                         x["in_time"] or "", x["out_time"] or "", round(h, 2) if h else ""])
        end = _fill_table(w2, r, ["Date", "Day", "Status", "In time", "Out time", "Hours"], data)
        w2.cell(end + 2, 1, f"Present {s['present']:g} | Absent {s['absent']:g} | Weekly offs {s['weekly_off']} | "
                            f"Paid leave {s['paid_leave']}")
        _page(w2, False)
    wb.save(path)
    return path

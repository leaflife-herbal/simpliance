"""PDF output with ReportLab (pure Python, fully offline). Uses built-in Helvetica, so amounts are
written as 'Rs.' rather than the rupee glyph."""
from datetime import date
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle)

from ..core.util import MONTHS, amount_in_words, fmt_date, inr, num
from .common import Report, company_lines

_ss = getSampleStyleSheet()
H1 = ParagraphStyle("h1", parent=_ss["Title"], fontSize=14, leading=17, spaceAfter=1)
SUB = ParagraphStyle("sub", parent=_ss["Normal"], fontSize=8.5, alignment=TA_CENTER, leading=11)
TITLE = ParagraphStyle("t", parent=_ss["Heading2"], fontSize=11.5, alignment=TA_CENTER, spaceBefore=4, spaceAfter=4)
GRID = colors.HexColor("#555555")
HEAD_BG = colors.HexColor("#DCE6F1")


def _p(text, size=8, bold=False, align=None):
    st = ParagraphStyle("c", parent=_ss["Normal"], fontSize=size, leading=size + 2,
                        fontName="Helvetica-Bold" if bold else "Helvetica")
    if align == "R":
        st.alignment = 2
    elif align == "C":
        st.alignment = 1
    return Paragraph(escape("" if text is None else str(text)).replace("\n", "<br/>"), st)


def _cell(v, size):
    if isinstance(v, bool):
        return _p("Yes" if v else "No", size)
    if isinstance(v, int):
        return _p(inr(v), size, align="R")
    if isinstance(v, float):
        return _p(num(v), size, align="R")
    return _p(v, size)


def _doc(path, company, landscape_mode, title):
    size = landscape(A4) if landscape_mode else A4
    doc = SimpleDocTemplate(path, pagesize=size, leftMargin=12 * mm, rightMargin=12 * mm, topMargin=12 * mm,
                            bottomMargin=14 * mm, title=title, author="Factory Compliance Manager")
    doc._fcm_company = company
    return doc


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    w = doc.pagesize[0]
    canvas.drawString(12 * mm, 8 * mm, f"Printed {date.today().strftime('%d-%m-%Y')} - Factory Compliance Manager")
    canvas.drawRightString(w - 12 * mm, 8 * mm, f"Page {doc.page}")
    canvas.restoreState()


def _letterhead(company):
    out = []
    lines = company_lines(company)
    out.append(Paragraph(escape(lines[0]), H1))
    for ln in lines[1:]:
        if ln:
            out.append(Paragraph(escape(ln), SUB))
    return out


def report_pdf(path, company, rep: Report):
    doc = _doc(path, company, rep.landscape, rep.title)
    avail = doc.pagesize[0] - 24 * mm
    story = _letterhead(company)
    story.append(Paragraph(escape(rep.title), TITLE))
    if rep.subtitle:
        story.append(Paragraph(escape(rep.subtitle), SUB))
        story.append(Spacer(1, 3))
    fs = rep.font_size
    data = [[_p(h, fs, True, "C") for h in rep.headers]]
    for r in rep.rows:
        data.append([_cell(v, fs) for v in r])
    for r in rep.footer_rows:
        data.append([_p(v if not isinstance(v, (int, float)) else inr(v) if isinstance(v, int) else num(v),
                        fs, True, "R" if isinstance(v, (int, float)) else None) for v in r])
    n = len(rep.headers)
    w = rep.widths or [1] * n
    colw = [avail * x / sum(w) for x in w]
    t = Table(data, colWidths=colw, repeatRows=1)
    style = [("GRID", (0, 0), (-1, -1), 0.4, GRID), ("BACKGROUND", (0, 0), (-1, 0), HEAD_BG),
             ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 2),
             ("RIGHTPADDING", (0, 0), (-1, -1), 2), ("TOPPADDING", (0, 0), (-1, -1), 2),
             ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]
    if rep.footer_rows:
        style.append(("BACKGROUND", (0, len(data) - len(rep.footer_rows)), (-1, -1), colors.HexColor("#F2F2F2")))
    t.setStyle(TableStyle(style))
    story.append(t)
    if not rep.rows:
        story.append(Spacer(1, 6))
        story.append(Paragraph("No records.", SUB))
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return path


# ------------------------------------------------------------------ salary slips

def _slip(company, ln, year, month):
    lines = company_lines(company)
    head = [Paragraph(escape(lines[0]), H1)] + [Paragraph(escape(x), SUB) for x in lines[1:3] if x]
    head.append(Paragraph(f"PAY SLIP FOR {MONTHS[month - 1].upper()} {year}", TITLE))
    info = [
        [_p("Employee code", 8.5, True), _p(ln["emp_code"], 8.5), _p("Name", 8.5, True), _p(ln["emp_name"], 8.5)],
        [_p("Designation", 8.5, True), _p(ln["designation"], 8.5), _p("Department", 8.5, True), _p(ln["department"], 8.5)],
        [_p("UAN", 8.5, True), _p(ln["uan"], 8.5), _p("ESIC No.", 8.5, True), _p(ln["esic_no"], 8.5)],
        [_p("Days in month", 8.5, True), _p(ln["days_in_month"], 8.5), _p("Days paid", 8.5, True),
         _p(num(ln["paid_days"]), 8.5)],
        [_p("Days present", 8.5, True), _p(num(ln["present_days"]), 8.5), _p("Absent (LOP)", 8.5, True),
         _p(num(ln["absent_days"]), 8.5)],
        [_p("Weekly offs", 8.5, True), _p(num(ln["weekly_offs"]), 8.5), _p("OT hours", 8.5, True),
         _p(num(ln["ot_hours"]), 8.5)],
    ]
    it = Table(info, colWidths=[30 * mm, 55 * mm, 30 * mm, 55 * mm])
    it.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.6, GRID), ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.grey),
                            ("TOPPADDING", (0, 0), (-1, -1), 1.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5)]))
    earn = [("Basic", ln["earned_basic"]), ("Dearness allowance", ln["earned_da"]), ("HRA", ln["earned_hra"]),
            ("Other allowance", ln["earned_other"]), ("Overtime", ln["ot_amount"])]
    ded = [("Provident Fund", ln["pf_employee"]), ("ESI", ln["esi_employee"]), ("Professional Tax", ln["prof_tax"]),
           ("Advance", ln["advance"]), ("Other deduction", ln["other_deduction"])]
    rows = [[_p("Earnings", 9, True), _p("Rs.", 9, True, "R"), _p("Deductions", 9, True), _p("Rs.", 9, True, "R")]]
    for (a, av), (d, dv) in zip(earn, ded):
        rows.append([_p(a, 9), _p(inr(av), 9, align="R"), _p(d, 9), _p(inr(dv), 9, align="R")])
    rows.append([_p("Gross earnings", 9, True), _p(inr(ln["gross"]), 9, True, "R"),
                 _p("Total deductions", 9, True), _p(inr(ln["total_deductions"]), 9, True, "R")])
    rows.append([_p("NET PAY", 10, True), _p(inr(ln["net_pay"]), 10, True, "R"), "", ""])
    et = Table(rows, colWidths=[50 * mm, 35 * mm, 50 * mm, 35 * mm])
    et.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, GRID), ("BACKGROUND", (0, 0), (-1, 0), HEAD_BG),
                            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#F2F2F2")),
                            ("SPAN", (1, -1), (3, -1)), ("ALIGN", (1, -1), (-1, -1), "LEFT")]))
    words = _p("Net pay in words: " + amount_in_words(ln["net_pay"]), 8.5)
    er = _p(f"Employer contribution (for information): PF Rs. {inr(ln['pf_employer'])}, "
            f"ESI Rs. {inr(ln['esi_employer'])}", 7.5)
    sign = Table([[_p("Employee signature", 8), _p("Authorised signatory", 8, align="R")]], colWidths=[85 * mm, 85 * mm])
    sign.setStyle(TableStyle([("TOPPADDING", (0, 0), (-1, -1), 14)]))
    return KeepTogether(head + [it, Spacer(1, 3), et, Spacer(1, 3), words, er, sign])


def salary_slips_pdf(path, company, year, month, lines):
    doc = _doc(path, company, False, f"Salary slips {MONTHS[month - 1]} {year}")
    story = []
    for i, ln in enumerate(lines):
        story.append(_slip(company, ln, year, month))
        if i % 2 == 0 and i != len(lines) - 1:
            story.append(Spacer(1, 10 * mm))
        elif i != len(lines) - 1:
            story.append(PageBreak())
    if not lines:
        story.append(Paragraph("No salary lines.", SUB))
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return path


# ------------------------------------------------------------------ attendance

def attendance_pdf(path, company, year, month, blocks):
    """blocks: list of (employee_row, [attendance rows], summary dict)."""
    from ..core.attendance_engine import STATUS_LABELS, day_hours
    doc = _doc(path, company, False, f"Attendance {MONTHS[month - 1]} {year}")
    story = []
    for i, (e, rows, s) in enumerate(blocks):
        story += _letterhead(company)
        story.append(Paragraph(f"ATTENDANCE REGISTER - {MONTHS[month - 1].upper()} {year}", TITLE))
        story.append(Paragraph(escape(f"{e['emp_code']} - {e['name']}   |   {e['designation'] or ''}   |   "
                                      f"Shift {e['shift_in']} - {e['shift_out']}   |   Weekly off: {e['weekly_off']}"),
                               SUB))
        story.append(Spacer(1, 4))
        data = [[_p(h, 8.5, True, "C") for h in ("Date", "Day", "Status", "In time", "Out time", "Hours", "Signature")]]
        for r in rows:
            d = date.fromisoformat(r["att_date"])
            data.append([_p(fmt_date(r["att_date"]), 8.5), _p(d.strftime("%a"), 8.5),
                         _p(STATUS_LABELS[r["status"]], 8.5), _p(r["in_time"] or "", 8.5, align="C"),
                         _p(r["out_time"] or "", 8.5, align="C"),
                         _p(f"{day_hours(r):.2f}" if day_hours(r) else "", 8.5, align="R"), ""])
        t = Table(data, colWidths=[24 * mm, 14 * mm, 28 * mm, 22 * mm, 22 * mm, 18 * mm, 52 * mm], repeatRows=1)
        t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, GRID), ("BACKGROUND", (0, 0), (-1, 0), HEAD_BG),
                               ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]))
        story.append(t)
        story.append(Spacer(1, 4))
        story.append(Paragraph(escape(
            f"Present: {num(s['present'])}   Absent: {num(s['absent'])}   Weekly offs: {s['weekly_off']}   "
            f"Paid leave: {s['paid_leave']}   Not employed: {s['not_employed']}"), SUB))
        if i != len(blocks) - 1:
            story.append(PageBreak())
    if not blocks:
        story.append(Paragraph("No attendance generated for this month.", SUB))
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return path

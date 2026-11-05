"""Employee master <-> Excel. Builds the downloadable template and parses a filled workbook into raw form values
(strings) that go through exactly the same validation as the Add Employee screen."""
import re
from datetime import date, datetime, time, timedelta
from io import BytesIO

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from .specs import EMPLOYEE_FIELDS

MAX_ROWS = 500
HEAD_FILL = PatternFill("solid", fgColor="DCE6F1")
REQ_FILL = PatternFill("solid", fgColor="FFE8B3")
TEXT_AS_TEXT = {"emp_code", "mobile", "uan", "esic_no", "bank_account", "ifsc"}
EXAMPLE = {
    "emp_code": "E001", "name": "Ramesh Kumar", "father_name": "Suresh Kumar", "gender": "Male",
    "date_of_birth": "15-08-1990", "address": "Ludhiana", "mobile": "9876543210", "designation": "Fitter",
    "department": "Machine shop", "skill_category": "Skilled", "date_of_joining": "01-04-2022",
    "date_of_leaving": "", "is_active": "Yes", "shift_in": "09:00", "shift_out": "18:00", "weekly_off": "Sunday",
    "uan": "", "esic_no": "", "bank_name": "", "bank_account": "", "ifsc": "", "salary_type": "MONTHLY",
    "basic": "10000", "da": "2000", "hra": "0", "other_allowance": "0", "pf_applicable": "Yes",
    "esi_applicable": "Yes", "pt_applicable": "Yes"}


def _norm(s):
    return re.sub(r"\s+", " ", str(s or "").replace("*", " ").strip().lower())


def header_label(f):
    return f.label + (" *" if f.required else "")


def build_template() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Employees"
    for c, f in enumerate(EMPLOYEE_FIELDS, 1):
        cell = ws.cell(1, c, header_label(f))
        cell.font = Font(bold=True)
        cell.fill = REQ_FILL if f.required else HEAD_FILL
        cell.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
        letter = get_column_letter(c)
        ws.column_dimensions[letter].width = max(14, min(32, len(f.label) // 2 + 8))
        fmt = {"date": "DD-MM-YYYY", "time": "HH:MM"}.get(f.type)
        if f.key in TEXT_AS_TEXT:
            fmt = "@"
        if fmt:
            for r in range(2, MAX_ROWS + 2):
                ws.cell(r, c).number_format = fmt
        opts = None
        if f.type == "choice" and f.choices:
            opts = ",".join(f.choices)
        elif f.type == "bool":
            opts = "Yes,No"
        if opts and len(opts) < 250:
            dv = DataValidation(type="list", formula1=f'"{opts}"', allow_blank=True)
            dv.error, dv.errorTitle = "Pick a value from the list", "Invalid entry"
            ws.add_data_validation(dv)
            dv.add(f"{letter}2:{letter}{MAX_ROWS + 1}")
    ws.row_dimensions[1].height = 48
    ws.freeze_panes = "C2"

    ins = wb.create_sheet("Instructions")
    lines = [
        "HOW TO USE THIS TEMPLATE",
        "1. Fill one employee per row on the 'Employees' sheet, starting at row 2. Do not rename or delete columns.",
        f"2. Maximum {MAX_ROWS} employees per upload. Columns marked * (orange) are required.",
        "3. Dates: DD-MM-YYYY (for example 15-08-1990). Times: 24-hour HH:MM (for example 09:00, 18:30; night shift 22:00 to 06:00).",
        "4. Yes/No columns: type Yes or No (blank = the default, normally Yes).",
        "5. Salary type MONTHLY: Basic/DA/HRA/Other are per month. DAILY: they are per day.",
        "6. Employee code must be unique. If a code already exists the upload is refused, unless you tick 'update existing' on the upload page.",
        "7. If any row has an error, nothing is imported - fix the listed rows and upload again.",
        "", "EXAMPLE ROW (do not copy the header; this sheet is not imported)"]
    for i, t in enumerate(lines, 1):
        ins.cell(i, 1, t).font = Font(bold=(i == 1))
    r0 = len(lines) + 2
    for c, f in enumerate(EMPLOYEE_FIELDS, 1):
        ins.cell(r0, c, f.label).font = Font(bold=True)
        ins.cell(r0 + 1, c, EXAMPLE.get(f.key, ""))
    ins.column_dimensions["A"].width = 60
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ------------------------------------------------------------------ parsing
_DATE_FORMATS = ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d.%m.%Y", "%d-%m-%y", "%d/%m/%y")


def _date(v):
    if isinstance(v, datetime):
        return v.date().isoformat()
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return (date(1899, 12, 30) + timedelta(days=int(v))).isoformat()
    s = str(v).strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            pass
    return s


def _time(v):
    if isinstance(v, datetime):
        return v.strftime("%H:%M")
    if isinstance(v, time):
        return v.strftime("%H:%M")
    if isinstance(v, (int, float)) and not isinstance(v, bool) and 0 <= v < 1:
        mins = round(v * 1440)
        return f"{(mins // 60) % 24:02d}:{mins % 60:02d}"
    m = re.fullmatch(r"\s*(\d{1,2})[:.](\d{2})(?::\d{2})?\s*", str(v))
    return f"{int(m.group(1)):02d}:{m.group(2)}" if m else str(v).strip()


def _text(v):
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def parse_workbook(data: bytes):
    """Returns (rows, errors): rows = [(excel_row_number, {field_key: raw string})]."""
    errors = []
    try:
        wb = load_workbook(BytesIO(data), data_only=True, read_only=True)
    except Exception:
        return [], ["This is not a valid Excel (.xlsx) file. Download the template and fill it in."]
    ws = wb["Employees"] if "Employees" in wb.sheetnames else wb.worksheets[0]
    it = ws.iter_rows(values_only=True)
    header = next(it, None)
    if not header:
        return [], ["The sheet is empty."]
    by_norm = {_norm(f.label): f for f in EMPLOYEE_FIELDS}
    colmap = {}
    for idx, h in enumerate(header):
        f = by_norm.get(_norm(h))
        if f:
            colmap[idx] = f
    found = {f.key for f in colmap.values()}
    missing = [f.label for f in EMPLOYEE_FIELDS if f.required and f.key not in found]
    if missing:
        return [], ["Missing required column(s): " + ", ".join(missing) + ". Use the downloaded template."]
    rows = []
    for n, raw in enumerate(it, start=2):
        if raw is None or all(v is None or str(v).strip() == "" for v in raw):
            continue
        if len(rows) >= MAX_ROWS:
            errors.append(f"More than {MAX_ROWS} employees - split the file.")
            break
        rec = {}
        for idx, f in colmap.items():
            v = raw[idx] if idx < len(raw) else None
            blank = v is None or str(v).strip() == ""
            if f.type == "bool":
                if blank:
                    rec[f.key] = "1" if f.default else ""
                else:
                    s = str(v).strip().lower()
                    if s in ("yes", "y", "true", "1", "x"):
                        rec[f.key] = "1"
                    elif s in ("no", "n", "false", "0"):
                        rec[f.key] = ""
                    else:
                        errors.append(f"Row {n}: {f.label} must be Yes or No")
                continue
            if blank:
                rec[f.key] = ""
            elif f.type == "date":
                rec[f.key] = _date(v)
            elif f.type == "time":
                rec[f.key] = _time(v)
            elif f.type == "choice":
                s = _text(v)
                rec[f.key] = next((c for c in (f.choices or []) if c.lower() == s.lower()), s)
            else:
                rec[f.key] = _text(v)
        for f in EMPLOYEE_FIELDS:   # columns left out of the sheet fall back to defaults
            if f.key not in rec:
                rec[f.key] = ("1" if f.default else "") if f.type == "bool" else (
                    "" if f.default is None else str(f.default))
        rows.append((n, rec))
    if not rows and not errors:
        errors.append("No employee rows found below the header.")
    return rows, errors

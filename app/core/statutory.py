"""Files for the EPFO and ESIC portals, built from the month's salary lines.

EPFO ECR 2.0: a text file, one line per member, 11 fields separated by '#~#' (UAN based). Rules checked here: gross
wages mandatory; EPF wages <= gross; EPS and EDLI wages <= Rs.15,000; NCP days whole numbers (half days round up).
ESIC monthly contribution (MC): an Excel sheet with IP number, IP name, days wages paid/payable, total monthly wages,
reason code (only for zero days) and last working day. The portal works out the contributions itself.
Portal formats change from time to time: always compare with the template or help file on the portal itself."""
import re
from decimal import Decimal as D
from math import ceil

from .payroll_engine import r0

ECR_HEADERS = ["UAN", "MEMBER_NAME", "GROSS_WAGES", "EPF_WAGES", "EPS_WAGES", "EDLI_WAGES", "EPF_CONTRI_REMITTED",
               "EPS_CONTRI_REMITTED", "EPF_EPS_DIFF_REMITTED", "NCP_DAYS", "REFUND_OF_ADVANCES"]
ESIC_HEADERS = ["IP Number", "IP Name", "No of Days for which wages paid/payable during the month",
                "Total Monthly Wages", "Reason Code for Zero workings days (numeric code only)",
                "Last Working Day (DD/MM/YYYY)"]
ESIC_REASONS = {1: "On leave", 2: "Left service", 3: "Retired", 4: "Out of coverage", 5: "Expired",
                6: "Non-implemented area", 7: "Compliance by immediate employer", 8: "Suspension of work",
                9: "Strike / lockout", 10: "Retrenchment", 11: "No work", 12: "Does not belong to this employer",
                13: "Duplicate IP"}
WAGE_CEILING = 15000   # EPS / EDLI wage ceiling


def clean_name(name):
    """Portals accept letters and spaces only for names."""
    n = re.sub(r"[^A-Za-z ]+", " ", name or "")
    return re.sub(r"\s+", " ", n).strip().upper()


def _digits(v):
    return re.sub(r"\D", "", str(v or ""))


def ecr_rows(lines, emps, pf_ceiling, pf_on_actual):
    """lines: salary line dicts; emps: {employee_id: employee dict}. Returns (rows, warnings)."""
    rows, warns = [], []
    for l in lines:
        if not l["pf_employee"]:
            continue
        who = f"{l['emp_code']} {l['emp_name']}"
        uan = _digits(l.get("uan") or emps.get(l["employee_id"], {}).get("uan"))
        if len(uan) != 12:
            warns.append(f"{who}: UAN missing or not 12 digits - left out of the ECR (ECR 2.0 accepts members with a UAN only)")
            continue
        name = clean_name(l["emp_name"])
        if name != str(l["emp_name"]).upper().strip():
            warns.append(f"{who}: name written as '{name}' (letters and spaces only) - it must match the name on the UAN record")
        pf_wages = l["earned_basic"] + l["earned_da"]
        epf_wages = pf_wages if pf_on_actual else min(pf_wages, int(pf_ceiling))
        epf_wages = min(epf_wages, l["gross"])
        eps_wages = min(epf_wages, WAGE_CEILING)
        edli_wages = min(epf_wages, WAGE_CEILING)
        eps = r0(D(eps_wages) * D("0.0833"))
        diff = max(0, l["pf_employer"] - eps)
        ncp = int(ceil(round(l["days_in_month"] - l["paid_days"], 6)))
        rows.append([uan, name, l["gross"], epf_wages, eps_wages, edli_wages, l["pf_employee"], eps, diff,
                     max(0, ncp), 0])
    if rows:
        warns.append("Check member names against the UAN records and EPS eligibility (members who already draw pension "
                     "or joined after the age limit may need EPS wages of 0) before uploading.")
    return rows, warns


def ecr_text(rows) -> str:
    return "\r\n".join("#~#".join(str(v) for v in r) for r in rows) + ("\r\n" if rows else "")


def esic_rows(lines, emps, y, m):
    """Returns (rows, warnings). Rows: [ip, name, days, wages, reason, last_working_day] - all text."""
    rows, warns = [], []
    for l in lines:
        e = emps.get(l["employee_id"], {})
        ip = _digits(l.get("esic_no") or e.get("esic_no"))
        covered = l["esi_employee"] > 0
        zero_wage = l["gross"] == 0 and e.get("esi_applicable") and ip
        if not covered and not zero_wage:
            continue
        who = f"{l['emp_code']} {l['emp_name']}"
        if len(ip) != 10:
            warns.append(f"{who}: ESIC IP number missing or not 10 digits - left out")
            continue
        name = clean_name(l["emp_name"])
        days = int(ceil(round(l["paid_days"], 6)))
        wages = l["gross"] - l["ot_amount"]            # ESI wages exclude overtime
        reason, last = "", ""
        if days == 0:
            leaving = e.get("date_of_leaving")
            if leaving and (leaving.year, leaving.month) <= (y, m):
                reason, last = "2", leaving.strftime("%d/%m/%Y")
            else:
                reason = "1"
            warns.append(f"{who}: zero days - reason code {reason} ({ESIC_REASONS[int(reason)]}) used; change it if wrong")
        rows.append([ip, name, str(days), str(wages), reason, last])
    return rows, warns

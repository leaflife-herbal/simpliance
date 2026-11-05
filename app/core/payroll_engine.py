"""Salary calculation. All money is computed with Decimal and rounded to whole rupees
(ROUND_HALF_UP) per component. ESI contributions are rounded UP to the next rupee, as ESIC requires.

Stated assumptions
------------------
MONTHLY employees
  LOP days    = Absent days + 0.5 x Half days          (weekly offs and paid leave are paid)
  Paid days   = max(0, min(Divisor, Days employed in month) - LOP)
  Each component earned = monthly rate x Paid days / Divisor
  Divisor = calendar days of the month, or fixed 30 / 26 as set on the company.
DAILY employees
  Each component earned = daily rate x (Present days + Paid leave + Paid holidays); weekly offs are unpaid.
Overtime (Sec. 59): hours x ordinary hourly rate x 2, where the ordinary rate is
  (basic + DA + HRA + other allowance) / (Divisor x normal hours)  [daily: / normal hours].
Provident Fund: employee 12% of (earned basic + DA), limited to the wage ceiling unless the company
  pays on actual wages. Employer 12% is shown for information.
ESI: applies if the employee is flagged, and fixed monthly gross <= threshold (Rs.21,000 default).
  ESI wages exclude overtime. Employee 0.75%, employer 3.25%, rounded up.
  (The ESIC 'contribution period' rule that keeps an employee covered after crossing the threshold
  mid-period is not modelled - untick 'ESI applicable' / adjust manually if that applies.)
Professional Tax: looked up from the company's slab table against the month's gross; nil if no slabs.
"""
import re
from decimal import Decimal as D, ROUND_CEILING, ROUND_HALF_UP

from .util import days_in_month

PF_RATE = D("0.12")
ESI_EE = D("0.0075")
ESI_ER = D("0.0325")


def r0(x) -> int:
    return int(D(x).quantize(D("1"), rounding=ROUND_HALF_UP))


def ceil0(x) -> int:
    return int(D(x).to_integral_value(rounding=ROUND_CEILING))


def dec(x) -> D:
    return D(str(x if x is not None else 0))


def parse_pt_slabs(text):
    """'from-to:amount' per line; 'to' may be '*' or blank for open-ended. Returns [(lo, hi|None, amt)]."""
    slabs = []
    for n, line in enumerate((text or "").splitlines(), 1):
        if not line.strip():
            continue
        m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?|\*)?\s*:\s*(\d+(?:\.\d+)?)\s*", line)
        if not m:
            raise ValueError(f"Professional Tax slab line {n} is not in the form from-to:amount")
        lo, hi, amt = D(m.group(1)), (None if m.group(2) in (None, "*") else D(m.group(2))), D(m.group(3))
        if hi is not None and hi < lo:
            raise ValueError(f"Professional Tax slab line {n}: 'to' is below 'from'")
        slabs.append((lo, hi, amt))
    return slabs


def pt_for(slabs, gross):
    for lo, hi, amt in slabs:
        if gross >= lo and (hi is None or gross <= hi):
            return r0(amt)
    return 0


def settings_for(company):
    return {"divisor_mode": company["wage_divisor"], "hours_per_day": dec(company["hours_per_day"]),
            "pf_ceiling": dec(company["pf_wage_ceiling"]), "pf_on_actual": bool(company["pf_on_actual"]),
            "esi_threshold": dec(company["esi_threshold"]), "pt_slabs": parse_pt_slabs(company["pt_slabs"])}


def compute_line(emp, summ, inp, st, year, month):
    """Pure calculation for one employee. emp: salary fields; summ: attendance.summarise(); inp: monthly inputs."""
    dim = days_in_month(year, month)
    divisor = {"Calendar days": dim, "30 days": 30, "26 days": 26}[st["divisor_mode"]]
    rates = [dec(emp["basic"]), dec(emp["da"]), dec(emp["hra"]), dec(emp["other_allowance"])]
    rate_sum = sum(rates)
    hpd = st["hours_per_day"]
    present, lop = dec(summ["present"]), dec(summ["absent"])
    pl, ne = dec(summ["paid_leave"]), summ["not_employed"]

    if emp["salary_type"] == "MONTHLY":
        employed = dec(dim - ne)
        paid_days = max(D(0), min(D(divisor), employed) - lop)
        factor = paid_days / D(divisor)
        earned = [r0(r * factor) for r in rates]
        fixed_monthly_gross = rate_sum
        hourly = rate_sum / (D(divisor) * hpd)
    else:
        paid_days = present + pl + dec(summ.get("paid_holiday", 0))
        earned = [r0(r * paid_days) for r in rates]
        fixed_monthly_gross = rate_sum * 26
        hourly = rate_sum / hpd

    ot_hours = dec(inp["ot_hours"])
    ot_amount = r0(ot_hours * hourly * 2)
    earned_total = sum(earned)
    gross = earned_total + ot_amount

    pf_wages = D(earned[0] + earned[1])
    pf_base = pf_wages if st["pf_on_actual"] else min(pf_wages, st["pf_ceiling"])
    pf_ee = r0(pf_base * PF_RATE) if emp["pf_applicable"] else 0
    pf_er = pf_ee

    esi_ok = bool(emp["esi_applicable"]) and fixed_monthly_gross <= st["esi_threshold"] and earned_total > 0
    esi_ee = ceil0(D(earned_total) * ESI_EE) if esi_ok else 0
    esi_er = ceil0(D(earned_total) * ESI_ER) if esi_ok else 0

    pt = pt_for(st["pt_slabs"], D(gross)) if emp["pt_applicable"] and gross > 0 else 0
    advance, other = r0(dec(inp["advance"])), r0(dec(inp["other_deduction"]))
    total_ded = pf_ee + esi_ee + pt + advance + other
    net = gross - total_ded
    return {
        "days_in_month": dim, "divisor": divisor,
        "present_days": float(summ["present"]), "paid_leave": float(summ["paid_leave"]),
        "weekly_offs": float(summ["weekly_off"] + summ.get("paid_holiday", 0)), "absent_days": float(summ["absent"]),
        "paid_days": float(paid_days), "ot_hours": float(ot_hours),
        "rate_basic": float(rates[0]), "rate_da": float(rates[1]), "rate_hra": float(rates[2]),
        "rate_other": float(rates[3]),
        "earned_basic": earned[0], "earned_da": earned[1], "earned_hra": earned[2], "earned_other": earned[3],
        "ot_amount": ot_amount, "gross": gross,
        "pf_employee": pf_ee, "esi_employee": esi_ee, "prof_tax": pt, "advance": advance,
        "other_deduction": other, "total_deductions": total_ded, "net_pay": net,
        "pf_employer": pf_er, "esi_employer": esi_er,
        "warning": "Deductions exceed earnings - net pay is negative" if net < 0 else None,
    }


LINE_COLS = ["days_in_month", "divisor", "present_days", "paid_leave", "weekly_offs", "absent_days", "paid_days",
             "ot_hours", "rate_basic", "rate_da", "rate_hra", "rate_other", "earned_basic", "earned_da",
             "earned_hra", "earned_other", "ot_amount", "gross", "pf_employee", "esi_employee", "prof_tax",
             "advance", "other_deduction", "total_deductions", "net_pay", "pf_employer", "esi_employer", "warning"]

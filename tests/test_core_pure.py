"""Pure-logic tests (no database / web framework needed): python -m pytest tests/test_core_pure.py"""
import unittest
from datetime import date

from app.core import attendance_engine as ae, payroll_engine as pe, validators as v
from app.core.forms import clean_values
from app.core.specs import COMPANY_FIELDS
from app.core.util import amount_in_words, inr


def emp(**kw):
    d = dict(salary_type="MONTHLY", basic=8000, da=1000, hra=0, other_allowance=0, pf_applicable=True,
             esi_applicable=True, pt_applicable=True)
    d.update(kw)
    return d


ST = dict(divisor_mode="Calendar days", hours_per_day=pe.D(8), pf_ceiling=pe.D(15000), pf_on_actual=False,
          esi_threshold=pe.D(21000), pt_slabs=pe.parse_pt_slabs("0-20833:0\n20834-*:200"))
INP0 = dict(ot_hours=0, advance=0, other_deduction=0)


class Pure(unittest.TestCase):
    def test_attendance_generation(self):
        r = ae.build_month(2026, 10, 24, "Sunday", "09:00", "18:00")
        s = ae.summarise(r)
        self.assertEqual((s["present"], s["absent"], s["weekly_off"], len(r)), (24, 3, 4, 31))
        r = ae.build_month(2026, 10, 20.5, "Sunday", "09:00", "17:00")
        self.assertEqual(ae.summarise(r)["present"], 20.5)
        self.assertEqual([x for x in r if x["status"] == "HD"][0]["out_time"], "13:00")
        r = ae.build_month(2026, 10, 29, "Sunday", "22:00", "06:00")
        self.assertEqual((ae.summarise(r)["present"], ae.summarise(r)["weekly_off"]), (29, 2))
        with self.assertRaises(ValueError):
            ae.build_month(2026, 10, 20, "Sunday", "09:00", "18:00", joining=date(2026, 10, 15))

    def test_salary_proration_ot_esi(self):
        summ = {"present": 24, "absent": 3, "weekly_off": 4, "paid_leave": 0, "not_employed": 0}
        l = pe.compute_line(emp(), summ, dict(ot_hours=10, advance=500, other_deduction=0), ST, 2026, 10)
        self.assertEqual((l["paid_days"], l["earned_basic"], l["earned_da"], l["ot_amount"]), (28, 7226, 903, 726))
        self.assertEqual(l["esi_employee"], 61)          # OT excluded from ESI wages, rounded up
        self.assertEqual(l["pf_employee"], round(0.12 * (7226 + 903)))
        self.assertEqual(l["net_pay"], l["gross"] - l["pf_employee"] - 61 - 500)

    def test_pf_ceiling_esi_threshold_pt_daily(self):
        full = {"present": 27, "absent": 0, "weekly_off": 4, "paid_leave": 0, "not_employed": 0}
        l = pe.compute_line(emp(basic=30000, da=5000, hra=5000), full, INP0, ST, 2026, 10)
        self.assertEqual((l["pf_employee"], l["esi_employee"], l["prof_tax"], l["gross"]), (1800, 0, 200, 40000))
        d = {"present": 20, "absent": 7, "weekly_off": 4, "paid_leave": 0, "not_employed": 0}
        l = pe.compute_line(emp(salary_type="DAILY", basic=500, da=0, esi_applicable=False), d, INP0, ST, 2026, 10)
        self.assertEqual((l["gross"], l["pf_employee"]), (10000, 1200))

    def test_child_labour_rules(self):
        base = dict(date_of_birth=date(2011, 6, 1), date_of_employment=date(2026, 1, 1), work_from="09:00",
                    work_to="12:00", hazardous=False, rest_minutes=0)
        e, w = v.child_labour(dict(base), None, None)
        self.assertEqual(e, [])
        self.assertTrue(w)                                  # no fitness certificate
        e, _ = v.child_labour(dict(base, date_of_birth=date(2014, 1, 1)), None, None)
        self.assertTrue(e)                                  # under 14
        e, _ = v.child_labour(dict(base, work_to="15:30"), None, None)
        self.assertTrue(e)                                  # >4.5h
        e, _ = v.child_labour(dict(base, work_from="21:00", work_to="23:00"), None, None)
        self.assertTrue(e)                                  # night

    def test_forms_and_words(self):
        vals = {"name": "Acme", "short_code": "AC", "factory_licence_no": "L1", "address1": "x", "city": "c",
                "state": "Punjab", "occupier_name": "o", "manager_name": "m", "wage_divisor": "Calendar days",
                "hours_per_day": "8", "pf_wage_ceiling": "15000", "esi_threshold": "21000",
                "licence_valid_from": "2026-01-01"}
        c, errs = clean_values(COMPANY_FIELDS, vals)
        self.assertEqual(errs, [])
        self.assertEqual(c["licence_valid_from"], date(2026, 1, 1))
        _, errs = clean_values(COMPANY_FIELDS, {**vals, "name": "", "hours_per_day": "x"})
        self.assertEqual(len(errs), 2)
        self.assertEqual(inr(1234567), "12,34,567")
        self.assertEqual(amount_in_words(12345), "Rupees Twelve Thousand Three Hundred Forty Five Only")


if __name__ == "__main__":
    unittest.main()

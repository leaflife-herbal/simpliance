"""Tests for holidays, bilingual labels, notice grouping, PF/ESI statements, expiry helpers."""
import unittest
from datetime import date

from app import reports
from app.core import attendance_engine as ae, payroll_engine as pe
from app.core.i18n import bi, bi_day, lang_code
from app.core.notice import group_shifts
from app.core.util import days_left, expiry_level

ST = dict(divisor_mode="Calendar days", hours_per_day=pe.D(8), pf_ceiling=pe.D(15000), pf_on_actual=False,
          esi_threshold=pe.D(21000), pt_slabs=[])
CO = dict(name="Acme", address1="x", address2="", city="Ludhiana", district="", state="Punjab", pincode="",
          factory_licence_no="L1", factory_registration_no="", occupier_name="o", manager_name="m")


def emp(**kw):
    d = dict(salary_type="MONTHLY", basic=9000, da=1000, hra=0, other_allowance=0, pf_applicable=True,
             esi_applicable=True, pt_applicable=True)
    d.update(kw)
    return d


class Pending(unittest.TestCase):
    def test_holidays_are_paid_and_not_working_days(self):
        hol = {date(2026, 10, 2), date(2026, 10, 20)}           # Fri and Tue
        r = ae.build_month(2026, 10, 25, "Sunday", "09:00", "18:00", holidays=hol)
        s = ae.summarise(r)
        self.assertEqual((s["paid_holiday"], s["present"], s["absent"], s["weekly_off"]), (2, 25, 0, 4))
        st = {x["date"]: x["status"] for x in r}
        self.assertEqual((st["2026-10-02"], st["2026-10-20"], st["2026-10-04"]), ("PH", "PH", "WO"))
        r = ae.build_month(2026, 10, 27, "Sunday", "09:00", "18:00", holidays=hol)   # 25 working + 2 worked on off days
        self.assertEqual(ae.summarise(r)["present"], 27)
        r = ae.build_month(2026, 10, 20, "Sunday", "09:00", "18:00", holidays={date(2026, 10, 4)})  # holiday on Sunday = WO
        self.assertEqual(ae.summarise(r)["paid_holiday"], 0)

    def test_holiday_pay(self):
        summ = {"present": 20, "absent": 5, "weekly_off": 4, "paid_leave": 0, "paid_holiday": 2, "not_employed": 0}
        inp = dict(ot_hours=0, advance=0, other_deduction=0)
        daily = pe.compute_line(emp(salary_type="DAILY", basic=500, da=0, esi_applicable=False), summ, inp, ST, 2026, 10)
        self.assertEqual(daily["gross"], 22 * 500)               # 20 present + 2 paid holidays
        monthly = pe.compute_line(emp(), summ, inp, ST, 2026, 10)
        self.assertEqual(monthly["paid_days"], 26)               # 31 days - 5 absent; holidays are not loss of pay

    def test_labels_and_language(self):
        self.assertEqual(bi("net", "en"), "NET PAY")
        self.assertEqual(bi("net", "hi"), "NET PAY / शुद्ध वेतन")
        self.assertIn("ਸ਼ੁੱਧ", bi("net", "pa"))
        self.assertEqual(bi_day("Sunday", "hi"), "Sunday / रविवार")
        self.assertEqual(lang_code("English + Punjabi"), "pa")
        self.assertEqual(lang_code(None), "hi")
        self.assertEqual(lang_code("English only", "pa"), "pa")

    def test_notice_groups(self):
        e = [dict(department="Press", shift_in="09:00", shift_out="18:00", weekly_off="Sunday") for _ in range(3)]
        e += [dict(department=None, shift_in="21:00", shift_out="06:00", weekly_off="Sunday")]
        g = group_shifts(e)
        self.assertEqual([(x["group"], x["count"]) for x in g], [("Press", 3), ("All workers", 1)])

    def test_statements(self):
        lines = []
        for i, basic in enumerate((10000, 30000), 1):
            e = emp(basic=basic, da=2000)
            l = pe.compute_line(e, {"present": 27, "absent": 0, "weekly_off": 4, "paid_leave": 0, "not_employed": 0},
                                dict(ot_hours=0, advance=0, other_deduction=0), ST, 2026, 10)
            lines.append({**l, "emp_code": f"E{i}", "emp_name": f"W{i}", "uan": "1000", "esic_no": "55"})
        pf = reports.pf_statement(lines, 15000, 2026, 10)
        self.assertEqual(len(pf.rows), 2)
        self.assertEqual(pf.rows[1][7], 1800)                    # 12% of 15,000 ceiling
        self.assertEqual(pf.rows[1][8], 1250)                    # EPS 8.33% of 15,000
        self.assertEqual(pf.rows[1][9], 1800 - 1250)
        esi = reports.esi_statement(lines, 2026, 10)
        self.assertEqual(len(esi.rows), 1)                       # second employee earns above the ESI limit
        for rep in (pf, esi):
            self.assertTrue(reports.report_pdf(CO, rep).startswith(b"%PDF"))
            self.assertTrue(reports.report_xlsx(CO, rep).startswith(b"PK"))

    def test_expiry(self):
        t = date(2026, 11, 4)
        self.assertEqual(days_left(date(2026, 12, 4), t), 30)
        self.assertEqual([expiry_level(x) for x in (None, 200, 30, -1)], ["none", "ok", "warn", "bad"])


class Templates(unittest.TestCase):
    def setUp(self):
        from jinja2 import Environment, FileSystemLoader
        from app.core import i18n
        from app.core.util import MONTHS, fmt_date, inr, num
        self.env = Environment(loader=FileSystemLoader("app/templates"), autoescape=True)
        self.env.filters.update(dmy=fmt_date, inr=inr, num=num)
        self.env.globals.update(APP_NAME="X", ROLE_LABELS={"OPERATOR": "O", "SUPER_ADMIN": "S"}, MONTHS=MONTHS,
                                bi=i18n.bi, bi_day=i18n.bi_day, LANG_NAMES=i18n.LANG_NAMES)
        U = type("U", (), dict(full_name="Op", role="OPERATOR", is_super=False, can_view_salary=True,
                               can_write_salary=True, must_change_password=False))
        self.base = dict(csrf="t", flash=[], errors=[], user=U(),
                         c=type("X", (), dict(company=type("C", (), dict(name="Acme"))(), can_edit=True, cid=1))())
        self.co = type("Co", (), dict(name="Acme", address1="Plot 5", address2="", city="Ludhiana", state="Punjab",
                                      pincode="141001", factory_licence_no="LDH/1", manager_name="K Kumar"))()

    def test_notice_languages(self):
        g = group_shifts([dict(department="Press", shift_in="09:00", shift_out="18:00", weekly_off="Sunday")])
        for lang, word in (("en", "NOTICE OF PERIODS OF WORK FOR ADULTS"), ("hi", "वयस्क श्रमिकों"), ("pa", "ਬਾਲਗ ਕਾਮਿਆਂ")):
            out = self.env.get_template("print_notice.html").render(**self.base, co=self.co, groups=g, lang=lang,
                                                                     rest="13:00 to 13:30", on="2026-11-04", path="/print/notice")
            self.assertIn(word, out)
            self.assertIn("13:00 to 13:30", out)
        self.assertIn("रविवार", self.env.get_template("print_notice.html").render(
            **self.base, co=self.co, groups=g, lang="hi", rest="", on="2026-11-04", path="/p"))

    def test_slip_and_other_pages(self):
        line = dict(emp_code="E1", emp_name="Ramesh", name_local="रमेश", designation="Fitter", department="Shop",
                    days_in_month=31, paid_days=28.0, present_days=24, absent_days=3, weekly_offs=4, ot_hours=2,
                    earned_basic=7226, earned_da=903, earned_hra=0, earned_other=0, ot_amount=100, gross=8229,
                    pf_employee=975, esi_employee=62, prof_tax=0, advance=0, other_deduction=0, total_deductions=1037,
                    net_pay=7192, words="Rupees Seven Thousand One Hundred Ninety Two Only")
        out = self.env.get_template("print_slips.html").render(**self.base, co=self.co, lines=[line], y=2026, m=10,
                                                                lang="hi", emp=0, path="/print/slips")
        self.assertIn("वेतन पर्ची", out)
        self.assertIn("रमेश", out)
        out = self.env.get_template("print_slips.html").render(**self.base, co=self.co, lines=[line], y=2026, m=10,
                                                                lang="en", emp=0, path="/print/slips")
        self.assertNotIn("रमेश", out)
        out = self.env.get_template("holidays.html").render(**self.base, y=2026, rows=[
            type("H", (), dict(id=1, holiday_date=date(2026, 11, 8), name="Diwali"))()])
        self.assertIn("Diwali", out)
        dash = dict(licence_level="warn", licence_days=30, licence_to=date(2026, 12, 4), employees=12, pending_notices=1,
                    open_dangerous=0, accidents_year=2, prev_salary="draft", prev_month=10, prev_year=2026)
        co = type("C2", (), dict(id=1, name="Acme", short_code="AC", factory_licence_no="L", city="L", state="P"))()
        out = self.env.get_template("home.html").render(**self.base, companies=[co], current=co, read_only="", dash=dash,
                                                         lic_due=[], sub_due=[])
        self.assertIn("30 days", out)
        sa = type("S", (), dict(full_name="S", role="SUPER_ADMIN", is_super=True, can_view_salary=True,
                                can_write_salary=False, must_change_password=False))()
        out = self.env.get_template("home.html").render(**{**self.base, "user": sa}, companies=[], current=None,
                                                         read_only="", dash=None, lic_due=[(co, -3)], sub_due=[])
        self.assertIn("Expired 3 days ago", out)


if __name__ == "__main__":
    unittest.main()


class Leave(unittest.TestCase):
    def test_accrual_and_balance(self):
        from app.core.leave import accrue, leave_row
        self.assertEqual([accrue(x) for x in (19, 29, 30, 39, 40, 0)], [1, 1, 2, 2, 2, 0])   # half-day rule
        r = leave_row(3, {"P": 200, "HD": 2, "PL": 4}, 20)       # worked 205 -> 10.25 -> 10 accrued
        self.assertEqual((r["days_worked"], r["accrued"], r["taken"], r["balance"]), (205, 10, 4, 9))
        self.assertEqual(leave_row(0, {}, 20)["balance"], 0)

    def test_leave_template_and_report(self):
        from jinja2 import Environment, FileSystemLoader
        from app.core.util import MONTHS, fmt_date, inr, num
        env = Environment(loader=FileSystemLoader("app/templates"), autoescape=True)
        env.filters.update(dmy=fmt_date, inr=inr, num=num)
        env.globals.update(APP_NAME="X", ROLE_LABELS={"OPERATOR": "O"}, MONTHS=MONTHS)
        U = type("U", (), dict(full_name="Op", role="OPERATOR", is_super=False, can_view_salary=True,
                               can_write_salary=True, must_change_password=False))()
        c = type("X", (), dict(company=type("C", (), dict(name="Acme"))(), can_edit=True, cid=1))()
        rows = [dict(employee_id=1, emp_code="E1", name="W", opening=3.0, days_worked=205, accrued=10, taken=4, balance=-1.5)]
        out = env.get_template("leave.html").render(csrf="t", flash=[], errors=[], user=U, c=c, y=2026, rows=rows, n=20)
        self.assertIn("badtxt", out)
        rep = reports.leave_report(rows, 2026, 20)
        self.assertTrue(reports.report_pdf(CO, rep).startswith(b"%PDF"))

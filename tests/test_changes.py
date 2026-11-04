"""Tests for: attendance time variation, Excel import template/parser, password rule.
Run: python -m unittest tests.test_changes"""
import unittest
from datetime import date, time
from io import BytesIO

from openpyxl import load_workbook

from app.core import attendance_engine as ae, importer
from app.core.forms import clean_values
from app.core.specs import EMPLOYEE_FIELDS
from app.core.util import minutes_between, t2m


class Variation(unittest.TestCase):
    def test_times_vary_within_range_and_repeat(self):
        r1 = ae.build_month(2026, 10, 27, "Sunday", "09:00", "18:00", variation=10, seed="1-5")
        r2 = ae.build_month(2026, 10, 27, "Sunday", "09:00", "18:00", variation=10, seed="1-5")
        self.assertEqual(r1, r2)                                   # repeatable
        pres = [x for x in r1 if x["status"] == "P"]
        for x in pres:
            self.assertTrue(530 <= t2m(x["in_time"]) <= 540)       # 08:50-09:00, never late
            self.assertTrue(1080 <= t2m(x["out_time"]) <= 1090)    # 18:00-18:10, never early
        self.assertGreater(len({(x["in_time"], x["out_time"]) for x in pres}), 8)
        for a, b in zip(pres, pres[1:]):                           # not identical on consecutive present days
            self.assertNotEqual((a["in_time"], a["out_time"]), (b["in_time"], b["out_time"]))
        other = ae.build_month(2026, 10, 27, "Sunday", "09:00", "18:00", variation=10, seed="1-6")
        self.assertNotEqual(r1, other)                             # different employee, different pattern

    def test_zero_variation_is_exact_and_night_shift(self):
        r = ae.build_month(2026, 10, 27, "Sunday", "09:00", "18:00", variation=0)
        self.assertTrue(all(x["in_time"] == "09:00" and x["out_time"] == "18:00" for x in r if x["status"] == "P"))
        n = ae.build_month(2026, 10, 27, "Sunday", "22:00", "06:00", variation=10, seed="x")
        for x in n:
            if x["status"] == "P":
                self.assertTrue(480 <= minutes_between(x["in_time"], x["out_time"]) <= 500)   # 8h to 8h20


class Import(unittest.TestCase):
    def _fill(self, rows):
        wb = load_workbook(BytesIO(importer.build_template()))
        ws = wb["Employees"]
        heads = {str(c.value).replace(" *", "").strip().lower(): c.column for c in ws[1]}
        for r, rec in enumerate(rows, start=2):
            for label, v in rec.items():
                ws.cell(r, heads[label.lower()], v)
        buf = BytesIO()
        wb.save(buf)
        return buf.getvalue()

    def test_template_has_every_field_and_instructions(self):
        wb = load_workbook(BytesIO(importer.build_template()))
        self.assertEqual(wb.sheetnames, ["Employees", "Instructions"])
        self.assertEqual(len([c for c in wb["Employees"][1] if c.value]), len(EMPLOYEE_FIELDS))

    def test_parse_and_validate(self):
        data = self._fill([
            {"Employee code": "E1", "Full name": "Asha Devi", "Gender": "female", "Date of birth": date(1992, 3, 4),
             "Date of joining": "01-04-2022", "Shift in-time (HH:MM)": time(9, 0), "Shift out-time (HH:MM)": "18:30",
             "Weekly off day": "sunday", "Salary type": "MONTHLY", "Basic (per month, or per day if DAILY)": 12000,
             "Dearness allowance": 1500, "Mobile": 9876543210},
            {"Employee code": "E2", "Full name": "Ravi", "Gender": "Male", "Date of birth": "15/08/1990",
             "Date of joining": date(2023, 1, 5), "Shift in-time (HH:MM)": "9:30", "Shift out-time (HH:MM)": "18:00",
             "Weekly off day": "Sunday", "Salary type": "DAILY", "Basic (per month, or per day if DAILY)": 450,
             "PF applicable": "No"}])
        rows, errs = importer.parse_workbook(data)
        self.assertEqual(errs, [])
        self.assertEqual(len(rows), 2)
        a, b = rows[0][1], rows[1][1]
        self.assertEqual((a["gender"], a["weekly_off"], a["shift_in"], a["mobile"]), ("Female", "Sunday", "09:00", "9876543210"))
        self.assertEqual((a["date_of_birth"], a["date_of_joining"]), ("1992-03-04", "2022-04-01"))
        self.assertEqual((b["date_of_birth"], b["shift_in"], b["pf_applicable"], b["is_active"]), ("1990-08-15", "09:30", "", "1"))
        for _, rec in rows:
            clean, e = clean_values(EMPLOYEE_FIELDS, rec)
            self.assertEqual(e, [])
        self.assertEqual(clean_values(EMPLOYEE_FIELDS, b)[0]["pf_applicable"], False)

    def test_bad_rows_reported(self):
        data = self._fill([{"Employee code": "E9", "Full name": "X", "Gender": "Male", "Date of birth": "not a date",
                            "Date of joining": "01-04-2022", "Shift in-time (HH:MM)": "09:00",
                            "Shift out-time (HH:MM)": "99:99", "Weekly off day": "Sunday", "Salary type": "MONTHLY",
                            "Basic (per month, or per day if DAILY)": 100, "PF applicable": "maybe"}])
        rows, errs = importer.parse_workbook(data)
        self.assertTrue(any("PF applicable" in e for e in errs))
        _, e = clean_values(EMPLOYEE_FIELDS, rows[0][1])
        self.assertTrue(any("date" in x.lower() for x in e) and any("time" in x.lower() for x in e))
        _, errs = importer.parse_workbook(b"not an excel file")
        self.assertTrue(errs)


class Password(unittest.TestCase):
    def test_min_six(self):
        try:
            from app import security
        except ModuleNotFoundError:
            self.skipTest("argon2-cffi not installed in this environment")
        self.assertIsNotNone(security.password_problem("ab1"))
        self.assertIsNotNone(security.password_problem("abcdef"))      # needs a digit
        self.assertIsNone(security.password_problem("abc123"))


if __name__ == "__main__":
    unittest.main()

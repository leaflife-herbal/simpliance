"""EPFO ECR and ESIC upload files:  python -m unittest tests.test_statutory"""
import unittest
from datetime import date
from io import BytesIO

from openpyxl import load_workbook

from app import reports
from app.core import payroll_engine as pe, statutory

ST = dict(divisor_mode="Calendar days", hours_per_day=pe.D(8), pf_ceiling=pe.D(15000), pf_on_actual=False,
          esi_threshold=pe.D(21000), pt_slabs=[])
FULL = {"present": 27, "absent": 0, "weekly_off": 4, "paid_leave": 0, "not_employed": 0}
INP = dict(ot_hours=0, advance=0, other_deduction=0)


def mk(i, basic, da, summ=FULL, uan="100257274743", ip="2504766611", name="Ramesh Kumar", st=ST, **kw):
    e = dict(salary_type="MONTHLY", basic=basic, da=da, hra=0, other_allowance=0, pf_applicable=True,
             esi_applicable=True, pt_applicable=True)
    e.update(kw)
    l = pe.compute_line(e, summ, INP, st, 2026, 10)
    l.update(employee_id=i, emp_code=f"E{i}", emp_name=name, uan=uan, esic_no=ip)
    return l, dict(id=i, uan=uan, esic_no=ip, esi_applicable=True, date_of_leaving=None)


class Statutory(unittest.TestCase):
    def test_ecr_line_and_rules(self):
        l1, e1 = mk(1, 10000, 2000, uan="100257274743")
        l2, e2 = mk(2, 30000, 5000, uan="100427601130", name="Asha D'Souza")
        rows, warns = statutory.ecr_rows([l1, l2], {1: e1, 2: e2}, 15000, False)
        self.assertEqual(rows[0], ["100257274743", "RAMESH KUMAR", 12000, 12000, 12000, 12000, 1440, 1000, 440, 0, 0])
        r2 = rows[1]                                               # wages above the ceiling
        self.assertEqual((r2[2], r2[3], r2[4], r2[5], r2[6], r2[7], r2[8]), (35000, 15000, 15000, 15000, 1800, 1250, 550))
        self.assertEqual(r2[1], "ASHA D SOUZA")
        self.assertTrue(any("name written as" in w for w in warns))
        txt = statutory.ecr_text(rows)
        first = txt.split("\r\n")[0].split("#~#")
        self.assertEqual(len(first), 11)
        self.assertEqual(first[0], "100257274743")
        for r in rows:                                             # EPFO validation rules
            self.assertTrue(r[3] <= r[2] and r[4] <= 15000 and r[5] <= 15000 and r[4] <= r[3])
            self.assertEqual(r[6], r[7] + r[8])                    # employee 12% = EPS + EPF difference

    def test_ecr_actual_wages_and_missing_uan(self):
        l, e = mk(1, 30000, 5000, st={**ST, "pf_on_actual": True})
        rows, _ = statutory.ecr_rows([l], {1: e}, 15000, True)
        self.assertEqual((rows[0][3], rows[0][4], rows[0][6], rows[0][7], rows[0][8]), (35000, 15000, 4200, 1250, 2950))
        l, e = mk(2, 10000, 2000, uan="123")
        rows, warns = statutory.ecr_rows([l], {2: e}, 15000, False)
        self.assertEqual(rows, [])
        self.assertTrue(any("UAN" in w for w in warns))

    def test_ncp_days(self):
        half = {"present": 20.5, "absent": 6.5, "weekly_off": 4, "paid_leave": 0, "not_employed": 0}
        l, e = mk(1, 10000, 2000, summ=half)
        rows, _ = statutory.ecr_rows([l], {1: e}, 15000, False)
        self.assertEqual(rows[0][9], 7)                            # 6.5 loss-of-pay days rounds up to 7

    def test_esic_rows_and_zero_wage(self):
        l1, e1 = mk(1, 10000, 2000)
        l2, e2 = mk(2, 30000, 5000, ip="2504766612")               # above ESI limit: not covered
        zero = {"present": 0, "absent": 27, "weekly_off": 4, "paid_leave": 0, "not_employed": 0}
        l3, e3 = mk(3, 10000, 2000, summ={**zero}, ip="2504766613")
        l3["paid_days"] = 0                                        # whole month without pay
        l3["gross"] = 0
        e3["date_of_leaving"] = date(2026, 10, 12)
        l4, e4 = mk(4, 10000, 2000, ip="25047")                    # bad IP number
        rows, warns = statutory.esic_rows([l1, l2, l3, l4], {1: e1, 2: e2, 3: e3, 4: e4}, 2026, 10)
        self.assertEqual(rows[0], ["2504766611", "RAMESH KUMAR", "31", "12000", "", ""])
        self.assertEqual(rows[1], ["2504766613", "RAMESH KUMAR", "0", "0", "2", "12/10/2026"])
        self.assertEqual(len(rows), 2)
        self.assertTrue(any("IP number" in w for w in warns))

    def test_excel_and_text_outputs(self):
        l1, e1 = mk(1, 10000, 2000)
        rows, warns = statutory.esic_rows([l1], {1: e1}, 2026, 10)
        wb = load_workbook(BytesIO(reports.esic_xlsx(rows, warns)))
        ws = wb["MC"]
        self.assertEqual([c.value for c in ws[1]], statutory.ESIC_HEADERS)
        self.assertTrue(all(c.number_format == "@" and (c.value is None or isinstance(c.value, str)) for c in ws[2]))
        self.assertIn("Notes", wb.sheetnames)
        rows, warns = statutory.ecr_rows([l1], {1: e1}, 15000, False)
        wb = load_workbook(BytesIO(reports.ecr_xlsx(rows, warns)))
        self.assertEqual([c.value for c in wb["ECR"][1]], statutory.ECR_HEADERS)
        data = reports.ecr_text_bytes(rows)
        self.assertEqual(data.decode().strip().count("#~#"), 10)
        self.assertFalse(data.decode().startswith("UAN"))          # no header row in the text file


if __name__ == "__main__":
    unittest.main()

"""Exports built in memory from plain dicts (no database): python -m unittest tests.test_reports"""
import unittest
from datetime import date

from app import reports
from app.core import attendance_engine as ae, payroll_engine as pe

CO = dict(name="Acme Forge", address1="Plot 5", address2="", city="Ludhiana", district="", state="Punjab", pincode="",
          factory_licence_no="LDH/1", factory_registration_no="", occupier_name="R", manager_name="K")
ST = dict(divisor_mode="Calendar days", hours_per_day=pe.D(8), pf_ceiling=pe.D(15000), pf_on_actual=False,
          esi_threshold=pe.D(21000), pt_slabs=[])


class Reports(unittest.TestCase):
    def test_all_downloads(self):
        emps, att, lines = [], {}, []
        for i in range(1, 4):
            e = dict(id=i, emp_code=f"E{i}", name=f"Worker {i}", designation="Fitter", department="Shop",
                     shift_in="09:00", shift_out="18:00", weekly_off="Sunday", salary_type="MONTHLY", basic=9000,
                     da=1000, hra=0, other_allowance=0, pf_applicable=True, esi_applicable=True, pt_applicable=True,
                     uan="", esic_no="", gender="Male", father_name="", date_of_birth=date(1990, 1, 1),
                     date_of_joining=date(2020, 1, 1), skill_category=None)
            emps.append(e)
            rows = [dict(att_date=r["date"], status=r["status"], in_time=r["in_time"], out_time=r["out_time"],
                         is_generated=True) for r in ae.build_month(2026, 10, 24 + i % 3, "Sunday", "09:00", "18:00")]
            att[i] = rows
            l = pe.compute_line(e, ae.summarise(rows), dict(ot_hours=2, advance=0, other_deduction=0), ST, 2026, 10)
            lines.append({**l, "emp_code": e["emp_code"], "emp_name": e["name"], "designation": "Fitter",
                          "department": "Shop", "uan": "", "esic_no": "", "employee_id": i})
        pdfs = [reports.slips_pdf(CO, 2026, 10, lines),
                reports.report_pdf(CO, reports.salary_register(lines, 2026, 10)),
                reports.report_pdf(CO, reports.muster_report(emps, att, 2026, 10)),
                reports.attendance_pdf(CO, 2026, 10, reports.attendance_blocks(emps, att)),
                reports.report_pdf(CO, reports.employee_report(emps))]
        xlsx = [reports.slips_xlsx(CO, 2026, 10, lines),
                reports.report_xlsx(CO, reports.salary_register(lines, 2026, 10)),
                reports.attendance_xlsx(CO, 2026, 10, reports.attendance_blocks(emps, att),
                                        reports.muster_report(emps, att, 2026, 10))]
        for b in pdfs:
            self.assertTrue(b.startswith(b"%PDF") and len(b) > 1500)
        for b in xlsx:
            self.assertTrue(b.startswith(b"PK") and len(b) > 1500)


if __name__ == "__main__":
    unittest.main()

"""Register report/templates without a database:  python -m unittest tests.test_registers_pure"""
import unittest
from datetime import date

from jinja2 import Environment, FileSystemLoader

from app import reports
from app.core import validators
from app.core.forms import clean_values
from app.core.specs import REGISTERS, REGISTER_BY_KEY
from app.core.util import MONTHS, fmt_date, inr, num

CO = dict(name="Acme", address1="x", address2="", city="Ludhiana", district="", state="Punjab", pincode="",
          factory_licence_no="L1", factory_registration_no="", occupier_name="o", manager_name="m")
RAW = {
    "child_labour": dict(name="Kid", date_of_birth="2011-06-01", date_of_employment="2026-01-01", work_from="09:00",
                         work_to="12:00", certificate_no="C-1"),
    "accidents": dict(accident_date="2026-10-02", injured_name="Ravi", nature_of_injury="Cut",
                      severity="Serious (disabled 48+ hrs)", days_lost="3", notice_date="2026-10-03"),
    "loss_damage": dict(incident_date="2026-10-02", asset_type="Tools", item="Drill", nature="Loss",
                        estimated_loss="4500"),
    "dangerous": dict(occurrence_date="2026-10-02", location="Boiler", description="Leak", cause="Gasket",
                      corrective_action="Replaced", status="Open", notice_date="2026-10-03"),
    "other": dict(occurrence_date="2026-10-02", occurrence_type="Fire / evacuation drill", description="Drill"),
}


class Registers(unittest.TestCase):
    def test_every_register_validates_and_reports(self):
        for spec in REGISTERS:
            clean, errs = clean_values(spec.fields, RAW[spec.key])
            self.assertEqual(errs, [], spec.key)
            e, w = validators.BY_REGISTER[spec.key](clean, 1, None)
            self.assertEqual(e, [], (spec.key, e))
            row = {f.key: clean.get(f.key) for f in spec.fields}
            rep = reports.register_report(spec, [row])
            self.assertEqual(len(rep.rows), 1)
            self.assertTrue(reports.report_pdf(CO, rep).startswith(b"%PDF"))
            self.assertTrue(reports.report_xlsx(CO, rep).startswith(b"PK"))
            self.assertTrue(reports.report_pdf(CO, reports.register_detail(spec, row)).startswith(b"%PDF"))
        clean, _ = clean_values(REGISTER_BY_KEY["child_labour"].fields, RAW["child_labour"])
        validators.child_labour(clean, 1, None)
        self.assertEqual((clean["category"], clean["daily_hours"]), ("Child (14-15)", 3.0))

    def test_rules(self):
        s = REGISTER_BY_KEY["accidents"]
        c, _ = clean_values(s.fields, {**RAW["accidents"], "severity": "Fatal", "notice_date": ""})
        e, w = validators.accident(c, 1, None)
        self.assertTrue(w and not e)                      # fatal without notice -> warning
        c, _ = clean_values(s.fields, {**RAW["accidents"], "notice_date": "2026-10-01"})
        self.assertTrue(validators.accident(c, 1, None)[0])   # notice before accident -> error
        s = REGISTER_BY_KEY["child_labour"]
        c, _ = clean_values(s.fields, {**RAW["child_labour"], "hazardous": "1"})
        self.assertTrue(validators.child_labour(c, 1, None)[0])

    def test_templates_render(self):
        env = Environment(loader=FileSystemLoader("app/templates"), autoescape=True)
        env.filters.update(dmy=fmt_date, inr=inr, num=num)
        env.globals.update(APP_NAME="X", ROLE_LABELS={"OPERATOR": "O"}, MONTHS=MONTHS)
        user = type("U", (), dict(full_name="Op", role="OPERATOR", is_super=False, can_view_salary=True,
                                  can_write_salary=True, must_change_password=False))()
        co = type("C", (), dict(name="Acme"))()
        c = type("X", (), dict(company=co, can_edit=True, cid=1))()
        base = dict(csrf="t", flash=[], errors=[], user=user, c=c)
        spec = REGISTER_BY_KEY["accidents"]
        self.assertIn("Accident Register", env.get_template("registers.html").render(**base, specs=REGISTERS))
        rep = reports.register_report(spec, [{"accident_date": date(2026, 10, 2), "injured_name": "R", "days_lost": 3}])
        out = env.get_template("register_list.html").render(**base, spec=spec, headers=rep.headers,
                                                            table=[(5, reports.display_rows(rep)[0])], date_from="", date_to="")
        self.assertIn("02-10-2026", out)
        emp = type("E", (), dict(id=7, emp_code="E1", name="Ravi"))()
        for obj in (None, type("O", (), dict(id=5))()):
            out = env.get_template("register_form.html").render(**base, spec=spec, obj=obj, fields=spec.fields,
                                                                values={"employee_id": "7"}, emps=[emp], warnings=["w"])
            self.assertIn("E1 - Ravi", out)
        child = REGISTER_BY_KEY["child_labour"]
        out = env.get_template("register_form.html").render(**base, spec=child, obj=None, fields=child.fields,
                                                            values={}, emps=[], warnings=[])
        self.assertIn("calculated on save", out)


if __name__ == "__main__":
    unittest.main()

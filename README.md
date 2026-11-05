# Factory Compliance Manager - cloud edition (Render + Aiven PostgreSQL)

FastAPI + Jinja2, SQLAlchemy 2, PostgreSQL. Business rules live in `app/core` (pure Python, tested without a
database). See docs/DEPLOY.md.

Modules
* Administration (Super Admin): organisations with licence limits, companies, users, audit log.
* Employees: master, Excel import (template download), shift times, salary structure.
* Monthly processing: days worked -> attendance register (natural in/out times) -> salary -> finalise/unlock.
* Salary: PF / ESI / Professional Tax / overtime, pay slips, salary register, muster roll - PDF and Excel.
* Factory Act registers: child & adolescent workers, accidents, loss & damage, dangerous occurrences, other
  occurrences - rule checks, print entry, PDF and Excel.

* Bilingual (English + Hindi/Punjabi) notice of work periods and pay slips, paid holidays, PF/ESI statements,
  licence/subscription renewal dashboard, per-company CSV backup, earned-leave register.

Tests: `python -m unittest tests.test_core_pure tests.test_reports tests.test_changes tests.test_registers_pure tests.test_pending`
(no database needed); `APP_ENV=development python -m pytest tests -q` for the service tests (SQLite).

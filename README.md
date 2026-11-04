# Factory Compliance Manager - cloud edition (Render + Aiven PostgreSQL)

FastAPI + Jinja2, SQLAlchemy 2, PostgreSQL. Business rules live in `app/core` (pure Python, tested without a
database). See docs/DEPLOY.md.

Build status
* Step 1 (done): login/security, organisations with licence limits, companies, users (Super Admin only).
* Step 2 (this build): employee master, monthly processing (days worked), attendance register generation and
  correction, salary calculation (PF / ESI / Professional Tax / overtime), finalise/unlock, pay slips, salary register,
  muster roll - PDF and Excel.
* Step 3 (next): the five Factory Act registers (child labour, accidents, loss & damage, dangerous occurrences, other).

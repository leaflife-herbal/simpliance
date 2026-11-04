# Factory Compliance Manager - cloud edition (Render + Aiven PostgreSQL)

FastAPI + Jinja2, SQLAlchemy 2, Alembic, PostgreSQL. Business rules live in `app/core` (pure Python, tested without
a database). See docs/DEPLOY.md.

Build status: **Step 1 of 3** - login/security, organisations with licence limits, companies, users (Super Admin only).
Step 2: employee master, monthly processing, attendance, salary and slips. Step 3: the five Factory Act registers and
PDF/Excel exports.

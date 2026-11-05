from datetime import datetime

from sqlalchemy import (BigInteger, Boolean, CheckConstraint, Column, Date, DateTime, Float, ForeignKey, Index, Integer,
                        Numeric, String, Text, UniqueConstraint, func, text)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from .core.specs import COMPANY_FIELDS, EMPLOYEE_FIELDS, REGISTERS
from .db import Base

ROLE_SUPER, ROLE_OPERATOR, ROLE_VIEWER = "SUPER_ADMIN", "OPERATOR", "VIEWER"
ROLE_LABELS = {ROLE_SUPER: "Super Admin", ROLE_OPERATOR: "Operator (data entry)", ROLE_VIEWER: "Viewer (read-only)"}
JSONType = JSON().with_variant(JSONB(), "postgresql")


def spec_column(f):
    t = f.type
    if t == "date":
        return Column(Date)
    if t == "multiline":
        return Column(Text)
    if t == "int":
        return Column(Integer)
    if t == "number":
        return Column(Numeric(12, 2))
    if t == "bool":
        return Column(Boolean, nullable=False, default=bool(f.default), server_default="true" if f.default else "false")
    if t == "time":
        return Column(String(5))
    return Column(String(255))


class Organisation(Base):
    """A customer. Licence limits live here and are controlled only by the platform Super Admin."""
    __tablename__ = "organisations"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    max_companies: Mapped[int] = mapped_column(Integer, default=1)
    max_users: Mapped[int] = mapped_column(Integer, default=5)
    valid_until: Mapped[datetime] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('SUPER_ADMIN','OPERATOR','VIEWER')", name="ck_users_role"),
        CheckConstraint("(role = 'SUPER_ADMIN') = (organisation_id IS NULL)", name="ck_users_org_for_role"),
        Index("uq_users_username_lower", text("lower(username)"), unique=True),
        # exactly one Super Admin may exist
        Index("uq_single_super_admin", "role", unique=True, postgresql_where=text("role = 'SUPER_ADMIN'"),
              sqlite_where=text("role = 'SUPER_ADMIN'")),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(30))
    full_name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(20))
    organisation_id: Mapped[int] = mapped_column(ForeignKey("organisations.id"), nullable=True)
    can_salary: Mapped[bool] = mapped_column(Boolean, default=False)
    password_hash: Mapped[str] = mapped_column(String(255))
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    session_version: Mapped[int] = mapped_column(Integer, default=1)   # bump to log the user out everywhere
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_login: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    organisation = relationship("Organisation")

    @property
    def is_super(self):
        return self.role == ROLE_SUPER

    @property
    def can_write(self):
        return self.role == ROLE_OPERATOR

    @property
    def can_view_salary(self):
        return self.is_super or self.can_salary

    @property
    def can_write_salary(self):
        return self.can_write and self.can_salary


class Company(Base):
    __tablename__ = "companies"
    __table_args__ = (UniqueConstraint("organisation_id", "short_code", name="uq_company_code"),)
    id = Column(Integer, primary_key=True)
    organisation_id = Column(Integer, ForeignKey("organisations.id"), nullable=False, index=True)
    locals().update({f.key: spec_column(f) for f in COMPANY_FIELDS})
    is_active = Column(Boolean, nullable=False, default=True)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    organisation = relationship("Organisation")


class UserCompany(Base):
    __tablename__ = "user_companies"
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), primary_key=True)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    ts = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    user_id = Column(Integer)
    username = Column(String(30))
    organisation_id = Column(Integer)
    company_id = Column(Integer)
    action = Column(String(40), nullable=False)
    entity = Column(String(60))
    entity_id = Column(Integer)
    detail = Column(JSONType)
    ip = Column(String(45))


class Employee(Base):
    __tablename__ = "employees"
    __table_args__ = (UniqueConstraint("company_id", "emp_code", name="uq_emp_code"),)
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    locals().update({f.key: spec_column(f) for f in EMPLOYEE_FIELDS})
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True))


class MonthlyInput(Base):
    __tablename__ = "monthly_inputs"
    __table_args__ = (UniqueConstraint("employee_id", "year", "month", name="uq_monthly_input"),)
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    days_worked = Column(Numeric(4, 1), nullable=False, default=0)
    ot_hours = Column(Numeric(6, 2), nullable=False, default=0)
    advance = Column(Numeric(12, 2), nullable=False, default=0)
    other_deduction = Column(Numeric(12, 2), nullable=False, default=0)
    remarks = Column(String(255))


class Attendance(Base):
    __tablename__ = "attendance"
    __table_args__ = (UniqueConstraint("employee_id", "att_date", name="uq_attendance_day"),
                      Index("ix_att_company_date", "company_id", "att_date"))
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    att_date = Column(Date, nullable=False)
    status = Column(String(2), nullable=False)
    in_time = Column(String(5))
    out_time = Column(String(5))
    is_generated = Column(Boolean, nullable=False, default=True)


class SalaryRun(Base):
    __tablename__ = "salary_runs"
    __table_args__ = (UniqueConstraint("company_id", "year", "month", name="uq_salary_run"),)
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    status = Column(String(5), nullable=False, default="DRAFT")
    calculated_at = Column(DateTime(timezone=True))
    calculated_by = Column(Integer, ForeignKey("users.id"))
    finalised_at = Column(DateTime(timezone=True))


class SalaryLine(Base):
    """Snapshot of one employee's salary for a month (rates and every amount), so history never changes."""
    __tablename__ = "salary_lines"
    __table_args__ = (UniqueConstraint("run_id", "employee_id", name="uq_salary_line"),)
    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("salary_runs.id", ondelete="CASCADE"), nullable=False)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    emp_code = Column(String(255))
    emp_name = Column(String(255))
    designation = Column(String(255))
    department = Column(String(255))
    uan = Column(String(255))
    esic_no = Column(String(255))
    salary_type = Column(String(10))
    days_in_month = Column(Integer)
    divisor = Column(Integer)
    present_days = Column(Float)
    paid_leave = Column(Float)
    weekly_offs = Column(Float)
    absent_days = Column(Float)
    paid_days = Column(Float)
    ot_hours = Column(Float)
    rate_basic = Column(Float)
    rate_da = Column(Float)
    rate_hra = Column(Float)
    rate_other = Column(Float)
    earned_basic = Column(Integer)
    earned_da = Column(Integer)
    earned_hra = Column(Integer)
    earned_other = Column(Integer)
    ot_amount = Column(Integer)
    gross = Column(Integer)
    pf_employee = Column(Integer)
    esi_employee = Column(Integer)
    prof_tax = Column(Integer)
    advance = Column(Integer)
    other_deduction = Column(Integer)
    total_deductions = Column(Integer)
    net_pay = Column(Integer)
    pf_employer = Column(Integer)
    esi_employer = Column(Integer)
    warning = Column(String(255))


def _register_model(spec):
    attrs = {"__tablename__": spec.table,
             "id": Column(Integer, primary_key=True),
             "company_id": Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)}
    for f in spec.fields:
        attrs[f.key] = (Column(Integer, ForeignKey("employees.id", ondelete="SET NULL"))
                        if f.type == "employee" else spec_column(f))
    attrs.update(created_by=Column(Integer, ForeignKey("users.id")),
                 created_at=Column(DateTime(timezone=True), server_default=func.now()),
                 updated_at=Column(DateTime(timezone=True)))
    return type("Register_" + spec.key, (Base,), attrs)


# Factory Act registers: child labour, accidents, loss & damage, dangerous occurrences, other occurrences
REGISTER_MODELS = {spec.key: _register_model(spec) for spec in REGISTERS}


class Holiday(Base):
    """Paid public / festival holidays for a company; used when generating attendance."""
    __tablename__ = "holidays"
    __table_args__ = (UniqueConstraint("company_id", "holiday_date", name="uq_holiday_day"),)
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    holiday_date = Column(Date, nullable=False)
    name = Column(String(120), nullable=False)


class LeaveOpening(Base):
    """Opening earned-leave balance (days) carried into a leave year."""
    __tablename__ = "leave_openings"
    __table_args__ = (UniqueConstraint("employee_id", "year", name="uq_leave_opening"),)
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    year = Column(Integer, nullable=False)
    opening = Column(Numeric(5, 1), nullable=False, default=0)

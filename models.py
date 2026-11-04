from datetime import datetime

from sqlalchemy import (BigInteger, Boolean, CheckConstraint, Column, Date, DateTime, ForeignKey, Index, Integer,
                        Numeric, String, Text, UniqueConstraint, func, text)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from .core.specs import COMPANY_FIELDS
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

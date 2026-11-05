"""initial schema: organisations, users, companies, user_companies, audit_log

Revision ID: 0001
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None

# Frozen snapshot of the company master columns (name, type, bool-default).
COMPANY_COLUMNS = [
    ('name', "String(255)", None),
    ('short_code', "String(255)", None),
    ('nature_of_industry', "String(255)", None),
    ('factory_licence_no', "String(255)", None),
    ('licence_valid_from', "Date", None),
    ('licence_valid_to', "Date", None),
    ('factory_registration_no', "String(255)", None),
    ('plan_approval_no', "String(255)", None),
    ('max_workers', "Integer", None),
    ('installed_power', "Numeric(12, 2)", None),
    ('cin', "String(255)", None),
    ('pan', "String(255)", None),
    ('gstin', "String(255)", None),
    ('pf_code', "String(255)", None),
    ('esic_code', "String(255)", None),
    ('udyam_no', "String(255)", None),
    ('pt_reg_no', "String(255)", None),
    ('address1', "String(255)", None),
    ('address2', "String(255)", None),
    ('city', "String(255)", None),
    ('district', "String(255)", None),
    ('state', "String(255)", None),
    ('pincode', "String(255)", None),
    ('occupier_name', "String(255)", None),
    ('occupier_father', "String(255)", None),
    ('occupier_designation', "String(255)", None),
    ('occupier_address', "Text", None),
    ('occupier_phone', "String(255)", None),
    ('manager_name', "String(255)", None),
    ('manager_father', "String(255)", None),
    ('manager_phone', "String(255)", None),
    ('manager_email', "String(255)", None),
    ('phone', "String(255)", None),
    ('email', "String(255)", None),
    ('website', "String(255)", None),
    ('wage_divisor', "String(255)", None),
    ('hours_per_day', "Numeric(12, 2)", None),
    ('pf_wage_ceiling', "Numeric(12, 2)", None),
    ('pf_on_actual', "Boolean", False),
    ('esi_threshold', "Numeric(12, 2)", None),
    ('pt_slabs', "Text", None),
]


def _type(t):
    return eval("sa." + t)


def upgrade():
    op.create_table(
        "organisations",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(200), nullable=False, unique=True),
        sa.Column("max_companies", sa.Integer, nullable=False, server_default="1"),
        sa.Column("max_users", sa.Integer, nullable=False, server_default="5"),
        sa.Column("valid_until", sa.Date),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("username", sa.String(30), nullable=False),
        sa.Column("full_name", sa.String(120), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("organisation_id", sa.Integer, sa.ForeignKey("organisations.id")),
        sa.Column("can_salary", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("must_change_password", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("failed_attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(timezone=True)),
        sa.Column("session_version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("created_by", sa.Integer, sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_login", sa.DateTime(timezone=True)),
        sa.CheckConstraint("role IN ('SUPER_ADMIN','OPERATOR','VIEWER')", name="ck_users_role"),
        sa.CheckConstraint("(role = 'SUPER_ADMIN') = (organisation_id IS NULL)", name="ck_users_org_for_role"),
    )
    op.execute("CREATE UNIQUE INDEX uq_users_username_lower ON users (lower(username))")
    op.execute("CREATE UNIQUE INDEX uq_single_super_admin ON users (role) WHERE role = 'SUPER_ADMIN'")

    cols = [sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("organisation_id", sa.Integer, sa.ForeignKey("organisations.id"), nullable=False)]
    for name, t, default in COMPANY_COLUMNS:
        if t == "Boolean":
            cols.append(sa.Column(name, sa.Boolean, nullable=False,
                                  server_default=sa.true() if default else sa.false()))
        else:
            cols.append(sa.Column(name, _type(t)))
    cols += [sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
             sa.Column("created_by", sa.Integer, sa.ForeignKey("users.id")),
             sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
             sa.UniqueConstraint("organisation_id", "short_code", name="uq_company_code")]
    op.create_table("companies", *cols)
    op.create_index("ix_companies_organisation_id", "companies", ["organisation_id"])

    op.create_table(
        "user_companies",
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("company_id", sa.Integer, sa.ForeignKey("companies.id", ondelete="CASCADE"), primary_key=True),
    )
    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("ts", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("user_id", sa.Integer), sa.Column("username", sa.String(30)),
        sa.Column("organisation_id", sa.Integer), sa.Column("company_id", sa.Integer),
        sa.Column("action", sa.String(40), nullable=False), sa.Column("entity", sa.String(60)),
        sa.Column("entity_id", sa.Integer), sa.Column("detail", postgresql.JSONB), sa.Column("ip", sa.String(45)),
    )
    op.create_index("ix_audit_log_ts", "audit_log", ["ts"])


def downgrade():
    for t in ("audit_log", "user_companies", "companies", "users", "organisations"):
        op.drop_table(t)

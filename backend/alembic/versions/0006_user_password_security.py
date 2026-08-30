"""Add password reset state and browser session versioning.

Revision ID: 0006_user_password_security
Revises: 0005_indx_t0_t7
"""

from alembic import op
import sqlalchemy as sa


revision = "0006_user_password_security"
down_revision = "0005_indx_t0_t7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("users", sa.Column("auth_version", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("users", "auth_version")
    op.drop_column("users", "must_change_password")

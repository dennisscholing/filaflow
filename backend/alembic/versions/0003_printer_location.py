"""Add printer location.

Revision ID: 0003_printer_location
Revises: 0002_indx_t1_t8
"""
from alembic import op
import sqlalchemy as sa


revision = "0003_printer_location"
down_revision = "0002_indx_t1_t8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("printers", sa.Column("location", sa.String(120), nullable=False, server_default=""))


def downgrade() -> None:
    op.drop_column("printers", "location")

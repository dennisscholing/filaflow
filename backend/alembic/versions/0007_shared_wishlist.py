"""Add the shared filament wishlist.

Revision ID: 0007_shared_wishlist
Revises: 0006_user_password_security
"""

from alembic import op
import sqlalchemy as sa


revision = "0007_shared_wishlist"
down_revision = "0006_user_password_security"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "wishlist_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("product_key", sa.String(500), nullable=False),
        sa.Column("active_key", sa.String(500), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="saved"),
        sa.Column("desired_quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("brand", sa.String(120), nullable=False, server_default="Generic"),
        sa.Column("material_name", sa.String(160), nullable=False),
        sa.Column("material_type", sa.String(40), nullable=False, server_default="PLA"),
        sa.Column("color_name", sa.String(80), nullable=False, server_default=""),
        sa.Column("color_hex", sa.String(9), nullable=False, server_default="#808080"),
        sa.Column("diameter_mm", sa.Numeric(6, 3), nullable=False, server_default="1.75"),
        sa.Column("density_g_cm3", sa.Numeric(7, 4), nullable=False, server_default="1.24"),
        sa.Column("nominal_weight_mg", sa.Integer(), nullable=True),
        sa.Column("nominal_length_mm", sa.Numeric(16, 3), nullable=True),
        sa.Column("tare_weight_mg", sa.Integer(), nullable=True),
        sa.Column("opt_brand_uuid", sa.Uuid(), nullable=True),
        sa.Column("opt_material_uuid", sa.Uuid(), nullable=True),
        sa.Column("opt_package_uuid", sa.Uuid(), nullable=True),
        sa.Column("opt_container_uuid", sa.Uuid(), nullable=True),
        sa.Column("catalog_snapshot", sa.JSON(), nullable=False),
        sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column("updated_by_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_wishlist_items_active_key", "wishlist_items", ["active_key"], unique=True)
    op.create_index("ix_wishlist_items_product_key", "wishlist_items", ["product_key"], unique=False)
    op.create_index("ix_wishlist_items_status", "wishlist_items", ["status"], unique=False)
    op.create_index("ix_wishlist_items_archived", "wishlist_items", ["archived"], unique=False)


def downgrade() -> None:
    op.drop_table("wishlist_items")

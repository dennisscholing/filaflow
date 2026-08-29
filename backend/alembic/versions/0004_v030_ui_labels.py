"""Add v0.3 label templates and reorder settings.

Revision ID: 0004_v030_ui_labels
Revises: 0003_printer_location
"""
from alembic import op
import sqlalchemy as sa
import uuid


revision = "0004_v030_ui_labels"
down_revision = "0003_printer_location"
branch_labels = None
depends_on = None


PRESET_90 = [
    {"id": "border", "type": "border", "x": 0.5, "y": 0.5, "width": 89, "height": 31, "font_size": 3, "visible": True, "text": "", "bold": False},
    {"id": "qr", "type": "qr", "x": 2, "y": 2, "width": 28, "height": 28, "font_size": 3, "visible": True, "text": "", "bold": False},
    {"id": "code", "type": "code", "x": 33, "y": 3, "width": 54, "height": 5, "font_size": 4, "visible": True, "text": "", "bold": True},
    {"id": "filament", "type": "filament", "x": 33, "y": 9, "width": 54, "height": 6, "font_size": 3.5, "visible": True, "text": "", "bold": True},
    {"id": "brand", "type": "brand", "x": 33, "y": 16, "width": 54, "height": 4, "font_size": 2.6, "visible": True, "text": "", "bold": False},
    {"id": "swatch", "type": "color_swatch", "x": 33, "y": 22, "width": 4, "height": 4, "font_size": 3, "visible": True, "text": "", "bold": False},
    {"id": "color", "type": "color_name", "x": 39, "y": 22, "width": 26, "height": 4, "font_size": 2.5, "visible": True, "text": "", "bold": False},
    {"id": "serial", "type": "serial", "x": 66, "y": 22, "width": 21, "height": 4, "font_size": 2.3, "visible": True, "text": "", "bold": False},
]


def _scaled(width: float, height: float) -> list[dict]:
    sx, sy = width / 90, height / 32
    result = []
    for element in PRESET_90:
        item = dict(element)
        item["x"], item["width"] = round(item["x"] * sx, 2), round(item["width"] * sx, 2)
        item["y"], item["height"] = round(item["y"] * sy, 2), round(item["height"] * sy, 2)
        item["font_size"] = max(1.5, round(item["font_size"] * min(sx, sy), 2))
        # Keep the QR code large enough to remain reliably scannable on the
        # smaller built-in presets. Other elements may scale proportionally.
        if item["type"] == "qr":
            item["width"] = item["height"] = max(16, min(item["width"], item["height"]))
        result.append(item)
    return result


def upgrade() -> None:
    op.create_table(
        "label_templates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("width_mm", sa.Numeric(7, 2), nullable=False),
        sa.Column("height_mm", sa.Numeric(7, 2), nullable=False),
        sa.Column("layout", sa.JSON(), nullable=False),
        sa.Column("builtin", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_label_templates_default", "label_templates", ["is_default"], unique=False)
    op.create_index("ix_label_templates_archived", "label_templates", ["archived"], unique=False)
    op.create_table(
        "inventory_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("reorder_threshold_mg", sa.Integer(), nullable=False, server_default="500000"),
        sa.Column("updated_by_id", sa.Uuid(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "reorder_rules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("product_key", sa.String(500), nullable=False),
        sa.Column("threshold_mg", sa.Integer(), nullable=True),
        sa.Column("ignored", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("product_snapshot", sa.JSON(), nullable=False),
        sa.Column("updated_by_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_reorder_rules_product_key", "reorder_rules", ["product_key"], unique=True)
    templates = sa.table(
        "label_templates",
        sa.column("id", sa.Uuid()), sa.column("name", sa.String()), sa.column("width_mm", sa.Numeric()),
        sa.column("height_mm", sa.Numeric()), sa.column("layout", sa.JSON()), sa.column("builtin", sa.Boolean()),
        sa.column("is_default", sa.Boolean()), sa.column("archived", sa.Boolean()),
    )
    op.bulk_insert(templates, [
        {"id": uuid.UUID("018f0000-0000-7000-8000-000000000090"), "name": "Default 90 × 32 mm", "width_mm": 90, "height_mm": 32, "layout": PRESET_90, "builtin": True, "is_default": True, "archived": False},
        {"id": uuid.UUID("018f0000-0000-7000-8000-000000000062"), "name": "Compact 62 × 29 mm", "width_mm": 62, "height_mm": 29, "layout": _scaled(62, 29), "builtin": True, "is_default": False, "archived": False},
        {"id": uuid.UUID("018f0000-0000-7000-8000-000000000050"), "name": "Mini 50 × 30 mm", "width_mm": 50, "height_mm": 30, "layout": _scaled(50, 30), "builtin": True, "is_default": False, "archived": False},
    ])
    settings = sa.table("inventory_settings", sa.column("id", sa.Integer()), sa.column("reorder_threshold_mg", sa.Integer()))
    op.bulk_insert(settings, [{"id": 1, "reorder_threshold_mg": 500000}])


def downgrade() -> None:
    op.drop_table("reorder_rules")
    op.drop_table("inventory_settings")
    op.drop_table("label_templates")

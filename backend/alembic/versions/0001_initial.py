"""Initial FilaFlow schema, frozen at the v0.1 baseline.

Revision ID: 0001_initial
"""
from alembic import op
import sqlalchemy as sa


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("users",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("email", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(120), nullable=False), sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.String(20), nullable=False), sa.Column("preferred_unit", sa.String(10), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_table("printers",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("code", sa.String(20), nullable=False),
        sa.Column("name", sa.String(120), nullable=False), sa.Column("manufacturer", sa.String(120), nullable=False),
        sa.Column("model", sa.String(120), nullable=False), sa.Column("slicer_profile", sa.String(255), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False), sa.Column("archived", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_printers_code", "printers", ["code"], unique=True)
    op.create_table("spools",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("code", sa.String(20), nullable=False),
        sa.Column("brand", sa.String(120), nullable=False), sa.Column("material_name", sa.String(160), nullable=False),
        sa.Column("material_type", sa.String(40), nullable=False), sa.Column("color_name", sa.String(80), nullable=False),
        sa.Column("color_hex", sa.String(9), nullable=False), sa.Column("location", sa.String(120), nullable=False),
        sa.Column("lot_number", sa.String(80), nullable=False), sa.Column("serial_number", sa.String(80), nullable=False),
        sa.Column("diameter_mm", sa.Numeric(6, 3), nullable=False), sa.Column("density_g_cm3", sa.Numeric(7, 4), nullable=False),
        sa.Column("tare_weight_mg", sa.Integer(), nullable=False), sa.Column("initial_weight_mg", sa.Integer(), nullable=False),
        sa.Column("remaining_weight_mg", sa.Integer(), nullable=False), sa.Column("initial_length_mm", sa.Numeric(16, 3), nullable=False),
        sa.Column("remaining_length_mm", sa.Numeric(16, 3), nullable=False), sa.Column("low_stock_weight_mg", sa.Integer(), nullable=False),
        sa.Column("purchase_price_cents", sa.Integer(), nullable=True), sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("opt_brand_uuid", sa.Uuid(), nullable=True), sa.Column("opt_material_uuid", sa.Uuid(), nullable=True),
        sa.Column("opt_package_uuid", sa.Uuid(), nullable=True), sa.Column("opt_container_uuid", sa.Uuid(), nullable=True),
        sa.Column("catalog_snapshot", sa.JSON(), nullable=False), sa.Column("archived", sa.Boolean(), nullable=False),
        sa.Column("discrepancy", sa.Boolean(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_spools_code", "spools", ["code"], unique=True)
    op.create_index("ix_spool_active_material", "spools", ["archived", "material_type"], unique=False)
    op.create_table("catalog_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("source_revision", sa.String(80), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False), sa.Column("material_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_catalog_snapshots_active", "catalog_snapshots", ["active"], unique=False)
    op.create_table("api_tokens",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("name", sa.String(120), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False), sa.Column("token_prefix", sa.String(12), nullable=False),
        sa.Column("printer_id", sa.Uuid(), nullable=True), sa.Column("created_by_id", sa.Uuid(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True), sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["printer_id"], ["printers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("token_hash"))
    op.create_table("printer_tools",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("printer_id", sa.Uuid(), nullable=False),
        sa.Column("slicer_index", sa.Integer(), nullable=False), sa.Column("label", sa.String(30), nullable=False),
        sa.Column("nozzle_diameter_mm", sa.Numeric(6, 3), nullable=True), sa.Column("loaded_spool_id", sa.Uuid(), nullable=True),
        sa.Column("archived", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["loaded_spool_id"], ["spools.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["printer_id"], ["printers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("loaded_spool_id"),
        sa.UniqueConstraint("printer_id", "slicer_index", name="uq_printer_tool_index"))
    op.create_index("ix_printer_tools_printer_id", "printer_tools", ["printer_id"], unique=False)
    op.create_table("print_jobs",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("code", sa.String(32), nullable=False),
        sa.Column("printer_id", sa.Uuid(), nullable=False), sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False), sa.Column("idempotency_key", sa.String(80), nullable=False),
        sa.Column("file_sha256", sa.String(64), nullable=False), sa.Column("status", sa.String(24), nullable=False),
        sa.Column("estimated_seconds", sa.Integer(), nullable=True), sa.Column("printer_snapshot", sa.JSON(), nullable=False),
        sa.Column("parser_warnings", sa.JSON(), nullable=False), sa.Column("submitted_by_id", sa.Uuid(), nullable=True),
        sa.Column("booked_by_id", sa.Uuid(), nullable=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("booked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["booked_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["printer_id"], ["printers.id"]),
        sa.ForeignKeyConstraint(["submitted_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("idempotency_key", "printer_id", name="uq_job_idempotency_printer"))
    op.create_index("ix_print_jobs_code", "print_jobs", ["code"], unique=True)
    op.create_index("ix_print_jobs_printer_id", "print_jobs", ["printer_id"], unique=False)
    op.create_index("ix_print_jobs_status", "print_jobs", ["status"], unique=False)
    op.create_index("ix_print_jobs_created_at", "print_jobs", ["created_at"], unique=False)
    op.create_table("inventory_entries",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("spool_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False), sa.Column("weight_delta_mg", sa.Integer(), nullable=False),
        sa.Column("length_delta_mm", sa.Numeric(16, 3), nullable=False), sa.Column("diameter_mm", sa.Numeric(6, 3), nullable=False),
        sa.Column("density_g_cm3", sa.Numeric(7, 4), nullable=False), sa.Column("note", sa.Text(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=True), sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["job_id"], ["print_jobs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["spool_id"], ["spools.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_inventory_entries_spool_id", "inventory_entries", ["spool_id"], unique=False)
    op.create_index("ix_inventory_entries_created_at", "inventory_entries", ["created_at"], unique=False)
    op.create_table("job_usages",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("tool_id", sa.Uuid(), nullable=True), sa.Column("tool_index", sa.Integer(), nullable=False),
        sa.Column("tool_label", sa.String(30), nullable=False), sa.Column("material_type", sa.String(40), nullable=False),
        sa.Column("color_hex", sa.String(9), nullable=False), sa.Column("diameter_mm", sa.Numeric(6, 3), nullable=False),
        sa.Column("density_g_cm3", sa.Numeric(7, 4), nullable=False), sa.Column("estimated_length_mm", sa.Numeric(16, 3), nullable=False),
        sa.Column("estimated_weight_mg", sa.Integer(), nullable=False), sa.Column("actual_length_mm", sa.Numeric(16, 3), nullable=True),
        sa.Column("actual_weight_mg", sa.Integer(), nullable=True), sa.Column("mapped_spool_id", sa.Uuid(), nullable=True),
        sa.Column("suggested_spool_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["job_id"], ["print_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["mapped_spool_id"], ["spools.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["suggested_spool_id"], ["spools.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tool_id"], ["printer_tools.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("job_id", "tool_index", name="uq_job_tool_usage"))
    op.create_index("ix_job_usages_job_id", "job_usages", ["job_id"], unique=False)
    op.create_table("catalog_materials",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("brand_uuid", sa.Uuid(), nullable=True), sa.Column("material_uuid", sa.Uuid(), nullable=True),
        sa.Column("package_uuid", sa.Uuid(), nullable=True), sa.Column("container_uuid", sa.Uuid(), nullable=True),
        sa.Column("brand", sa.String(120), nullable=False), sa.Column("material_name", sa.String(160), nullable=False),
        sa.Column("material_type", sa.String(40), nullable=False), sa.Column("color_name", sa.String(80), nullable=False),
        sa.Column("color_hex", sa.String(9), nullable=False), sa.Column("diameter_mm", sa.Numeric(6, 3), nullable=False),
        sa.Column("density_g_cm3", sa.Numeric(7, 4), nullable=False), sa.Column("nominal_weight_mg", sa.Integer(), nullable=True),
        sa.Column("nominal_length_mm", sa.Numeric(16, 3), nullable=True), sa.Column("tare_weight_mg", sa.Integer(), nullable=True),
        sa.Column("raw_data", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["snapshot_id"], ["catalog_snapshots.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"))
    for name in ("snapshot_id", "material_uuid", "brand", "material_name", "material_type"):
        op.create_index(f"ix_catalog_materials_{name}", "catalog_materials", [name], unique=False)
    op.create_table("audit_events",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(80), nullable=False), sa.Column("entity_type", sa.String(40), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=True), sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"), sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_audit_events_action", "audit_events", ["action"], unique=False)
    op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"], unique=False)


def downgrade() -> None:
    for table in ("audit_events", "catalog_materials", "job_usages", "inventory_entries", "print_jobs", "printer_tools", "api_tokens", "catalog_snapshots", "spools", "printers", "users"):
        op.drop_table(table)

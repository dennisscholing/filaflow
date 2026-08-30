from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, Uuid, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base
from .ids import uuid7


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid7)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(20), default="operator")
    preferred_unit: Mapped[str] = mapped_column(String(10), default="both")
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    auth_version: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class ApiToken(Base):
    __tablename__ = "api_tokens"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid7)
    name: Mapped[str] = mapped_column(String(120))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    token_prefix: Mapped[str] = mapped_column(String(12))
    printer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("printers.id", ondelete="CASCADE"), nullable=True)
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Printer(Base):
    __tablename__ = "printers"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid7)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    manufacturer: Mapped[str] = mapped_column(String(120), default="")
    model: Mapped[str] = mapped_column(String(120), default="")
    location: Mapped[str] = mapped_column(String(120), default="")
    slicer_profile: Mapped[str] = mapped_column(String(255), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    tools: Mapped[list[PrinterTool]] = relationship(back_populates="printer", cascade="all, delete-orphan", order_by="PrinterTool.slicer_index")


class PrinterTool(Base):
    __tablename__ = "printer_tools"
    __table_args__ = (UniqueConstraint("printer_id", "slicer_index", name="uq_printer_tool_index"),)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid7)
    printer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("printers.id", ondelete="CASCADE"), index=True)
    slicer_index: Mapped[int] = mapped_column(Integer)
    label: Mapped[str] = mapped_column(String(30))
    nozzle_diameter_mm: Mapped[Decimal | None] = mapped_column(Numeric(6, 3))
    loaded_spool_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("spools.id", ondelete="SET NULL"), unique=True)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    printer: Mapped[Printer] = relationship(back_populates="tools")
    loaded_spool: Mapped[Spool | None] = relationship(foreign_keys=[loaded_spool_id])


class Spool(Base):
    __tablename__ = "spools"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid7)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    brand: Mapped[str] = mapped_column(String(120), default="Generic")
    material_name: Mapped[str] = mapped_column(String(160))
    material_type: Mapped[str] = mapped_column(String(40), default="PLA")
    color_name: Mapped[str] = mapped_column(String(80), default="")
    color_hex: Mapped[str] = mapped_column(String(9), default="#808080")
    location: Mapped[str] = mapped_column(String(120), default="")
    lot_number: Mapped[str] = mapped_column(String(80), default="")
    serial_number: Mapped[str] = mapped_column(String(80), default="")
    diameter_mm: Mapped[Decimal] = mapped_column(Numeric(6, 3), default=Decimal("1.75"))
    density_g_cm3: Mapped[Decimal] = mapped_column(Numeric(7, 4), default=Decimal("1.24"))
    tare_weight_mg: Mapped[int] = mapped_column(Integer, default=0)
    initial_weight_mg: Mapped[int] = mapped_column(Integer)
    remaining_weight_mg: Mapped[int] = mapped_column(Integer)
    initial_length_mm: Mapped[Decimal] = mapped_column(Numeric(16, 3))
    remaining_length_mm: Mapped[Decimal] = mapped_column(Numeric(16, 3))
    low_stock_weight_mg: Mapped[int] = mapped_column(Integer, default=100_000)
    purchase_price_cents: Mapped[int | None] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    opt_brand_uuid: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    opt_material_uuid: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    opt_package_uuid: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    opt_container_uuid: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    catalog_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    discrepancy: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class InventoryEntry(Base):
    __tablename__ = "inventory_entries"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid7)
    spool_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("spools.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(30))
    weight_delta_mg: Mapped[int] = mapped_column(Integer)
    length_delta_mm: Mapped[Decimal] = mapped_column(Numeric(16, 3))
    diameter_mm: Mapped[Decimal] = mapped_column(Numeric(6, 3))
    density_g_cm3: Mapped[Decimal] = mapped_column(Numeric(7, 4))
    note: Mapped[str] = mapped_column(Text, default="")
    job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("print_jobs.id", ondelete="SET NULL"))
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, index=True)


class PrintJob(Base):
    __tablename__ = "print_jobs"
    __table_args__ = (UniqueConstraint("idempotency_key", "printer_id", name="uq_job_idempotency_printer"),)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid7)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    printer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("printers.id"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(255))
    idempotency_key: Mapped[str] = mapped_column(String(80))
    file_sha256: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24), default="NEW", index=True)
    estimated_seconds: Mapped[int | None] = mapped_column(Integer)
    printer_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    parser_warnings: Mapped[list] = mapped_column(JSON, default=list)
    submitted_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    booked_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, index=True)
    booked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    usages: Mapped[list[JobUsage]] = relationship(back_populates="job", cascade="all, delete-orphan", order_by="JobUsage.tool_index")


class JobUsage(Base):
    __tablename__ = "job_usages"
    __table_args__ = (UniqueConstraint("job_id", "tool_index", name="uq_job_tool_usage"),)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid7)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("print_jobs.id", ondelete="CASCADE"), index=True)
    tool_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("printer_tools.id", ondelete="SET NULL"))
    tool_index: Mapped[int] = mapped_column(Integer)
    tool_label: Mapped[str] = mapped_column(String(30))
    material_type: Mapped[str] = mapped_column(String(40), default="")
    color_hex: Mapped[str] = mapped_column(String(9), default="")
    diameter_mm: Mapped[Decimal] = mapped_column(Numeric(6, 3))
    density_g_cm3: Mapped[Decimal] = mapped_column(Numeric(7, 4))
    estimated_length_mm: Mapped[Decimal] = mapped_column(Numeric(16, 3))
    estimated_weight_mg: Mapped[int] = mapped_column(Integer)
    actual_length_mm: Mapped[Decimal | None] = mapped_column(Numeric(16, 3))
    actual_weight_mg: Mapped[int | None] = mapped_column(Integer)
    mapped_spool_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("spools.id", ondelete="SET NULL"))
    suggested_spool_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("spools.id", ondelete="SET NULL"))
    job: Mapped[PrintJob] = relationship(back_populates="usages")
    mapped_spool: Mapped[Spool | None] = relationship(foreign_keys=[mapped_spool_id])


class CatalogMaterial(Base):
    __tablename__ = "catalog_materials"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid7)
    snapshot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("catalog_snapshots.id", ondelete="CASCADE"), index=True)
    brand_uuid: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    material_uuid: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    package_uuid: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    container_uuid: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    brand: Mapped[str] = mapped_column(String(120), index=True)
    material_name: Mapped[str] = mapped_column(String(160), index=True)
    material_type: Mapped[str] = mapped_column(String(40), index=True)
    color_name: Mapped[str] = mapped_column(String(80), default="")
    color_hex: Mapped[str] = mapped_column(String(9), default="#808080")
    diameter_mm: Mapped[Decimal] = mapped_column(Numeric(6, 3), default=Decimal("1.75"))
    density_g_cm3: Mapped[Decimal] = mapped_column(Numeric(7, 4), default=Decimal("1.24"))
    nominal_weight_mg: Mapped[int | None] = mapped_column(Integer)
    nominal_length_mm: Mapped[Decimal | None] = mapped_column(Numeric(16, 3))
    tare_weight_mg: Mapped[int | None] = mapped_column(Integer)
    raw_data: Mapped[dict] = mapped_column(JSON, default=dict)


class CatalogSnapshot(Base):
    __tablename__ = "catalog_snapshots"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid7)
    source_revision: Mapped[str] = mapped_column(String(80))
    active: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    material_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid7)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(80), index=True)
    entity_type: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, index=True)


class LabelTemplate(Base):
    __tablename__ = "label_templates"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid7)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    width_mm: Mapped[Decimal] = mapped_column(Numeric(7, 2))
    height_mm: Mapped[Decimal] = mapped_column(Numeric(7, 2))
    layout: Mapped[list] = mapped_column(JSON, default=list)
    builtin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)


class InventorySetting(Base):
    __tablename__ = "inventory_settings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    reorder_threshold_mg: Mapped[int] = mapped_column(Integer, default=500_000)
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)


class ReorderRule(Base):
    __tablename__ = "reorder_rules"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid7)
    product_key: Mapped[str] = mapped_column(String(500), unique=True, index=True)
    threshold_mg: Mapped[int | None] = mapped_column(Integer)
    ignored: Mapped[bool] = mapped_column(Boolean, default=False)
    product_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)


Index("ix_spool_active_material", Spool.archived, Spool.material_type)

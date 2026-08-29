"""Seed and verify a representative v0.2.0 database during release checks."""
from __future__ import annotations

import sys
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from argon2 import PasswordHasher
from sqlalchemy import MetaData, Table, func, select, text

from app.database import engine


USER_ID = "00000000-0000-7000-8000-000000000001"
PRINTER_ID = "00000000-0000-7000-8000-000000000002"
SPOOL_ID = "00000000-0000-7000-8000-000000000003"
TOKEN_ID = "00000000-0000-7000-8000-000000000004"
JOB_ID = "00000000-0000-7000-8000-000000000005"
USAGE_ID = "00000000-0000-7000-8000-000000000006"
LEDGER_ID = "00000000-0000-7000-8000-000000000007"


def identifier(value: str) -> uuid.UUID | str:
    parsed = uuid.UUID(value)
    # SQLite reflects Alembic's UUID columns as CHAR(32), whereas PostgreSQL
    # preserves their native UUID type.
    return parsed.hex if engine.dialect.name == "sqlite" else parsed


def normalized_identifier(value: uuid.UUID | str) -> str:
    return str(uuid.UUID(str(value)))


def reflected(*names: str) -> dict[str, Table]:
    metadata = MetaData()
    return {name: Table(name, metadata, autoload_with=engine) for name in names}


def seed() -> None:
    tables = reflected("users", "printers", "spools", "printer_tools", "api_tokens", "print_jobs", "job_usages", "inventory_entries")
    created_at = datetime.now(timezone.utc)
    with engine.begin() as connection:
        connection.execute(tables["users"].insert().values(
            id=identifier(USER_ID), email="admin@test.local", display_name="Upgrade Administrator",
            password_hash=PasswordHasher().hash("test-password-123"), role="admin",
            preferred_unit="both", active=True, created_at=created_at,
        ))
        connection.execute(tables["printers"].insert().values(
            id=identifier(PRINTER_ID), code="PRN-0001", name="INDX fixture", manufacturer="Prusa",
            model="INDX", slicer_profile="INDX fixture profile", notes="Must survive upgrade",
            archived=False, created_at=created_at,
        ))
        connection.execute(tables["spools"].insert().values(
            id=identifier(SPOOL_ID), code="SPL-0001", brand="Fixture brand", material_name="Fixture PLA",
            material_type="PLA", color_name="Red", color_hex="#FF0000", location="Shelf A",
            lot_number="LOT-UPGRADE", serial_number="SER-UPGRADE", diameter_mm=Decimal("1.750"),
            density_g_cm3=Decimal("1.2400"), tare_weight_mg=210000, initial_weight_mg=1000000,
            remaining_weight_mg=765432, initial_length_mm=Decimal("335000"),
            remaining_length_mm=Decimal("256410"), low_stock_weight_mg=100000,
            purchase_price_cents=2595, currency="EUR", catalog_snapshot={}, archived=False,
            discrepancy=False, created_at=created_at,
        ))
        for index in range(1, 9):
            connection.execute(tables["printer_tools"].insert().values(
                id=identifier(f"00000000-0000-7000-8000-{100 + index:012d}"),
                printer_id=identifier(PRINTER_ID), slicer_index=index, label=f"T{index}",
                nozzle_diameter_mm=Decimal("0.400"),
                loaded_spool_id=identifier(SPOOL_ID) if index == 1 else None, archived=False,
            ))
        connection.execute(tables["api_tokens"].insert().values(
            id=identifier(TOKEN_ID), name="Fixture hook", token_hash="a" * 64,
            token_prefix="ff_fixture", printer_id=identifier(PRINTER_ID),
            created_by_id=identifier(USER_ID), created_at=created_at,
        ))
        connection.execute(tables["print_jobs"].insert().values(
            id=identifier(JOB_ID), code="JOB-20260828-0001", printer_id=identifier(PRINTER_ID),
            filename="fixture.gcode", display_name="fixture", idempotency_key="fixture-idem",
            file_sha256="b" * 64, status="MAPPED", estimated_seconds=120,
            printer_snapshot={"code": "PRN-0001", "tools": []}, parser_warnings=[],
            submitted_by_id=identifier(USER_ID), created_at=created_at,
        ))
        connection.execute(tables["job_usages"].insert().values(
            id=identifier(USAGE_ID), job_id=identifier(JOB_ID),
            tool_id=identifier("00000000-0000-7000-8000-000000000101"), tool_index=1,
            tool_label="T1", material_type="PLA", color_hex="#FF0000",
            diameter_mm=Decimal("1.750"), density_g_cm3=Decimal("1.2400"),
            estimated_length_mm=Decimal("1000"), estimated_weight_mg=3000,
            mapped_spool_id=identifier(SPOOL_ID), suggested_spool_id=identifier(SPOOL_ID),
        ))
        connection.execute(tables["inventory_entries"].insert().values(
            id=identifier(LEDGER_ID), spool_id=identifier(SPOOL_ID), kind="INITIAL",
            weight_delta_mg=1000000, length_delta_mm=Decimal("335000"),
            diameter_mm=Decimal("1.750"), density_g_cm3=Decimal("1.2400"),
            note="Upgrade fixture", actor_id=identifier(USER_ID), created_at=created_at,
        ))


def verify() -> None:
    tables = reflected("printers", "printer_tools", "spools", "api_tokens", "print_jobs", "inventory_entries", "label_templates", "inventory_settings")
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0004_v030_ui_labels"
        printer = connection.execute(select(tables["printers"].c.id, tables["printers"].c.code, tables["printers"].c.location).where(tables["printers"].c.id == identifier(PRINTER_ID))).one()
        assert (normalized_identifier(printer.id), printer.code, printer.location) == (PRINTER_ID, "PRN-0001", "")
        tools = connection.execute(select(tables["printer_tools"].c.slicer_index, tables["printer_tools"].c.label).where(tables["printer_tools"].c.printer_id == identifier(PRINTER_ID)).order_by(tables["printer_tools"].c.slicer_index)).all()
        assert tools == [(index, f"T{index}") for index in range(1, 9)]
        spool = connection.execute(select(tables["spools"].c.id, tables["spools"].c.code, tables["spools"].c.remaining_weight_mg, tables["spools"].c.remaining_length_mm).where(tables["spools"].c.id == identifier(SPOOL_ID))).one()
        assert normalized_identifier(spool.id) == SPOOL_ID
        assert (spool.code, spool.remaining_weight_mg, spool.remaining_length_mm) == ("SPL-0001", 765432, 256410)
        assert connection.scalar(select(func.count()).select_from(tables["api_tokens"]).where(tables["api_tokens"].c.id == identifier(TOKEN_ID))) == 1
        assert connection.scalar(select(func.count()).select_from(tables["print_jobs"]).where(tables["print_jobs"].c.id == identifier(JOB_ID))) == 1
        ledger = connection.execute(select(tables["inventory_entries"].c.weight_delta_mg, tables["inventory_entries"].c.length_delta_mm).where(tables["inventory_entries"].c.id == identifier(LEDGER_ID))).one()
        assert ledger == (1000000, 335000)
        assert connection.scalar(select(func.count()).select_from(tables["label_templates"]).where(tables["label_templates"].c.builtin.is_(True))) == 3
        assert connection.scalar(select(tables["inventory_settings"].c.reorder_threshold_mg).where(tables["inventory_settings"].c.id == 1)) == 500000
    print("Representative v0.2.0 upgrade preserved identities, tools, relationships, and inventory")


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in {"seed", "verify"}:
        raise SystemExit("Usage: upgrade_fixture.py seed|verify")
    seed() if sys.argv[1] == "seed" else verify()

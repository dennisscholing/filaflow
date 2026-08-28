"""Seed and verify a representative v0.1.6 PostgreSQL database in CI."""
from __future__ import annotations

import sys

from argon2 import PasswordHasher
from sqlalchemy import text

from app.database import engine


USER_ID = "00000000-0000-7000-8000-000000000001"
PRINTER_ID = "00000000-0000-7000-8000-000000000002"
SPOOL_ID = "00000000-0000-7000-8000-000000000003"
TOKEN_ID = "00000000-0000-7000-8000-000000000004"
JOB_ID = "00000000-0000-7000-8000-000000000005"
USAGE_ID = "00000000-0000-7000-8000-000000000006"
LEDGER_ID = "00000000-0000-7000-8000-000000000007"


def seed() -> None:
    with engine.begin() as connection:
        connection.execute(
            text("""INSERT INTO users
                (id, email, display_name, password_hash, role, preferred_unit, active, created_at)
                VALUES (:id, 'admin@test.local', 'Upgrade Administrator', :password, 'admin', 'both', true, now())"""),
            {"id": USER_ID, "password": PasswordHasher().hash("test-password-123")},
        )
        connection.execute(
            text("""INSERT INTO printers
                (id, code, name, manufacturer, model, slicer_profile, notes, archived, created_at)
                VALUES (:id, 'PRN-0001', 'INDX fixture', 'Prusa', 'INDX', 'INDX fixture profile',
                        'Must survive upgrade', false, now())"""),
            {"id": PRINTER_ID},
        )
        connection.execute(
            text("""INSERT INTO spools
                (id, code, brand, material_name, material_type, color_name, color_hex, location,
                 lot_number, serial_number, diameter_mm, density_g_cm3, tare_weight_mg,
                 initial_weight_mg, remaining_weight_mg, initial_length_mm, remaining_length_mm,
                 low_stock_weight_mg, purchase_price_cents, currency, opt_brand_uuid,
                 opt_material_uuid, opt_package_uuid, opt_container_uuid, catalog_snapshot,
                 archived, discrepancy, created_at)
                VALUES (:id, 'SPL-0001', 'Fixture brand', 'Fixture PLA', 'PLA', 'Red', '#FF0000',
                        'Shelf A', 'LOT-UPGRADE', 'SER-UPGRADE', 1.750, 1.2400, 210000,
                        1000000, 765432, 335000.000, 256410.000, 100000, 2595, 'EUR',
                        NULL, NULL, NULL, NULL, CAST('{}' AS json), false, false, now())"""),
            {"id": SPOOL_ID},
        )
        for index in range(1, 9):
            tool_id = f"00000000-0000-7000-8000-{100 + index:012d}"
            connection.execute(
                text("""INSERT INTO printer_tools
                    (id, printer_id, slicer_index, label, nozzle_diameter_mm, loaded_spool_id, archived)
                    VALUES (:id, :printer, :index, :label, 0.400, :spool, false)"""),
                {
                    "id": tool_id,
                    "printer": PRINTER_ID,
                    "index": index,
                    "label": f"T{index}",
                    "spool": SPOOL_ID if index == 1 else None,
                },
            )
        connection.execute(
            text("""INSERT INTO api_tokens
                (id, name, token_hash, token_prefix, printer_id, created_by_id, revoked_at, last_used_at, created_at)
                VALUES (:id, 'Fixture hook', :hash, 'ff_fixture', :printer, :user, NULL, NULL, now())"""),
            {"id": TOKEN_ID, "hash": "a" * 64, "printer": PRINTER_ID, "user": USER_ID},
        )
        connection.execute(
            text("""INSERT INTO print_jobs
                (id, code, printer_id, filename, display_name, idempotency_key, file_sha256, status,
                 estimated_seconds, printer_snapshot, parser_warnings, submitted_by_id, booked_by_id,
                 created_at, booked_at)
                VALUES (:id, 'JOB-20260828-0001', :printer, 'fixture.gcode', 'fixture', 'fixture-idem',
                        :hash, 'MAPPED', 120, CAST('{"code":"PRN-0001","tools":[]}' AS json),
                        CAST('[]' AS json), :user, NULL, now(), NULL)"""),
            {"id": JOB_ID, "printer": PRINTER_ID, "hash": "b" * 64, "user": USER_ID},
        )
        connection.execute(
            text("""INSERT INTO job_usages
                (id, job_id, tool_id, tool_index, tool_label, material_type, color_hex,
                 diameter_mm, density_g_cm3, estimated_length_mm, estimated_weight_mg,
                 actual_length_mm, actual_weight_mg, mapped_spool_id, suggested_spool_id)
                VALUES (:id, :job, :tool, 1, 'T1', 'PLA', '#FF0000', 1.750, 1.2400,
                        1000.000, 3000, NULL, NULL, :spool, :spool)"""),
            {
                "id": USAGE_ID,
                "job": JOB_ID,
                "tool": "00000000-0000-7000-8000-000000000101",
                "spool": SPOOL_ID,
            },
        )
        connection.execute(
            text("""INSERT INTO inventory_entries
                (id, spool_id, kind, weight_delta_mg, length_delta_mm, diameter_mm, density_g_cm3,
                 note, job_id, actor_id, created_at)
                VALUES (:id, :spool, 'INITIAL', 1000000, 335000.000, 1.750, 1.2400,
                        'Upgrade fixture', NULL, :user, now())"""),
            {"id": LEDGER_ID, "spool": SPOOL_ID, "user": USER_ID},
        )


def verify() -> None:
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0003_printer_location"
        printer = connection.execute(
            text("SELECT id::text, code, location FROM printers WHERE id = CAST(:id AS uuid)"),
            {"id": PRINTER_ID},
        ).one()
        assert printer == (PRINTER_ID, "PRN-0001", "")
        tools = connection.execute(
            text("SELECT slicer_index, label FROM printer_tools WHERE printer_id = CAST(:id AS uuid) ORDER BY slicer_index"),
            {"id": PRINTER_ID},
        ).all()
        assert tools == [(index, f"T{index}") for index in range(1, 9)]
        spool = connection.execute(
            text("SELECT id::text, code, remaining_weight_mg, remaining_length_mm FROM spools WHERE id = CAST(:id AS uuid)"),
            {"id": SPOOL_ID},
        ).one()
        assert str(spool[0]) == SPOOL_ID
        assert spool[1:] == ("SPL-0001", 765432, 256410)
        assert connection.scalar(text("SELECT count(*) FROM api_tokens WHERE id = CAST(:id AS uuid)"), {"id": TOKEN_ID}) == 1
        assert connection.scalar(text("SELECT count(*) FROM print_jobs WHERE id = CAST(:id AS uuid)"), {"id": JOB_ID}) == 1
        ledger = connection.execute(
            text("SELECT weight_delta_mg, length_delta_mm FROM inventory_entries WHERE id = CAST(:id AS uuid)"),
            {"id": LEDGER_ID},
        ).one()
        assert ledger == (1000000, 335000)
    print("Representative v0.1.6 upgrade preserved identities, tools, relationships, and inventory")


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in {"seed", "verify"}:
        raise SystemExit("Usage: upgrade_fixture.py seed|verify")
    seed() if sys.argv[1] == "seed" else verify()

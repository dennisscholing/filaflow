from __future__ import annotations

import asyncio
import contextlib
import csv
import hashlib
import io
import json
import re
import secrets
import shutil
import uuid
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import FileResponse
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from .audit import audit
from .auth import admin_user, clear_session, current_user, hash_password, issue_api_token, set_session, token_hash, verify_password
from .catalog import CatalogSyncError, catalog_metadata, sync_catalog
from .colors import color_distance, nearest_color
from .config import settings
from .database import SessionLocal, get_db
from .gcode import parse_gcode
from .ids import next_code
from .labels import DEFAULT_LAYOUT, render_label, template_json, validate_layout
from .models import ApiToken, AuditEvent, CatalogMaterial, CatalogSnapshot, InventoryEntry, InventorySetting, JobUsage, LabelTemplate, PrintJob, Printer, PrinterTool, ReorderRule, Spool, User, WishlistItem, now_utc
from .schemas import AdminPasswordResetInput, InventorySettingsInput, JobBookInput, JobMapInput, JobPrinterInput, LabelTemplateInput, LoadoutInput, LoginInput, PasswordChangeInput, PrinterInput, PrinterUpdateInput, ReorderRuleInput, SpoolInput, SpoolRepurposeInput, SpoolUpdateInput, TokenInput, UserCreateInput, UserPreferenceInput, UserStatusInput, WeighInput, WishlistConvertInput, WishlistInput
from .units import grams_to_mg, length_mm_to_weight_mg, mg_to_grams, weight_mg_to_length_mm


app = FastAPI(title="FilaFlow API", version="0.6.0", docs_url="/api/docs", redoc_url=None)


def spool_json(db: Session, spool: Spool) -> dict:
    open_statuses = ["MAPPED", "NEEDS_REVIEW"]
    reserved_weight = db.scalar(select(func.coalesce(func.sum(func.coalesce(JobUsage.actual_weight_mg, JobUsage.estimated_weight_mg)), 0)).join(PrintJob).where(JobUsage.mapped_spool_id == spool.id, PrintJob.status.in_(open_statuses))) or 0
    reserved_length = db.scalar(select(func.coalesce(func.sum(func.coalesce(JobUsage.actual_length_mm, JobUsage.estimated_length_mm)), 0)).join(PrintJob).where(JobUsage.mapped_spool_id == spool.id, PrintJob.status.in_(open_statuses))) or Decimal("0")
    loaded = db.scalar(select(PrinterTool).where(PrinterTool.loaded_spool_id == spool.id).options(selectinload(PrinterTool.printer)))
    last_weighed = db.scalar(select(InventoryEntry.created_at).where(InventoryEntry.spool_id == spool.id, InventoryEntry.kind == "WEIGHING").order_by(InventoryEntry.created_at.desc()).limit(1))
    return {
        "id": str(spool.id), "code": spool.code, "brand": spool.brand, "materialName": spool.material_name, "materialType": spool.material_type,
        "colorName": spool.color_name, "colorHex": spool.color_hex, "location": spool.location, "lotNumber": spool.lot_number, "serialNumber": spool.serial_number, "diameterMm": float(spool.diameter_mm), "density": float(spool.density_g_cm3), "tareWeightG": mg_to_grams(spool.tare_weight_mg), "lowStockWeightG": mg_to_grams(spool.low_stock_weight_mg),
        "initialWeightG": mg_to_grams(spool.initial_weight_mg), "remainingWeightG": mg_to_grams(spool.remaining_weight_mg), "reservedWeightG": mg_to_grams(int(reserved_weight)),
        "availableWeightG": mg_to_grams(spool.remaining_weight_mg - int(reserved_weight)), "initialLengthM": float(spool.initial_length_mm / 1000),
        "remainingLengthM": float(spool.remaining_length_mm / 1000), "reservedLengthM": float(Decimal(reserved_length) / 1000), "availableLengthM": float((spool.remaining_length_mm - Decimal(reserved_length)) / 1000),
        "remainingPercent": round((spool.remaining_weight_mg / spool.initial_weight_mg * 100) if spool.initial_weight_mg else 0, 1),
        "lowStock": spool.remaining_weight_mg <= spool.low_stock_weight_mg, "archived": spool.archived, "discrepancy": spool.discrepancy,
        "loadedOn": {"printerId": str(loaded.printer.id), "printer": loaded.printer.name, "printerCode": loaded.printer.code, "toolId": str(loaded.id), "tool": loaded.label} if loaded else None,
        "lastWeighedAt": last_weighed.isoformat() if last_weighed else None,
        "purchasePrice": spool.purchase_price_cents / 100 if spool.purchase_price_cents is not None else None, "currency": spool.currency,
        "catalogSnapshot": spool.catalog_snapshot,
        "productKey": product_key(spool),
        "openPrintTag": {"brandUuid": str(spool.opt_brand_uuid) if spool.opt_brand_uuid else None, "materialUuid": str(spool.opt_material_uuid) if spool.opt_material_uuid else None, "packageUuid": str(spool.opt_package_uuid) if spool.opt_package_uuid else None, "containerUuid": str(spool.opt_container_uuid) if spool.opt_container_uuid else None},
    }


def printer_json(printer: Printer) -> dict:
    return {"id": str(printer.id), "code": printer.code, "name": printer.name, "manufacturer": printer.manufacturer, "model": printer.model, "location": printer.location, "slicerProfile": printer.slicer_profile, "notes": printer.notes, "archived": printer.archived,
            "tools": [{"id": str(tool.id), "index": tool.slicer_index, "label": tool.label, "nozzleDiameterMm": float(tool.nozzle_diameter_mm) if tool.nozzle_diameter_mm else None,
                       "loadedSpool": {"id": str(tool.loaded_spool.id), "code": tool.loaded_spool.code, "brand": tool.loaded_spool.brand, "material": tool.loaded_spool.material_name, "materialType": tool.loaded_spool.material_type, "colorHex": tool.loaded_spool.color_hex, "remainingWeightG": mg_to_grams(tool.loaded_spool.remaining_weight_mg), "remainingLengthM": float(tool.loaded_spool.remaining_length_mm / 1000)} if tool.loaded_spool else None}
                      for tool in printer.tools if not tool.archived]}


def job_json(job: PrintJob) -> dict:
    return {"id": str(job.id), "code": job.code, "filename": job.filename, "displayName": job.display_name, "status": job.status, "estimatedSeconds": job.estimated_seconds, "createdAt": job.created_at.isoformat(), "warnings": job.parser_warnings, "printer": job.printer_snapshot, "slicerProfile": job.printer_snapshot.get("slicerSourceProfile", ""), "routingMode": job.printer_snapshot.get("routingMode", "profile"),
            "usages": [{"id": str(usage.id), "toolIndex": usage.tool_index, "toolLabel": usage.tool_label, "materialType": usage.material_type, "colorHex": usage.color_hex, "estimatedLengthM": float(usage.estimated_length_mm / 1000), "estimatedWeightG": mg_to_grams(usage.estimated_weight_mg), "actualLengthM": float(usage.actual_length_mm / 1000) if usage.actual_length_mm is not None else None, "actualWeightG": mg_to_grams(usage.actual_weight_mg) if usage.actual_weight_mg is not None else None, "suggestedSpoolId": str(usage.suggested_spool_id) if usage.suggested_spool_id else None, "mappedSpoolId": str(usage.mapped_spool_id) if usage.mapped_spool_id else None} for usage in job.usages]}


def next_job_code(db: Session) -> str:
    prefix = f"JOB-{datetime.now():%Y%m%d}-"
    codes = db.scalars(select(PrintJob.code).where(PrintJob.code.like(f"{prefix}%"))).all()
    highest = 0
    for code in codes:
        try: highest = max(highest, int(code.rsplit("-", 1)[1]))
        except (ValueError, IndexError): pass
    return f"{prefix}{highest + 1:04d}"


def printer_snapshot(printer: Printer, source_profile: str = "", physical_profile: str = "", routing_mode: str = "profile") -> dict:
    return {"id": str(printer.id), "code": printer.code, "name": printer.name, "model": printer.model, "location": printer.location,
            "slicerSourceProfile": source_profile, "slicerPhysicalProfile": physical_profile, "routingMode": routing_mode,
            "tools": [{"id": str(tool.id), "index": tool.slicer_index, "label": tool.label} for tool in printer.tools if not tool.archived]}


def render_spool_label(spool: Spool, target: str) -> bytes:
    return render_label(spool, target, 90, 32, DEFAULT_LAYOUT)


def user_json(user: User) -> dict:
    return {"id": str(user.id), "email": user.email, "displayName": user.display_name, "role": user.role, "preferredUnit": user.preferred_unit, "mustChangePassword": user.must_change_password, "active": user.active, "createdAt": user.created_at.isoformat()}


def product_key(spool: Spool) -> str:
    diameter = f"{Decimal(spool.diameter_mm):.3f}"
    if spool.opt_brand_uuid and spool.opt_material_uuid:
        return f"opt:{spool.opt_brand_uuid}:{spool.opt_material_uuid}:{diameter}"
    fields = (spool.brand, spool.material_name, spool.material_type, spool.color_hex, diameter)
    return "manual:" + "|".join(re.sub(r"\s+", " ", str(value).strip().casefold()) for value in fields)


def wishlist_product_key(data: WishlistInput) -> str:
    opt_ids = (data.opt_brand_uuid, data.opt_material_uuid, data.opt_package_uuid, data.opt_container_uuid)
    if any(opt_ids):
        return "opt:" + ":".join(str(value or "-").casefold() for value in opt_ids)
    diameter = f"{Decimal(data.diameter_mm):.3f}"
    fields = (data.brand, data.material_name, data.material_type, data.color_hex, diameter)
    return "manual:" + "|".join(re.sub(r"\s+", " ", str(value).strip().casefold()) for value in fields)


def wishlist_json(item: WishlistItem) -> dict:
    return {
        "id": str(item.id), "status": item.status, "desiredQuantity": item.desired_quantity, "note": item.note,
        "brand": item.brand, "materialName": item.material_name, "materialType": item.material_type,
        "colorName": item.color_name, "colorHex": item.color_hex, "diameterMm": float(item.diameter_mm),
        "density": float(item.density_g_cm3),
        "nominalWeightG": mg_to_grams(item.nominal_weight_mg) if item.nominal_weight_mg is not None else None,
        "nominalLengthM": float(item.nominal_length_mm / 1000) if item.nominal_length_mm is not None else None,
        "tareWeightG": mg_to_grams(item.tare_weight_mg) if item.tare_weight_mg is not None else None,
        "catalogSnapshot": item.catalog_snapshot, "productKey": item.product_key, "archived": item.archived,
        "openPrintTag": {
            "brandUuid": str(item.opt_brand_uuid) if item.opt_brand_uuid else None,
            "materialUuid": str(item.opt_material_uuid) if item.opt_material_uuid else None,
            "packageUuid": str(item.opt_package_uuid) if item.opt_package_uuid else None,
            "containerUuid": str(item.opt_container_uuid) if item.opt_container_uuid else None,
        },
        "createdAt": item.created_at.isoformat(), "updatedAt": item.updated_at.isoformat(),
    }


def apply_wishlist_input(item: WishlistItem, data: WishlistInput, user: User) -> None:
    key = wishlist_product_key(data)
    item.product_key = key
    item.active_key = key
    item.status = data.status
    item.desired_quantity = data.desired_quantity
    item.note = data.note.strip()
    item.brand = data.brand.strip()
    item.material_name = data.material_name.strip()
    item.material_type = data.material_type.strip()
    item.color_name = data.color_name.strip() or nearest_color(data.color_hex)[0]
    item.color_hex = data.color_hex
    item.diameter_mm = data.diameter_mm
    item.density_g_cm3 = data.density_g_cm3
    item.nominal_weight_mg = grams_to_mg(data.nominal_weight_g) if data.nominal_weight_g is not None else None
    item.nominal_length_mm = data.nominal_length_m * 1000 if data.nominal_length_m is not None else None
    item.tare_weight_mg = grams_to_mg(data.tare_weight_g) if data.tare_weight_g is not None else None
    item.opt_brand_uuid = data.opt_brand_uuid
    item.opt_material_uuid = data.opt_material_uuid
    item.opt_package_uuid = data.opt_package_uuid
    item.opt_container_uuid = data.opt_container_uuid
    item.catalog_snapshot = data.catalog_snapshot
    item.updated_by_id = user.id
    item.updated_at = now_utc()


def inventory_setting(db: Session) -> InventorySetting:
    record = db.get(InventorySetting, 1)
    if not record:
        record = InventorySetting(id=1, reorder_threshold_mg=500_000)
        db.add(record)
        db.flush()
    return record


def latest_revision(db: Session) -> dict:
    event = db.scalar(select(AuditEvent).order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc()).limit(1))
    return {"revision": str(event.id) if event else "0", "changedAt": event.created_at.isoformat() if event else None}


def bootstrap() -> None:
    with SessionLocal() as db:
        if not db.scalar(select(User.id).limit(1)):
            db.add(User(email=settings.bootstrap_admin_email.lower(), display_name="Administrator", password_hash=hash_password(settings.bootstrap_admin_password), role="admin"))
            db.commit()


async def catalog_scheduler() -> None:
    await asyncio.sleep(30)
    while True:
        try:
            with SessionLocal() as db:
                latest = db.scalar(select(CatalogSnapshot).where(CatalogSnapshot.active.is_(True)))
                stale = not latest or (datetime.now(timezone.utc) - latest.created_at).total_seconds() > 86400
                if stale:
                    await asyncio.to_thread(sync_catalog, db)
        except Exception:
            pass
        await asyncio.sleep(3600)


@app.on_event("startup")
async def startup() -> None:
    bootstrap()
    app.state.catalog_task = asyncio.create_task(catalog_scheduler())


@app.on_event("shutdown")
async def shutdown() -> None:
    task = getattr(app.state, "catalog_task", None)
    if task:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


@app.get("/api/health")
def health(db: Session = Depends(get_db)):
    db.execute(select(1))
    return {"status": "ok"}


@app.post("/api/auth/login")
def login(data: LoginInput, response: Response, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(func.lower(User.email) == data.email.lower()))
    if not user or not user.active or not verify_password(user.password_hash, data.password):
        raise HTTPException(401, "Incorrect email address or password")
    csrf = set_session(response, user)
    return {"user": user_json(user), "csrf": csrf}


@app.post("/api/auth/logout")
def logout(response: Response):
    clear_session(response)
    return {"ok": True}


@app.get("/api/auth/me")
def me(user: User = Depends(current_user)):
    return user_json(user)


@app.put("/api/account/preferences")
def account_preferences(data: UserPreferenceInput, db: Session = Depends(get_db), user: User = Depends(current_user)):
    old = user.preferred_unit
    user.preferred_unit = data.preferred_unit
    audit(db, user, "account.preferences_updated", "user", user.id, {"preferredUnit": {"old": old, "new": user.preferred_unit}})
    db.commit()
    return user_json(user)


@app.put("/api/account/password")
def account_password(data: PasswordChangeInput, response: Response, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if not verify_password(user.password_hash, data.current_password):
        raise HTTPException(422, "Current password is incorrect")
    if verify_password(user.password_hash, data.new_password):
        raise HTTPException(422, "New password must be different from the current password")
    user.password_hash = hash_password(data.new_password)
    user.must_change_password = False
    user.auth_version += 1
    audit(db, user, "account.password_changed", "user", user.id)
    db.commit()
    set_session(response, user)
    return user_json(user)


@app.get("/api/state/revision")
def state_revision(request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)):
    payload = latest_revision(db)
    etag = f'"{payload["revision"]}"'
    headers = {"ETag": etag, "Cache-Control": "private, no-cache, must-revalidate"}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    return JSONResponse(payload, headers=headers)


@app.get("/api/users")
def list_users(db: Session = Depends(get_db), user: User = Depends(admin_user)):
    return [user_json(row) for row in db.scalars(select(User).order_by(User.display_name, User.email)).all()]


@app.post("/api/users", status_code=201)
def create_user(data: UserCreateInput, db: Session = Depends(get_db), user: User = Depends(admin_user)):
    email = data.email.strip().lower()
    display_name = data.display_name.strip()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise HTTPException(422, "Enter a valid email address")
    if not display_name:
        raise HTTPException(422, "Enter a display name")
    record = User(email=email, display_name=display_name, password_hash=hash_password(data.password), role=data.role, must_change_password=True, active=True)
    db.add(record)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A user with this email address already exists") from None
    audit(db, user, "user.created", "user", record.id, {"email": record.email, "role": record.role})
    db.commit()
    return user_json(record)


@app.patch("/api/users/{user_id}/status")
def update_user_status(user_id: uuid.UUID, data: UserStatusInput, db: Session = Depends(get_db), user: User = Depends(admin_user)):
    record = db.get(User, user_id)
    if not record:
        raise HTTPException(404, "User not found")
    if record.id == user.id and not data.active:
        raise HTTPException(409, "You cannot deactivate your own account")
    if record.role == "admin" and not data.active:
        active_admins = db.scalar(select(func.count()).select_from(User).where(User.role == "admin", User.active.is_(True))) or 0
        if active_admins <= 1:
            raise HTTPException(409, "At least one active administrator is required")
    record.active = data.active
    audit(db, user, "user.activated" if data.active else "user.deactivated", "user", record.id)
    db.commit()
    return user_json(record)


@app.put("/api/users/{user_id}/password")
def reset_user_password(user_id: uuid.UUID, data: AdminPasswordResetInput, db: Session = Depends(get_db), user: User = Depends(admin_user)):
    record = db.get(User, user_id)
    if not record:
        raise HTTPException(404, "User not found")
    if record.id == user.id:
        raise HTTPException(409, "Change your own password under Account")
    if verify_password(record.password_hash, data.temporary_password):
        raise HTTPException(422, "Temporary password must be different from the current password")
    record.password_hash = hash_password(data.temporary_password)
    record.must_change_password = True
    record.auth_version += 1
    audit(db, user, "user.password_reset", "user", record.id)
    db.commit()
    return user_json(record)


def reorder_payload(db: Session, include_all: bool = False) -> dict:
    global_setting = inventory_setting(db)
    rules = {rule.product_key: rule for rule in db.scalars(select(ReorderRule)).all()}
    grouped: dict[str, dict] = {}
    for spool in db.scalars(select(Spool).where(Spool.archived.is_(False))).all():
        item = spool_json(db, spool)
        key = product_key(spool)
        group = grouped.setdefault(key, {
            "productKey": key, "brand": spool.brand, "materialName": spool.material_name,
            "materialType": spool.material_type, "colorName": spool.color_name, "colorHex": spool.color_hex,
            "diameterMm": float(spool.diameter_mm), "spoolCount": 0,
            "remainingWeightG": 0.0, "reservedWeightG": 0.0, "availableWeightG": 0.0,
            "remainingLengthM": 0.0, "reservedLengthM": 0.0, "availableLengthM": 0.0,
        })
        group["spoolCount"] += 1
        for field in ("remainingWeightG", "reservedWeightG", "availableWeightG", "remainingLengthM", "reservedLengthM", "availableLengthM"):
            group[field] += item[field]
    result = []
    for key, group in grouped.items():
        rule = rules.get(key)
        threshold_mg = rule.threshold_mg if rule and rule.threshold_mg is not None else global_setting.reorder_threshold_mg
        group["thresholdG"] = mg_to_grams(threshold_mg)
        group["ignored"] = bool(rule and rule.ignored)
        group["shortageG"] = max(0.0, group["thresholdG"] - group["availableWeightG"])
        group["needsOrdering"] = not group["ignored"] and group["availableWeightG"] < group["thresholdG"]
        for field in ("remainingWeightG", "reservedWeightG", "availableWeightG", "remainingLengthM", "reservedLengthM", "availableLengthM", "shortageG"):
            group[field] = round(group[field], 3)
        if include_all or group["needsOrdering"]: result.append(group)
    result.sort(key=lambda item: (-item["shortageG"], item["brand"].casefold(), item["materialName"].casefold()))
    return {"defaultThresholdG": mg_to_grams(global_setting.reorder_threshold_mg), "groups": result}


def operational_status(db: Session) -> dict:
    now = now_utc()
    def utc_value(value: datetime | None) -> datetime | None:
        return value.replace(tzinfo=timezone.utc) if value and value.tzinfo is None else value
    snapshot = db.scalar(select(CatalogSnapshot).where(CatalogSnapshot.active.is_(True)))
    catalog_failure = db.scalar(select(AuditEvent).where(AuditEvent.action == "catalog.sync_failed").order_by(AuditEvent.created_at.desc()).limit(1))
    snapshot_at = utc_value(snapshot.created_at) if snapshot else None
    failure_at = utc_value(catalog_failure.created_at) if catalog_failure else None
    catalog_failed = bool(failure_at and (not snapshot_at or failure_at > snapshot_at))
    backup_files = []
    with contextlib.suppress(OSError):
        backup_files = [path for path in settings.backup_dir.rglob("*.dump") if path.is_file()]
    latest_backup = max((datetime.fromtimestamp(path.stat().st_mtime, timezone.utc) for path in backup_files), default=None)
    oldest_job = db.scalar(select(PrintJob.created_at).where(PrintJob.status.in_(["NEW", "MAPPED", "NEEDS_REVIEW"])).order_by(PrintJob.created_at).limit(1))
    stale_jobs = db.scalar(select(func.count()).select_from(PrintJob).where(PrintJob.status.in_(["NEW", "MAPPED", "NEEDS_REVIEW"]), PrintJob.created_at < now - timedelta(days=7))) or 0
    open_job_rows = db.scalars(select(PrintJob).where(PrintJob.status.in_(["NEW", "MAPPED", "NEEDS_REVIEW"]))).all()
    unknown_profiles = sum(1 for job in open_job_rows if job.printer_snapshot.get("routingMode") == "default")
    unweighed = 0
    for spool in db.scalars(select(Spool).where(Spool.archived.is_(False))).all():
        weighed = db.scalar(select(InventoryEntry.created_at).where(InventoryEntry.spool_id == spool.id, InventoryEntry.kind == "WEIGHING").order_by(InventoryEntry.created_at.desc()).limit(1))
        weighed_at, created_at = utc_value(weighed), utc_value(spool.created_at)
        if (weighed_at and weighed_at < now - timedelta(days=90)) or (not weighed_at and created_at and created_at < now - timedelta(days=90)): unweighed += 1
    return {
        "catalog": {"ready": bool(snapshot), "updatedAt": snapshot_at.isoformat() if snapshot_at else None, "stale": not snapshot_at or snapshot_at < now - timedelta(days=2), "failed": catalog_failed},
        "backup": {"ready": bool(latest_backup), "updatedAt": latest_backup.isoformat() if latest_backup else None, "stale": not latest_backup or latest_backup < now - timedelta(days=2)},
        "oldestOpenJobAt": oldest_job.isoformat() if oldest_job else None,
        "staleJobs": stale_jobs, "unknownProfiles": unknown_profiles, "unweighedSpools": unweighed,
    }


@app.get("/api/inventory/reorder-suggestions")
def reorder_suggestions(all_groups: bool = Query(False, alias="all"), db: Session = Depends(get_db), user: User = Depends(current_user)):
    return reorder_payload(db, all_groups)


@app.put("/api/inventory/settings")
def update_inventory_settings(data: InventorySettingsInput, db: Session = Depends(get_db), user: User = Depends(admin_user)):
    record = inventory_setting(db); old = record.reorder_threshold_mg
    record.reorder_threshold_mg = grams_to_mg(data.reorder_threshold_g); record.updated_by_id = user.id; record.updated_at = now_utc()
    audit(db, user, "inventory.settings_updated", "inventory_settings", None, {"reorderThresholdMg": {"old": old, "new": record.reorder_threshold_mg}}); db.commit()
    return {"reorderThresholdG": mg_to_grams(record.reorder_threshold_mg)}


@app.put("/api/inventory/reorder-rules")
def update_reorder_rule(data: ReorderRuleInput, db: Session = Depends(get_db), user: User = Depends(admin_user)):
    record = db.scalar(select(ReorderRule).where(ReorderRule.product_key == data.product_key).with_for_update())
    if not record:
        record = ReorderRule(product_key=data.product_key, updated_by_id=user.id)
        db.add(record)
    record.threshold_mg = grams_to_mg(data.threshold_g) if data.threshold_g is not None else None
    record.ignored, record.product_snapshot, record.updated_by_id, record.updated_at = data.ignored, data.product_snapshot, user.id, now_utc()
    db.flush(); audit(db, user, "inventory.reorder_rule_updated", "reorder_rule", record.id, {"productKey": record.product_key}); db.commit()
    return {"id": str(record.id), "productKey": record.product_key, "thresholdG": mg_to_grams(record.threshold_mg) if record.threshold_mg is not None else None, "ignored": record.ignored}


@app.get("/api/wishlist")
def list_wishlist(
    q: str = "", status: str = "", brand: str = "", material: str = "", archived: bool = False,
    db: Session = Depends(get_db), user: User = Depends(current_user),
):
    if status and status not in {"saved", "buy_soon"}:
        raise HTTPException(422, "Unknown wishlist status")
    statement = select(WishlistItem).where(WishlistItem.archived == archived)
    searchable = (WishlistItem.brand, WishlistItem.material_name, WishlistItem.material_type, WishlistItem.color_name, WishlistItem.color_hex, WishlistItem.note)
    for token in re.findall(r"[^\s]+", q.strip())[:12]:
        needle = f"%{token}%"
        statement = statement.where(or_(*(column.ilike(needle) for column in searchable)))
    if status:
        statement = statement.where(WishlistItem.status == status)
    if brand:
        statement = statement.where(func.lower(WishlistItem.brand) == brand.casefold())
    if material:
        statement = statement.where(func.lower(WishlistItem.material_type) == material.casefold())
    rows = list(db.scalars(statement).all())
    rows.sort(key=lambda row: (row.status != "buy_soon", -row.updated_at.timestamp(), row.brand.casefold(), row.material_name.casefold()))
    return [wishlist_json(row) for row in rows]


@app.post("/api/wishlist", status_code=201)
def create_wishlist_item(data: WishlistInput, db: Session = Depends(get_db), user: User = Depends(current_user)):
    key = wishlist_product_key(data)
    existing = db.scalar(select(WishlistItem).where(WishlistItem.active_key == key))
    if existing:
        raise HTTPException(409, f"This filament is already on the wishlist as {existing.brand} · {existing.material_name}")
    item = WishlistItem(product_key=key, active_key=key, created_by_id=user.id, updated_by_id=user.id)
    apply_wishlist_input(item, data, user)
    db.add(item)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "This filament is already on the wishlist") from exc
    audit(db, user, "wishlist.created", "wishlist_item", item.id, {"status": item.status, "productKey": item.product_key})
    db.commit()
    return wishlist_json(item)


@app.put("/api/wishlist/{item_id}")
def update_wishlist_item(item_id: uuid.UUID, data: WishlistInput, db: Session = Depends(get_db), user: User = Depends(current_user)):
    item = db.get(WishlistItem, item_id, with_for_update=True)
    if not item or item.archived:
        raise HTTPException(404, "Wishlist item not found")
    key = wishlist_product_key(data)
    duplicate = db.scalar(select(WishlistItem.id).where(WishlistItem.active_key == key, WishlistItem.id != item.id))
    if duplicate:
        raise HTTPException(409, "This filament is already on the wishlist")
    previous_status = item.status
    apply_wishlist_input(item, data, user)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "This filament is already on the wishlist") from exc
    audit(db, user, "wishlist.updated", "wishlist_item", item.id, {"status": {"old": previous_status, "new": item.status}, "productKey": item.product_key})
    db.commit()
    return wishlist_json(item)


@app.post("/api/wishlist/{item_id}/archive")
def archive_wishlist_item(item_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(current_user)):
    item = db.get(WishlistItem, item_id, with_for_update=True)
    if not item or item.archived:
        raise HTTPException(404, "Wishlist item not found")
    item.archived = True
    item.active_key = None
    item.updated_by_id = user.id
    item.updated_at = now_utc()
    audit(db, user, "wishlist.archived", "wishlist_item", item.id, {"productKey": item.product_key})
    db.commit()
    return {"ok": True}


@app.post("/api/wishlist/{item_id}/convert-to-spool", status_code=201)
def convert_wishlist_to_spool(item_id: uuid.UUID, data: WishlistConvertInput, db: Session = Depends(get_db), user: User = Depends(current_user)):
    item = db.get(WishlistItem, item_id, with_for_update=True)
    if not item or item.archived:
        raise HTTPException(404, "Wishlist item not found")
    weight_mg = grams_to_mg(data.initial_weight_g)
    if weight_mg < 0:
        raise HTTPException(422, "Initial filament inventory cannot be negative")
    length_mm = data.initial_length_m * 1000 if data.initial_length_m is not None else weight_mg_to_length_mm(weight_mg, data.diameter_mm, data.density_g_cm3)
    spool = Spool(
        code=next_code(db, Spool, "SPL"), brand=data.brand.strip(), material_name=data.material_name.strip(), material_type=data.material_type.strip(),
        color_name=data.color_name.strip() or nearest_color(data.color_hex)[0], color_hex=data.color_hex, location=data.location.strip(),
        lot_number=data.lot_number.strip(), serial_number=data.serial_number.strip(), diameter_mm=data.diameter_mm, density_g_cm3=data.density_g_cm3,
        tare_weight_mg=grams_to_mg(data.tare_weight_g), initial_weight_mg=weight_mg, remaining_weight_mg=weight_mg,
        initial_length_mm=length_mm, remaining_length_mm=length_mm, low_stock_weight_mg=grams_to_mg(data.low_stock_weight_g),
        purchase_price_cents=int(data.purchase_price * 100) if data.purchase_price is not None else None, currency=data.currency.upper(),
        opt_brand_uuid=item.opt_brand_uuid, opt_material_uuid=item.opt_material_uuid, opt_package_uuid=item.opt_package_uuid,
        opt_container_uuid=item.opt_container_uuid, catalog_snapshot=item.catalog_snapshot,
    )
    db.add(spool)
    db.flush()
    db.add(InventoryEntry(
        spool_id=spool.id, kind="INITIAL", weight_delta_mg=weight_mg, length_delta_mm=length_mm,
        diameter_mm=spool.diameter_mm, density_g_cm3=spool.density_g_cm3, note=f"Created from wishlist: {item.brand} · {item.material_name}", actor_id=user.id,
    ))
    item.archived = True
    item.active_key = None
    item.updated_by_id = user.id
    item.updated_at = now_utc()
    audit(db, user, "spool.created", "spool", spool.id, {"code": spool.code, "wishlistItemId": str(item.id)})
    audit(db, user, "wishlist.converted_to_spool", "wishlist_item", item.id, {"spoolId": str(spool.id), "spoolCode": spool.code})
    db.commit()
    return spool_json(db, spool)


@app.get("/api/operational-status")
def get_operational_status(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return operational_status(db)


@app.get("/api/activity")
def entity_activity(entity_type: str, entity_id: uuid.UUID, limit: int = Query(50, ge=1, le=200), db: Session = Depends(get_db), user: User = Depends(current_user)):
    if entity_type not in {"spool", "printer", "printer_tool", "print_job"}: raise HTTPException(422, "Unsupported activity entity")
    rows = db.scalars(select(AuditEvent).where(AuditEvent.entity_type == entity_type, AuditEvent.entity_id == entity_id).order_by(AuditEvent.created_at.desc()).limit(limit)).all()
    return [{"id": str(row.id), "action": row.action, "details": row.details, "createdAt": row.created_at.isoformat()} for row in rows]


@app.get("/api/dashboard")
def dashboard(db: Session = Depends(get_db), user: User = Depends(current_user)):
    spools = db.scalars(select(Spool).where(Spool.archived.is_(False))).all()
    spool_payload = [spool_json(db, spool) for spool in spools]
    remaining_weight = sum(spool.remaining_weight_mg for spool in spools)
    remaining_length = sum((spool.remaining_length_mm for spool in spools), Decimal("0"))
    open_statuses = ["NEW", "MAPPED", "NEEDS_REVIEW"]
    reserved_weight = db.scalar(select(func.coalesce(func.sum(func.coalesce(JobUsage.actual_weight_mg, JobUsage.estimated_weight_mg)), 0)).join(PrintJob).where(PrintJob.status.in_(open_statuses))) or 0
    reserved_length = db.scalar(select(func.coalesce(func.sum(func.coalesce(JobUsage.actual_length_mm, JobUsage.estimated_length_mm)), 0)).join(PrintJob).where(PrintJob.status.in_(open_statuses))) or Decimal("0")
    mapped_reserved_weight = db.scalar(select(func.coalesce(func.sum(func.coalesce(JobUsage.actual_weight_mg, JobUsage.estimated_weight_mg)), 0)).join(PrintJob).where(PrintJob.status.in_(open_statuses), JobUsage.mapped_spool_id.is_not(None))) or 0
    mapped_reserved_length = db.scalar(select(func.coalesce(func.sum(func.coalesce(JobUsage.actual_length_mm, JobUsage.estimated_length_mm)), 0)).join(PrintJob).where(PrintJob.status.in_(open_statuses), JobUsage.mapped_spool_id.is_not(None))) or Decimal("0")
    printers = db.scalars(select(Printer).where(Printer.archived.is_(False)).options(selectinload(Printer.tools).selectinload(PrinterTool.loaded_spool))).all()
    jobs = db.scalars(select(PrintJob).where(PrintJob.status.in_(["NEW", "MAPPED", "NEEDS_REVIEW"])).options(selectinload(PrintJob.usages)).order_by(PrintJob.created_at.desc()).limit(8)).all()
    open_job_count = db.scalar(select(func.count()).select_from(PrintJob).where(PrintJob.status.in_(["NEW", "MAPPED", "NEEDS_REVIEW"]))) or 0
    status = operational_status(db)
    reorder = reorder_payload(db)
    return {"summary": {"remainingWeightG": mg_to_grams(remaining_weight), "remainingLengthM": float(remaining_length / 1000), "reservedWeightG": mg_to_grams(int(reserved_weight)), "reservedLengthM": float(Decimal(reserved_length) / 1000), "mappedReservedWeightG": mg_to_grams(int(mapped_reserved_weight)), "mappedReservedLengthM": float(Decimal(mapped_reserved_length) / 1000), "unassignedReservedWeightG": mg_to_grams(int(reserved_weight) - int(mapped_reserved_weight)), "unassignedReservedLengthM": float((Decimal(reserved_length) - Decimal(mapped_reserved_length)) / 1000), "availableWeightG": mg_to_grams(remaining_weight - int(reserved_weight)), "availableLengthM": float((remaining_length - Decimal(reserved_length)) / 1000), "activeSpools": len(spools), "lowStockSpools": sum(1 for spool in spools if spool.remaining_weight_mg <= spool.low_stock_weight_mg), "loadedSpools": sum(1 for item in spool_payload if item["loadedOn"]), "openJobs": open_job_count, "negativeSpools": sum(1 for item in spool_payload if item["availableWeightG"] < 0)}, "spools": spool_payload[:8], "printers": [printer_json(p) for p in printers], "jobs": [job_json(j) for j in jobs], "attention": status, "reorder": {"defaultThresholdG": reorder["defaultThresholdG"], "groups": reorder["groups"][:8]}}


@app.get("/api/spools")
def list_spools(
    q: str = "", archived: bool = False, brand: str = "", material: str = "", color: str = "", location: str = "",
    load_state: str = Query("", alias="loadState"), stock_state: str = Query("", alias="stockState"),
    printer: str = "", color_hex: str = Query("", alias="colorHex"), delta_e: float = Query(12, alias="deltaE", ge=2, le=30),
    sort: str = "code-desc", db: Session = Depends(get_db), user: User = Depends(current_user),
):
    statement = select(Spool).where(Spool.archived == archived)
    searchable = (Spool.code, Spool.brand, Spool.material_name, Spool.material_type, Spool.color_name, Spool.color_hex, Spool.location, Spool.lot_number, Spool.serial_number)
    for token in re.findall(r"[^\s]+", q.strip())[:12]:
        needle = f"%{token}%"
        statement = statement.where(or_(*(column.ilike(needle) for column in searchable)))
    if brand: statement = statement.where(func.lower(Spool.brand) == brand.casefold())
    if material: statement = statement.where(func.lower(Spool.material_type) == material.casefold())
    if color: statement = statement.where(or_(func.lower(Spool.color_name) == color.casefold(), func.lower(Spool.color_hex) == color.casefold()))
    if location: statement = statement.where(func.lower(Spool.location) == location.casefold())
    rows = list(db.scalars(statement).all())
    payload = [spool_json(db, spool) for spool in rows]
    if load_state in {"loaded", "unloaded"}:
        payload = [item for item in payload if bool(item["loadedOn"]) == (load_state == "loaded")]
    if stock_state in {"low", "healthy", "negative"}:
        payload = [item for item in payload if (item["availableWeightG"] < 0 if stock_state == "negative" else item["lowStock"] == (stock_state == "low"))]
    if printer:
        payload = [item for item in payload if item["loadedOn"] and item["loadedOn"]["printerCode"] == printer]
    if color_hex:
        try: payload = [item for item in payload if color_distance(item["colorHex"], color_hex) <= delta_e]
        except ValueError as exc: raise HTTPException(422, str(exc)) from exc
    sorters = {
        "code-asc": lambda item: item["code"], "code-desc": lambda item: item["code"],
        "brand-asc": lambda item: (item["brand"].casefold(), item["materialName"].casefold()),
        "available-asc": lambda item: item["availableWeightG"], "available-desc": lambda item: item["availableWeightG"],
    }
    if sort not in sorters: raise HTTPException(422, "Unknown spool sort order")
    return sorted(payload, key=sorters[sort], reverse=sort.endswith("desc"))


@app.post("/api/spools", status_code=201)
def create_spool(data: SpoolInput, db: Session = Depends(get_db), user: User = Depends(current_user)):
    weight_mg = grams_to_mg(data.initial_weight_g)
    length_mm = data.initial_length_m * 1000 if data.initial_length_m is not None else weight_mg_to_length_mm(weight_mg, data.diameter_mm, data.density_g_cm3)
    color_name = data.color_name.strip() or nearest_color(data.color_hex)[0]
    spool = Spool(code=next_code(db, Spool, "SPL"), brand=data.brand.strip(), material_name=data.material_name.strip(), material_type=data.material_type.strip(), color_name=color_name, color_hex=data.color_hex, location=data.location.strip(), lot_number=data.lot_number.strip(), serial_number=data.serial_number.strip(), diameter_mm=data.diameter_mm, density_g_cm3=data.density_g_cm3, tare_weight_mg=grams_to_mg(data.tare_weight_g), initial_weight_mg=weight_mg, remaining_weight_mg=weight_mg, initial_length_mm=length_mm, remaining_length_mm=length_mm, low_stock_weight_mg=grams_to_mg(data.low_stock_weight_g), purchase_price_cents=int(data.purchase_price * 100) if data.purchase_price is not None else None, currency=data.currency.upper(), opt_brand_uuid=uuid.UUID(data.opt_brand_uuid) if data.opt_brand_uuid else None, opt_material_uuid=uuid.UUID(data.opt_material_uuid) if data.opt_material_uuid else None, opt_package_uuid=uuid.UUID(data.opt_package_uuid) if data.opt_package_uuid else None, opt_container_uuid=uuid.UUID(data.opt_container_uuid) if data.opt_container_uuid else None, catalog_snapshot=data.catalog_snapshot)
    db.add(spool); db.flush()
    db.add(InventoryEntry(spool_id=spool.id, kind="INITIAL", weight_delta_mg=weight_mg, length_delta_mm=length_mm, diameter_mm=spool.diameter_mm, density_g_cm3=spool.density_g_cm3, note="New spool", actor_id=user.id))
    audit(db, user, "spool.created", "spool", spool.id, {"code": spool.code}); db.commit()
    return spool_json(db, spool)


@app.get("/api/spools/ranked")
def ranked_spools(
    material_type: str = Query("", alias="materialType"),
    color_hex: str = Query("", alias="colorHex"),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """Rank candidates for job mapping without excluding imperfect matches."""
    rows = db.scalars(select(Spool).where(Spool.archived.is_(False))).all()
    payload = [spool_json(db, spool) for spool in rows]
    try:
        return sorted(
            payload,
            key=lambda item: (
                item["materialType"].casefold() != material_type.casefold(),
                color_distance(item["colorHex"], color_hex) if color_hex else 0,
                -item["availableWeightG"],
                item["code"],
            ),
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.put("/api/spools/{spool_id}")
def update_spool(spool_id: uuid.UUID, data: SpoolUpdateInput, db: Session = Depends(get_db), user: User = Depends(current_user)):
    spool = db.get(Spool, spool_id, with_for_update=True)
    if not spool: raise HTTPException(404, "Spool not found")
    old = {"brand": spool.brand, "materialName": spool.material_name, "materialType": spool.material_type, "colorName": spool.color_name, "colorHex": spool.color_hex, "location": spool.location, "lotNumber": spool.lot_number, "serialNumber": spool.serial_number, "diameterMm": str(spool.diameter_mm), "density": str(spool.density_g_cm3), "tareWeightMg": spool.tare_weight_mg, "lowStockWeightMg": spool.low_stock_weight_mg, "purchasePriceCents": spool.purchase_price_cents, "currency": spool.currency}
    conversion_changed = spool.diameter_mm != data.diameter_mm or spool.density_g_cm3 != data.density_g_cm3
    if conversion_changed:
        new_initial_length = weight_mg_to_length_mm(spool.initial_weight_mg, data.diameter_mm, data.density_g_cm3)
        new_remaining_length = weight_mg_to_length_mm(spool.remaining_weight_mg, data.diameter_mm, data.density_g_cm3)
        delta_length = new_remaining_length - spool.remaining_length_mm
        spool.initial_length_mm, spool.remaining_length_mm = new_initial_length, new_remaining_length
        if delta_length:
            db.add(InventoryEntry(spool_id=spool.id, kind="METADATA_CORRECTION", weight_delta_mg=0, length_delta_mm=delta_length, diameter_mm=data.diameter_mm, density_g_cm3=data.density_g_cm3, note="Length recalculated after diameter or density correction", actor_id=user.id))
    spool.brand, spool.material_name, spool.material_type = data.brand.strip(), data.material_name.strip(), data.material_type.strip()
    spool.color_name, spool.color_hex = data.color_name.strip() or nearest_color(data.color_hex)[0], data.color_hex
    spool.location, spool.lot_number, spool.serial_number = data.location.strip(), data.lot_number.strip(), data.serial_number.strip()
    spool.diameter_mm, spool.density_g_cm3 = data.diameter_mm, data.density_g_cm3
    spool.tare_weight_mg, spool.low_stock_weight_mg = grams_to_mg(data.tare_weight_g), grams_to_mg(data.low_stock_weight_g)
    spool.purchase_price_cents = int(data.purchase_price * 100) if data.purchase_price is not None else None
    spool.currency = data.currency
    new = {"brand": spool.brand, "materialName": spool.material_name, "materialType": spool.material_type, "colorName": spool.color_name, "colorHex": spool.color_hex, "location": spool.location, "lotNumber": spool.lot_number, "serialNumber": spool.serial_number, "diameterMm": str(spool.diameter_mm), "density": str(spool.density_g_cm3), "tareWeightMg": spool.tare_weight_mg, "lowStockWeightMg": spool.low_stock_weight_mg, "purchasePriceCents": spool.purchase_price_cents, "currency": spool.currency}
    changes = {key: {"old": old[key], "new": value} for key, value in new.items() if old[key] != value}
    audit(db, user, "spool.updated", "spool", spool.id, {"changes": changes}); db.commit()
    return spool_json(db, spool)


@app.get("/api/spools/{spool_id}")
def get_spool(spool_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(current_user)):
    spool = db.get(Spool, spool_id)
    if not spool: raise HTTPException(404, "Spool not found")
    payload = spool_json(db, spool)
    entries = db.scalars(select(InventoryEntry).where(InventoryEntry.spool_id == spool.id).order_by(InventoryEntry.created_at.desc())).all()
    payload["ledger"] = [{"id": str(e.id), "kind": e.kind, "weightDeltaG": mg_to_grams(e.weight_delta_mg), "lengthDeltaM": float(e.length_delta_mm / 1000), "note": e.note, "createdAt": e.created_at.isoformat()} for e in entries]
    return payload


@app.post("/api/spools/{spool_id}/weigh")
def weigh_spool(spool_id: uuid.UUID, data: WeighInput, db: Session = Depends(get_db), user: User = Depends(current_user)):
    spool = db.get(Spool, spool_id, with_for_update=True)
    if not spool: raise HTTPException(404, "Spool not found")
    supplied = [data.total_weight_g is not None, data.net_weight_g is not None, data.consumed_weight_g is not None]
    if sum(supplied) != 1: raise HTTPException(422, "Enter exactly one total, net, or consumed weight")
    if data.consumed_weight_g is not None:
        consumed_mg = grams_to_mg(data.consumed_weight_g)
        if consumed_mg <= 0: raise HTTPException(422, "Consumed weight must be greater than zero")
        target_mg = spool.remaining_weight_mg - consumed_mg
        if target_mg < 0 and not data.allow_negative:
            raise HTTPException(409, f"{spool.code} would become negative; confirm the inventory discrepancy")
        entry_kind = "MANUAL_CONSUMPTION"
        audit_action = "spool.consumption_recorded"
    else:
        target_mg = grams_to_mg(data.net_weight_g) if data.net_weight_g is not None else grams_to_mg(data.total_weight_g) - spool.tare_weight_mg
        entry_kind = "WEIGHING"
        audit_action = "spool.weighed"
    target_length = weight_mg_to_length_mm(target_mg, spool.diameter_mm, spool.density_g_cm3)
    delta_weight, delta_length = target_mg - spool.remaining_weight_mg, target_length - spool.remaining_length_mm
    spool.remaining_weight_mg, spool.remaining_length_mm = target_mg, target_length
    if target_mg < 0 or target_length < 0: spool.discrepancy = True
    db.add(InventoryEntry(spool_id=spool.id, kind=entry_kind, weight_delta_mg=delta_weight, length_delta_mm=delta_length, diameter_mm=spool.diameter_mm, density_g_cm3=spool.density_g_cm3, note=data.note, actor_id=user.id))
    audit(db, user, audit_action, "spool", spool.id, {"weight_delta_mg": delta_weight}); db.commit()
    return spool_json(db, spool)


@app.post("/api/spools/{spool_id}/archive")
def archive_spool(spool_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(current_user)):
    spool = db.get(Spool, spool_id)
    if not spool: raise HTTPException(404, "Spool not found")
    db.query(PrinterTool).filter(PrinterTool.loaded_spool_id == spool.id).update({PrinterTool.loaded_spool_id: None})
    spool.archived = True; audit(db, user, "spool.archived", "spool", spool.id); db.commit(); return {"ok": True}


@app.post("/api/spools/{spool_id}/restore-and-repurpose")
def restore_and_repurpose_spool(
    spool_id: uuid.UUID,
    data: SpoolRepurposeInput,
    db: Session = Depends(get_db),
    user: User = Depends(admin_user),
):
    """Reuse an inactive setup record only when it has no print history."""
    spool = db.get(Spool, spool_id, with_for_update=True)
    if not spool:
        raise HTTPException(404, "Spool not found")
    if not spool.archived:
        raise HTTPException(409, "Only an inactive spool can be restored and repurposed")

    print_ledger_entries = db.scalar(
        select(func.count()).select_from(InventoryEntry).where(
            InventoryEntry.spool_id == spool.id,
            or_(InventoryEntry.job_id.is_not(None), InventoryEntry.kind == "PRINT"),
        )
    ) or 0
    job_references = db.scalar(
        select(func.count()).select_from(JobUsage).where(
            or_(JobUsage.mapped_spool_id == spool.id, JobUsage.suggested_spool_id == spool.id)
        )
    ) or 0
    if print_ledger_entries or job_references:
        raise HTTPException(
            409,
            "This spool has print-job history and cannot be repurposed. Restore it as the same physical spool instead.",
        )

    if not data.brand.strip() or not data.material_name.strip() or not data.material_type.strip():
        raise HTTPException(422, "Brand, material name, and material type are required")

    previous = {
        "brand": spool.brand,
        "materialName": spool.material_name,
        "materialType": spool.material_type,
        "remainingWeightMg": spool.remaining_weight_mg,
    }
    target_weight_mg = grams_to_mg(data.initial_weight_g)
    target_length_mm = (
        data.initial_length_m * 1000
        if data.initial_length_m is not None
        else weight_mg_to_length_mm(target_weight_mg, data.diameter_mm, data.density_g_cm3)
    )
    if target_weight_mg < 0 or target_length_mm < 0:
        raise HTTPException(422, "Current filament inventory cannot be negative")
    delta_weight = target_weight_mg - spool.remaining_weight_mg
    delta_length = target_length_mm - spool.remaining_length_mm

    spool.brand = data.brand.strip()
    spool.material_name = data.material_name.strip()
    spool.material_type = data.material_type.strip()
    spool.color_name = data.color_name.strip() or nearest_color(data.color_hex)[0]
    spool.color_hex = data.color_hex
    spool.location = data.location.strip()
    spool.lot_number = data.lot_number.strip()
    spool.serial_number = data.serial_number.strip()
    spool.diameter_mm = data.diameter_mm
    spool.density_g_cm3 = data.density_g_cm3
    spool.tare_weight_mg = grams_to_mg(data.tare_weight_g)
    spool.initial_weight_mg = target_weight_mg
    spool.remaining_weight_mg = target_weight_mg
    spool.initial_length_mm = target_length_mm
    spool.remaining_length_mm = target_length_mm
    spool.low_stock_weight_mg = grams_to_mg(data.low_stock_weight_g)
    spool.purchase_price_cents = int(data.purchase_price * 100) if data.purchase_price is not None else None
    spool.currency = data.currency.strip().upper()
    spool.opt_brand_uuid = uuid.UUID(data.opt_brand_uuid) if data.opt_brand_uuid else None
    spool.opt_material_uuid = uuid.UUID(data.opt_material_uuid) if data.opt_material_uuid else None
    spool.opt_package_uuid = uuid.UUID(data.opt_package_uuid) if data.opt_package_uuid else None
    spool.opt_container_uuid = uuid.UUID(data.opt_container_uuid) if data.opt_container_uuid else None
    spool.catalog_snapshot = data.catalog_snapshot
    spool.archived = False
    spool.discrepancy = False
    db.add(InventoryEntry(
        spool_id=spool.id,
        kind="REPURPOSED",
        weight_delta_mg=delta_weight,
        length_delta_mm=delta_length,
        diameter_mm=spool.diameter_mm,
        density_g_cm3=spool.density_g_cm3,
        note=data.note,
        actor_id=user.id,
    ))
    audit(db, user, "spool.restored_and_repurposed", "spool", spool.id, {
        "code": spool.code,
        "previous": previous,
        "new": {
            "brand": spool.brand,
            "materialName": spool.material_name,
            "materialType": spool.material_type,
            "remainingWeightMg": spool.remaining_weight_mg,
        },
        "weightDeltaMg": delta_weight,
        "lengthDeltaMm": str(delta_length),
    })
    db.commit()
    return spool_json(db, spool)


@app.post("/api/spools/{spool_id}/empty")
def empty_spool(spool_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(current_user)):
    spool = db.get(Spool, spool_id, with_for_update=True)
    if not spool:
        raise HTTPException(404, "Spool not found")
    if spool.archived:
        raise HTTPException(409, "Spool is already inactive")
    reservations = db.scalar(
        select(func.count())
        .select_from(JobUsage)
        .join(PrintJob, PrintJob.id == JobUsage.job_id)
        .where(JobUsage.mapped_spool_id == spool.id, PrintJob.status.in_(["MAPPED", "NEEDS_REVIEW"]))
    ) or 0
    if reservations:
        raise HTTPException(409, "This spool is reserved by an open print job. Remap or dismiss that job first.")
    delta_weight = -spool.remaining_weight_mg
    delta_length = -spool.remaining_length_mm
    had_stock = spool.remaining_weight_mg != 0 or spool.remaining_length_mm != 0
    spool.remaining_weight_mg = 0
    spool.remaining_length_mm = Decimal("0")
    spool.archived = True
    if had_stock:
        spool.discrepancy = True
    db.query(PrinterTool).filter(PrinterTool.loaded_spool_id == spool.id).update({PrinterTool.loaded_spool_id: None})
    db.add(InventoryEntry(spool_id=spool.id, kind="EMPTY", weight_delta_mg=delta_weight, length_delta_mm=delta_length, diameter_mm=spool.diameter_mm, density_g_cm3=spool.density_g_cm3, note="Marked empty and archived", actor_id=user.id))
    audit(db, user, "spool.emptied", "spool", spool.id, {"weight_delta_mg": delta_weight, "length_delta_mm": str(delta_length)})
    db.commit()
    return spool_json(db, spool)


@app.get("/api/spools/{spool_id}/label.svg")
def spool_label(spool_id: uuid.UUID, request: Request, template_id: uuid.UUID | None = Query(default=None, alias="templateId"), monochrome: bool = False, db: Session = Depends(get_db), user: User = Depends(current_user)):
    spool = db.get(Spool, spool_id)
    if not spool: raise HTTPException(404, "Spool not found")
    template = db.get(LabelTemplate, template_id) if template_id else db.scalar(select(LabelTemplate).where(LabelTemplate.is_default.is_(True), LabelTemplate.archived.is_(False)))
    if template_id and (not template or template.archived): raise HTTPException(404, "Label template not found")
    base_url = settings.public_url or str(request.base_url)
    target = f"{base_url.rstrip('/')}/spools/{spool.id}"
    rendered = render_label(spool, target, float(template.width_mm), float(template.height_mm), template.layout, monochrome) if template else render_spool_label(spool, target)
    return Response(rendered, media_type="image/svg+xml", headers={"Content-Disposition": f'inline; filename="{spool.code}.svg"', "Cache-Control": "private, no-cache"})


@app.get("/api/label-templates")
def list_label_templates(archived: bool = False, db: Session = Depends(get_db), user: User = Depends(current_user)):
    rows = db.scalars(select(LabelTemplate).where(LabelTemplate.archived == archived).order_by(LabelTemplate.builtin.desc(), LabelTemplate.name)).all()
    return [template_json(row) for row in rows]


@app.post("/api/label-templates", status_code=201)
def create_label_template(data: LabelTemplateInput, db: Session = Depends(get_db), user: User = Depends(admin_user)):
    try: layout = validate_layout(data.width_mm, data.height_mm, data.layout)
    except ValueError as exc: raise HTTPException(422, str(exc)) from exc
    record = LabelTemplate(name=data.name, width_mm=data.width_mm, height_mm=data.height_mm, layout=layout, created_by_id=user.id)
    db.add(record)
    try: db.flush()
    except IntegrityError: db.rollback(); raise HTTPException(409, "A label template with this name already exists") from None
    audit(db, user, "label_template.created", "label_template", record.id, {"name": record.name}); db.commit()
    return template_json(record)


@app.put("/api/label-templates/{template_id}")
def update_label_template(template_id: uuid.UUID, data: LabelTemplateInput, db: Session = Depends(get_db), user: User = Depends(admin_user)):
    record = db.get(LabelTemplate, template_id, with_for_update=True)
    if not record or record.archived: raise HTTPException(404, "Label template not found")
    if record.builtin: raise HTTPException(409, "Built-in templates are immutable; duplicate this template first")
    try: layout = validate_layout(data.width_mm, data.height_mm, data.layout)
    except ValueError as exc: raise HTTPException(422, str(exc)) from exc
    record.name, record.width_mm, record.height_mm, record.layout, record.updated_at = data.name, data.width_mm, data.height_mm, layout, now_utc()
    try: db.flush()
    except IntegrityError: db.rollback(); raise HTTPException(409, "A label template with this name already exists") from None
    audit(db, user, "label_template.updated", "label_template", record.id, {"name": record.name}); db.commit()
    return template_json(record)


@app.post("/api/label-templates/{template_id}/duplicate", status_code=201)
def duplicate_label_template(template_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(admin_user)):
    source = db.get(LabelTemplate, template_id)
    if not source or source.archived: raise HTTPException(404, "Label template not found")
    base, name, suffix = f"{source.name} copy", f"{source.name} copy", 2
    while db.scalar(select(LabelTemplate.id).where(LabelTemplate.name == name)):
        name, suffix = f"{base} {suffix}", suffix + 1
    record = LabelTemplate(name=name, width_mm=source.width_mm, height_mm=source.height_mm, layout=json.loads(json.dumps(source.layout)), created_by_id=user.id)
    db.add(record); db.flush(); audit(db, user, "label_template.duplicated", "label_template", record.id, {"sourceId": str(source.id)}); db.commit()
    return template_json(record)


@app.post("/api/label-templates/{template_id}/default")
def default_label_template(template_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(admin_user)):
    record = db.get(LabelTemplate, template_id)
    if not record or record.archived: raise HTTPException(404, "Label template not found")
    db.query(LabelTemplate).filter(LabelTemplate.id != record.id).update({LabelTemplate.is_default: False})
    record.is_default = True; record.updated_at = now_utc()
    audit(db, user, "label_template.defaulted", "label_template", record.id); db.commit()
    return template_json(record)


@app.post("/api/label-templates/{template_id}/archive")
def archive_label_template(template_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(admin_user)):
    record = db.get(LabelTemplate, template_id)
    if not record: raise HTTPException(404, "Label template not found")
    if record.builtin: raise HTTPException(409, "Built-in templates cannot be archived")
    if record.is_default: raise HTTPException(409, "Choose a different default template first")
    record.archived = True; record.updated_at = now_utc()
    audit(db, user, "label_template.archived", "label_template", record.id); db.commit()
    return {"ok": True}


@app.get("/api/printers")
def list_printers(db: Session = Depends(get_db), user: User = Depends(current_user)):
    printers = db.scalars(select(Printer).options(selectinload(Printer.tools).selectinload(PrinterTool.loaded_spool)).order_by(Printer.code)).all()
    return [printer_json(p) for p in printers]


@app.post("/api/printers", status_code=201)
def create_printer(data: PrinterInput, db: Session = Depends(get_db), user: User = Depends(current_user)):
    counts = {"single": 1, "dual": 2, "indx8": 8}
    count = data.tool_count or counts.get(data.preset, 1)
    start_index = 0
    printer = Printer(code=next_code(db, Printer, "PRN"), name=data.name.strip(), manufacturer=data.manufacturer.strip(), model=data.model.strip(), location=data.location.strip(), slicer_profile=data.slicer_profile.strip(), notes=data.notes.strip())
    db.add(printer); db.flush()
    for index in range(start_index, start_index + count):
        label_index = index + 1 if data.preset == "indx8" else index
        db.add(PrinterTool(printer_id=printer.id, slicer_index=index, label=f"T{label_index}", nozzle_diameter_mm=Decimal("0.4")))
    audit(db, user, "printer.created", "printer", printer.id, {"tools": count}); db.commit()
    printer = db.scalar(select(Printer).where(Printer.id == printer.id).options(selectinload(Printer.tools).selectinload(PrinterTool.loaded_spool)))
    return printer_json(printer)


@app.put("/api/printers/{printer_id}")
def update_printer(printer_id: uuid.UUID, data: PrinterUpdateInput, db: Session = Depends(get_db), user: User = Depends(current_user)):
    printer = db.scalar(select(Printer).where(Printer.id == printer_id).options(selectinload(Printer.tools).selectinload(PrinterTool.loaded_spool)))
    if not printer: raise HTTPException(404, "Printer not found")
    old = {"name": printer.name, "manufacturer": printer.manufacturer, "model": printer.model, "location": printer.location, "slicerProfile": printer.slicer_profile, "notes": printer.notes}
    printer.name, printer.manufacturer, printer.model = data.name.strip(), data.manufacturer.strip(), data.model.strip()
    printer.location, printer.slicer_profile, printer.notes = data.location.strip(), data.slicer_profile.strip(), data.notes.strip()
    new = {"name": printer.name, "manufacturer": printer.manufacturer, "model": printer.model, "location": printer.location, "slicerProfile": printer.slicer_profile, "notes": printer.notes}
    changes = {key: {"old": old[key], "new": value} for key, value in new.items() if old[key] != value}
    audit(db, user, "printer.updated", "printer", printer.id, {"changes": changes}); db.commit()
    return printer_json(printer)


@app.put("/api/printers/{printer_id}/tools/{tool_id}/loadout")
def update_loadout(printer_id: uuid.UUID, tool_id: uuid.UUID, data: LoadoutInput, db: Session = Depends(get_db), user: User = Depends(current_user)):
    tool = db.scalar(select(PrinterTool).where(PrinterTool.id == tool_id, PrinterTool.printer_id == printer_id).with_for_update())
    if not tool: raise HTTPException(404, "Tool not found")
    spool_id = uuid.UUID(data.spool_id) if data.spool_id else None
    if spool_id:
        spool = db.get(Spool, spool_id)
        if not spool or spool.archived: raise HTTPException(422, "Spool is not available")
        db.query(PrinterTool).filter(PrinterTool.loaded_spool_id == spool_id, PrinterTool.id != tool.id).update({PrinterTool.loaded_spool_id: None})
    tool.loaded_spool_id = spool_id
    audit(db, user, "loadout.changed", "printer_tool", tool.id, {"spool_id": data.spool_id}); db.commit()
    printer = db.scalar(select(Printer).where(Printer.id == printer_id).options(selectinload(Printer.tools).selectinload(PrinterTool.loaded_spool)))
    return printer_json(printer)


@app.get("/api/jobs")
def list_jobs(status: str | None = None, db: Session = Depends(get_db), user: User = Depends(current_user)):
    statement = select(PrintJob).options(selectinload(PrintJob.usages)).order_by(PrintJob.created_at.desc())
    if status: statement = statement.where(PrintJob.status == status)
    return [job_json(job) for job in db.scalars(statement).all()]


@app.post("/api/slicer/jobs", status_code=201)
async def ingest_job(request: Request, printer_id: str = Form(...), file: UploadFile = File(...), source_profile: str = Form(""), physical_profile: str = Form(""), routing_mode: str = Form("profile"), idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), db: Session = Depends(get_db), user: User = Depends(current_user)):
    printer_uuid = uuid.UUID(printer_id)
    printer = db.scalar(select(Printer).where(Printer.id == printer_uuid).options(selectinload(Printer.tools).selectinload(PrinterTool.loaded_spool)))
    if not printer: raise HTTPException(404, "Printer not found")
    api_token = getattr(request.state, "api_token", None)
    if api_token and api_token.printer_id and api_token.printer_id != printer.id: raise HTTPException(403, "Token belongs to a different printer")
    idem = idempotency_key or secrets.token_urlsafe(24)
    existing = db.scalar(select(PrintJob).where(PrintJob.printer_id == printer.id, PrintJob.idempotency_key == idem).options(selectinload(PrintJob.usages)))
    if existing: return JSONResponse(job_json(existing), status_code=200)
    upload_dir = settings.config_dir / "uploads"; upload_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename or "job.gcode").suffix or ".gcode"
    target = upload_dir / f"{uuid.uuid4()}{suffix}"
    digest = hashlib.sha256(); total = 0
    with target.open("wb") as output:
        while chunk := await file.read(1024 * 1024):
            total += len(chunk)
            if total > settings.upload_limit_mb * 1024 * 1024: target.unlink(missing_ok=True); raise HTTPException(413, "G-code file is too large")
            digest.update(chunk); output.write(chunk)
    try:
        parsed = parse_gcode(target)
    except Exception as exc:
        parsed = None; warnings = [str(exc)]
    finally:
        target.unlink(missing_ok=True)
    code = next_job_code(db)
    snapshot = printer_snapshot(printer, source_profile[:255], physical_profile[:255], routing_mode[:30])
    warnings = parsed.warnings if parsed else warnings
    if routing_mode == "default": warnings.append(f'Unknown PrusaSlicer profile "{source_profile or "(not provided)"}" was routed through the default printer')
    job = PrintJob(code=code, printer_id=printer.id, filename=file.filename or "print.gcode", display_name=Path(file.filename or "print").stem, idempotency_key=idem, file_sha256=digest.hexdigest(), status="NEEDS_REVIEW" if warnings or not parsed or not parsed.usages else "NEW", estimated_seconds=parsed.estimated_seconds if parsed else None, printer_snapshot=snapshot, parser_warnings=warnings, submitted_by_id=user.id)
    db.add(job); db.flush()
    tools = {t.slicer_index: t for t in printer.tools}
    if parsed:
        for item in parsed.usages:
            tool = tools.get(item.tool_index)
            db.add(JobUsage(job_id=job.id, tool_id=tool.id if tool else None, tool_index=item.tool_index, tool_label=tool.label if tool else f"T{item.tool_index}", material_type=item.material_type, color_hex=item.color_hex, diameter_mm=item.diameter_mm, density_g_cm3=item.density_g_cm3, estimated_length_mm=item.length_mm, estimated_weight_mg=item.weight_mg, suggested_spool_id=tool.loaded_spool_id if tool else None))
    audit(db, user, "job.ingested", "print_job", job.id, {"filename": job.filename, "printer": printer.code}); db.commit()
    job = db.scalar(select(PrintJob).where(PrintJob.id == job.id).options(selectinload(PrintJob.usages)))
    return job_json(job)


@app.put("/api/jobs/{job_id}/printer")
def change_job_printer(job_id: uuid.UUID, data: JobPrinterInput, db: Session = Depends(get_db), user: User = Depends(current_user)):
    job = db.scalar(select(PrintJob).where(PrintJob.id == job_id).options(selectinload(PrintJob.usages)).with_for_update())
    if not job: raise HTTPException(404, "Print job not found")
    if job.status in {"BOOKED", "DISMISSED"}: raise HTTPException(409, "A booked or dismissed job cannot change printer")
    target_id = uuid.UUID(data.printer_id)
    printer = db.scalar(select(Printer).where(Printer.id == target_id, Printer.archived.is_(False)).options(selectinload(Printer.tools).selectinload(PrinterTool.loaded_spool)))
    if not printer: raise HTTPException(404, "Printer not found")
    duplicate = db.scalar(select(PrintJob.id).where(PrintJob.id != job.id, PrintJob.printer_id == printer.id, PrintJob.idempotency_key == job.idempotency_key))
    if duplicate: raise HTTPException(409, "This job already exists for the selected printer")
    old_printer = {"id": str(job.printer_id), "code": job.printer_snapshot.get("code")}
    source_profile = job.printer_snapshot.get("slicerSourceProfile", "")
    physical_profile = job.printer_snapshot.get("slicerPhysicalProfile", "")
    tools = {tool.slicer_index: tool for tool in printer.tools if not tool.archived}
    warnings = [warning for warning in job.parser_warnings if not warning.startswith("Unknown PrusaSlicer profile") and not warning.startswith("No matching tool")]
    unresolved = False
    for usage in job.usages:
        tool = tools.get(usage.tool_index)
        usage.mapped_spool_id = None
        usage.tool_id = tool.id if tool else None
        usage.suggested_spool_id = tool.loaded_spool_id if tool else None
        usage.tool_label = tool.label if tool else f"T{usage.tool_index}"
        if not tool:
            unresolved = True
            warnings.append(f"No matching tool T{usage.tool_index} exists on {printer.code}")
    job.printer_id = printer.id
    job.printer_snapshot = printer_snapshot(printer, source_profile, physical_profile, "corrected")
    job.parser_warnings = list(dict.fromkeys(warnings))
    job.status = "NEEDS_REVIEW" if unresolved or warnings else "NEW"
    audit(db, user, "job.printer_changed", "print_job", job.id, {"oldPrinter": old_printer, "newPrinter": {"id": str(printer.id), "code": printer.code}}); db.commit()
    return job_json(job)


@app.put("/api/jobs/{job_id}/mapping")
def map_job(job_id: uuid.UUID, data: JobMapInput, db: Session = Depends(get_db), user: User = Depends(current_user)):
    job = db.scalar(select(PrintJob).where(PrintJob.id == job_id).options(selectinload(PrintJob.usages)).with_for_update())
    if not job or job.status in {"BOOKED", "DISMISSED"}: raise HTTPException(409, "Job can no longer be mapped")
    usage_by_id = {str(u.id): u for u in job.usages}
    if {m.usage_id for m in data.mappings} != set(usage_by_id): raise HTTPException(422, "Map exactly one spool to every used tool")
    warnings = list(job.parser_warnings)
    for mapping in data.mappings:
        usage, spool = usage_by_id[mapping.usage_id], db.get(Spool, uuid.UUID(mapping.spool_id))
        if not spool or spool.archived: raise HTTPException(422, "A selected spool is not available")
        usage.mapped_spool_id = spool.id
        if spool.remaining_weight_mg < usage.estimated_weight_mg: warnings.append(f"{spool.code} has less stock than estimated for {usage.tool_label}")
    job.status = "MAPPED"; job.parser_warnings = list(dict.fromkeys(warnings)); audit(db, user, "job.mapped", "print_job", job.id); db.commit()
    return job_json(job)


@app.post("/api/jobs/{job_id}/book")
def book_job(job_id: uuid.UUID, data: JobBookInput, db: Session = Depends(get_db), user: User = Depends(current_user)):
    job = db.scalar(select(PrintJob).where(PrintJob.id == job_id).options(selectinload(PrintJob.usages)).with_for_update())
    if not job or job.status != "MAPPED": raise HTTPException(409, "Confirm the spool mapping first")
    supplied = {item.usage_id: item for item in data.usages}
    _apply_booking(db, user, job, supplied, data.allow_negative)
    db.commit()
    return job_json(job)


def _apply_booking(db: Session, user: User, job: PrintJob, supplied: dict, allow_negative: bool) -> None:
    for usage in job.usages:
        if not usage.mapped_spool_id: raise HTTPException(422, "Not every tool has a spool")
        spool = db.get(Spool, usage.mapped_spool_id, with_for_update=True)
        item = supplied.get(str(usage.id))
        weight = grams_to_mg(item.actual_weight_g) if item and item.actual_weight_g is not None else usage.estimated_weight_mg
        length = item.actual_length_m * 1000 if item and item.actual_length_m is not None else (weight_mg_to_length_mm(weight, spool.diameter_mm, spool.density_g_cm3) if item and item.actual_weight_g is not None else usage.estimated_length_mm)
        if spool.remaining_weight_mg - weight < 0 and not allow_negative: raise HTTPException(409, f"{spool.code} would become negative; confirm the inventory discrepancy")
        usage.actual_weight_mg, usage.actual_length_mm = weight, length
        spool.remaining_weight_mg -= weight; spool.remaining_length_mm -= length
        if spool.remaining_weight_mg < 0 or spool.remaining_length_mm < 0: spool.discrepancy = True
        db.add(InventoryEntry(spool_id=spool.id, kind="PRINT", weight_delta_mg=-weight, length_delta_mm=-length, diameter_mm=spool.diameter_mm, density_g_cm3=spool.density_g_cm3, note=f"{job.code} · {usage.tool_label}", job_id=job.id, actor_id=user.id))
    job.status = "BOOKED"; job.booked_by_id = user.id; job.booked_at = now_utc(); audit(db, user, "job.booked", "print_job", job.id)


@app.post("/api/jobs/{job_id}/confirm-and-book")
def confirm_and_book(job_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(current_user)):
    job = db.scalar(select(PrintJob).where(PrintJob.id == job_id).options(selectinload(PrintJob.usages)).with_for_update())
    if not job or job.status != "NEW": raise HTTPException(409, "Quick booking is only available for a new job")
    if job.parser_warnings: raise HTTPException(409, "Review this job before booking")
    if not job.usages or any(not usage.suggested_spool_id or not usage.tool_id for usage in job.usages):
        raise HTTPException(422, "Every used tool needs a valid suggested spool")
    for usage in job.usages:
        spool = db.get(Spool, usage.suggested_spool_id)
        if not spool or spool.archived: raise HTTPException(422, "A suggested spool is no longer available")
        usage.mapped_spool_id = spool.id
    audit(db, user, "job.mapped", "print_job", job.id, {"quick": True})
    _apply_booking(db, user, job, {}, True)
    audit(db, user, "job.quick_booked", "print_job", job.id)
    db.commit()
    return job_json(job)


@app.post("/api/jobs/{job_id}/dismiss")
def dismiss_job(job_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(current_user)):
    job = db.get(PrintJob, job_id)
    if not job or job.status == "BOOKED": raise HTTPException(409, "A booked job cannot be dismissed")
    job.status = "DISMISSED"; audit(db, user, "job.dismissed", "print_job", job.id); db.commit(); return {"ok": True}


@app.get("/api/colors/nearest")
def nearest_color_name(hex: str = Query(...), user: User = Depends(current_user)):
    try: name, matched = nearest_color(hex)
    except ValueError as exc: raise HTTPException(422, str(exc)) from exc
    return {"name": name, "matchedHex": matched}


@app.get("/api/locations")
def list_locations(db: Session = Depends(get_db), user: User = Depends(current_user)):
    values = list(db.scalars(select(Spool.location).where(Spool.location != "")).all())
    values.extend(db.scalars(select(Printer.location).where(Printer.location != "")).all())
    unique: dict[str, str] = {}
    for value in values:
        cleaned = value.strip()
        if cleaned: unique.setdefault(cleaned.casefold(), cleaned)
    return sorted(unique.values(), key=str.casefold)


@app.get("/api/analytics/usage")
def usage_analytics(days: int = Query(30, ge=1, le=366), timezone_name: str = Query("UTC", alias="timezone"), db: Session = Depends(get_db), user: User = Depends(current_user)):
    try: zone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc: raise HTTPException(422, "Unknown IANA timezone") from exc
    today = datetime.now(zone).date()
    first_day = today - timedelta(days=days - 1)
    start = datetime.combine(first_day, time.min, zone).astimezone(timezone.utc)
    end = datetime.combine(today + timedelta(days=1), time.min, zone).astimezone(timezone.utc)
    entries = db.scalars(select(InventoryEntry).where(InventoryEntry.kind == "PRINT", InventoryEntry.created_at >= start, InventoryEntry.created_at < end).order_by(InventoryEntry.created_at)).all()
    daily = {first_day + timedelta(days=index): {"weightG": 0.0, "lengthM": 0.0} for index in range(days)}
    for entry in entries:
        created = entry.created_at
        if created.tzinfo is None: created = created.replace(tzinfo=timezone.utc)
        key = created.astimezone(zone).date()
        if key in daily:
            daily[key]["weightG"] += max(0, -entry.weight_delta_mg) / 1000
            daily[key]["lengthM"] += float(max(Decimal("0"), -entry.length_delta_mm) / 1000)
    points = [{"date": day.isoformat(), "weightG": round(values["weightG"], 3), "lengthM": round(values["lengthM"], 3)} for day, values in daily.items()]
    return {"range": {"from": first_day.isoformat(), "to": today.isoformat(), "days": days, "timezone": timezone_name}, "totals": {"weightG": round(sum(point["weightG"] for point in points), 3), "lengthM": round(sum(point["lengthM"] for point in points), 3)}, "points": points}


@app.get("/api/catalog/search")
def catalog_search(q: str = "", limit: int = 30, db: Session = Depends(get_db), user: User = Depends(current_user)):
    snapshot = db.scalar(select(CatalogSnapshot).where(CatalogSnapshot.active.is_(True)))
    if not snapshot: return []
    statement = select(CatalogMaterial).where(CatalogMaterial.snapshot_id == snapshot.id)
    if q:
        searchable = (CatalogMaterial.brand, CatalogMaterial.material_name, CatalogMaterial.material_type, CatalogMaterial.color_name, cast(CatalogMaterial.raw_data, String))
        # Every word must occur, but it may occur in a different field. The raw
        # snapshot includes slugs, GTINs, tags, URLs and package/container data.
        for token in re.findall(r"[^\s]+", q.strip())[:12]:
            needle = f"%{token}%"
            statement = statement.where(or_(*(column.ilike(needle) for column in searchable)))
    rows = db.scalars(statement.order_by(CatalogMaterial.brand, CatalogMaterial.material_name).limit(min(limit, 100))).all()
    result = []
    for row in rows:
        metadata = catalog_metadata(row.raw_data)
        result.append({"id": str(row.id), "brand": row.brand, "materialName": row.material_name, "materialType": row.material_type, "colorName": row.color_name, "colorHex": metadata["colorHex"] if metadata["colorHex"] != "#808080" else row.color_hex, "diameterMm": float(row.diameter_mm), "density": float(row.density_g_cm3), "nominalWeightG": mg_to_grams(row.nominal_weight_mg) if row.nominal_weight_mg is not None else None, "nominalLengthM": float(row.nominal_length_mm / 1000) if row.nominal_length_mm is not None else None, "tareWeightG": mg_to_grams(row.tare_weight_mg) if row.tare_weight_mg is not None else None, "packageName": metadata["packageName"], "containerName": metadata["containerName"], "gtin": metadata["gtin"], "productUrl": metadata["productUrl"], "photoUrl": metadata["photoUrl"], "tags": metadata["tags"], "properties": metadata["properties"], "opt": {"brandUuid": str(row.brand_uuid) if row.brand_uuid else None, "materialUuid": str(row.material_uuid) if row.material_uuid else None, "packageUuid": str(row.package_uuid) if row.package_uuid else None, "containerUuid": str(row.container_uuid) if row.container_uuid else None}, "raw": row.raw_data})
    return result


@app.post("/api/catalog/sync")
def catalog_sync(db: Session = Depends(get_db), user: User = Depends(admin_user)):
    try:
        snapshot = sync_catalog(db)
    except CatalogSyncError as error:
        audit(db, user, "catalog.sync_failed", "catalog_snapshot", None, {"error": str(error)[:500]}); db.commit()
        raise HTTPException(502, str(error)) from error
    except Exception as error:
        audit(db, user, "catalog.sync_failed", "catalog_snapshot", None, {"error": type(error).__name__}); db.commit()
        raise HTTPException(502, "OpenPrintTag synchronization failed. The previous catalog remains active.") from error
    audit(db, user, "catalog.synced", "catalog_snapshot", snapshot.id, {"count": snapshot.material_count}); db.commit(); return {"id": str(snapshot.id), "revision": snapshot.source_revision, "count": snapshot.material_count}


@app.get("/api/catalog/status")
def catalog_status(db: Session = Depends(get_db), user: User = Depends(current_user)):
    snapshot = db.scalar(select(CatalogSnapshot).where(CatalogSnapshot.active.is_(True)))
    return {"ready": bool(snapshot), "revision": snapshot.source_revision if snapshot else None, "count": snapshot.material_count if snapshot else 0, "updatedAt": snapshot.created_at.isoformat() if snapshot else None}


@app.post("/api/tokens")
def create_token(data: TokenInput, db: Session = Depends(get_db), user: User = Depends(admin_user)):
    raw = issue_api_token(); record = ApiToken(name=data.name, token_hash=token_hash(raw), token_prefix=raw[:10], printer_id=uuid.UUID(data.printer_id) if data.printer_id else None, created_by_id=user.id)
    db.add(record); db.flush(); audit(db, user, "token.created", "api_token", record.id, {"name": data.name}); db.commit(); return {"id": str(record.id), "token": raw, "prefix": record.token_prefix}


@app.get("/api/tokens")
def list_tokens(db: Session = Depends(get_db), user: User = Depends(admin_user)):
    rows = db.scalars(select(ApiToken).order_by(ApiToken.created_at.desc())).all()
    printers = {p.id: p for p in db.scalars(select(Printer)).all()}
    return [{"id": str(row.id), "name": row.name, "prefix": row.token_prefix, "printerId": str(row.printer_id) if row.printer_id else None, "printerCode": printers[row.printer_id].code if row.printer_id in printers else None, "revoked": row.revoked_at is not None, "lastUsedAt": row.last_used_at.isoformat() if row.last_used_at else None, "createdAt": row.created_at.isoformat()} for row in rows]


@app.post("/api/tokens/{token_id}/revoke")
def revoke_token(token_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(admin_user)):
    record = db.get(ApiToken, token_id)
    if not record: raise HTTPException(404, "Token not found")
    record.revoked_at = now_utc(); audit(db, user, "token.revoked", "api_token", record.id); db.commit(); return {"ok": True}


@app.get("/api/audit")
def audit_log(limit: int = 100, db: Session = Depends(get_db), user: User = Depends(admin_user)):
    rows = db.scalars(select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(min(limit, 500))).all()
    return [{"id": str(e.id), "action": e.action, "entityType": e.entity_type, "entityId": str(e.entity_id) if e.entity_id else None, "details": e.details, "createdAt": e.created_at.isoformat()} for e in rows]


@app.get("/api/export/spools.csv")
def export_spools(db: Session = Depends(get_db), user: User = Depends(current_user)):
    buffer = io.StringIO(); writer = csv.writer(buffer); writer.writerow(["code", "brand", "material", "type", "color", "remaining_g", "remaining_m", "location"])
    for spool in db.scalars(select(Spool).order_by(Spool.code)).all(): writer.writerow([spool.code, spool.brand, spool.material_name, spool.material_type, spool.color_name, mg_to_grams(spool.remaining_weight_mg), float(spool.remaining_length_mm / 1000), spool.location])
    return Response(buffer.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=filaflow-spools.csv"})


@app.get("/api/export/backup.json")
def export_json(db: Session = Depends(get_db), user: User = Depends(admin_user)):
    settings_row = inventory_setting(db)
    payload = {
        "version": 3,
        "exportedAt": now_utc().isoformat(),
        "spools": [spool_json(db, s) for s in db.scalars(select(Spool)).all()],
        "printers": [printer_json(p) for p in db.scalars(select(Printer).options(selectinload(Printer.tools).selectinload(PrinterTool.loaded_spool))).all()],
        "jobs": [job_json(j) for j in db.scalars(select(PrintJob).options(selectinload(PrintJob.usages))).all()],
        "labelTemplates": [template_json(row) for row in db.scalars(select(LabelTemplate)).all()],
        "inventorySettings": {"reorderThresholdG": mg_to_grams(settings_row.reorder_threshold_mg)},
        "reorderRules": [
            {"id": str(row.id), "productKey": row.product_key, "thresholdG": mg_to_grams(row.threshold_mg) if row.threshold_mg is not None else None, "ignored": row.ignored, "productSnapshot": row.product_snapshot}
            for row in db.scalars(select(ReorderRule)).all()
        ],
        "wishlist": [wishlist_json(row) for row in db.scalars(select(WishlistItem)).all()],
    }
    return Response(json.dumps(payload, indent=2), media_type="application/json", headers={"Content-Disposition": "attachment; filename=filaflow-export.json"})


class SPAStaticFiles(StaticFiles):
    """Serve the SPA entry point for client-side routes such as /labels/print."""

    def __init__(self, *args, fallback_file: Path, **kwargs):
        super().__init__(*args, **kwargs)
        self.fallback_file = fallback_file

    async def get_response(self, path: str, scope):
        try:
            response = await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code != 404 or "." in Path(path).name:
                raise
            return FileResponse(self.fallback_file)
        if response.status_code == 404 and "." not in Path(path).name:
            return FileResponse(self.fallback_file)
        return response


web_dir = Path(__file__).resolve().parent.parent / "web"
if web_dir.exists():
    app.mount("/", SPAStaticFiles(directory=web_dir, html=True, fallback_file=web_dir / "index.html"), name="web")

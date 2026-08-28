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
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from xml.sax.saxutils import escape

import qrcode
import qrcode.image.svg
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, Response, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from .audit import audit
from .auth import admin_user, clear_session, current_user, hash_password, issue_api_token, set_session, token_hash, verify_password
from .catalog import CatalogSyncError, catalog_metadata, sync_catalog
from .config import settings
from .database import Base, SessionLocal, engine, get_db
from .gcode import parse_gcode
from .ids import next_code
from .models import ApiToken, AuditEvent, CatalogMaterial, CatalogSnapshot, InventoryEntry, JobUsage, PrintJob, Printer, PrinterTool, Spool, User, now_utc
from .schemas import JobBookInput, JobMapInput, LoadoutInput, LoginInput, PrinterInput, SpoolInput, TokenInput, UserCreateInput, UserStatusInput, WeighInput
from .units import grams_to_mg, length_mm_to_weight_mg, mg_to_grams, weight_mg_to_length_mm


app = FastAPI(title="FilaFlow API", version="1.0.0", docs_url="/api/docs", redoc_url=None)


def spool_json(db: Session, spool: Spool) -> dict:
    reserved_weight = db.scalar(select(func.coalesce(func.sum(JobUsage.actual_weight_mg), 0)).join(PrintJob).where(JobUsage.mapped_spool_id == spool.id, PrintJob.status == "MAPPED")) or 0
    if not reserved_weight:
        reserved_weight = db.scalar(select(func.coalesce(func.sum(JobUsage.estimated_weight_mg), 0)).join(PrintJob).where(JobUsage.mapped_spool_id == spool.id, PrintJob.status == "MAPPED")) or 0
    reserved_length = db.scalar(select(func.coalesce(func.sum(JobUsage.estimated_length_mm), 0)).join(PrintJob).where(JobUsage.mapped_spool_id == spool.id, PrintJob.status == "MAPPED")) or Decimal("0")
    loaded = db.scalar(select(PrinterTool).where(PrinterTool.loaded_spool_id == spool.id).options(selectinload(PrinterTool.printer)))
    return {
        "id": str(spool.id), "code": spool.code, "brand": spool.brand, "materialName": spool.material_name, "materialType": spool.material_type,
        "colorName": spool.color_name, "colorHex": spool.color_hex, "location": spool.location, "lotNumber": spool.lot_number, "serialNumber": spool.serial_number, "diameterMm": float(spool.diameter_mm), "density": float(spool.density_g_cm3),
        "initialWeightG": mg_to_grams(spool.initial_weight_mg), "remainingWeightG": mg_to_grams(spool.remaining_weight_mg), "reservedWeightG": mg_to_grams(int(reserved_weight)),
        "availableWeightG": mg_to_grams(spool.remaining_weight_mg - int(reserved_weight)), "initialLengthM": float(spool.initial_length_mm / 1000),
        "remainingLengthM": float(spool.remaining_length_mm / 1000), "reservedLengthM": float(Decimal(reserved_length) / 1000),
        "remainingPercent": round((spool.remaining_weight_mg / spool.initial_weight_mg * 100) if spool.initial_weight_mg else 0, 1),
        "lowStock": spool.remaining_weight_mg <= spool.low_stock_weight_mg, "archived": spool.archived, "discrepancy": spool.discrepancy,
        "loadedOn": {"printer": loaded.printer.name, "printerCode": loaded.printer.code, "tool": loaded.label} if loaded else None,
        "purchasePrice": spool.purchase_price_cents / 100 if spool.purchase_price_cents is not None else None, "currency": spool.currency,
        "catalogSnapshot": spool.catalog_snapshot,
    }


def printer_json(printer: Printer) -> dict:
    return {"id": str(printer.id), "code": printer.code, "name": printer.name, "manufacturer": printer.manufacturer, "model": printer.model, "slicerProfile": printer.slicer_profile, "notes": printer.notes, "archived": printer.archived,
            "tools": [{"id": str(tool.id), "index": tool.slicer_index, "label": tool.label, "nozzleDiameterMm": float(tool.nozzle_diameter_mm) if tool.nozzle_diameter_mm else None,
                       "loadedSpool": {"id": str(tool.loaded_spool.id), "code": tool.loaded_spool.code, "brand": tool.loaded_spool.brand, "material": tool.loaded_spool.material_name, "colorHex": tool.loaded_spool.color_hex, "remainingWeightG": mg_to_grams(tool.loaded_spool.remaining_weight_mg)} if tool.loaded_spool else None}
                      for tool in printer.tools if not tool.archived]}


def job_json(job: PrintJob) -> dict:
    return {"id": str(job.id), "code": job.code, "filename": job.filename, "displayName": job.display_name, "status": job.status, "estimatedSeconds": job.estimated_seconds, "createdAt": job.created_at.isoformat(), "warnings": job.parser_warnings, "printer": job.printer_snapshot,
            "usages": [{"id": str(usage.id), "toolIndex": usage.tool_index, "toolLabel": usage.tool_label, "materialType": usage.material_type, "colorHex": usage.color_hex, "estimatedLengthM": float(usage.estimated_length_mm / 1000), "estimatedWeightG": mg_to_grams(usage.estimated_weight_mg), "actualLengthM": float(usage.actual_length_mm / 1000) if usage.actual_length_mm is not None else None, "actualWeightG": mg_to_grams(usage.actual_weight_mg) if usage.actual_weight_mg is not None else None, "suggestedSpoolId": str(usage.suggested_spool_id) if usage.suggested_spool_id else None, "mappedSpoolId": str(usage.mapped_spool_id) if usage.mapped_spool_id else None} for usage in job.usages]}


def next_job_code(db: Session) -> str:
    prefix = f"JOB-{datetime.now():%Y%m%d}-"
    codes = db.scalars(select(PrintJob.code).where(PrintJob.code.like(f"{prefix}%"))).all()
    highest = 0
    for code in codes:
        try: highest = max(highest, int(code.rsplit("-", 1)[1]))
        except (ValueError, IndexError): pass
    return f"{prefix}{highest + 1:04d}"


def render_spool_label(spool: Spool, target: str) -> bytes:
    factory = qrcode.image.svg.SvgPathImage
    qr = qrcode.make(target, image_factory=factory, box_size=8, border=1)
    qr_root = ET.fromstring(qr.to_string(encoding="unicode"))
    qr_path = next(element for element in qr_root.iter() if element.tag.endswith("path"))
    _, _, qr_width, qr_height = [float(value) for value in qr_root.attrib["viewBox"].split()]
    qr_size = 270
    scale = qr_size / max(qr_width, qr_height)
    qr_x = 20 + (qr_size - qr_width * scale) / 2
    qr_y = 25 + (qr_size - qr_height * scale) / 2

    def short(value: str, limit: int) -> str:
        value = value.strip()
        return value if len(value) <= limit else f"{value[: limit - 1]}…"

    code = escape(spool.code)
    material = escape(short(spool.material_name, 40))
    description = escape(short(" · ".join(value for value in (spool.brand, spool.material_type) if value), 48))
    color_name = escape(short(spool.color_name or "Unnamed color", 34))
    serial_number = escape(short(spool.serial_number or spool.code, 34))
    color_hex = spool.color_hex if re.fullmatch(r"#[0-9A-Fa-f]{6}(?:[0-9A-Fa-f]{2})?", spool.color_hex or "") else "#808080"
    path_data = escape(qr_path.attrib["d"])
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="90mm" height="32mm" viewBox="0 0 900 320">
  <rect width="900" height="320" rx="18" fill="#ffffff"/>
  <rect x="1" y="1" width="898" height="318" rx="17" fill="none" stroke="#d1d5db" stroke-width="2"/>
  <g transform="translate({qr_x:.3f} {qr_y:.3f}) scale({scale:.6f})"><path d="{path_data}" fill="#111827"/></g>
  <g font-family="Open Sans, Arial, sans-serif" fill="#111827">
    <text x="330" y="68" font-size="38" font-weight="700">{code}</text>
    <text x="330" y="122" font-size="30" font-weight="700">{material}</text>
    <text x="330" y="160" font-size="21" fill="#4b5563">{description}</text>
    <rect x="330" y="184" width="34" height="34" rx="7" fill="{color_hex}" stroke="#d1d5db" stroke-width="2"/>
    <text x="380" y="209" font-size="20" fill="#374151">{color_name}</text>
    <text x="330" y="270" font-size="20" fill="#4b5563">Spool S/N: <tspan font-weight="700" fill="#111827">{serial_number}</tspan></text>
  </g>
</svg>'''
    return svg.encode("utf-8")


def user_json(user: User) -> dict:
    return {"id": str(user.id), "email": user.email, "displayName": user.display_name, "role": user.role, "preferredUnit": user.preferred_unit, "active": user.active, "createdAt": user.created_at.isoformat()}


def bootstrap() -> None:
    Base.metadata.create_all(engine)
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
    record = User(email=email, display_name=display_name, password_hash=hash_password(data.password), role=data.role, active=True)
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


@app.get("/api/dashboard")
def dashboard(db: Session = Depends(get_db), user: User = Depends(current_user)):
    spools = db.scalars(select(Spool).where(Spool.archived.is_(False))).all()
    spool_payload = [spool_json(db, spool) for spool in spools]
    remaining_weight = sum(spool.remaining_weight_mg for spool in spools)
    remaining_length = sum((spool.remaining_length_mm for spool in spools), Decimal("0"))
    reserved_weight = sum(int(item["reservedWeightG"] * 1000) for item in spool_payload)
    reserved_length = sum(Decimal(str(item["reservedLengthM"])) * 1000 for item in spool_payload)
    printers = db.scalars(select(Printer).where(Printer.archived.is_(False)).options(selectinload(Printer.tools).selectinload(PrinterTool.loaded_spool))).all()
    jobs = db.scalars(select(PrintJob).where(PrintJob.status.in_(["NEW", "MAPPED", "NEEDS_REVIEW"])).options(selectinload(PrintJob.usages)).order_by(PrintJob.created_at.desc()).limit(8)).all()
    return {"summary": {"remainingWeightG": mg_to_grams(remaining_weight), "remainingLengthM": float(remaining_length / 1000), "reservedWeightG": mg_to_grams(reserved_weight), "reservedLengthM": float(reserved_length / 1000), "availableWeightG": mg_to_grams(remaining_weight - reserved_weight), "availableLengthM": float((remaining_length - reserved_length) / 1000), "activeSpools": len(spools), "lowStockSpools": sum(1 for spool in spools if spool.remaining_weight_mg <= spool.low_stock_weight_mg), "loadedSpools": sum(1 for item in spool_payload if item["loadedOn"]), "openJobs": len(jobs)}, "spools": spool_payload[:8], "printers": [printer_json(p) for p in printers], "jobs": [job_json(j) for j in jobs]}


@app.get("/api/spools")
def list_spools(q: str = "", archived: bool = False, db: Session = Depends(get_db), user: User = Depends(current_user)):
    statement = select(Spool).where(Spool.archived == archived).order_by(Spool.code.desc())
    if q:
        needle = f"%{q}%"
        statement = statement.where(or_(Spool.code.ilike(needle), Spool.brand.ilike(needle), Spool.material_name.ilike(needle), Spool.material_type.ilike(needle), Spool.location.ilike(needle)))
    return [spool_json(db, spool) for spool in db.scalars(statement).all()]


@app.post("/api/spools", status_code=201)
def create_spool(data: SpoolInput, db: Session = Depends(get_db), user: User = Depends(current_user)):
    weight_mg = grams_to_mg(data.initial_weight_g)
    length_mm = data.initial_length_m * 1000 if data.initial_length_m is not None else weight_mg_to_length_mm(weight_mg, data.diameter_mm, data.density_g_cm3)
    spool = Spool(code=next_code(db, Spool, "SPL"), brand=data.brand, material_name=data.material_name, material_type=data.material_type, color_name=data.color_name, color_hex=data.color_hex, location=data.location, lot_number=data.lot_number, serial_number=data.serial_number, diameter_mm=data.diameter_mm, density_g_cm3=data.density_g_cm3, tare_weight_mg=grams_to_mg(data.tare_weight_g), initial_weight_mg=weight_mg, remaining_weight_mg=weight_mg, initial_length_mm=length_mm, remaining_length_mm=length_mm, low_stock_weight_mg=grams_to_mg(data.low_stock_weight_g), purchase_price_cents=int(data.purchase_price * 100) if data.purchase_price is not None else None, currency=data.currency, opt_brand_uuid=uuid.UUID(data.opt_brand_uuid) if data.opt_brand_uuid else None, opt_material_uuid=uuid.UUID(data.opt_material_uuid) if data.opt_material_uuid else None, opt_package_uuid=uuid.UUID(data.opt_package_uuid) if data.opt_package_uuid else None, opt_container_uuid=uuid.UUID(data.opt_container_uuid) if data.opt_container_uuid else None, catalog_snapshot=data.catalog_snapshot)
    db.add(spool); db.flush()
    db.add(InventoryEntry(spool_id=spool.id, kind="INITIAL", weight_delta_mg=weight_mg, length_delta_mm=length_mm, diameter_mm=spool.diameter_mm, density_g_cm3=spool.density_g_cm3, note="New spool", actor_id=user.id))
    audit(db, user, "spool.created", "spool", spool.id, {"code": spool.code}); db.commit()
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
    if data.net_weight_g is None and data.total_weight_g is None: raise HTTPException(422, "Enter a total or net weight")
    target_mg = grams_to_mg(data.net_weight_g) if data.net_weight_g is not None else grams_to_mg(data.total_weight_g) - spool.tare_weight_mg
    target_length = weight_mg_to_length_mm(target_mg, spool.diameter_mm, spool.density_g_cm3)
    delta_weight, delta_length = target_mg - spool.remaining_weight_mg, target_length - spool.remaining_length_mm
    spool.remaining_weight_mg, spool.remaining_length_mm = target_mg, target_length
    db.add(InventoryEntry(spool_id=spool.id, kind="WEIGHING", weight_delta_mg=delta_weight, length_delta_mm=delta_length, diameter_mm=spool.diameter_mm, density_g_cm3=spool.density_g_cm3, note=data.note, actor_id=user.id))
    audit(db, user, "spool.weighed", "spool", spool.id, {"weight_delta_mg": delta_weight}); db.commit()
    return spool_json(db, spool)


@app.post("/api/spools/{spool_id}/archive")
def archive_spool(spool_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(current_user)):
    spool = db.get(Spool, spool_id)
    if not spool: raise HTTPException(404, "Spool not found")
    db.query(PrinterTool).filter(PrinterTool.loaded_spool_id == spool.id).update({PrinterTool.loaded_spool_id: None})
    spool.archived = True; audit(db, user, "spool.archived", "spool", spool.id); db.commit(); return {"ok": True}


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
def spool_label(spool_id: uuid.UUID, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)):
    spool = db.get(Spool, spool_id)
    if not spool: raise HTTPException(404, "Spool not found")
    base_url = settings.public_url or str(request.base_url)
    target = f"{base_url.rstrip('/')}/spools/{spool.id}"
    return Response(render_spool_label(spool, target), media_type="image/svg+xml", headers={"Content-Disposition": f'inline; filename="{spool.code}.svg"'})


@app.get("/api/printers")
def list_printers(db: Session = Depends(get_db), user: User = Depends(current_user)):
    printers = db.scalars(select(Printer).options(selectinload(Printer.tools).selectinload(PrinterTool.loaded_spool)).order_by(Printer.code)).all()
    return [printer_json(p) for p in printers]


@app.post("/api/printers", status_code=201)
def create_printer(data: PrinterInput, db: Session = Depends(get_db), user: User = Depends(current_user)):
    counts = {"single": 1, "dual": 2, "indx8": 8}
    count = data.tool_count or counts.get(data.preset, 1)
    start_index = 1 if data.preset == "indx8" else 0
    printer = Printer(code=next_code(db, Printer, "PRN"), name=data.name, manufacturer=data.manufacturer, model=data.model, slicer_profile=data.slicer_profile, notes=data.notes)
    db.add(printer); db.flush()
    for index in range(start_index, start_index + count): db.add(PrinterTool(printer_id=printer.id, slicer_index=index, label=f"T{index}", nozzle_diameter_mm=Decimal("0.4")))
    audit(db, user, "printer.created", "printer", printer.id, {"tools": count}); db.commit()
    printer = db.scalar(select(Printer).where(Printer.id == printer.id).options(selectinload(Printer.tools).selectinload(PrinterTool.loaded_spool)))
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
async def ingest_job(request: Request, printer_id: str = Form(...), file: UploadFile = File(...), idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), db: Session = Depends(get_db), user: User = Depends(current_user)):
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
    snapshot = {"id": str(printer.id), "code": printer.code, "name": printer.name, "model": printer.model, "tools": [{"id": str(t.id), "index": t.slicer_index, "label": t.label} for t in printer.tools]}
    warnings = parsed.warnings if parsed else warnings
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
    for usage in job.usages:
        if not usage.mapped_spool_id: raise HTTPException(422, "Not every tool has a spool")
        spool = db.get(Spool, usage.mapped_spool_id, with_for_update=True)
        item = supplied.get(str(usage.id))
        weight = grams_to_mg(item.actual_weight_g) if item and item.actual_weight_g is not None else usage.estimated_weight_mg
        length = item.actual_length_m * 1000 if item and item.actual_length_m is not None else (weight_mg_to_length_mm(weight, spool.diameter_mm, spool.density_g_cm3) if item and item.actual_weight_g is not None else usage.estimated_length_mm)
        if spool.remaining_weight_mg - weight < 0 and not data.allow_negative: raise HTTPException(409, f"{spool.code} would become negative; confirm the inventory discrepancy")
        usage.actual_weight_mg, usage.actual_length_mm = weight, length
        spool.remaining_weight_mg -= weight; spool.remaining_length_mm -= length
        if spool.remaining_weight_mg < 0 or spool.remaining_length_mm < 0: spool.discrepancy = True
        db.add(InventoryEntry(spool_id=spool.id, kind="PRINT", weight_delta_mg=-weight, length_delta_mm=-length, diameter_mm=spool.diameter_mm, density_g_cm3=spool.density_g_cm3, note=f"{job.code} · {usage.tool_label}", job_id=job.id, actor_id=user.id))
    job.status = "BOOKED"; job.booked_by_id = user.id; job.booked_at = now_utc(); audit(db, user, "job.booked", "print_job", job.id); db.commit(); return job_json(job)


@app.post("/api/jobs/{job_id}/dismiss")
def dismiss_job(job_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(current_user)):
    job = db.get(PrintJob, job_id)
    if not job or job.status == "BOOKED": raise HTTPException(409, "A booked job cannot be dismissed")
    job.status = "DISMISSED"; audit(db, user, "job.dismissed", "print_job", job.id); db.commit(); return {"ok": True}


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
        raise HTTPException(502, str(error)) from error
    except Exception as error:
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
    payload = {"version": 1, "exportedAt": now_utc().isoformat(), "spools": [spool_json(db, s) for s in db.scalars(select(Spool)).all()], "printers": [printer_json(p) for p in db.scalars(select(Printer).options(selectinload(Printer.tools).selectinload(PrinterTool.loaded_spool))).all()], "jobs": [job_json(j) for j in db.scalars(select(PrintJob).options(selectinload(PrintJob.usages))).all()]}
    return Response(json.dumps(payload, indent=2), media_type="application/json", headers={"Content-Disposition": "attachment; filename=filaflow-export.json"})


web_dir = Path(__file__).resolve().parent.parent / "web"
if web_dir.exists():
    class SPAStaticFiles(StaticFiles):
        async def get_response(self, path: str, scope):
            response = await super().get_response(path, scope)
            if response.status_code == 404 and "." not in Path(path).name:
                return FileResponse(web_dir / "index.html")
            return response

    app.mount("/", SPAStaticFiles(directory=web_dir, html=True), name="web")

from __future__ import annotations

import io
import uuid
import zipfile
from decimal import Decimal, InvalidOperation

import httpx
import yaml
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from .config import settings
from .models import CatalogMaterial, CatalogSnapshot


class CatalogSyncError(RuntimeError):
    pass


def _uuid(value) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value)) if value else None
    except (ValueError, TypeError):
        return None


def _decimal(value, fallback: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(fallback)


def _hex(value) -> str:
    if isinstance(value, dict):
        for key in ("color_rgba", "color_rgb", "hex", "value", "color"):
            if key in value:
                return _hex(value[key])
    if isinstance(value, str):
        candidate = value.strip()
        if candidate.startswith("#") and len(candidate) in (4, 7, 9):
            if len(candidate) == 4:
                return "#" + "".join(character * 2 for character in candidate[1:])
            return candidate[:7]
        if candidate.startswith("0x") and len(candidate) >= 8:
            return f"#{candidate[2:8]}"
        if len(candidate) in (6, 8) and all(character in "0123456789abcdefABCDEF" for character in candidate):
            return f"#{candidate[:6]}"
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        return "#" + "".join(f"{int(v):02x}" for v in value[:3])
    return "#808080"


def _reference_keys(value) -> list[str]:
    if isinstance(value, dict):
        return [str(value[key]) for key in ("uuid", "slug") if value.get(key)]
    return [str(value)] if value else []


def _index_documents(rows: list[tuple[str, dict]]) -> dict[str, dict]:
    indexed: dict[str, dict] = {}
    for filename, document in rows:
        keys = _reference_keys(document)
        keys.append(filename.rsplit("/", 1)[-1].rsplit(".", 1)[0])
        for key in keys:
            indexed[key] = document
    return indexed


def _first(*values):
    return next((value for value in values if value is not None and value != ""), None)


def _diameter_mm(value) -> Decimal:
    diameter = _decimal(value, "1.75")
    # OpenPrintTag stores filament diameter in micrometres (1750 = 1.75 mm).
    return diameter / 1000 if diameter > 10 else diameter


def catalog_metadata(raw_data: dict) -> dict:
    """Return UI-friendly metadata while preserving the complete source snapshot."""
    material = raw_data.get("material") if isinstance(raw_data, dict) else {}
    package = raw_data.get("package") if isinstance(raw_data, dict) else {}
    container = raw_data.get("container") if isinstance(raw_data, dict) else {}
    material = material if isinstance(material, dict) else {}
    package = package if isinstance(package, dict) else {}
    container = container if isinstance(container, dict) else {}
    primary_color = material.get("primary_color") or material.get("color")
    properties = material.get("properties") if isinstance(material.get("properties"), dict) else {}
    photo = next((entry.get("url") for entry in material.get("photos", []) if isinstance(entry, dict) and entry.get("url")), None)
    return {
        "colorHex": _hex(primary_color),
        "packageName": str(package.get("name") or package.get("slug") or ""),
        "containerName": str(container.get("name") or container.get("slug") or ""),
        "gtin": str(package.get("gtin") or ""),
        "productUrl": str(package.get("url") or material.get("url") or ""),
        "photoUrl": photo,
        "tags": [str(tag) for tag in material.get("tags", [])],
        "properties": properties,
    }


def _load_yaml(archive: zipfile.ZipFile, marker: str) -> list[tuple[str, dict]]:
    rows = []
    for name in archive.namelist():
        if marker not in name or not name.endswith((".yaml", ".yml")):
            continue
        try:
            payload = yaml.safe_load(archive.read(name))
        except Exception:
            continue
        documents = payload if isinstance(payload, list) else [payload]
        for document in documents:
            if isinstance(document, dict):
                rows.append((name, document))
    return rows


def sync_catalog(db: Session) -> CatalogSnapshot:
    try:
        response = httpx.get(settings.catalog_url, follow_redirects=True, timeout=120)
        response.raise_for_status()
    except httpx.HTTPError as error:
        raise CatalogSyncError(
            "Could not download OpenPrintTag. Check the NAS internet connection, DNS and firewall, then try again."
        ) from error
    revision = response.headers.get("etag", "").strip('W/\"') or response.headers.get("last-modified", "unknown")
    try:
        archive = zipfile.ZipFile(io.BytesIO(response.content))
    except zipfile.BadZipFile as error:
        raise CatalogSyncError("OpenPrintTag returned an invalid archive. The previous catalog remains active.") from error
    brands = _index_documents(_load_yaml(archive, "/data/brands/"))
    materials = _load_yaml(archive, "/data/materials/")
    packages = _load_yaml(archive, "/data/material-packages/")
    containers = _index_documents(_load_yaml(archive, "/data/material-containers/"))

    package_by_material: dict[str, list[dict]] = {}
    for _, package in packages:
        reference = package.get("material") or package.get("material_uuid") or package.get("material_slug")
        for key in _reference_keys(reference):
            package_by_material.setdefault(key, []).append(package)

    snapshot = CatalogSnapshot(source_revision=revision, active=False)
    db.add(snapshot)
    db.flush()
    count = 0
    for filename, material in materials:
        material_uuid = material.get("uuid") or material.get("material_uuid")
        brand_reference = material.get("brand") or material.get("brand_uuid") or material.get("brand_slug")
        brand_doc = next((brands.get(key) for key in _reference_keys(brand_reference) if brands.get(key)), {})
        brand_uuid = brand_doc.get("uuid") or (brand_reference.get("uuid") if isinstance(brand_reference, dict) else material.get("brand_uuid"))
        brand_slug = (brand_reference.get("slug") if isinstance(brand_reference, dict) else None) or material.get("brand_slug") or filename.split("/data/materials/", 1)[-1].split("/", 1)[0]
        brand_name = material.get("brand_name") or brand_doc.get("name") or brand_doc.get("brand_name") or brand_slug.replace("-", " ").title()
        linked_packages: list[dict] = []
        for key in _reference_keys(material):
            linked_packages.extend(package_by_material.get(key, []))
        linked_packages = list({str(package.get("uuid") or package.get("slug")): package for package in linked_packages}.values()) or [None]
        for package in linked_packages:
            package = package or {}
            container_reference = package.get("container") or package.get("container_uuid") or package.get("material_container_uuid")
            container = next((containers.get(key) for key in _reference_keys(container_reference) if containers.get(key)), {})
            container_uuid = container.get("uuid") or (container_reference.get("uuid") if isinstance(container_reference, dict) else package.get("container_uuid"))
            nominal_weight = _first(package.get("nominal_netto_full_weight"), material.get("nominal_netto_full_weight"))
            nominal_length = _first(package.get("nominal_full_length"), material.get("nominal_full_length"))
            tare = _first(container.get("empty_weight"), container.get("empty_container_weight"), package.get("empty_weight"), package.get("empty_container_weight"))
            properties = material.get("properties") if isinstance(material.get("properties"), dict) else {}
            primary_color = material.get("primary_color") or material.get("color")
            color_name = material.get("color_name") or material.get("colour_name")
            if isinstance(primary_color, dict):
                color_name = color_name or primary_color.get("name") or primary_color.get("color_name")
            db.add(CatalogMaterial(
                snapshot_id=snapshot.id,
                brand_uuid=_uuid(brand_uuid), material_uuid=_uuid(material_uuid), package_uuid=_uuid(package.get("uuid") or package.get("package_uuid")), container_uuid=_uuid(container_uuid),
                brand=str(brand_name), material_name=str(material.get("material_name") or material.get("name") or filename.rsplit("/", 1)[-1].rsplit(".", 1)[0]),
                material_type=str(material.get("material_type") or material.get("type") or material.get("abbreviation") or ""), color_name=str(color_name or ""),
                color_hex=_hex(primary_color), diameter_mm=_diameter_mm(_first(package.get("filament_diameter"), material.get("filament_diameter"))), density_g_cm3=_decimal(_first(properties.get("density"), material.get("density")), "1.24"),
                nominal_weight_mg=int(_decimal(nominal_weight, "0") * 1000) if nominal_weight is not None else None,
                nominal_length_mm=_decimal(nominal_length, "0") if nominal_length is not None else None,
                tare_weight_mg=int(_decimal(tare, "0") * 1000) if tare is not None else None,
                raw_data={"brand": brand_doc, "material": material, "package": package, "container": container},
            ))
            count += 1
    snapshot.material_count = count
    if count == 0:
        db.rollback()
        raise ValueError("OpenPrintTag synchronization returned no valid materials")
    db.execute(update(CatalogSnapshot).values(active=False))
    snapshot.active = True
    db.commit()
    old_ids = db.scalars(select(CatalogSnapshot.id).where(CatalogSnapshot.active.is_(False))).all()
    if len(old_ids) > 2:
        for old_id in old_ids[:-2]:
            db.execute(delete(CatalogSnapshot).where(CatalogSnapshot.id == old_id))
        db.commit()
    return snapshot

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from decimal import Decimal
from xml.sax.saxutils import escape

import qrcode
import qrcode.image.svg

from .models import LabelTemplate, Spool


DEFAULT_LAYOUT = [
    {"id": "border", "type": "border", "x": 0.5, "y": 0.5, "width": 89, "height": 31, "font_size": 3, "visible": True, "text": "", "bold": False},
    {"id": "qr", "type": "qr", "x": 2, "y": 2, "width": 28, "height": 28, "font_size": 3, "visible": True, "text": "", "bold": False},
    {"id": "code", "type": "code", "x": 33, "y": 3, "width": 54, "height": 5, "font_size": 4, "visible": True, "text": "", "bold": True},
    {"id": "filament", "type": "filament", "x": 33, "y": 9, "width": 54, "height": 6, "font_size": 3.5, "visible": True, "text": "", "bold": True},
    {"id": "brand", "type": "brand", "x": 33, "y": 16, "width": 54, "height": 4, "font_size": 2.6, "visible": True, "text": "", "bold": False},
    {"id": "swatch", "type": "color_swatch", "x": 33, "y": 22, "width": 4, "height": 4, "font_size": 3, "visible": True, "text": "", "bold": False},
    {"id": "color", "type": "color_name", "x": 39, "y": 22, "width": 26, "height": 4, "font_size": 2.5, "visible": True, "text": "", "bold": False},
    {"id": "serial", "type": "serial", "x": 66, "y": 22, "width": 21, "height": 4, "font_size": 2.3, "visible": True, "text": "", "bold": False},
]

ALLOWED_TYPES = {"qr", "code", "serial", "brand", "filament", "material", "color_swatch", "color_name", "color_hex", "location", "remaining", "custom_text", "border"}


def validate_layout(width_mm: Decimal | float, height_mm: Decimal | float, raw_layout: list) -> list[dict]:
    width, height = float(width_mm), float(height_mm)
    if not 20 <= width <= 200 or not 15 <= height <= 150:
        raise ValueError("Label dimensions must be between 20 × 15 mm and 200 × 150 mm")
    if not 1 <= len(raw_layout) <= 40:
        raise ValueError("A template must contain between 1 and 40 elements")
    result: list[dict] = []
    identifiers: set[str] = set()
    for raw in raw_layout:
        item = raw.model_dump(mode="json") if hasattr(raw, "model_dump") else dict(raw)
        identifier = str(item.get("id", "")).strip()
        kind = str(item.get("type", ""))
        if not identifier or identifier in identifiers:
            raise ValueError("Every label element needs a unique id")
        if kind not in ALLOWED_TYPES:
            raise ValueError(f"Unsupported label element: {kind}")
        identifiers.add(identifier)
        normalized = {
            "id": identifier[:80], "type": kind,
            "x": round(float(item.get("x", 0)), 2), "y": round(float(item.get("y", 0)), 2),
            "width": round(float(item.get("width", 0)), 2), "height": round(float(item.get("height", 0)), 2),
            "font_size": round(float(item.get("font_size", 3.2)), 2), "visible": bool(item.get("visible", True)),
            "text": str(item.get("text", ""))[:160], "bold": bool(item.get("bold", False)),
        }
        if normalized["x"] < 0 or normalized["y"] < 0 or normalized["width"] <= 0 or normalized["height"] <= 0:
            raise ValueError(f"Element {identifier} has invalid geometry")
        if normalized["x"] + normalized["width"] > width + 0.01 or normalized["y"] + normalized["height"] > height + 0.01:
            raise ValueError(f"Element {identifier} extends beyond the label")
        if not 1.5 <= normalized["font_size"] <= 20:
            raise ValueError(f"Element {identifier} has an invalid font size")
        if kind == "qr" and (normalized["width"] < 16 or normalized["height"] < 16 or abs(normalized["width"] - normalized["height"]) > 0.1):
            raise ValueError("QR elements must be square and at least 16 mm")
        if kind == "custom_text" and any(ord(character) < 32 and character not in "\t" for character in normalized["text"]):
            raise ValueError("Custom text contains unsupported control characters")
        result.append(normalized)
    return result


def template_json(template: LabelTemplate) -> dict:
    return {
        "id": str(template.id), "name": template.name,
        "widthMm": float(template.width_mm), "heightMm": float(template.height_mm),
        "layout": template.layout, "builtin": template.builtin,
        "isDefault": template.is_default, "archived": template.archived,
        "createdAt": template.created_at.isoformat(), "updatedAt": template.updated_at.isoformat(),
    }


def _text_value(kind: str, spool: Spool, custom: str) -> str:
    values = {
        "code": spool.code,
        "serial": f"Spool S/N: {spool.serial_number or spool.code}",
        "brand": spool.brand,
        "filament": spool.material_name,
        "material": spool.material_type,
        "color_name": spool.color_name or "Unnamed color",
        "color_hex": spool.color_hex,
        "location": getattr(spool, "location", "") or "No location",
        "remaining": f"{getattr(spool, 'remaining_weight_mg', 0) / 1000:.0f} g remaining",
        "custom_text": custom,
    }
    return values.get(kind, "")


def render_label(spool: Spool, target: str, width_mm: float = 90, height_mm: float = 32, layout: list | None = None, monochrome: bool = False) -> bytes:
    elements = validate_layout(width_mm, height_mm, layout or DEFAULT_LAYOUT)
    scale = 10
    width, height = width_mm * scale, height_mm * scale
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width_mm:g}mm" height="{height_mm:g}mm" viewBox="0 0 {width:g} {height:g}">', f'<rect width="{width:g}" height="{height:g}" fill="#ffffff"/>']
    for item in elements:
        if not item["visible"]:
            continue
        x, y, w, h = (item[key] * scale for key in ("x", "y", "width", "height"))
        kind = item["type"]
        if kind == "qr":
            qr = qrcode.make(target, image_factory=qrcode.image.svg.SvgPathImage, box_size=8, border=4)
            root = ET.fromstring(qr.to_string(encoding="unicode"))
            path = next(element for element in root.iter() if element.tag.endswith("path"))
            _, _, source_width, source_height = [float(value) for value in root.attrib["viewBox"].split()]
            factor = min(w / source_width, h / source_height)
            offset_x, offset_y = x + (w - source_width * factor) / 2, y + (h - source_height * factor) / 2
            parts.append(f'<g transform="translate({offset_x:.3f} {offset_y:.3f}) scale({factor:.6f})"><path d="{escape(path.attrib["d"])}" fill="#111111"/></g>')
        elif kind == "color_swatch":
            fill = "#ffffff" if monochrome else (spool.color_hex if re.fullmatch(r"#[0-9A-Fa-f]{6}", spool.color_hex or "") else "#808080")
            parts.append(f'<rect x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" rx="3" fill="{fill}" stroke="#111111" stroke-width="1.5"/>')
        elif kind == "border":
            parts.append(f'<rect x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" rx="5" fill="none" stroke="#111111" stroke-width="1.5"/>')
        else:
            value = escape(_text_value(kind, spool, item["text"]).strip())
            font_size = item["font_size"] * scale
            baseline = y + min(h * 0.78, font_size)
            weight = "700" if item["bold"] else "400"
            estimated = max(1, len(value)) * font_size * 0.56
            length = f' textLength="{w:g}" lengthAdjust="spacingAndGlyphs"' if estimated > w else ""
            parts.append(f'<text x="{x:g}" y="{baseline:g}" font-family="Open Sans,Arial,sans-serif" font-size="{font_size:g}" font-weight="{weight}" fill="#111827"{length}><tspan>{value}</tspan></text>')
    parts.append("</svg>")
    return "".join(parts).encode("utf-8")

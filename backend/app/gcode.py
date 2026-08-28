from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

from .units import length_mm_to_weight_mg


LIST_PATTERNS = {
    "length": re.compile(r"^;\s*filament used \[mm\]\s*=\s*(.+)$", re.I),
    "weight": re.compile(r"^;\s*filament used \[g\]\s*=\s*(.+)$", re.I),
    "type": re.compile(r"^;\s*filament_type\s*=\s*(.+)$", re.I),
    "color": re.compile(r"^;\s*(?:filament_colour|default_filament_colour)\s*=\s*(.+)$", re.I),
    "diameter": re.compile(r"^;\s*filament_diameter\s*=\s*(.+)$", re.I),
    "density": re.compile(r"^;\s*filament_density\s*=\s*(.+)$", re.I),
}
TIME_RE = re.compile(r"^;\s*estimated printing time.*?=\s*(.+)$", re.I)


@dataclass
class ParsedUsage:
    tool_index: int
    length_mm: Decimal
    weight_mg: int
    material_type: str
    color_hex: str
    diameter_mm: Decimal
    density_g_cm3: Decimal


@dataclass
class ParsedGcode:
    usages: list[ParsedUsage]
    estimated_seconds: int | None
    warnings: list[str]


def _split(value: str) -> list[str]:
    delimiter = ";" if ";" in value else ","
    return [item.strip().strip('"') for item in value.split(delimiter)]


def _at(values: list[str], index: int, fallback: str) -> str:
    return values[index] if index < len(values) and values[index] else fallback


def _seconds(value: str) -> int | None:
    total = 0
    matches = re.findall(r"(\d+)\s*([dhms])", value.lower())
    if not matches:
        return None
    multipliers = {"d": 86400, "h": 3600, "m": 60, "s": 1}
    for amount, unit in matches:
        total += int(amount) * multipliers[unit]
    return total


def decode_bgcode(path: Path) -> tuple[Path, TemporaryDirectory | None]:
    if path.suffix.lower() != ".bgcode" and path.read_bytes()[:4] != b"GCDE":
        return path, None
    temporary = TemporaryDirectory(prefix="filaflow-bgcode-")
    source = Path(temporary.name) / path.name
    source.write_bytes(path.read_bytes())
    result = subprocess.run(["bgcode", str(source)], capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        temporary.cleanup()
        raise ValueError(f"Binary G-code could not be decoded: {result.stderr.strip()}")
    decoded = source.with_suffix(".gcode")
    if not decoded.exists():
        candidates = list(Path(temporary.name).glob("*.gcode"))
        if not candidates:
            temporary.cleanup()
            raise ValueError("libbgcode did not produce text G-code")
        decoded = candidates[0]
    return decoded, temporary


def parse_gcode(path: Path) -> ParsedGcode:
    decoded, temporary = decode_bgcode(path)
    try:
        lines = decoded.read_text(encoding="utf-8", errors="replace").splitlines()
        values: dict[str, list[str]] = {}
        estimated_seconds = None
        for line in lines:
            for key, pattern in LIST_PATTERNS.items():
                match = pattern.match(line)
                if match:
                    values[key] = _split(match.group(1))
            match = TIME_RE.match(line)
            if match:
                estimated_seconds = _seconds(match.group(1))

        direct_lengths = [Decimal(v or "0") for v in values.get("length", [])]
        direct_weights = [int(Decimal(v or "0") * 1000) for v in values.get("weight", [])]
        simulated = _simulate_extrusion(lines)
        count = max(len(direct_lengths), len(direct_weights), max(simulated.keys(), default=-1) + 1)
        warnings: list[str] = []
        usages: list[ParsedUsage] = []
        for index in range(count):
            length = direct_lengths[index] if index < len(direct_lengths) else simulated.get(index, Decimal("0"))
            diameter = Decimal(_at(values.get("diameter", []), index, "1.75"))
            density = Decimal(_at(values.get("density", []), index, "1.24"))
            weight = direct_weights[index] if index < len(direct_weights) else length_mm_to_weight_mg(length, diameter, density)
            if length <= 0 and weight <= 0:
                continue
            usages.append(ParsedUsage(index, length, weight, _at(values.get("type", []), index, ""), _at(values.get("color", []), index, ""), diameter, density))
        if not usages:
            warnings.append("No filament usage found in the file")
        if direct_lengths and simulated:
            direct_total = sum(direct_lengths)
            simulated_total = sum(simulated.values())
            if direct_total and abs(simulated_total - direct_total) / direct_total > Decimal("0.01"):
                warnings.append("Calculated tool totals differ from slicer metadata by more than 1%")
        return ParsedGcode(usages, estimated_seconds, warnings)
    finally:
        if temporary:
            temporary.cleanup()


def _simulate_extrusion(lines: list[str]) -> dict[int, Decimal]:
    active_tool = 0
    relative = True
    current_e: dict[int, Decimal] = {}
    retract_debt: dict[int, Decimal] = {}
    consumed: dict[int, Decimal] = {}
    for raw in lines:
        line = raw.split(";", 1)[0].strip()
        if not line:
            continue
        tool = re.match(r"^T(\d+)\b", line, re.I)
        if tool:
            active_tool = int(tool.group(1))
            continue
        if re.match(r"^M82\b", line, re.I):
            relative = False
            continue
        if re.match(r"^M83\b", line, re.I):
            relative = True
            continue
        reset = re.match(r"^G92\b.*?\bE(-?[\d.]+)", line, re.I)
        if reset:
            current_e[active_tool] = Decimal(reset.group(1))
            continue
        move = re.match(r"^G[01]\b", line, re.I)
        e_match = re.search(r"(?:^|\s)E(-?[\d.]+)", line, re.I)
        if not move or not e_match:
            continue
        value = Decimal(e_match.group(1))
        previous = current_e.get(active_tool, Decimal("0"))
        delta = value if relative else value - previous
        current_e[active_tool] = previous + value if relative else value
        if delta < 0:
            retract_debt[active_tool] = retract_debt.get(active_tool, Decimal("0")) - delta
            continue
        debt = retract_debt.get(active_tool, Decimal("0"))
        printable = max(Decimal("0"), delta - debt)
        retract_debt[active_tool] = max(Decimal("0"), debt - delta)
        consumed[active_tool] = consumed.get(active_tool, Decimal("0")) + printable
    return consumed

from decimal import Decimal
from pathlib import Path
from app.gcode import parse_gcode


def test_parses_per_tool_plain_gcode(tmp_path: Path):
    source = tmp_path / "multi.gcode"
    source.write_text("""M83
T0
G1 X1 E10
G1 E-1
G1 E1
T1
G1 X2 E20
; filament used [mm] = 10.00, 20.00
; filament used [g] = 0.03, 0.06
; filament_type = PLA;PETG
; filament_colour = #ff0000;#0000ff
; filament_diameter = 1.75;1.75
; filament_density = 1.24;1.27
; estimated printing time (normal mode) = 1h 2m 3s
""", encoding="utf-8")
    parsed = parse_gcode(source)
    assert len(parsed.usages) == 2
    assert parsed.usages[0].length_mm == Decimal("10.00")
    assert parsed.usages[1].material_type == "PETG"
    assert parsed.estimated_seconds == 3723
    assert parsed.warnings == []


def test_simulation_excludes_retract_and_deretract(tmp_path: Path):
    source = tmp_path / "fallback.gcode"
    source.write_text("M83\nG1 E10\nG1 E-2\nG1 E2\nG1 E5\n", encoding="utf-8")
    parsed = parse_gcode(source)
    assert parsed.usages[0].length_mm == Decimal("15")
